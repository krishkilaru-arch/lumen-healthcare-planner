# Databricks notebook source
# DBTITLE 1,State Normalization ETL — Overview
# MAGIC %md
# MAGIC ## State Normalization ETL
# MAGIC Cleans `address_stateOrRegion` in `dais2026.healthcare.facilities`.
# MAGIC
# MAGIC **Issues found (10,088 rows total):**
# MAGIC - 255 distinct raw values vs. 36 canonical Indian states/UTs
# MAGIC - Typos/variants: `Tamilnadu`, `Chattisgarh`, `Orissa`, `U.p.`, `Ts`, `Gj`, etc.
# MAGIC - Cities stored as state: `Mumbai`, `Chennai`, `Thane`, `Kolkata`, `Hyderabad` (93 rows)
# MAGIC - Composite values: `Ghaziabad, Uttar Pradesh`, `Kutch, Gujarat` (extract state after comma)
# MAGIC - Garbage: numeric strings (`0`, `1500`), GeoJSON blobs, `null` strings (70 rows)
# MAGIC
# MAGIC **Strategy:**
# MAGIC 1. Static mapping dict handles ~99% of known variants
# MAGIC 2. `ai_classify()` SQL function handles remaining ambiguous values
# MAGIC 3. Writes a new column `state_normalized` to a new UC table `dais2026.healthcare.facilities_clean`
# MAGIC 4. Syncs to Lakebase as `facilities_clean`

# COMMAND ----------

# DBTITLE 1,Cell 2 — Config
# ── Config ──────────────────────────────────────────────────────────────────
SOURCE_TABLE  = "dais2026.healthcare.facilities"
TARGET_TABLE  = "dais2026.healthcare.facilities_clean"
TARGET_SCHEMA = "dais2026.healthcare"
print(f"Source : {SOURCE_TABLE}")
print(f"Target : {TARGET_TABLE}")

# COMMAND ----------

# DBTITLE 1,Cell 3 — Audit raw state distribution
print("=== Raw state distribution (top 60) ===")
spark.sql(f"""
    SELECT address_stateOrRegion, COUNT(*) as cnt
    FROM {SOURCE_TABLE}
    GROUP BY address_stateOrRegion
    ORDER BY cnt DESC
    LIMIT 60
""").show(60, truncate=False)

# COMMAND ----------

# DBTITLE 1,Cell 4 — Mapping dictionaries
import re

# ── Canonical set (uppercase) ────────────────────────────────────────────────
CANONICAL = {
    'ANDHRA PRADESH', 'ARUNACHAL PRADESH', 'ASSAM', 'BIHAR', 'CHHATTISGARH',
    'GOA', 'GUJARAT', 'HARYANA', 'HIMACHAL PRADESH', 'JHARKHAND', 'KARNATAKA',
    'KERALA', 'MADHYA PRADESH', 'MAHARASHTRA', 'MANIPUR', 'MEGHALAYA', 'MIZORAM',
    'NAGALAND', 'ODISHA', 'PUNJAB', 'RAJASTHAN', 'SIKKIM', 'TAMIL NADU',
    'TELANGANA', 'TRIPURA', 'UTTAR PRADESH', 'UTTARAKHAND', 'WEST BENGAL',
    'ANDAMAN AND NICOBAR ISLANDS', 'CHANDIGARH',
    'DADRA AND NAGAR HAVELI AND DAMAN AND DIU', 'DELHI',
    'JAMMU AND KASHMIR', 'LADAKH', 'LAKSHADWEEP', 'PUDUCHERRY',
}

# ── State name variants → canonical ─────────────────────────────────────────
STATE_VARIANTS = {
    'TAMILNADU': 'TAMIL NADU',
    # Uttar Pradesh
    'UP': 'UTTAR PRADESH', 'U.P.': 'UTTAR PRADESH', 'U.P': 'UTTAR PRADESH',
    'UTTAR PRADES H': 'UTTAR PRADESH',
    # Odisha
    'ORISSA': 'ODISHA',
    # Chhattisgarh
    'CHATTISGARH': 'CHHATTISGARH', 'CG': 'CHHATTISGARH',
    # J&K
    'JAMMU & KASHMIR': 'JAMMU AND KASHMIR', 'KASHMIR': 'JAMMU AND KASHMIR',
    'SRINAGAR KASHMIR': 'JAMMU AND KASHMIR', 'KUPWARA': 'JAMMU AND KASHMIR',
    # Telangana
    'TELENGANA': 'TELANGANA', 'TS': 'TELANGANA',
    # Madhya Pradesh
    'M.P.': 'MADHYA PRADESH', 'MADHYAPRADESH': 'MADHYA PRADESH', 'MP': 'MADHYA PRADESH',
    # Delhi
    'NEW DELHI': 'DELHI', 'NCT OF DELHI': 'DELHI', 'NCT DELHI': 'DELHI',
    'NCT': 'DELHI', 'DL': 'DELHI', 'DELHI/NCR': 'DELHI', 'WEST DELHI': 'DELHI',
    'NCT OF DELHI': 'DELHI',
    # Puducherry
    'PONDICHERRY': 'PUDUCHERRY',
    # Uttarakhand
    'UTTARANCHAL': 'UTTARAKHAND',
    # Gujarat
    'GJ': 'GUJARAT',
    # Bihar
    'BR': 'BIHAR',
    # Maharashtra abbreviations
    'MH': 'MAHARASHTRA', 'MS': 'MAHARASHTRA',
    # Uttarakhand abbreviation
    'UT': 'UTTARAKHAND',
    # Uttar Pradesh (no-space variant)
    'UTTARPRADESH': 'UTTAR PRADESH',
    # Madhya Pradesh (partial)
    'MADHYA': 'MADHYA PRADESH',
    # Puducherry UT label
    'U.T OF PUDUCHERRY': 'PUDUCHERRY', 'U.T. OF PUDUCHERRY': 'PUDUCHERRY',
    # Punjab
    'PUNJAB REGION': 'PUNJAB',
    # Goa
    'NORTH GOA': 'GOA', 'SOUTH GOA': 'GOA',
    # Tripura
    'WEST TRIPURA': 'TRIPURA',
}

# ── City → canonical state ───────────────────────────────────────────────────
CITY_TO_STATE = {
    # Maharashtra
    'MUMBAI': 'MAHARASHTRA', 'NAVI MUMBAI': 'MAHARASHTRA', 'NAVI-MUMBAI': 'MAHARASHTRA',
    'THANE': 'MAHARASHTRA', 'PUNE': 'MAHARASHTRA', 'NASHIK': 'MAHARASHTRA',
    'NANDED': 'MAHARASHTRA', 'KOLHAPUR': 'MAHARASHTRA', 'SOLAPUR': 'MAHARASHTRA',
    'NAGPUR': 'MAHARASHTRA', 'LATUR': 'MAHARASHTRA', 'AHMEDNAGAR': 'MAHARASHTRA',
    'SANGLI': 'MAHARASHTRA', 'PALGHAR': 'MAHARASHTRA', 'DHULE': 'MAHARASHTRA',
    'AMRAVATI': 'MAHARASHTRA', 'PIMPRI-CHINCHWAD': 'MAHARASHTRA',
    'NEW MONDHA': 'MAHARASHTRA', 'CHIKHALI': 'MAHARASHTRA',
    # Gujarat
    'AHMEDABAD': 'GUJARAT', 'BHAVNAGAR': 'GUJARAT', 'GANDHIDHAM': 'GUJARAT',
    'BANAS KANTHA': 'GUJARAT', 'KUTCH': 'GUJARAT', 'KACHCHH': 'GUJARAT',
    'KHAMBHA': 'GUJARAT',
    # Tamil Nadu
    'CHENNAI': 'TAMIL NADU', 'ERODE': 'TAMIL NADU', 'NAMAKKAL': 'TAMIL NADU',
    'KANCHIPURAM': 'TAMIL NADU', 'THANJAVUR': 'TAMIL NADU', 'VALLIYOOR': 'TAMIL NADU',
    'SALEM': 'TAMIL NADU', 'AMBASAMUDRAM': 'TAMIL NADU', 'ST.THOMAS MOUNT': 'TAMIL NADU',
    # Telangana
    'HYDERABAD': 'TELANGANA',
    # West Bengal
    'KOLKATA': 'WEST BENGAL', 'HOWRAH': 'WEST BENGAL',
    'NORTH 24 PARGANAS': 'WEST BENGAL', 'SOUTH 24 PARGANAS': 'WEST BENGAL',
    'NADIA': 'WEST BENGAL', 'HOOGLY': 'WEST BENGAL',
    'SECTOR 1 SALT LAKE CITY SECTOR 1': 'WEST BENGAL',
    # Kerala
    'THIRUVANANTHAPURAM': 'KERALA', 'TRIVANDRUM': 'KERALA', 'KOLLAM': 'KERALA',
    'MALAPPURAM': 'KERALA', 'ERNAKULAM': 'KERALA', 'IDUKKI': 'KERALA',
    'KOTTAYAM': 'KERALA', 'PALAKKAD': 'KERALA', 'ALAPPUZHA': 'KERALA',
    'THRISSUR DISTRICT': 'KERALA', 'CHADAYAMANGALAM': 'KERALA',
    'PALLOM': 'KERALA', 'ANCHAL': 'KERALA',
    # Punjab
    'LUDHIANA': 'PUNJAB', 'JALANDHAR': 'PUNJAB', 'PATIALA': 'PUNJAB',
    'MOHALI': 'PUNJAB', 'JALANDHAR-EAST': 'PUNJAB', 'LUDHIANA-1': 'PUNJAB',
    # Madhya Pradesh
    'INDORE': 'MADHYA PRADESH', 'REWA': 'MADHYA PRADESH',
    # Uttarakhand
    'DEHRADUN': 'UTTARAKHAND',
    # Haryana
    'FARIDABAD': 'HARYANA', 'JHAJJAR': 'HARYANA', 'SIRSA': 'HARYANA',
    # Uttar Pradesh
    'GHAZIABAD': 'UTTAR PRADESH', 'KUSHINAGAR': 'UTTAR PRADESH',
    'GOMTINAGAR': 'UTTAR PRADESH', 'BUDAUN': 'UTTAR PRADESH',
    'AZAD NAGAR': 'UTTAR PRADESH', 'NAGLADEENA FATEHGARH': 'UTTAR PRADESH',
    # Karnataka
    'MANGALORE': 'KARNATAKA', 'DHARWAD': 'KARNATAKA', 'GADAG': 'KARNATAKA',
    'DAKSHIN KANNAD': 'KARNATAKA',
    # Jharkhand
    'EAST SINGHBHUM': 'JHARKHAND',
    # Odisha
    'KHORDHA': 'ODISHA',
    # Andhra Pradesh
    'GUNTUR': 'ANDHRA PRADESH', 'PRAKASAM': 'ANDHRA PRADESH',
    # Himachal Pradesh
    'SIRMAUR': 'HIMACHAL PRADESH',
    # Bihar
    'DARBHANGA': 'BIHAR',
    # Karnataka (extra cities)
    'MYSORE': 'KARNATAKA', 'MYSURU': 'KARNATAKA',
    # Maharashtra (extra)
    'TASGAON': 'MAHARASHTRA',
    # West Bengal (extra districts)
    'BIRBHUM': 'WEST BENGAL', 'MIDNAPORE': 'WEST BENGAL',
    '24PGS (S)': 'WEST BENGAL',
    # Tamil Nadu (extra)
    'TIRUVANNAMALAI': 'TAMIL NADU', 'ANNANAGAR EAST': 'TAMIL NADU',
    # Gujarat (extra)
    'KHEDA': 'GUJARAT',
    # J&K district
    'SAMBA': 'JAMMU AND KASHMIR',
    # Rajasthan district
    'BARMER': 'RAJASTHAN',
    # Uttar Pradesh (extra)
    'BALRAMPUR': 'UTTAR PRADESH', 'SIKANDRA': 'UTTAR PRADESH',
    # Assam district
    'KAMRUP': 'ASSAM',
    # Andhra Pradesh district
    'WEST GODAVARI': 'ANDHRA PRADESH',
}

print(f"STATE_VARIANTS entries : {len(STATE_VARIANTS)}")
print(f"CITY_TO_STATE entries  : {len(CITY_TO_STATE)}")
print(f"Total canonical states : {len(CANONICAL)}")

# COMMAND ----------

# DBTITLE 1,Cell 5 — Normalization UDF
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType

GARBAGE_RE = re.compile(r'^\d+$')   # purely numeric

def normalize_state(raw: str) -> str:
    """Return canonical title-case state name, or None for garbage/unresolved."""
    if raw is None:
        return None
    val = raw.strip()

    # Null-like strings
    if val.lower() in ('null', '', 'none', 'n/a'):
        return None

    # Purely numeric
    if GARBAGE_RE.fullmatch(val):
        return None

    # GeoJSON blobs, JSON arrays, quoted specialty strings, long wrong-field values
    if val[0] in ('{', '[', '"') or len(val) > 80:
        return None

    upper = val.upper().strip()

    # Direct canonical match
    if upper in CANONICAL:
        return val.title()

    # State variant map
    if upper in STATE_VARIANTS:
        return STATE_VARIANTS[upper].title()

    # City → state map
    if upper in CITY_TO_STATE:
        return CITY_TO_STATE[upper].title()

    # Composite "City, State" or "District, State" — extract after last comma
    if ',' in upper:
        after = upper.rsplit(',', 1)[-1].strip()
        if after in CANONICAL:
            return after.title()
        if after in STATE_VARIANTS:
            return STATE_VARIANTS[after].title()

    # Strip common district/region suffixes
    for suffix in (' DISTRICT', ' REGION'):
        if upper.endswith(suffix):
            base = upper[:-len(suffix)].strip()
            if base in CANONICAL:
                return base.title()
            if base in CITY_TO_STATE:
                return CITY_TO_STATE[base].title()

    # Return None → will be handled by ai_classify in the next cell
    return None

normalize_state_udf = udf(normalize_state, StringType())

# Quick sanity test
tests = [
    'Tamilnadu', 'U.p.', 'Mumbai', 'Ghaziabad, Uttar Pradesh',
    '{"coordinates":[80.3,26.4],"type":"Point"}', 'null', '1500',
    'West Tripura', 'Orissa', 'Chattisgarh', 'Navi-Mumbai',
]
for t in tests:
    print(f"  {t!r:<45} → {normalize_state(t)!r}")

# COMMAND ----------

# DBTITLE 1,Cell 6 — Apply normalization, identify unresolved rows
from pyspark.sql import functions as F

df = spark.table(SOURCE_TABLE)

# Apply UDF to produce state_normalized
df_norm = df.withColumn("state_normalized", normalize_state_udf(F.col("address_stateOrRegion")))

# Identify rows still unresolved (state was not null originally but UDF returned None)
df_unresolved = df_norm.filter(
    F.col("address_stateOrRegion").isNotNull()
    & ~F.col("address_stateOrRegion").isin('null', '')
    & F.col("state_normalized").isNull()
)

print(f"Total rows              : {df.count()}")
print(f"Rows resolved by map    : {df_norm.filter(F.col('state_normalized').isNotNull()).count()}")
print(f"Rows needing ai_classify: {df_unresolved.count()}")

print("\nUnresolved values:")
df_unresolved.groupBy("address_stateOrRegion").count().orderBy(F.col("count").desc()).show(30, truncate=False)

# COMMAND ----------

# DBTITLE 1,Cell 7 — ai_classify for unresolved rows
# ai_classify supports at most 20 labels
# Use the top-19 states by facility count plus 'Unknown' = exactly 20
AI_LABELS = [
    'Maharashtra', 'Gujarat', 'Uttar Pradesh', 'Tamil Nadu', 'Karnataka',
    'Kerala', 'West Bengal', 'Punjab', 'Haryana', 'Telangana', 'Rajasthan',
    'Delhi', 'Andhra Pradesh', 'Madhya Pradesh', 'Bihar', 'Jharkhand',
    'Chhattisgarh', 'Uttarakhand', 'Assam', 'Unknown',
]

GARBAGE_PREFIXES = ('{', '[', '"')
GARBAGE_WORDS = {'kie', 'sarna', 'bigbara', 'green city'}

def is_garbage_val(v):
    if not v:
        return True
    s = v.strip()
    if not s or len(s) > 80:
        return True
    if s[0] in GARBAGE_PREFIXES:
        return True
    if GARBAGE_RE.fullmatch(s):
        return True
    if s.lower() in GARBAGE_WORDS:
        return True
    return False

unresolved_vals = [
    r['address_stateOrRegion']
    for r in df_unresolved.select('address_stateOrRegion').distinct().collect()
    if not is_garbage_val(r['address_stateOrRegion'])
]
print(f'Distinct values to classify via ai_classify : {len(unresolved_vals)}')
print(f'Labels used                                  : {len(AI_LABELS)}')

if unresolved_vals:
    from pyspark.sql import Row
    ai_input_df = spark.createDataFrame([Row(raw_state=v) for v in unresolved_vals])
    ai_input_df.createOrReplaceTempView('unresolved_states')

    label_sql = ', '.join("'" + lbl + "'" for lbl in AI_LABELS)

    ai_classified = spark.sql(
        'SELECT raw_state, '
        'ai_classify(raw_state, ARRAY(' + label_sql + ')) AS ai_state '
        'FROM unresolved_states'
    )
    ai_classified.show(50, truncate=False)

    ai_map = {
        r['raw_state']: (r['ai_state'] if r['ai_state'] != 'Unknown' else None)
        for r in ai_classified.collect()
    }
    print('ai_classify corrections:')
    for k, v in sorted(ai_map.items()):
        print(f'  {k!r:<45} -> {v!r}')
else:
    ai_map = {}
    print('Nothing to classify - static map covered everything!')

# COMMAND ----------

# DBTITLE 1,Cell 8 — Merge ai_classify results and write final table
# Apply ai_classify corrections via a second UDF
# spark.sparkContext.broadcast() is not supported on Databricks Serverless (Spark Connect)
# Use a plain dict closure instead — serialized with the UDF automatically
ai_map_local = dict(ai_map)  # snapshot for closure

@udf(StringType())
def apply_ai_correction(raw):
    """Return ai_classify result for rows where static map returned None."""
    if raw is None:
        return None
    return ai_map_local.get(raw.strip())

df_final = df_norm.withColumn(
    "state_normalized",
    F.coalesce(
        F.col("state_normalized"),
        apply_ai_correction(F.col("address_stateOrRegion"))
    )
)

# Write to UC target table (CREATE OR REPLACE)
df_final.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET_TABLE)
print(f"Written {df_final.count()} rows to {TARGET_TABLE}")

# COMMAND ----------

# DBTITLE 1,Cell 9 — Verification
print("=== Normalization Results ===")
spark.sql(f"""
    SELECT
        state_normalized,
        COUNT(*) as facility_count
    FROM {TARGET_TABLE}
    GROUP BY state_normalized
    ORDER BY facility_count DESC
""").show(50, truncate=False)

# Coverage stats
spark.sql(f"""
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN state_normalized IS NOT NULL THEN 1 ELSE 0 END) as resolved,
        SUM(CASE WHEN state_normalized IS NULL     THEN 1 ELSE 0 END) as still_null,
        ROUND(100.0 * SUM(CASE WHEN state_normalized IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_resolved
    FROM {TARGET_TABLE}
""").show()

# COMMAND ----------

# DBTITLE 1,Cell 9b — Deduplicate source tables (required for Lakebase sync)
# ── Deduplicate all 10 source tables on their PKs ────────────────────────────
# Root cause: duplicate PK rows cause the Synced Table (DLT) pipeline to fail
# at flow resolution with "Online Table creation failed".
# india_post_pincode_directory already synced (162K rows) — skip it.
from pyspark.sql import Window
from pyspark.sql import functions as F

SCHEMA = "dais2026.lakebase_sync_clean"

dedup_config = [
    (f"{SCHEMA}.facilities",                        ["unique_id"]),
    (f"{SCHEMA}.facilities_base",                   ["unique_id"]),
    (f"{SCHEMA}.facilities_capabilities",           ["unique_id", "capability_item"]),
    (f"{SCHEMA}.facilities_equipment",              ["unique_id", "equipment_item"]),
    (f"{SCHEMA}.facilities_phones",                 ["unique_id", "phone_number"]),
    (f"{SCHEMA}.facilities_procedures",             ["unique_id", "procedure_item"]),
    (f"{SCHEMA}.facilities_specialties",            ["unique_id", "specialty"]),
    (f"{SCHEMA}.facilities_websites",               ["unique_id", "website_url"]),
    (f"{SCHEMA}.nfhs_5_district_health_indicators", ["district_name"]),
    # india_post_pincode_directory skipped — already synced successfully
]

print(f"Deduplicating {len(dedup_config)} tables in {SCHEMA}...\n")
for tbl, pk_cols in dedup_config:
    before = spark.sql(f"SELECT COUNT(*) FROM {tbl}").collect()[0][0]
    w_spec = Window.partitionBy(*pk_cols).orderBy(*pk_cols)
    df_dedup = (
        spark.table(tbl)
        .withColumn("_rn", F.row_number().over(w_spec))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )
    df_dedup.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(tbl)
    after = spark.sql(f"SELECT COUNT(*) FROM {tbl}").collect()[0][0]
    removed = before - after
    flag = " ← had dupes!" if removed > 0 else ""
    print(f"  {tbl.split('.')[-1]:<45} {before:>8,} → {after:>8,}  (removed {removed}){flag}")

print("\nDedup done. Now re-run Cell 21 to retry the failed syncs.")

# COMMAND ----------

# DBTITLE 1,Fix routes_readiness.py — DOUBLE PRECISION columns
# Fix "invalid input syntax for type double precision" error in Data Readiness Desk.
# latitude/longitude are DOUBLE PRECISION in Lakebase — cannot compare with '' or '[]'.

import pathlib

fix_path = pathlib.Path(
    '/Workspace/Users/krish.kilaru@lumenalta.com/lumen-healthcare-planner/routes_readiness.py'
)
src = fix_path.read_text()

# 1. Add NUMERIC_FIELDS constant after PROFILE_FIELDS list
old_anchor = ']\n\n\n@router.get("/profile")'
new_anchor = (
    ']\n\n'
    '# Numeric columns — only check IS NOT NULL (no string comparisons)\n'
    'NUMERIC_FIELDS = {\'latitude\', \'longitude\'}\n'
    '\n\n@router.get("/profile")'
)
assert old_anchor in src, "Anchor not found — file may already be patched"
src = src.replace(old_anchor, new_anchor, 1)

# 2. Make coverage loop type-aware for numeric fields
old_loop = (
    '    coverage = {}\n'
    '    for field in PROFILE_FIELDS:\n'
    '        sql = f\"\"\"\n'
    '            SELECT COUNT(*) as cnt FROM {SYNCED_SCHEMA}.facilities\n'
    '            WHERE \"{field}\" IS NOT NULL AND \"{field}\" != \'\' AND \"{field}\" != \'[]\'\n'
    '        \"\"\"\n'
    '        result = query(sql)'
)
new_loop = (
    '    coverage = {}\n'
    '    for field in PROFILE_FIELDS:\n'
    '        if field in NUMERIC_FIELDS:\n'
    '            sql = f\"\"\"\n'
    '                SELECT COUNT(*) as cnt FROM {SYNCED_SCHEMA}.facilities\n'
    '                WHERE \"{field}\" IS NOT NULL\n'
    '            \"\"\"\n'
    '        else:\n'
    '            sql = f\"\"\"\n'
    '                SELECT COUNT(*) as cnt FROM {SYNCED_SCHEMA}.facilities\n'
    '                WHERE \"{field}\" IS NOT NULL AND \"{field}\" != \'\' AND \"{field}\" != \'[]\'\n'
    '            \"\"\"\n'
    '        result = query(sql)'
)
assert old_loop in src, "Loop pattern not found — file may already be patched"
src = src.replace(old_loop, new_loop, 1)

fix_path.write_text(src)
print("✓ routes_readiness.py patched — numeric fields skip string comparisons")

# COMMAND ----------

# DBTITLE 1,Cell 10 — Sync to Lakebase
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import (
    SyncedDatabaseTable, SyncedTableSpec, SyncedTableSchedulingPolicy
)

w = WorkspaceClient()

INSTANCE_NAME = "hackathon-healthcare"
SOURCE_CATALOG = "dais2026"
SOURCE_SCHEMA  = "healthcare"
LOGICAL_DB     = "healthcare"
DEST_CATALOG   = "dais2026"
DEST_SCHEMA    = "lakebase_sync"

# facilities_clean is primary (normalized states); others are supplemental
tables_config = [
    ("facilities_clean",                  ["unique_id"]),
    ("facilities",                         ["unique_id"]),
    ("india_post_pincode_directory",        ["pincode", "officename"]),
    ("nfhs_5_district_health_indicators",  ["district_name"]),
]

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {DEST_CATALOG}.{DEST_SCHEMA}")

for table_name, pk_cols in tables_config:
    source_full = f"{SOURCE_CATALOG}.{SOURCE_SCHEMA}.{table_name}"
    dest_full   = f"{DEST_CATALOG}.{DEST_SCHEMA}.{table_name}"
    print(f"Syncing {table_name} → Lakebase...")

    # Delete any existing failed sync before recreating
    try:
        w.database.delete_synced_database_table(name=dest_full)
        print(f"  ↻ deleted stale synced table")
    except Exception:
        pass  # not found or already gone is fine

    try:
        sync = w.database.create_synced_database_table(
            synced_table=SyncedDatabaseTable(
                name=dest_full,
                database_instance_name=INSTANCE_NAME,
                logical_database_name=LOGICAL_DB,
                spec=SyncedTableSpec(
                    source_table_full_name=source_full,
                    primary_key_columns=pk_cols,
                    create_database_objects_if_missing=True,
                    scheduling_policy=SyncedTableSchedulingPolicy.SNAPSHOT,
                ),
            )
        )
        print(f"  ✓ {sync.name}")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"  ✓ already synced (skipped)")
        else:
            print(f"  ✗ {e}")

# COMMAND ----------

# DBTITLE 1,Cell 11 — Next Steps
# MAGIC %md
# MAGIC ## Next Steps
# MAGIC
# MAGIC After running this notebook:
# MAGIC
# MAGIC 1. **Update `app.py`** — change all references from `facilities` to `facilities_clean` in the `SYNCED_SCHEMA` queries.
# MAGIC    In `/api/filters/states`, change the JOIN to use `f.state_normalized` directly instead of `UPPER(f."address_stateOrRegion")`:
# MAGIC    ```sql
# MAGIC    ON UPPER(f.state_normalized) = g.state_name
# MAGIC    ```
# MAGIC
# MAGIC 2. **Schedule this notebook** to re-run whenever the source `facilities` table is updated.
# MAGIC
# MAGIC 3. **Verify coverage** — after running Cell 9, `pct_resolved` should be ≥ 99%.

# COMMAND ----------

# DBTITLE 1,Verify Lakebase schemas and tables
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import (
    SyncedDatabaseTable, SyncedTableSpec, SyncedTableSchedulingPolicy
)

w = WorkspaceClient()

INSTANCE_NAME  = "hackathon-healthcare"
LOGICAL_DB     = "healthcare"
SOURCE_CATALOG = "dais2026"
SOURCE_SCHEMA  = "lakebase_sync_clean"   # user's clean data lives here
DEST_CATALOG   = "dais2026"
DEST_SCHEMA    = "lakebase_sync_clean"   # new Lakebase Postgres schema
OLD_DEST_SCHEMA = "lakebase_sync"        # stale schema to remove

# ── Step 1: Inspect source tables in dais2026.lakebase_sync_clean ────────────
print("=== Tables in dais2026.lakebase_sync_clean ===")
tables_raw = [t for t in spark.sql(f"SHOW TABLES IN {SOURCE_CATALOG}.{SOURCE_SCHEMA}").collect() if not t.isTemporary]
for t in tables_raw:
    cnt = spark.sql(f"SELECT COUNT(*) FROM {SOURCE_CATALOG}.{SOURCE_SCHEMA}.{t.tableName}").collect()[0][0]
    print(f"  {t.tableName:<50} {cnt:>8,} rows")

# ── Step 2: Sync from dais2026.lakebase_sync_clean → Lakebase ───────────────
# (stale lakebase_sync tables already deleted in previous run)
print(f"\n=== Syncing {SOURCE_SCHEMA} → Lakebase schema '{DEST_SCHEMA}' ===")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {DEST_CATALOG}.{DEST_SCHEMA}")

# PK map — all 10 tables, PKs confirmed from schema inspection
pk_map = {
    "facilities":                        ["unique_id"],
    "facilities_base":                   ["unique_id"],
    "facilities_capabilities":           ["unique_id", "capability_item"],
    "facilities_equipment":              ["unique_id", "equipment_item"],
    "facilities_phones":                 ["unique_id", "phone_number"],
    "facilities_procedures":             ["unique_id", "procedure_item"],
    "facilities_specialties":            ["unique_id", "specialty"],
    "facilities_websites":               ["unique_id", "website_url"],
    "india_post_pincode_directory":      ["pincode", "officename"],
    "nfhs_5_district_health_indicators": ["district_name"],
}

for t in tables_raw:
    table_name = t.tableName
    if table_name not in pk_map:
        print(f"  ! No PK defined for {table_name} — skipping (add to pk_map above)")
        continue
    source_full = f"{SOURCE_CATALOG}.{SOURCE_SCHEMA}.{table_name}"
    dest_full   = f"{DEST_CATALOG}.{DEST_SCHEMA}.{table_name}"
    pk_cols     = pk_map[table_name]
    print(f"  Syncing {table_name} ...")
    try:
        sync = w.database.create_synced_database_table(
            synced_table=SyncedDatabaseTable(
                name=dest_full,
                database_instance_name=INSTANCE_NAME,
                logical_database_name=LOGICAL_DB,
                spec=SyncedTableSpec(
                    source_table_full_name=source_full,
                    primary_key_columns=pk_cols,
                    create_database_objects_if_missing=True,
                    scheduling_policy=SyncedTableSchedulingPolicy.SNAPSHOT,
                ),
            )
        )
        print(f"    ✓ {sync.name}")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"    ✓ already exists (skipped)")
        else:
            print(f"    ✗ {e}")

print("\nDone. Monitor sync status in the Databricks UI or re-run this cell to check.")

# COMMAND ----------

# DBTITLE 1,Drop stale lakebase_sync schema from Lakebase Postgres
import psycopg2, uuid
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()),
    instance_names=["hackathon-healthcare"],
)

conn = psycopg2.connect(
    host="ep-noisy-wave-d2hhvbvx.database.us-east-1.cloud.databricks.com",
    database="healthcare",
    user="krish.kilaru@lumenalta.com",
    port=5432,
    password=cred.token,
    sslmode="require",
)
conn.autocommit = True
cur = conn.cursor()

# List what's currently in lakebase_sync schema
cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'lakebase_sync'
    ORDER BY table_name;
""")
stale = [row[0] for row in cur.fetchall()]
print(f"Tables found in lakebase_sync: {stale}")

if stale:
    # Drop each table individually first
    for tbl in stale:
        cur.execute(f'DROP TABLE IF EXISTS lakebase_sync."{tbl}" CASCADE;')
        print(f"  dropped lakebase_sync.{tbl}")
    # Drop the schema itself
    cur.execute("DROP SCHEMA IF EXISTS lakebase_sync CASCADE;")
    print("  dropped schema lakebase_sync")
else:
    print("  lakebase_sync schema is already empty or does not exist — nothing to do")

cur.close()
conn.close()
print("Done.")

# COMMAND ----------

# DBTITLE 1,Verify lakebase_sync_clean row counts in Lakebase
import psycopg2, uuid
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()),
    instance_names=["hackathon-healthcare"],
)
conn = psycopg2.connect(
    host="ep-noisy-wave-d2hhvbvx.database.us-east-1.cloud.databricks.com",
    database="healthcare",
    user="krish.kilaru@lumenalta.com",
    port=5432,
    password=cred.token,
    sslmode="require",
)
cur = conn.cursor()

# Which tables exist in lakebase_sync_clean?
cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'lakebase_sync_clean'
    ORDER BY table_name;
""")
existing = [r[0] for r in cur.fetchall()]
print(f"Tables in lakebase_sync_clean ({len(existing)}):")

expected = [
    'facilities', 'facilities_base', 'facilities_capabilities',
    'facilities_equipment', 'facilities_phones', 'facilities_procedures',
    'facilities_specialties', 'facilities_websites',
    'india_post_pincode_directory', 'nfhs_5_district_health_indicators',
]

for tbl in expected:
    if tbl in existing:
        cur.execute(f'SELECT COUNT(*) FROM lakebase_sync_clean."{tbl}";')
        cnt = cur.fetchone()[0]
        status = f"{cnt:>10,} rows"
    else:
        status = "  MISSING"
    print(f"  {tbl:<45} {status}")

missing = [t for t in expected if t not in existing]
if missing:
    print(f"\n{len(missing)} tables missing from Lakebase — sync not yet complete.")
else:
    print("\nAll 10 tables present in Lakebase.")

cur.close()
conn.close()

# COMMAND ----------

# DBTITLE 1,Check sync status + force re-sync all 10 tables
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import (
    SyncedDatabaseTable, SyncedTableSpec, SyncedTableSchedulingPolicy
)

w = WorkspaceClient()

DEST_CATALOG   = "dais2026"
DEST_SCHEMA    = "lakebase_sync_clean"
SOURCE_CATALOG = "dais2026"
SOURCE_SCHEMA  = "lakebase_sync_clean"
INSTANCE_NAME  = "hackathon-healthcare"
LOGICAL_DB     = "healthcare"

pk_map = {
    "facilities":                        ["unique_id"],
    "facilities_base":                   ["unique_id"],
    "facilities_capabilities":           ["unique_id", "capability_item"],
    "facilities_equipment":              ["unique_id", "equipment_item"],
    "facilities_phones":                 ["unique_id", "phone_number"],
    "facilities_procedures":             ["unique_id", "procedure_item"],
    "facilities_specialties":            ["unique_id", "specialty"],
    "facilities_websites":               ["unique_id", "website_url"],
    "india_post_pincode_directory":      ["pincode", "officename"],
    "nfhs_5_district_health_indicators": ["district_name"],
}

print("=== Checking sync status ===")
for table_name in pk_map:
    dest_full = f"{DEST_CATALOG}.{DEST_SCHEMA}.{table_name}"
    try:
        tbl = w.database.get_synced_database_table(name=dest_full)
        state = getattr(tbl, 'status', None)
        pipeline_state = getattr(state, 'detailed_state', None) or getattr(state, 'state', None) or state
        print(f"  {table_name:<45} {pipeline_state}")
    except Exception as e:
        print(f"  {table_name:<45} NOT FOUND: {e}")

print("\n=== Force delete + recreate all 10 sync entries ===")
for table_name, pk_cols in pk_map.items():
    dest_full   = f"{DEST_CATALOG}.{DEST_SCHEMA}.{table_name}"
    source_full = f"{SOURCE_CATALOG}.{SOURCE_SCHEMA}.{table_name}"

    # Delete existing
    try:
        w.database.delete_synced_database_table(name=dest_full)
        print(f"  deleted {table_name}")
    except Exception:
        pass

    # Recreate
    try:
        sync = w.database.create_synced_database_table(
            synced_table=SyncedDatabaseTable(
                name=dest_full,
                database_instance_name=INSTANCE_NAME,
                logical_database_name=LOGICAL_DB,
                spec=SyncedTableSpec(
                    source_table_full_name=source_full,
                    primary_key_columns=pk_cols,
                    create_database_objects_if_missing=True,
                    scheduling_policy=SyncedTableSchedulingPolicy.SNAPSHOT,
                ),
            )
        )
        state = getattr(getattr(sync, 'status', None), 'detailed_state', None) \
                or getattr(getattr(sync, 'status', None), 'state', None) \
                or 'created'
        print(f"  ✓ {table_name:<45} {state}")
    except Exception as e:
        print(f"  ✗ {table_name}: {e}")

print("\nSync triggered. Re-run the previous cell in ~2-5 min to verify row counts.")

# COMMAND ----------

# DBTITLE 1,Sync lakebase_sync_clean → lakebase_pg_sync (Lakebase-backed)
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import (
    SyncedDatabaseTable, SyncedTableSpec, SyncedTableSchedulingPolicy
)

w = WorkspaceClient()

INSTANCE_NAME  = "hackathon-healthcare"
LOGICAL_DB     = "healthcare"
SOURCE_CATALOG = "dais2026"
SOURCE_SCHEMA  = "lakebase_sync_clean"   # regular Delta tables (existing clean data)
DEST_CATALOG   = "dais2026"
DEST_SCHEMA    = "lakebase_pg_sync"      # NEW UC schema — will be backed by Lakebase Postgres

pk_map = {
    "facilities":                        ["unique_id"],
    "facilities_base":                   ["unique_id"],
    "facilities_capabilities":           ["unique_id", "capability_item"],
    "facilities_equipment":              ["unique_id", "equipment_item"],
    "facilities_phones":                 ["unique_id", "phone_number"],
    "facilities_procedures":             ["unique_id", "procedure_item"],
    "facilities_specialties":            ["unique_id", "specialty"],
    "facilities_websites":               ["unique_id", "website_url"],
    "india_post_pincode_directory":      ["pincode", "officename"],
    "nfhs_5_district_health_indicators": ["district_name"],
}

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {DEST_CATALOG}.{DEST_SCHEMA}")
print(f"Syncing {len(pk_map)} tables: {SOURCE_CATALOG}.{SOURCE_SCHEMA} → Lakebase schema 'lakebase_pg_sync'\n")

for table_name, pk_cols in pk_map.items():
    source_full = f"{SOURCE_CATALOG}.{SOURCE_SCHEMA}.{table_name}"
    dest_full   = f"{DEST_CATALOG}.{DEST_SCHEMA}.{table_name}"
    try:
        sync = w.database.create_synced_database_table(
            synced_table=SyncedDatabaseTable(
                name=dest_full,
                database_instance_name=INSTANCE_NAME,
                logical_database_name=LOGICAL_DB,
                spec=SyncedTableSpec(
                    source_table_full_name=source_full,
                    primary_key_columns=pk_cols,
                    create_database_objects_if_missing=True,
                    scheduling_policy=SyncedTableSchedulingPolicy.SNAPSHOT,
                ),
            )
        )
        state = getattr(getattr(sync, 'status', None), 'detailed_state', None) \
                or getattr(getattr(sync, 'status', None), 'state', None) \
                or 'triggered'
        print(f"  ✓ {table_name:<45} {state}")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"  ✓ {table_name:<45} already exists")
        else:
            print(f"  ✗ {table_name}: {e}")

print("\nDone. Wait 2–5 min then run the row-count verification cell to confirm data is in Lakebase.")
print("Then update db.py: SYNCED_SCHEMA = 'lakebase_pg_sync'")

# COMMAND ----------

# DBTITLE 1,Create facilities_full view in Lakebase (run after sync completes)
# Run this AFTER the sync completes (verify row counts first with cell 16)
# Creates a denormalized view joining all 7 tables so the app queries one place
import psycopg2, uuid
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()),
    instance_names=["hackathon-healthcare"],
)
conn = psycopg2.connect(
    host="ep-noisy-wave-d2hhvbvx.database.us-east-1.cloud.databricks.com",
    database="healthcare",
    user="krish.kilaru@lumenalta.com",
    port=5432,
    password=cred.token,
    sslmode="require",
)
conn.autocommit = True
cur = conn.cursor()

# First check what the actual column names are (Postgres may lowercase camelCase)
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_schema = 'lakebase_pg_sync' AND table_name = 'facilities'
    ORDER BY ordinal_position;
""")
cols = [r[0] for r in cur.fetchall()]
print("facilities columns:", cols)

# Detect correct column names (Postgres may fold camelCase to lowercase)
state_col  = 'address_stateorregion'  if 'address_stateorregion'  in cols else 'address_stateOrRegion'
num_doc    = 'numberdoctors'          if 'numberdoctors'          in cols else 'numberDoctors'
yr_est     = 'yearestablished'        if 'yearestablished'        in cols else 'yearEstablished'
off_phone  = 'officialphone'          if 'officialphone'          in cols else 'officialPhone'
off_web    = 'officialwebsite'        if 'officialwebsite'        in cols else 'officialWebsite'

print(f"Using: state={state_col}, doctors={num_doc}, year={yr_est}")

view_sql = f"""
CREATE OR REPLACE VIEW lakebase_pg_sync.facilities_full AS
SELECT
    f.unique_id,
    f.name,
    f.organization_type,
    f.address_city,
    f."{state_col}"                                      AS state_normalized,
    f."{state_col}"                                      AS address_stateOrRegion,
    f.latitude,
    f.longitude,
    f.email,
    f."{off_phone}"                                      AS "officialPhone",
    f."{off_web}"                                        AS "officialWebsite",
    f."{num_doc}"                                        AS "numberDoctors",
    f.capacity,
    f."{yr_est}"                                         AS "yearEstablished",
    fb.description,
    fb.source                                            AS source_urls,
    fb.facebook_link                                     AS "facebookLink",
    COALESCE('[' || string_agg(DISTINCT '"' || fc.capability_item || '"', ', ') || ']', '[]') AS capability,
    COALESCE('[' || string_agg(DISTINCT '"' || fp.procedure_item  || '"', ', ') || ']', '[]') AS procedure,
    COALESCE('[' || string_agg(DISTINCT '"' || fe.equipment_item  || '"', ', ') || ']', '[]') AS equipment,
    COALESCE('[' || string_agg(DISTINCT '"' || fs.specialty        || '"', ', ') || ']', '[]') AS specialties,
    string_agg(DISTINCT fph.phone_number, ', ')          AS phone_numbers,
    string_agg(DISTINCT fw.website_url,   ', ')          AS websites
FROM lakebase_pg_sync.facilities f
LEFT JOIN lakebase_pg_sync.facilities_base         fb  ON f.unique_id = fb.unique_id
LEFT JOIN lakebase_pg_sync.facilities_capabilities fc  ON f.unique_id = fc.unique_id
LEFT JOIN lakebase_pg_sync.facilities_procedures   fp  ON f.unique_id = fp.unique_id
LEFT JOIN lakebase_pg_sync.facilities_equipment    fe  ON f.unique_id = fe.unique_id
LEFT JOIN lakebase_pg_sync.facilities_specialties  fs  ON f.unique_id = fs.unique_id
LEFT JOIN lakebase_pg_sync.facilities_phones       fph ON f.unique_id = fph.unique_id
LEFT JOIN lakebase_pg_sync.facilities_websites     fw  ON f.unique_id = fw.unique_id
GROUP BY
    f.unique_id, f.name, f.organization_type, f.address_city,
    f."{state_col}", f.latitude, f.longitude, f.email,
    f."{off_phone}", f."{off_web}", f."{num_doc}", f.capacity, f."{yr_est}",
    fb.description, fb.source, fb.facebook_link;
"""

cur.execute(view_sql)
print("\n✓ View lakebase_pg_sync.facilities_full created successfully")

# Quick sanity check
cur.execute("SELECT COUNT(*) FROM lakebase_pg_sync.facilities_full;")
print(f"  Row count: {cur.fetchone()[0]:,}")

cur.execute("SELECT unique_id, name, state_normalized, description IS NOT NULL as has_desc FROM lakebase_pg_sync.facilities_full LIMIT 2;")
for row in cur.fetchall():
    print(f"  {row}")

cur.close()
conn.close()

# COMMAND ----------

# DBTITLE 1,FASTER: Hard push facilities_full as TABLE (Spark JOIN → Postgres, indexed)
# Spark does the 7-way JOIN in ~30s, then we push 9,959 rows to Postgres.
# Much faster than a live VIEW that recomputes the JOIN on every API call.
import psycopg2, psycopg2.extras, uuid, time, pandas as pd
from databricks.sdk import WorkspaceClient
from pyspark.sql.types import DoubleType, FloatType, LongType, IntegerType, BooleanType

PG_SCHEMA = "lakebase_pg_sync"
TBL       = "facilities_full_clean"

# ── 0. Declare PK/FK constraints (NOT ENFORCED) so Spark eliminates redundant aggregates ──
_S = "dais2026.lakebase_sync_clean"
_constraints = [
    f"ALTER TABLE {_S}.facilities      ADD CONSTRAINT pk_facilities      PRIMARY KEY (unique_id)  NOT ENFORCED RELY",
    f"ALTER TABLE {_S}.facilities_base ADD CONSTRAINT pk_facilities_base PRIMARY KEY (unique_id)  NOT ENFORCED RELY",
    f"ALTER TABLE {_S}.facilities_capabilities ADD CONSTRAINT fk_cap_uid  FOREIGN KEY (unique_id) REFERENCES {_S}.facilities(unique_id) NOT ENFORCED RELY",
    f"ALTER TABLE {_S}.facilities_procedures   ADD CONSTRAINT fk_proc_uid FOREIGN KEY (unique_id) REFERENCES {_S}.facilities(unique_id) NOT ENFORCED RELY",
    f"ALTER TABLE {_S}.facilities_equipment    ADD CONSTRAINT fk_eq_uid   FOREIGN KEY (unique_id) REFERENCES {_S}.facilities(unique_id) NOT ENFORCED RELY",
    f"ALTER TABLE {_S}.facilities_specialties  ADD CONSTRAINT fk_spec_uid FOREIGN KEY (unique_id) REFERENCES {_S}.facilities(unique_id) NOT ENFORCED RELY",
    f"ALTER TABLE {_S}.facilities_phones       ADD CONSTRAINT fk_ph_uid   FOREIGN KEY (unique_id) REFERENCES {_S}.facilities(unique_id) NOT ENFORCED RELY",
    f"ALTER TABLE {_S}.facilities_websites     ADD CONSTRAINT fk_web_uid  FOREIGN KEY (unique_id) REFERENCES {_S}.facilities(unique_id) NOT ENFORCED RELY",
]
for _c in _constraints:
    try:
        spark.sql(_c)
    except Exception:
        pass  # already exists or not supported — advisory only

# ── 1. Build denormalized DataFrame in Spark ─────────────────────────────────
t0 = time.time()
df_full = spark.sql("""
SELECT
    f.unique_id, f.name, f.organization_type, f.address_city,
    f.address_stateOrRegion AS state_normalized,
    f.address_stateOrRegion,
    f.latitude,  f.longitude, f.email,
    f.officialPhone, f.officialWebsite, f.numberDoctors, f.capacity, f.yearEstablished,
    fb.description, fb.source AS source_urls, fb.facebook_link AS facebookLink,
    CASE WHEN size(collect_set(fc.capability_item)) > 0
         THEN to_json(collect_set(fc.capability_item)) ELSE '[]' END AS capability,
    CASE WHEN size(collect_set(fp.procedure_item))  > 0
         THEN to_json(collect_set(fp.procedure_item))  ELSE '[]' END AS procedure,
    CASE WHEN size(collect_set(fe.equipment_item))  > 0
         THEN to_json(collect_set(fe.equipment_item))  ELSE '[]' END AS equipment,
    CASE WHEN size(collect_set(fs.specialty))        > 0
         THEN to_json(collect_set(fs.specialty))        ELSE '[]' END AS specialties,
    concat_ws(', ', collect_set(fph.phone_number))  AS phone_numbers,
    concat_ws(', ', collect_set(fw.website_url))    AS websites
FROM dais2026.lakebase_sync_clean.facilities f
LEFT JOIN dais2026.lakebase_sync_clean.facilities_base         fb  ON f.unique_id = fb.unique_id
LEFT JOIN dais2026.lakebase_sync_clean.facilities_capabilities fc  ON f.unique_id = fc.unique_id
LEFT JOIN dais2026.lakebase_sync_clean.facilities_procedures   fp  ON f.unique_id = fp.unique_id
LEFT JOIN dais2026.lakebase_sync_clean.facilities_equipment    fe  ON f.unique_id = fe.unique_id
LEFT JOIN dais2026.lakebase_sync_clean.facilities_specialties  fs  ON f.unique_id = fs.unique_id
LEFT JOIN dais2026.lakebase_sync_clean.facilities_phones       fph ON f.unique_id = fph.unique_id
LEFT JOIN dais2026.lakebase_sync_clean.facilities_websites     fw  ON f.unique_id = fw.unique_id
GROUP BY
    f.unique_id, f.name, f.organization_type, f.address_city,
    f.address_stateOrRegion, f.latitude, f.longitude, f.email,
    f.officialPhone, f.officialWebsite, f.numberDoctors, f.capacity, f.yearEstablished,
    fb.description, fb.source, fb.facebook_link
""")
# ── 2. Push to Postgres ──────────────────────────────────────────────────────
def spark_to_pg(f):
    if isinstance(f.dataType, (DoubleType, FloatType)): return "DOUBLE PRECISION"
    if isinstance(f.dataType, (LongType, IntegerType)):  return "BIGINT"
    if isinstance(f.dataType, BooleanType):              return "BOOLEAN"
    return "TEXT"

w = WorkspaceClient()
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()), instance_names=["hackathon-healthcare"])
conn = psycopg2.connect(
    host="ep-noisy-wave-d2hhvbvx.database.us-east-1.cloud.databricks.com",
    database="healthcare", user="krish.kilaru@lumenalta.com",
    port=5432, password=cred.token, sslmode="require",
)
conn.autocommit = True
cur = conn.cursor()

# Drop + recreate as plain table (no partitioning)
col_defs = ", ".join([f'"{f.name}" {spark_to_pg(f)}' for f in df_full.schema.fields])
cur.execute(f'DROP TABLE IF EXISTS {PG_SCHEMA}."{TBL}" ;')
cur.execute(f'CREATE TABLE {PG_SCHEMA}."{TBL}" ({col_defs});')

# Convert to pandas + clean (single Spark action — avoids double recompute)
df = df_full.toPandas()
print(f"Spark JOIN + toPandas complete: {len(df):,} rows  ({time.time()-t0:.1f}s)")
for col in df.select_dtypes(include='object').columns:
    df[col] = df[col].str.replace('\x00', '', regex=False)
df = df.where(pd.notna(df), None)

# Bulk insert
quoted_cols  = ", ".join([f'"{c}"' for c in df.columns])
placeholders = ", ".join(["%s"] * len(df.columns))
sql  = f'INSERT INTO {PG_SCHEMA}."{TBL}" ({quoted_cols}) VALUES ({placeholders})'
rows = [tuple(r) for r in df.itertuples(index=False, name=None)]
psycopg2.extras.execute_batch(cur, sql, rows, page_size=500)

cur.execute(f'SELECT COUNT(*) FROM {PG_SCHEMA}."{TBL}";')
print(f"\n\u2713 {PG_SCHEMA}.{TBL}: {cur.fetchone()[0]:,} rows  (total: {time.time()-t0:.1f}s)")
cur.execute(f'SELECT unique_id, name, state_normalized FROM {PG_SCHEMA}."{TBL}" LIMIT 2;')
for r in cur.fetchall(): print(f"  {r}")

cur.close()
conn.close()

# COMMAND ----------

# DBTITLE 1,Add indexes to facilities_full (state, city, unique_id)
import psycopg2, uuid
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()), instance_names=["hackathon-healthcare"])
conn = psycopg2.connect(
    host="ep-noisy-wave-d2hhvbvx.database.us-east-1.cloud.databricks.com",
    database="healthcare", user="krish.kilaru@lumenalta.com",
    port=5432, password=cred.token, sslmode="require",
)
conn.autocommit = True
cur = conn.cursor()

PG = 'lakebase_pg_sync."facilities_full"'

indexes = [
    # All 4 tracks filter/group by state
    ("idx_ff_state",       f'CREATE INDEX IF NOT EXISTS idx_ff_state       ON {PG}(state_normalized);'),
    # Deserts + referral group/filter by city
    ("idx_ff_city",        f'CREATE INDEX IF NOT EXISTS idx_ff_city        ON {PG}(address_city);'),
    # Deserts uses (state, city) GROUP BY constantly
    ("idx_ff_state_city",  f'CREATE INDEX IF NOT EXISTS idx_ff_state_city  ON {PG}(state_normalized, address_city);'),
    # Trust + referral lookup by unique_id
    ("idx_ff_uid",         f'CREATE INDEX IF NOT EXISTS idx_ff_uid         ON {PG}(unique_id);'),
    # Referral specialty search (GIN for ILIKE) — speeds up specialties ILIKE %x%
    ("idx_ff_spec_trgm",   'CREATE EXTENSION IF NOT EXISTS pg_trgm;'),
    ("idx_ff_spec_gin",    f'CREATE INDEX IF NOT EXISTS idx_ff_spec_gin    ON {PG} USING gin(specialties gin_trgm_ops);'),
]

for name, sql in indexes:
    try:
        cur.execute(sql)
        print(f"  ✓ {name}")
    except Exception as e:
        print(f"  ! {name}: {e}")

cur.close()
conn.close()
print("\nIndexes ready. Redeploy app to pick up the facilities_full table.")

# COMMAND ----------

# DBTITLE 1,ETL: dais2026.healthcare.facilities → facilities_final (clean) + facilities_errors
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StringType, IntegerType, DoubleType
from functools import reduce

SOURCE  = "dais2026.healthcare.facilities"
TARGET  = "dais2026.lakebase_sync_clean.facilities_final"
ERR_TBL = "dais2026.lakebase_sync_error.facilities_errors"

# ── Setup ────────────────────────────────────────────────────────────────────
spark.sql("CREATE SCHEMA IF NOT EXISTS dais2026.lakebase_sync_clean")
spark.sql("CREATE SCHEMA IF NOT EXISTS dais2026.lakebase_sync_error")

df = spark.table(SOURCE)
SOURCE_COUNT = df.count()
print(f"Source: {SOURCE_COUNT:,} rows, {len(df.columns)} columns")

# Accumulate error rows: (unique_id, name, error_type, field, bad_value)
error_frames = []


# ── Helper ───────────────────────────────────────────────────────────────────
def capture_and_null(df, col_name, bad_flag_col, error_type):
    """Null out bad values in col_name and snapshot them to error_frames."""
    bad = df.filter(F.col(bad_flag_col)).select(
        F.col("unique_id"),
        F.col("name"),
        F.lit(error_type).alias("error_type"),
        F.lit(col_name).alias("field"),
        F.col(col_name).cast("string").alias("bad_value"),
    )
    error_frames.append(bad)
    df = df.withColumn(
        col_name,
        F.when(F.col(bad_flag_col), None).otherwise(F.col(col_name))
    ).drop(bad_flag_col)
    return df


# ── 1. Strip NUL bytes + collapse blank/null sentinels on all STRING cols ─────
# Pre-compute schema once (avoids repeated Analyze RPC per loop iteration)
_schema_fields = df.schema.fields
STR_COLS = [f.name for f in _schema_fields if isinstance(f.dataType, StringType)]

# Build all string-clean expressions in one .withColumns() call (no nested plan)
clean_exprs = {
    c: F.when(
        F.trim(F.regexp_replace(F.col(c), r'\x00', '')).isin(
            '', 'null', 'NULL', 'None', 'N/A', 'n/a', 'NA'
        ),
        None
    ).otherwise(F.trim(F.regexp_replace(F.col(c), r'\x00', '')))
    for c in STR_COLS
}
df = df.withColumns(clean_exprs)
print("  ✓ NUL/blank sentinel cleanup done")


# ── 2. Validate JSON array columns ───────────────────────────────────────────
JSON_COLS = [
    "capability", "procedure", "equipment", "specialties",
    "phone_numbers", "websites", "affiliationTypeIds",
    "source_types", "source_ids",
]
JSON_SCHEMA = ArrayType(StringType())
# Pre-compute column set once; build all flag + parsed exprs together
_df_cols = set(df.columns)
json_present = [c for c in JSON_COLS if c in _df_cols]

# Add all parsed + flag columns in a single .withColumns() call
json_exprs = {}
for c in json_present:
    json_exprs[f"_parsed_{c}"] = F.from_json(F.col(c), JSON_SCHEMA)
json_exprs.update({
    f"_bad_{c}": F.col(c).isNotNull() & F.col(f"_parsed_{c}").isNull()
    for c in json_present
})
df = df.withColumns(json_exprs).drop(*[f"_parsed_{c}" for c in json_present])

for c in json_present:
    df = capture_and_null(df, c, f"_bad_{c}", "invalid_json")
print(f"  ✓ JSON array validation done ({len(json_present)} columns checked)")


# ── 3. Validate lat / lon  (India bbox: lat 6–37.5 °N, lon 68–97.5 °E) ──────
df = df.withColumn("_bad_lat",
    F.col("latitude").isNotNull() &
    (~F.col("latitude").between(6.0, 37.5))
).withColumn("_bad_lon",
    F.col("longitude").isNotNull() &
    (~F.col("longitude").between(68.0, 97.5))
)
df = capture_and_null(df, "latitude",  "_bad_lat", "out_of_bounds_lat")
df = capture_and_null(df, "longitude", "_bad_lon", "out_of_bounds_lon")
print("  ✓ Lat/lon bounds validation done (India bbox)")


# ── 4. Validate numeric-as-string columns ────────────────────────────────────
NUMERIC_RULES = {
    # col               : (min, max)
    "yearEstablished"                    : (1800, 2026),
    "numberDoctors"                      : (0, 100_000),
    "capacity"                           : (0, 1_000_000),
    "distinct_social_media_presence_count": (0, 10_000),
    "number_of_facts_about_the_organization": (0, 10_000),
    "post_metrics_post_count"            : (0, 10_000_000),
    "engagement_metrics_n_followers"     : (0, 100_000_000),
    "engagement_metrics_n_likes"         : (0, 100_000_000),
    "engagement_metrics_n_engagements"   : (0, 100_000_000),
}
# Build all numeric flag expressions in one .withColumns() call
_df_cols2 = set(df.columns)
num_present = {c: bounds for c, bounds in NUMERIC_RULES.items() if c in _df_cols2}
num_flag_exprs = {
    f"_bad_{c}": (
        F.col(c).isNotNull() &
        (F.expr(f"try_cast(`{c}` AS DOUBLE)").isNull() |
         ~F.expr(f"try_cast(`{c}` AS DOUBLE)").between(lo, hi))
    )
    for c, (lo, hi) in num_present.items()
}
df = df.withColumns(num_flag_exprs)
for col_name in num_present:
    df = capture_and_null(df, col_name, f"_bad_{col_name}", "invalid_numeric")
print(f"  ✓ Numeric validation done ({len(num_present)} columns checked)")


# ── 5. Validate email (basic regex) ──────────────────────────────────────────
df = df.withColumn("_bad_email",
    F.col("email").isNotNull() &
    (~F.col("email").rlike(r'^[^@\s]+@[^@\s]+\.[^@\s]+$'))
)
df = capture_and_null(df, "email", "_bad_email", "invalid_email")
print("  ✓ Email format validation done")


# ── 6. Write error table ─────────────────────────────────────────────────────
if error_frames:
    errors_df = reduce(lambda a, b: a.unionByName(b), error_frames)
    errors_df = errors_df.withColumn("source_table", F.lit(SOURCE))
    err_count = errors_df.count()
    errors_df.write.format("delta") \
        .mode("overwrite") \
        .option("overwriteSchema", "true") \
        .saveAsTable(ERR_TBL)
    print(f"\n  ✓ {ERR_TBL}: {err_count:,} error records written")
else:
    print("\n  ✓ No errors found — error table not written")
    err_count = 0


# ── 7. Write facilities_final ─────────────────────────────────────────────────
FINAL_COUNT = df.count()
assert FINAL_COUNT == SOURCE_COUNT, \
    f"RECORD COUNT MISMATCH: source={SOURCE_COUNT:,} final={FINAL_COUNT:,}"

df.write.format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable(TARGET)

print(f"\n{'='*60}")
print(f"  Source : {SOURCE}")
print(f"  Target : {TARGET}")
print(f"  Errors : {ERR_TBL}")
print(f"  Rows   : {FINAL_COUNT:,}  (= source ✓)")
print(f"  Errors : {err_count:,} bad-value records (rows kept, values nulled)")
print(f"{'='*60}")

# COMMAND ----------

# DBTITLE 1,Error analysis: facilities_errors breakdown
from pyspark.sql import functions as F

ERR_TBL = "dais2026.lakebase_sync_error.facilities_errors"
SOURCE_COUNT = spark.table("dais2026.healthcare.facilities").count()

err = spark.table(ERR_TBL)
total_errors = err.count()
affected_facilities = err.select("unique_id").distinct().count()

print(f"{'='*65}")
print(f"  Total error records  : {total_errors:,}")
print(f"  Affected facilities  : {affected_facilities:,} / {SOURCE_COUNT:,}  ({affected_facilities/SOURCE_COUNT*100:.1f}%)")
print(f"{'='*65}")

# ── 1. Breakdown by error_type + field ────────────────────────────
print("\nBreakdown by error type + field:")
display(
    err.groupBy("error_type", "field")
    .agg(
        F.count("*").alias("error_count"),
        F.countDistinct("unique_id").alias("distinct_facilities"),
        F.round(F.countDistinct("unique_id") / SOURCE_COUNT * 100, 2).alias("pct_of_source")
    )
    .orderBy(F.col("error_count").desc())
)

# ── 2. Sample bad values per field (5 examples each) ────────────────────
print("\nSample bad values per field (up to 5 each):")
display(
    err.withColumn(
        "rn",
        F.row_number().over(
            __import__("pyspark.sql.window", fromlist=["Window"]).Window
            .partitionBy("field").orderBy("unique_id")
        )
    )
    .filter(F.col("rn") <= 5)
    .drop("rn", "source_table")
    .orderBy("field", "error_type")
)

# ── 3. Fields with highest null-out rate after cleaning ──────────────────
print("\nNull-out impact per field (% of source rows cleaned to NULL):")
display(
    err.groupBy("field")
    .agg(F.countDistinct("unique_id").alias("facilities_affected"))
    .withColumn("pct_nulled", F.round(F.col("facilities_affected") / SOURCE_COUNT * 100, 2))
    .orderBy(F.col("pct_nulled").desc())
)

# COMMAND ----------

# DBTITLE 1,Push facilities_final → Postgres lakebase_pg_sync.facilities_full
import psycopg2, psycopg2.extras, uuid, time, pandas as pd
from databricks.sdk import WorkspaceClient
from pyspark.sql.types import DoubleType, FloatType

PG_SCHEMA = "lakebase_pg_sync"
TBL       = "facilities_full"
t0 = time.time()

from pyspark.sql import functions as F

# ── 0. State normalisation map (28 states + 8 UTs of India) ──────────────────
_SM = {
    # Full names (lowercase key → canonical value)
    "andhra pradesh":"Andhra Pradesh","arunachal pradesh":"Arunachal Pradesh",
    "assam":"Assam","bihar":"Bihar","chhattisgarh":"Chhattisgarh",
    "chattisgarh":"Chhattisgarh","goa":"Goa","gujarat":"Gujarat",
    "haryana":"Haryana","himachal pradesh":"Himachal Pradesh",
    "jharkhand":"Jharkhand","karnataka":"Karnataka","kerala":"Kerala",
    "madhya pradesh":"Madhya Pradesh","maharashtra":"Maharashtra",
    "manipur":"Manipur","meghalaya":"Meghalaya","mizoram":"Mizoram",
    "nagaland":"Nagaland","odisha":"Odisha","orissa":"Odisha",
    "punjab":"Punjab","rajasthan":"Rajasthan","sikkim":"Sikkim",
    "tamil nadu":"Tamil Nadu","tamilnadu":"Tamil Nadu",
    "telangana":"Telangana","tripura":"Tripura",
    "uttar pradesh":"Uttar Pradesh","uttarakhand":"Uttarakhand",
    "uttaranchal":"Uttarakhand","west bengal":"West Bengal",
    # UTs
    "andaman and nicobar":"Andaman and Nicobar Islands",
    "andaman & nicobar":"Andaman and Nicobar Islands",
    "chandigarh":"Chandigarh",
    "dadra and nagar haveli":"Dadra and Nagar Haveli and Daman and Diu",
    "daman and diu":"Dadra and Nagar Haveli and Daman and Diu",
    "delhi":"Delhi","new delhi":"Delhi",
    "jammu and kashmir":"Jammu and Kashmir",
    "jammu & kashmir":"Jammu and Kashmir","j&k":"Jammu and Kashmir",
    "ladakh":"Ladakh","lakshadweep":"Lakshadweep",
    "puducherry":"Puducherry","pondicherry":"Puducherry",
    # Common abbreviations
    "up":"Uttar Pradesh","mp":"Madhya Pradesh","hp":"Himachal Pradesh",
    "wb":"West Bengal","ap":"Andhra Pradesh","tn":"Tamil Nadu",
    "mh":"Maharashtra","ka":"Karnataka","rj":"Rajasthan",
    "gj":"Gujarat","hr":"Haryana","pb":"Punjab","br":"Bihar",
    "jh":"Jharkhand","uk":"Uttarakhand","cg":"Chhattisgarh",
    "ts":"Telangana","kl":"Kerala","or":"Odisha","as":"Assam",
    "mn":"Manipur","ml":"Meghalaya","mz":"Mizoram","nl":"Nagaland",
    "tr":"Tripura","sk":"Sikkim","ga":"Goa","ar":"Arunachal Pradesh",
    "dl":"Delhi","ch":"Chandigarh",
}
# Long-key substring matches (applied only when direct lookup fails)
_SM_SUBSTR = {k: v for k, v in _SM.items() if len(k) > 4}

@F.udf("string")
def _norm_state(raw):
    if not raw:
        return None
    s = raw.strip()
    if len(s) > 80:          # JSON array / long description → discard
        return None
    key = s.lower()
    if key in _SM:
        return _SM[key]
    for k, v in _SM_SUBSTR.items():
        if k in key:
            return v
    return None              # unknown → NULL

@F.udf("string")
def _norm_city(raw):
    """Title-case trim — removes cap/spacing duplicates."""
    if not raw:
        return None
    s = raw.strip()
    return s.title() if len(s) <= 80 else None

# ── 1a. Pincode → official district lookup (india_post_pincode_directory) ───────
df_pin = spark.sql("""
    SELECT
        CAST(pincode AS STRING)  AS pincode_str,
        FIRST(district)          AS district_official,
        FIRST(statename)         AS state_from_pin
    FROM dais2026.healthcare.india_post_pincode_directory
    WHERE district IS NOT NULL AND pincode IS NOT NULL
    GROUP BY pincode
""")
print(f"Pincode lookup: {df_pin.count():,} unique pincodes")

# ── 1b. Select columns + join pincode lookup ───────────────────────────────
df_pg = spark.sql("""
SELECT
    unique_id, name, organization_type,
    address_city, address_stateOrRegion, address_zipOrPostcode,
    latitude, longitude, email,
    officialPhone, officialWebsite,
    numberDoctors, capacity, yearEstablished,
    description, source_urls, facebookLink,
    capability, procedure, equipment, specialties,
    phone_numbers, websites
FROM dais2026.lakebase_sync_clean.facilities_final
""")

# Join pincode lookup (broadcast — small table)
df_pg = df_pg.join(
    F.broadcast(df_pin),
    F.trim(df_pg.address_zipOrPostcode) == df_pin.pincode_str,
    "left"
)

# Apply normalisations
df_pg = (
    df_pg
    .withColumn("state_normalized",  _norm_state(F.col("address_stateOrRegion")))
    # Use official district from pincode if available, else title-cased raw city
    .withColumn("address_city",
        F.coalesce(
            F.when(F.col("district_official").isNotNull(),
                   F.initcap(F.col("district_official"))),
            _norm_city(F.col("address_city"))
        )
    )
    # Also use pincode's statename to fill NULL state_normalized
    .withColumn("state_normalized",
        F.coalesce(
            F.col("state_normalized"),
            _norm_state(F.col("state_from_pin"))
        )
    )
    .drop("address_zipOrPostcode", "pincode_str", "district_official", "state_from_pin")
)

distinct_states = df_pg.select("state_normalized").distinct().count()
distinct_cities = df_pg.select("address_city").distinct().count()
print(f"Rows to push : {df_pg.count():,}  cols: {len(df_pg.columns)}")
print(f"Distinct states : {distinct_states}  (target ≤36)")
print(f"Distinct cities : {distinct_cities}")

# ── 2. Connect to Postgres ───────────────────────────────────────────────
w = WorkspaceClient()
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()), instance_names=["hackathon-healthcare"])
conn = psycopg2.connect(
    host="ep-noisy-wave-d2hhvbvx.database.us-east-1.cloud.databricks.com",
    database="healthcare", user="krish.kilaru@lumenalta.com",
    port=5432, password=cred.token, sslmode="require",
)
conn.autocommit = True
cur = conn.cursor()

# ── 3. Drop + recreate table ───────────────────────────────────────────────
def pg_type(f):
    if isinstance(f.dataType, (DoubleType, FloatType)): return "DOUBLE PRECISION"
    return "TEXT"

col_defs = ", ".join([f'"{f.name}" {pg_type(f)}' for f in df_pg.schema.fields])
cur.execute(f'DROP TABLE IF EXISTS {PG_SCHEMA}."{TBL}" CASCADE;')
cur.execute(f'CREATE TABLE {PG_SCHEMA}."{TBL}" ({col_defs});')

# ── 4. toPandas + clean + bulk insert ─────────────────────────────────────────
df = df_pg.toPandas()
for col in df.select_dtypes(include='object').columns:
    df[col] = df[col].str.replace('\x00', '', regex=False)
df = df.where(pd.notna(df), None)

quoted_cols  = ", ".join([f'"{c}"' for c in df.columns])
placeholders = ", ".join(["%s"] * len(df.columns))
insert_sql   = f'INSERT INTO {PG_SCHEMA}."{TBL}" ({quoted_cols}) VALUES ({placeholders})'
rows = [tuple(r) for r in df.itertuples(index=False, name=None)]
psycopg2.extras.execute_batch(cur, insert_sql, rows, page_size=500)

# ── 5. Indexes ───────────────────────────────────────────────────────────────
PG = f'{PG_SCHEMA}."{TBL}"'
for idx_sql in [
    f'CREATE INDEX ON {PG}(state_normalized);',
    f'CREATE INDEX ON {PG}(address_city);',
    f'CREATE INDEX ON {PG}(state_normalized, address_city);',
    f'CREATE INDEX ON {PG}(unique_id);',
    'CREATE EXTENSION IF NOT EXISTS pg_trgm;',
    f'CREATE INDEX ON {PG} USING gin(specialties gin_trgm_ops);',
    f'CREATE INDEX ON {PG} USING gin(capability gin_trgm_ops);',
]:
    try: cur.execute(idx_sql)
    except Exception as e: print(f"  index warning: {e}")

# ── 6. Verify ─────────────────────────────────────────────────────────────────
cur.execute(f'SELECT COUNT(*) FROM {PG_SCHEMA}."{TBL}";')
final_count = cur.fetchone()[0]
cur.execute(f'SELECT unique_id, name, state_normalized, specialties IS NOT NULL FROM {PG_SCHEMA}."{TBL}" LIMIT 2;')
samples = cur.fetchall()
cur.close()
conn.close()

print(f"\n{'='*60}")
print(f"  {PG_SCHEMA}.{TBL}: {final_count:,} rows  ({time.time()-t0:.1f}s)")
print(f"  Indexes  : state, city, (state+city), unique_id, GIN specialties+capability")
for r in samples: print(f"  sample   : {r}")
print(f"{'='*60}")
print("\n✓ Redeploy app to pick up the new facilities_full table.")

# COMMAND ----------

# DBTITLE 1,GRANT service principal SELECT on lakebase_pg_sync schema
# App service principal: c7841054-bfed-4e93-9abd-8af52b993043
# Grant it read access on everything in lakebase_pg_sync so the app can query facilities_full
import psycopg2, uuid
from databricks.sdk import WorkspaceClient

SP = "c7841054-bfed-4e93-9abd-8af52b993043"  # app service principal client_id

w = WorkspaceClient()
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()), instance_names=["hackathon-healthcare"])
conn = psycopg2.connect(
    host="ep-noisy-wave-d2hhvbvx.database.us-east-1.cloud.databricks.com",
    database="healthcare", user="krish.kilaru@lumenalta.com",
    port=5432, password=cred.token, sslmode="require",
)
conn.autocommit = True
cur = conn.cursor()

grants = [
    f'GRANT USAGE ON SCHEMA lakebase_pg_sync TO "{SP}";',
    f'GRANT SELECT ON ALL TABLES IN SCHEMA lakebase_pg_sync TO "{SP}";',
    f'ALTER DEFAULT PRIVILEGES IN SCHEMA lakebase_pg_sync GRANT SELECT ON TABLES TO "{SP}";',
    f'GRANT USAGE ON SCHEMA app_data TO "{SP}";',
    f'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA app_data TO "{SP}";',
    f'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA app_data TO "{SP}";',
    f'ALTER DEFAULT PRIVILEGES IN SCHEMA app_data GRANT ALL PRIVILEGES ON TABLES TO "{SP}";',
    f'ALTER DEFAULT PRIVILEGES IN SCHEMA app_data GRANT ALL PRIVILEGES ON SEQUENCES TO "{SP}";',
]
for g in grants:
    try:
        cur.execute(g)
        print(f"  \u2713 {g[:80]}")
    except Exception as e:
        print(f"  ! {g[:60]} => {e}")

cur.close()
conn.close()
print("\nDone. Redeploy app to pick up the grants.")

# COMMAND ----------

# DBTITLE 1,Enable CDF on all source tables + retry failed syncs
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import (
    SyncedDatabaseTable, SyncedTableSpec, SyncedTableSchedulingPolicy
)

w = WorkspaceClient()

SOURCE_CATALOG = "dais2026"
SOURCE_SCHEMA  = "lakebase_sync_clean"
DEST_CATALOG   = "dais2026"
DEST_SCHEMA    = "lakebase_pg_sync"
INSTANCE_NAME  = "hackathon-healthcare"
LOGICAL_DB     = "healthcare"

pk_map = {
    "facilities":                        ["unique_id"],
    "facilities_base":                   ["unique_id"],
    "facilities_capabilities":           ["unique_id", "capability_item"],
    "facilities_equipment":              ["unique_id", "equipment_item"],
    "facilities_phones":                 ["unique_id", "phone_number"],
    "facilities_procedures":             ["unique_id", "procedure_item"],
    "facilities_specialties":            ["unique_id", "specialty"],
    "facilities_websites":               ["unique_id", "website_url"],
    "india_post_pincode_directory":      ["pincode", "officename"],
    "nfhs_5_district_health_indicators": ["district_name"],
}

# Step 1: Check + enable CDF on each source table
print("=== Checking/enabling CDF on source tables ===")
for table_name in pk_map:
    full = f"{SOURCE_CATALOG}.{SOURCE_SCHEMA}.{table_name}"
    props = spark.sql(f"SHOW TBLPROPERTIES {full}").collect()
    cdf = next((r['value'] for r in props if r['key'] == 'delta.enableChangeDataFeed'), 'false')
    if cdf == 'true':
        print(f"  {table_name:<45} CDF already ON")
    else:
        spark.sql(f"ALTER TABLE {full} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")
        print(f"  {table_name:<45} CDF ENABLED")

print("\n✓ CDF enabled on all source tables. Run the next cell (manually) to delete+recreate the failed syncs.")

# COMMAND ----------

# DBTITLE 1,Step 2: Delete + recreate failed syncs (run after Step 1)
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import (
    SyncedDatabaseTable, SyncedTableSpec, SyncedTableSchedulingPolicy
)

w = WorkspaceClient()

DEST_CATALOG   = "dais2026"
DEST_SCHEMA    = "lakebase_pg_sync"
SOURCE_CATALOG = "dais2026"
SOURCE_SCHEMA  = "lakebase_sync_clean"
INSTANCE_NAME  = "hackathon-healthcare"
LOGICAL_DB     = "healthcare"

pk_map = {
    "facilities":                        ["unique_id"],
    "facilities_base":                   ["unique_id"],
    "facilities_capabilities":           ["unique_id", "capability_item"],
    "facilities_equipment":              ["unique_id", "equipment_item"],
    "facilities_phones":                 ["unique_id", "phone_number"],
    "facilities_procedures":             ["unique_id", "procedure_item"],
    "facilities_specialties":            ["unique_id", "specialty"],
    "facilities_websites":               ["unique_id", "website_url"],
    "india_post_pincode_directory":      ["pincode", "officename"],
    "nfhs_5_district_health_indicators": ["district_name"],
}

print("=== Retrying failed syncs ===")
for table_name, pk_cols in pk_map.items():
    dest_full   = f"{DEST_CATALOG}.{DEST_SCHEMA}.{table_name}"
    source_full = f"{SOURCE_CATALOG}.{SOURCE_SCHEMA}.{table_name}"

    # Check if already healthy
    try:
        tbl   = w.database.get_synced_database_table(name=dest_full)
        state = str(tbl.data_synchronization_status.detailed_state)
        if 'FAILED' not in state and 'OFFLINE' not in state:
            print(f"  {table_name:<45} OK — skipping ({state})")
            continue
    except Exception:
        pass

    # Delete stale failed entry
    try:
        w.database.delete_synced_database_table(name=dest_full)
    except Exception:
        pass

    # Recreate
    try:
        w.database.create_synced_database_table(
            synced_table=SyncedDatabaseTable(
                name=dest_full,
                database_instance_name=INSTANCE_NAME,
                logical_database_name=LOGICAL_DB,
                spec=SyncedTableSpec(
                    source_table_full_name=source_full,
                    primary_key_columns=pk_cols,
                    create_database_objects_if_missing=True,
                    scheduling_policy=SyncedTableSchedulingPolicy.SNAPSHOT,
                ),
            )
        )
        print(f"  {table_name:<45} re-triggered")
    except Exception as e:
        print(f"  {table_name:<45} ERROR: {e}")

print("\nDone. Wait 3-5 min, then re-run cell 20 (Postgres row counts) to verify.")

# COMMAND ----------

# DBTITLE 1,Drop empty Postgres tables blocking sync (0-row tables only)
import psycopg2, uuid
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()),
    instance_names=["hackathon-healthcare"],
)
conn = psycopg2.connect(
    host="ep-noisy-wave-d2hhvbvx.database.us-east-1.cloud.databricks.com",
    database="healthcare", user="krish.kilaru@lumenalta.com",
    port=5432, password=cred.token, sslmode="require",
)
conn.autocommit = True
cur = conn.cursor()

# Only drop tables that are at 0 rows (safe — never had data)
# Keep india_post_pincode_directory (162,994 rows — already synced successfully)
to_drop = [
    "facilities", "facilities_base", "facilities_capabilities",
    "facilities_equipment", "facilities_phones", "facilities_procedures",
    "facilities_specialties", "facilities_websites",
    "nfhs_5_district_health_indicators",
]

for tbl in to_drop:
    try:
        cur.execute(f'SELECT COUNT(*) FROM lakebase_pg_sync."{tbl}";')
        cnt = cur.fetchone()[0]
        if cnt == 0:
            cur.execute(f'DROP TABLE IF EXISTS lakebase_pg_sync."{tbl}" CASCADE;')
            print(f"  dropped lakebase_pg_sync.{tbl} (was 0 rows)")
        else:
            print(f"  SKIPPED lakebase_pg_sync.{tbl} ({cnt:,} rows — has data!)")
    except Exception as e:
        print(f"  {tbl}: {e}")

cur.close()
conn.close()
print("\nDone. Now re-run Cell 21 to recreate the sync entries.")

# COMMAND ----------

# DBTITLE 1,Diagnose sync state — inspect SDK object fields
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Inspect available fields on SyncedDatabaseTable
tbl = w.database.get_synced_database_table(name="dais2026.lakebase_pg_sync.facilities")
print("All fields on SyncedDatabaseTable:")
for attr in dir(tbl):
    if not attr.startswith('_'):
        val = getattr(tbl, attr, None)
        if not callable(val):
            print(f"  {attr}: {val}")

# Also try facilities_base to compare
print("\nfacilities_base:")
tbl2 = w.database.get_synced_database_table(name="dais2026.lakebase_pg_sync.facilities_base")
for attr in dir(tbl2):
    if not attr.startswith('_'):
        val = getattr(tbl2, attr, None)
        if not callable(val):
            print(f"  {attr}: {val}")

# COMMAND ----------

# DBTITLE 1,Check lakebase_pg_sync pipeline status
from databricks.sdk import WorkspaceClient
import psycopg2, uuid

w = WorkspaceClient()

DEST_CATALOG = "dais2026"
DEST_SCHEMA  = "lakebase_pg_sync"

tables = [
    "facilities", "facilities_base", "facilities_capabilities",
    "facilities_equipment", "facilities_phones", "facilities_procedures",
    "facilities_specialties", "facilities_websites",
    "india_post_pincode_directory", "nfhs_5_district_health_indicators",
]

print("=== Synced table pipeline status ===")
for t in tables:
    dest_full = f"{DEST_CATALOG}.{DEST_SCHEMA}.{t}"
    try:
        tbl    = w.database.get_synced_database_table(name=dest_full)
        status = tbl.status
        state  = getattr(status, 'detailed_state', None) or getattr(status, 'state', None)
        msg    = getattr(status, 'message', '') or ''
        print(f"  {t:<45} {state}  {msg[:80] if msg else ''}")
    except Exception as e:
        print(f"  {t:<45} ERROR: {e}")

# Also check Postgres row counts
print("\n=== Postgres row counts ===")
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()),
    instance_names=["hackathon-healthcare"],
)
conn = psycopg2.connect(
    host="ep-noisy-wave-d2hhvbvx.database.us-east-1.cloud.databricks.com",
    database="healthcare", user="krish.kilaru@lumenalta.com",
    port=5432, password=cred.token, sslmode="require",
)
cur = conn.cursor()
for t in tables:
    try:
        cur.execute(f'SELECT COUNT(*) FROM lakebase_pg_sync."{t}";')
        cnt = cur.fetchone()[0]
        print(f"  {t:<45} {cnt:>10,} rows")
    except Exception as e:
        print(f"  {t:<45} {e}")
cur.close()
conn.close()

# COMMAND ----------

# DBTITLE 1,HARD PUSH — Spark → Postgres direct bulk insert (bypasses Synced Tables)
# Bypasses the Synced Tables DLT pipeline entirely.
# Reads each Delta table with Spark, pushes rows directly to Lakebase via psycopg2.
import psycopg2, psycopg2.extras, uuid, time
import pandas as pd
from databricks.sdk import WorkspaceClient
from pyspark.sql.types import DoubleType, FloatType, LongType, IntegerType, BooleanType

SOURCE = "dais2026.lakebase_sync_clean"
PG_SCHEMA = "lakebase_pg_sync"

# Tables with partial data from interrupted first run — force full re-push
force_tables = {"facilities", "facilities_base", "facilities_capabilities"}

tables_pks = {
    "facilities":                        ["unique_id"],
    "facilities_base":                   ["unique_id"],
    "facilities_capabilities":           ["unique_id", "capability_item"],
    "facilities_equipment":              ["unique_id", "equipment_item"],
    "facilities_phones":                 ["unique_id", "phone_number"],
    "facilities_procedures":             ["unique_id", "procedure_item"],
    "facilities_specialties":            ["unique_id", "specialty"],
    "facilities_websites":               ["unique_id", "website_url"],
    "nfhs_5_district_health_indicators": ["district_name"],
    # india_post_pincode_directory already has 162,994 rows — skip
}

def spark_to_pg_type(f):
    if isinstance(f.dataType, (DoubleType, FloatType)): return "DOUBLE PRECISION"
    if isinstance(f.dataType, (LongType, IntegerType)): return "BIGINT"
    if isinstance(f.dataType, BooleanType): return "BOOLEAN"
    return "TEXT"

def get_conn():
    w = WorkspaceClient()
    cred = w.database.generate_database_credential(
        request_id=str(uuid.uuid4()), instance_names=["hackathon-healthcare"])
    return psycopg2.connect(
        host="ep-noisy-wave-d2hhvbvx.database.us-east-1.cloud.databricks.com",
        database="healthcare", user="krish.kilaru@lumenalta.com",
        port=5432, password=cred.token, sslmode="require",
    )

for tbl, pks in tables_pks.items():
    t0 = time.time()
    conn = get_conn()   # fresh token per table
    conn.autocommit = True
    cur = conn.cursor()

    # Skip if already populated
    try:
        cur.execute(f'SELECT COUNT(*) FROM {PG_SCHEMA}."{tbl}";')
        cnt = cur.fetchone()[0]
        if cnt > 0 and tbl not in force_tables:
            print(f"  {tbl:<45} already {cnt:,} rows — skipping")
            cur.close(); conn.close()
            continue
    except Exception:
        pass

    # Read from Delta
    df_spark = spark.table(f"{SOURCE}.{tbl}")
    spark_schema = df_spark.schema
    df = df_spark.toPandas()
    # Strip NUL bytes (\x00) first — must be before NaN→None so str accessor sees NaN not None
    for col in df.select_dtypes(include='object').columns:
        df[col] = df[col].str.replace('\x00', '', regex=False)
    df = df.where(pd.notna(df), None)   # NaN → None (SQL NULL) — done after strip

    # Drop and recreate as plain (unpartitioned) table
    # The Synced Tables pipeline left a partitioned shell — INSERTs fail on it
    col_defs = ", ".join([f'"{f.name}" {spark_to_pg_type(f)}' for f in spark_schema.fields])
    cur.execute(f'DROP TABLE IF EXISTS {PG_SCHEMA}."{tbl}" CASCADE;')
    cur.execute(f'CREATE TABLE {PG_SCHEMA}."{tbl}" ({col_defs});')

    # Bulk insert in chunks of 1 000
    quoted_cols = ", ".join([f'"{c}"' for c in df.columns])
    placeholders = ", ".join(["%s"] * len(df.columns))
    sql = f'INSERT INTO {PG_SCHEMA}."{tbl}" ({quoted_cols}) VALUES ({placeholders})'
    rows = [tuple(r) for r in df.itertuples(index=False, name=None)]
    psycopg2.extras.execute_batch(cur, sql, rows, page_size=1000)

    elapsed = time.time() - t0
    print(f"  ✓ {tbl:<45} {len(rows):>8,} rows  ({elapsed:.1f}s)")
    cur.close()
    conn.close()

print("\n✓ Hard push complete. Re-run Cell 19 to rebuild facilities_full view.")

# COMMAND ----------

# DBTITLE 1,Source vs Destination row count comparison
import psycopg2, uuid
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()), instance_names=["hackathon-healthcare"])
conn = psycopg2.connect(
    host="ep-noisy-wave-d2hhvbvx.database.us-east-1.cloud.databricks.com",
    database="healthcare", user="krish.kilaru@lumenalta.com",
    port=5432, password=cred.token, sslmode="require",
)
cur = conn.cursor()

tables = [
    ("facilities",                        "lakebase_pg_sync"),
    ("facilities_base",                   "lakebase_pg_sync"),
    ("facilities_capabilities",           "lakebase_pg_sync"),
    ("facilities_equipment",              "lakebase_pg_sync"),
    ("facilities_phones",                 "lakebase_pg_sync"),
    ("facilities_procedures",             "lakebase_pg_sync"),
    ("facilities_specialties",            "lakebase_pg_sync"),
    ("facilities_websites",               "lakebase_pg_sync"),
    ("india_post_pincode_directory",      "lakebase_pg_sync"),
    ("nfhs_5_district_health_indicators", "lakebase_pg_sync"),
]

print(f"{'Table':<45} {'Source':>10} {'Dest':>10} {'Match':>7}")
print("-" * 75)
mismatch = []
for tbl, pg_schema in tables:
    # Source count (Spark)
    src = spark.sql(f"SELECT COUNT(*) FROM dais2026.lakebase_sync_clean.{tbl}").collect()[0][0]
    # Dest count (Postgres)
    try:
        cur.execute(f'SELECT COUNT(*) FROM {pg_schema}."{tbl}";')
        dst = cur.fetchone()[0]
    except Exception as e:
        dst = f"ERR: {e}"
    ok = "✓" if src == dst else "✗ MISMATCH"
    print(f"  {tbl:<43} {src:>10,} {str(dst):>10}   {ok}")
    if src != dst:
        mismatch.append(tbl)

cur.close()
conn.close()

if mismatch:
    print(f"\n{len(mismatch)} table(s) need re-push: {mismatch}")
else:
    print("\nAll tables match — ready to rebuild facilities_full view (Cell 19).")

# COMMAND ----------


