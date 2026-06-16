# Databricks notebook source
# DBTITLE 1,Hackathon Infrastructure Setup
# MAGIC %md
# MAGIC # Hackathon Infrastructure Setup
# MAGIC Creates Lakebase instance and syncs the healthcare facility dataset for sub-10ms reads.

# COMMAND ----------

# DBTITLE 1,Create Lakebase instance
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import DatabaseInstance

w = WorkspaceClient()

# Instance already created - verify it's available
inst = w.database.get_database_instance(name="hackathon-healthcare")
print(f"✓ Instance: {inst.name}")
print(f"  UID: {inst.uid}")
print(f"  State: {inst.state}")

# COMMAND ----------

# DBTITLE 1,Sync facilities table to Lakebase
# Verify tables in dais2026.healthcare
for t in ['facilities', 'india_post_pincode_directory', 'nfhs_5_district_health_indicators']:
    try:
        cnt = spark.table(f"dais2026.healthcare.{t}").count()
        print(f"✓ {t}: {cnt} rows")
    except Exception as e:
        print(f"✗ {t}: {e}")

# COMMAND ----------

# DBTITLE 1,Sync supplemental tables
from databricks.sdk.service.database import SyncedDatabaseTable, SyncedTableSpec, SyncedTableSchedulingPolicy

INSTANCE_NAME = "hackathon-healthcare"
# All 3 tables synced to Lakebase instance 'hackathon-healthcare'
# Synced tables live in dais2026.lakebase_sync schema
# Source data in dais2026.healthcare
SOURCE_CATALOG = "dais2026"
SOURCE_SCHEMA = "healthcare"
LOGICAL_DB = "healthcare"
DEST_CATALOG = "dais2026"
DEST_SCHEMA = "lakebase_sync"

tables_config = [
    ("facilities", ["unique_id"]),
    ("india_post_pincode_directory", ["pincode", "officename"]),
    ("nfhs_5_district_health_indicators", ["district_name"]),
]

# Create dedicated schema for synced Lakebase tables
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {DEST_CATALOG}.{DEST_SCHEMA}")

for table_name, pk_cols in tables_config:
    source_full = f"{SOURCE_CATALOG}.{SOURCE_SCHEMA}.{table_name}"
    dest_full = f"{DEST_CATALOG}.{DEST_SCHEMA}.{table_name}"
    print(f"Syncing {table_name} to Lakebase...")
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
                    scheduling_policy=SyncedTableSchedulingPolicy.SNAPSHOT
                )
            )
        )
        print(f"  ✓ Synced: {sync.name}")
    except Exception as e:
        print(f"  ✗ Error: {e}")

# COMMAND ----------

# DBTITLE 1,Verify sync status and generate credentials
# Verify Lakebase instance
inst = w.database.get_database_instance(name="hackathon-healthcare")
print(f"Lakebase Instance: {inst.name}")
print(f"  State: {inst.state}")
print(f"  Read/Write: {inst.read_write_dns}")
print(f"  Read-Only:  {inst.read_only_dns}")

# Generate credentials for app connection
try:
    cred = w.database.generate_database_credential(database_instance_name="hackathon-healthcare")
    print(f"\nCredentials:")
    print(f"  Username: {cred.username}")
    print(f"  Password: {cred.password[:10]}...")
except Exception as e:
    print(f"\nCredential generation: {e}")

# Verify data availability
print(f"\nData tables available:")
for t in ['facilities', 'india_post_pincode_directory', 'nfhs_5_district_health_indicators']:
    try:
        cnt = spark.table(f"dais2026.healthcare.{t}").count()
        print(f"  dais2026.healthcare.{t}: {cnt} rows")
    except:
        print(f"  dais2026.healthcare.{t}: not found")

print(f"\n{'='*50}")
print(f"INFRASTRUCTURE SUMMARY")
print(f"{'='*50}")
print(f"Lakebase instance: hackathon-healthcare")
print(f"Endpoint: {inst.read_write_dns}")
print(f"Source catalog: dais2026.healthcare")
print(f"Tables: facilities (10K), pincode (165K), nfhs5 (706)")

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.apps import (
    App, AppResource, AppResourceDatabase, AppResourceDatabaseDatabasePermission
)

w = WorkspaceClient()
w.apps.update(
    name="lumen-healthcare-planner",
    app=App(
        name="lumen-healthcare-planner",
        description="Lumen Healthcare Planner - DAIS 2026 Hackathon",
        resources=[
            AppResource(
                name="lakebase-healthcare",
                database=AppResourceDatabase(
                    instance_name="hackathon-healthcare",
                    database_name="databricks_postgres",
                    permission=AppResourceDatabaseDatabasePermission.CAN_CONNECT_AND_CREATE,
                ),
            )
        ],
    )
)

# COMMAND ----------


from databricks.sdk import WorkspaceClient
from databricks.sdk.service.apps import App, AppResource, AppResourceDatabase, AppResourceDatabaseDatabasePermission
w = WorkspaceClient()
w.apps.update(name="lumen-healthcare-planner", app=App(
    name="lumen-healthcare-planner",
    description="Lumen Healthcare Planner - DAIS 2026 Hackathon",
    resources=[AppResource(name="lakebase-healthcare", database=AppResourceDatabase(
        instance_name="hackathon-healthcare",
        database_name="healthcare",  # Changed from databricks_postgres
        permission=AppResourceDatabaseDatabasePermission.CAN_CONNECT_AND_CREATE,
    ))],
))

# COMMAND ----------


from databricks.sdk.service.apps import AppDeployment
w.apps.deploy(app_name="lumen-healthcare-planner", app_deployment=AppDeployment(
    source_code_path="/Workspace/Users/krish.kilaru@lumenalta.com/lumen-healthcare-planner"))

# COMMAND ----------

# DBTITLE 1,Grant schema access to app SP
# Grant the app's service principal access to the 'data' schema
import uuid
from databricks.sdk import WorkspaceClient
import psycopg2

w = WorkspaceClient()
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()),
    instance_names=["hackathon-healthcare"]
)
conn = psycopg2.connect(
    host="ep-noisy-wave-d2hhvbvx.database.us-east-1.cloud.databricks.com",
    database="healthcare", user="krish.kilaru@lumenalta.com",
    port=5432, password=cred.token, sslmode="require"
)
with conn.cursor() as cur:
    # Grant to PUBLIC (covers all roles including the app SP)
    cur.execute("GRANT USAGE ON SCHEMA data TO PUBLIC")
    cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA data TO PUBLIC")
    cur.execute("GRANT USAGE ON SCHEMA app_data TO PUBLIC")
    cur.execute("GRANT ALL ON ALL TABLES IN SCHEMA app_data TO PUBLIC")
    cur.execute("GRANT ALL ON ALL SEQUENCES IN SCHEMA app_data TO PUBLIC")
    cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA data GRANT SELECT ON TABLES TO PUBLIC")
    cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA app_data GRANT ALL ON TABLES TO PUBLIC")
conn.commit()
conn.close()
print("✓ Granted access to data & app_data schemas for app SP")

# COMMAND ----------


