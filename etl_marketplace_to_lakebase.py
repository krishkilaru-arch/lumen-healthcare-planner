# Databricks notebook source
# DBTITLE 1,Overview
# MAGIC %md
# MAGIC ## Lumen Healthcare Planner — ETL: Marketplace → Unity Catalog → Lakebase
# MAGIC
# MAGIC This notebook ingests the DAIS 2026 healthcare facility dataset from the Databricks Marketplace,
# MAGIC normalizes state names, deduplicates records, and syncs the clean table to Lakebase (Postgres).
# MAGIC
# MAGIC **Pipeline:**
# MAGIC ```
# MAGIC Marketplace catalog
# MAGIC   → dais2026.healthcare.facilities (raw)
# MAGIC   → dais2026.healthcare.facilities_clean (normalized + deduplicated)
# MAGIC   → Lakebase hackathon-healthcare / lakebase_pg_sync.facilities_full
# MAGIC ```
# MAGIC
# MAGIC **Run order:** Execute cells top to bottom. Re-running is safe (CREATE OR REPLACE).

# COMMAND ----------

# DBTITLE 1,Config
# ── Config ──────────────────────────────────────────────────────────────────
MARKETPLACE_TABLE = "databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities"
SOURCE_CATALOG    = "dais2026"
SOURCE_SCHEMA     = "dais2026.healthcare"
SOURCE_TABLE      = "dais2026.healthcare.facilities"
TARGET_TABLE      = "dais2026.healthcare.facilities_clean"

LAKEBASE_INSTANCE = "hackathon-healthcare"
LAKEBASE_SYNC_SCHEMA = "lakebase_pg_sync"

print(f"Marketplace : {MARKETPLACE_TABLE}")
print(f"Source      : {SOURCE_TABLE}")
print(f"Target      : {TARGET_TABLE}")
print(f"Lakebase    : {LAKEBASE_INSTANCE}")

# COMMAND ----------

# DBTITLE 1,Step 1 — Create working schema and copy from Marketplace
# Create the working schema if it doesn't exist, then copy the raw marketplace table.
# CDF (Change Data Feed) is enabled so Lakebase sync can track incremental changes.

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SOURCE_SCHEMA}")

spark.sql(f"""
    CREATE OR REPLACE TABLE {SOURCE_TABLE}
    TBLPROPERTIES (delta.enableChangeDataFeed = true)
    AS SELECT * FROM {MARKETPLACE_TABLE}
""")

count = spark.sql(f"SELECT COUNT(*) FROM {SOURCE_TABLE}").collect()[0][0]
print(f"✓ {SOURCE_TABLE}: {count:,} rows")

# COMMAND ----------

# DBTITLE 1,Step 2 — Audit raw state distribution
print("=== Raw state distribution (top 40) ===")
spark.sql(f"""
    SELECT address_stateOrRegion, COUNT(*) AS cnt
    FROM {SOURCE_TABLE}
    GROUP BY address_stateOrRegion
    ORDER BY cnt DESC
    LIMIT 40
""").show(40, truncate=False)

# COMMAND ----------

# DBTITLE 1,Step 3 — State normalization (static mapping + ai_classify fallback)
import re
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType

# Canonical Indian states/UTs (uppercase)
CANONICAL = {
    'ANDHRA PRADESH', 'ARUNACHAL PRADESH', 'ASSAM', 'BIHAR', 'CHHATTISGARH',
    'GOA', 'GUJARAT', 'HARYANA', 'HIMACHAL PRADESH', 'JHARKHAND', 'KARNATAKA',
    'KERALA', 'MADHYA PRADESH', 'MAHARASHTRA', 'MANIPUR', 'MEGHALAYA', 'MIZORAM',
    'NAGALAND', 'ODISHA', 'PUNJAB', 'RAJASTHAN', 'SIKKIM', 'TAMIL NADU',
    'TELANGANA', 'TRIPURA', 'UTTAR PRADESH', 'UTTARAKHAND', 'WEST BENGAL',
    'ANDAMAN AND NICOBAR ISLANDS', 'CHANDIGARH', 'DADRA AND NAGAR HAVELI AND DAMAN AND DIU',
    'DELHI', 'JAMMU AND KASHMIR', 'LADAKH', 'LAKSHADWEEP', 'PUDUCHERRY'
}

# Static mapping — handles ~99% of known variants
STATE_MAP = {
    # Typos / abbreviations
    'TAMILNADU': 'Tamil Nadu',    'TAMILANDU': 'Tamil Nadu',
    'CHATTISGARH': 'Chhattisgarh', 'CHHATISGARH': 'Chhattisgarh',
    'ORISSA': 'Odisha',            'ORRISA': 'Odisha',
    'UTTARANCHAL': 'Uttarakhand',  'UTTRAKHAND': 'Uttarakhand',
    'PONDICHERRY': 'Puducherry',   'PONDY': 'Puducherry',
    'J&K': 'Jammu and Kashmir',    'J AND K': 'Jammu and Kashmir',
    'JAMMU': 'Jammu and Kashmir',  'KASHMIR': 'Jammu and Kashmir',
    'NCT': 'Delhi',                'NEW DELHI': 'Delhi',
    'U.P.': 'Uttar Pradesh',       'UP': 'Uttar Pradesh',
    'M.P.': 'Madhya Pradesh',      'MP': 'Madhya Pradesh',
    'H.P.': 'Himachal Pradesh',    'HP': 'Himachal Pradesh',
    'AP': 'Andhra Pradesh',        'TS': 'Telangana',
    'TN': 'Tamil Nadu',            'KA': 'Karnataka',
    'KL': 'Kerala',                'MH': 'Maharashtra',
    'GJ': 'Gujarat',               'GUJ': 'Gujarat',
    'RJ': 'Rajasthan',             'WB': 'West Bengal',
    'PB': 'Punjab',
    # Cities stored as state → infer state
    'MUMBAI': 'Maharashtra',       'PUNE': 'Maharashtra',    'NAGPUR': 'Maharashtra',
    'THANE': 'Maharashtra',        'NASHIK': 'Maharashtra',
    'CHENNAI': 'Tamil Nadu',       'COIMBATORE': 'Tamil Nadu',
    'KOLKATA': 'West Bengal',      'HOWRAH': 'West Bengal',
    'HYDERABAD': 'Telangana',      'SECUNDERABAD': 'Telangana',
    'BENGALURU': 'Karnataka',      'BANGALORE': 'Karnataka',  'MYSURU': 'Karnataka',
    'AHMEDABAD': 'Gujarat',        'SURAT': 'Gujarat',        'VADODARA': 'Gujarat',
    'JAIPUR': 'Rajasthan',         'JODHPUR': 'Rajasthan',
    'LUCKNOW': 'Uttar Pradesh',    'KANPUR': 'Uttar Pradesh', 'AGRA': 'Uttar Pradesh',
    'PATNA': 'Bihar',              'BHOPAL': 'Madhya Pradesh',
    'INDORE': 'Madhya Pradesh',    'GUWAHATI': 'Assam',
    'BHUBANESWAR': 'Odisha',       'RANCHI': 'Jharkhand',
    'CHANDIGARH': 'Chandigarh',    'AMRITSAR': 'Punjab',
    'LUDHIANA': 'Punjab',          'KOCHI': 'Kerala',
    'THIRUVANANTHAPURAM': 'Kerala','VISAKHAPATNAM': 'Andhra Pradesh',
    'GHAZIABAD': 'Uttar Pradesh',  'NOIDA': 'Uttar Pradesh',
    'GURUGRAM': 'Haryana',         'FARIDABAD': 'Haryana',
}

GARBAGE_RE = re.compile(r'^[\d\W]+$')   # purely numeric or punctuation
GEOJSON_RE = re.compile(r'\{.*\}')       # GeoJSON blobs

def normalize_state(raw: str) -> str:
    """Return canonical title-case state name, or None for garbage/unresolved."""
    if raw is None:
        return None
    val = raw.strip()
    if not val or val.lower() in ('null', 'none', 'n/a', 'na'):
        return None
    if GARBAGE_RE.fullmatch(val) or GEOJSON_RE.search(val):
        return None
    # Extract state from composite: "Ghaziabad, Uttar Pradesh" → "Uttar Pradesh"
    if ',' in val:
        parts = [p.strip() for p in val.split(',')]
        for part in reversed(parts):   # try rightmost part first
            result = normalize_state(part)
            if result:
                return result
    up = val.upper()
    if up in CANONICAL:
        return val.title().replace(' And ', ' and ').replace(' Of ', ' of ')
    if up in STATE_MAP:
        return STATE_MAP[up]
    return None

normalize_state_udf = udf(normalize_state, StringType())
print("✓ Normalization UDF registered")

# COMMAND ----------

# DBTITLE 1,Step 4 — Apply UDF, identify unresolved rows for ai_classify
from pyspark.sql import functions as F

df = spark.table(SOURCE_TABLE)
df_norm = df.withColumn("state_normalized", normalize_state_udf(F.col("address_stateOrRegion")))

# Rows still unresolved (had a value but UDF returned None)
df_unresolved = df_norm.filter(
    F.col("address_stateOrRegion").isNotNull()
    & ~F.col("address_stateOrRegion").isin('null', '', 'none')
    & F.col("state_normalized").isNull()
).select("unique_id", "address_stateOrRegion").distinct()

resolved   = df_norm.filter(F.col("state_normalized").isNotNull()).count()
unresolved = df_unresolved.count()
total      = df_norm.count()
print(f"Total rows      : {total:,}")
print(f"Resolved (UDF)  : {resolved:,}  ({resolved/total*100:.1f}%)")
print(f"Unresolved      : {unresolved:,}  → will use ai_classify")

df_unresolved.show(20, truncate=False)

# COMMAND ----------

# DBTITLE 1,Step 5 — ai_classify for unresolved rows
# ai_classify supports max 20 labels — use top-19 states + 'Unknown'
AI_LABELS = [
    'Maharashtra', 'Gujarat', 'Uttar Pradesh', 'Tamil Nadu', 'Karnataka',
    'Kerala', 'West Bengal', 'Punjab', 'Haryana', 'Telangana', 'Rajasthan',
    'Delhi', 'Andhra Pradesh', 'Madhya Pradesh', 'Bihar', 'Jharkhand',
    'Chhattisgarh', 'Uttarakhand', 'Assam', 'Unknown'
]
labels_sql = ", ".join(f"'{l}'" for l in AI_LABELS)

if unresolved > 0:
    df_unresolved.createOrReplaceTempView("unresolved_states")
    ai_results = spark.sql(f"""
        SELECT unique_id,
               address_stateOrRegion,
               ai_classify(address_stateOrRegion,
                           ARRAY({labels_sql})) AS ai_state
        FROM unresolved_states
    """)
    ai_map = {
        r["address_stateOrRegion"]: r["ai_state"]
        for r in ai_results.collect()
        if r["ai_state"] and r["ai_state"] != "Unknown"
    }
    print(f"ai_classify resolved {len(ai_map)} additional variants")
else:
    ai_map = {}
    print("No unresolved rows — skipping ai_classify")

ai_map_local = dict(ai_map)

@udf(StringType())
def apply_ai_correction(raw):
    if raw is None:
        return None
    return ai_map_local.get(raw.strip(), None)

apply_ai_udf = apply_ai_correction
print("✓ ai_classify UDF ready")

# COMMAND ----------

# DBTITLE 1,Step 6 — Merge results and write facilities_clean
from pyspark.sql.functions import coalesce

# Final state_normalized = static UDF result OR ai_classify fallback
df_final = df_norm.withColumn(
    "state_normalized",
    coalesce(
        F.col("state_normalized"),
        apply_ai_udf(F.col("address_stateOrRegion"))
    )
)

# Deduplication on unique_id (keep first occurrence)
df_final = df_final.dropDuplicates(["unique_id"])

# Write
df_final.write.format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable(TARGET_TABLE)

final_count = spark.sql(f"SELECT COUNT(*) FROM {TARGET_TABLE}").collect()[0][0]
cov = spark.sql(f"""
    SELECT
        ROUND(SUM(CASE WHEN state_normalized IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS pct
    FROM {TARGET_TABLE}
""").collect()[0][0]

print(f"✓ {TARGET_TABLE}: {final_count:,} rows  |  state_normalized coverage: {cov}%")

# COMMAND ----------

# DBTITLE 1,Step 7 — Verify normalization results
print("=== State coverage after normalization ===")
spark.sql(f"""
    SELECT
        state_normalized,
        COUNT(*) AS facility_count,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
    FROM {TARGET_TABLE}
    GROUP BY state_normalized
    ORDER BY facility_count DESC
""").show(40, truncate=False)

print("=== Field coverage ===")
spark.sql(f"""
    SELECT
        ROUND(AVG(CASE WHEN description  IS NOT NULL AND description  != '' THEN 1.0 ELSE 0.0 END)*100,1) AS description_pct,
        ROUND(AVG(CASE WHEN capability   IS NOT NULL AND capability   != '' THEN 1.0 ELSE 0.0 END)*100,1) AS capability_pct,
        ROUND(AVG(CASE WHEN procedure    IS NOT NULL AND procedure    != '' THEN 1.0 ELSE 0.0 END)*100,1) AS procedure_pct,
        ROUND(AVG(CASE WHEN equipment    IS NOT NULL AND equipment    != '' THEN 1.0 ELSE 0.0 END)*100,1) AS equipment_pct,
        ROUND(AVG(CASE WHEN "numberDoctors" IS NOT NULL AND "numberDoctors" != '' THEN 1.0 ELSE 0.0 END)*100,1) AS doctors_pct,
        ROUND(AVG(CASE WHEN capacity     IS NOT NULL AND capacity     != '' THEN 1.0 ELSE 0.0 END)*100,1) AS capacity_pct
    FROM {TARGET_TABLE}
""").show(truncate=False)

# COMMAND ----------

# DBTITLE 1,Step 8 — Deduplicate all source tables (required for Lakebase sync)
# Lakebase sync requires unique PKs — deduplicate all tables before sync.
# The facilities_clean table is already deduplicated. Handle supplemental tables here.

from pyspark.sql import functions as F

SUPPLEMENTAL = {
    "dais2026.healthcare.nfhs_5_district_health_indicators": "district_name",
}

for table, pk in SUPPLEMENTAL.items():
    try:
        df_t = spark.table(table)
        orig = df_t.count()
        df_dedup = df_t.dropDuplicates([pk])
        dedup_count = df_dedup.count()
        if dedup_count < orig:
            df_dedup.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)
            print(f"✓ {table}: {orig:,} → {dedup_count:,} rows  ({orig-dedup_count} dupes removed)")
        else:
            print(f"✓ {table}: {dedup_count:,} rows (no dupes)")
    except Exception as e:
        print(f"  Skipped {table}: {e}")

# COMMAND ----------

# DBTITLE 1,Step 9 — Sync facilities_clean to Lakebase
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import (
    SyncedDatabaseTable, SyncedTableSpec, SyncedTableSchedulingPolicy
)

w = WorkspaceClient()

TABLES_TO_SYNC = [
    # (unity_catalog_table,   lakebase_table_name)
    (TARGET_TABLE,            "facilities_full"),
    ("dais2026.healthcare.nfhs_5_district_health_indicators", "nfhs_5_district_health_indicators"),
]

for uc_table, lb_name in TABLES_TO_SYNC:
    try:
        synced = w.database.create_synced_database_table(
            SyncedDatabaseTable(
                name=lb_name,
                instance_name=LAKEBASE_INSTANCE,
                spec=SyncedTableSpec(
                    source_table_full_name=uc_table,
                    scheduling_policy=SyncedTableSchedulingPolicy(triggered={})
                )
            )
        )
        print(f"✓ Sync created: {uc_table} → {LAKEBASE_INSTANCE}/{lb_name}")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"  Already synced: {lb_name} (trigger a manual refresh if needed)")
        else:
            print(f"  Error syncing {lb_name}: {e}")

# COMMAND ----------

# DBTITLE 1,Step 10 — Trigger sync and verify Lakebase connection
import psycopg2, uuid, os

cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()),
    instance_names=[LAKEBASE_INSTANCE]
)

conn = psycopg2.connect(
    host=os.environ.get("PGHOST", "ep-noisy-wave-d2hhvbvx.database.us-east-1.cloud.databricks.com"),
    database="healthcare",
    user=os.environ.get("PGUSER", spark.sql("SELECT current_user()").collect()[0][0]),
    port=5432,
    password=cred.token,
    sslmode="require",
)
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM lakebase_pg_sync.facilities_full")
count = cur.fetchone()[0]
print(f"✓ Lakebase lakebase_pg_sync.facilities_full: {count:,} rows")

cur.execute("SELECT state_normalized, COUNT(*) FROM lakebase_pg_sync.facilities_full GROUP BY state_normalized ORDER BY COUNT(*) DESC LIMIT 5")
print("Top 5 states:", cur.fetchall())

cur.close()
conn.close()
print("✓ Lakebase connection verified")

# COMMAND ----------

# DBTITLE 1,Done
# MAGIC %md
# MAGIC ## ✅ ETL Complete
# MAGIC
# MAGIC | Step | Output |
# MAGIC |---|---|
# MAGIC | Marketplace copy | `dais2026.healthcare.facilities` |
# MAGIC | State normalization | Static map (~99%) + `ai_classify` fallback |
# MAGIC | Deduplication | Unique `unique_id` per row |
# MAGIC | Clean table | `dais2026.healthcare.facilities_clean` |
# MAGIC | Lakebase sync | `hackathon-healthcare / lakebase_pg_sync.facilities_full` |
# MAGIC
# MAGIC The Databricks App (`lumen-healthcare-planner`) reads from `lakebase_pg_sync.facilities_full` via `db.py`.

# COMMAND ----------


