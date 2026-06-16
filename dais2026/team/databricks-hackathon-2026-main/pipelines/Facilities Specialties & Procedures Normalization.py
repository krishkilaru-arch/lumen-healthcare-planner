# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# DBTITLE 1,Source Table Stats
# MAGIC %sql
# MAGIC -- Source table statistics from facilities
# MAGIC SELECT 
# MAGIC   COUNT(*) AS total_facilities,
# MAGIC   COUNT(specialties) AS facilities_with_specialties,
# MAGIC   ROUND(COUNT(specialties) * 100.0 / COUNT(*), 2) AS pct_with_specialties,
# MAGIC   COUNT(procedure) AS facilities_with_procedures,
# MAGIC   ROUND(COUNT(procedure) * 100.0 / COUNT(*), 2) AS pct_with_procedures
# MAGIC FROM databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities

# COMMAND ----------

# DBTITLE 1,Create Schema
# MAGIC %sql
# MAGIC -- Create schema for credential lookup tables
# MAGIC CREATE SCHEMA IF NOT EXISTS workspace.credential_lookup
# MAGIC COMMENT 'Normalized facility specialties and procedures lookup tables'

# COMMAND ----------

# DBTITLE 1,Table 1: Facility Specialties
# MAGIC %sql
# MAGIC -- Parse and normalize facility specialties from JSON array
# MAGIC -- Converts camelCase to readable format using zero-width lookahead
# MAGIC CREATE OR REPLACE TABLE workspace.credential_lookup.facility_specialties AS
# MAGIC SELECT DISTINCT
# MAGIC   f.unique_id,
# MAGIC   f.name AS facility_name,
# MAGIC   f.address_city,
# MAGIC   f.address_stateOrRegion AS state_region,
# MAGIC   f.address_country,
# MAGIC   specialty_raw,
# MAGIC   initcap(trim(regexp_replace(specialty_raw, '(?=[A-Z])', ' '))) AS specialty_name
# MAGIC FROM databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities f
# MAGIC LATERAL VIEW explode(from_json(specialties, 'ARRAY<STRING>')) AS specialty_raw
# MAGIC WHERE specialty_raw IS NOT NULL AND trim(specialty_raw) != ''

# COMMAND ----------

# DBTITLE 1,Data Quality Check: Facility Specialties
# MAGIC %sql
# MAGIC -- Data quality checks for facility_specialties
# MAGIC SELECT 
# MAGIC   'facility_specialties' AS table_name,
# MAGIC   COUNT(*) AS total_rows,
# MAGIC   COUNT(DISTINCT unique_id) AS distinct_facilities,
# MAGIC   COUNT(DISTINCT specialty_raw) AS distinct_specialties_raw,
# MAGIC   COUNT(DISTINCT specialty_name) AS distinct_specialties_normalized,
# MAGIC   SUM(CASE WHEN specialty_raw IS NULL THEN 1 ELSE 0 END) AS null_specialty_raw,
# MAGIC   SUM(CASE WHEN specialty_name IS NULL THEN 1 ELSE 0 END) AS null_specialty_name,
# MAGIC   SUM(CASE WHEN length(specialty_raw) < 5 THEN 1 ELSE 0 END) AS short_values_raw,
# MAGIC   SUM(CASE WHEN length(specialty_name) < 5 THEN 1 ELSE 0 END) AS short_values_normalized
# MAGIC FROM workspace.credential_lookup.facility_specialties

# COMMAND ----------

# DBTITLE 1,Table 2: Facility Procedures
# MAGIC %sql
# MAGIC -- Parse and normalize facility procedures from JSON array
# MAGIC CREATE OR REPLACE TABLE workspace.credential_lookup.facility_procedures AS
# MAGIC SELECT 
# MAGIC   f.unique_id,
# MAGIC   f.name AS facility_name,
# MAGIC   f.address_city,
# MAGIC   f.address_stateOrRegion AS state_region,
# MAGIC   f.address_country,
# MAGIC   procedure_text
# MAGIC FROM databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities f
# MAGIC LATERAL VIEW explode(from_json(procedure, 'ARRAY<STRING>')) AS procedure_text
# MAGIC WHERE procedure_text IS NOT NULL 
# MAGIC   AND trim(procedure_text) != ''
# MAGIC   AND length(trim(procedure_text)) > 0

# COMMAND ----------

# DBTITLE 1,Data Quality Check: Facility Procedures
# MAGIC %sql
# MAGIC -- Data quality checks for facility_procedures
# MAGIC SELECT 
# MAGIC   'facility_procedures' AS table_name,
# MAGIC   COUNT(*) AS total_rows,
# MAGIC   COUNT(DISTINCT unique_id) AS distinct_facilities,
# MAGIC   COUNT(DISTINCT procedure_text) AS distinct_procedures,
# MAGIC   SUM(CASE WHEN procedure_text IS NULL THEN 1 ELSE 0 END) AS null_procedures,
# MAGIC   SUM(CASE WHEN length(procedure_text) < 5 THEN 1 ELSE 0 END) AS short_values,
# MAGIC   MIN(length(procedure_text)) AS min_length,
# MAGIC   MAX(length(procedure_text)) AS max_length,
# MAGIC   ROUND(AVG(length(procedure_text)), 2) AS avg_length
# MAGIC FROM workspace.credential_lookup.facility_procedures

# COMMAND ----------

# DBTITLE 1,Table 3: Facility Services Summary
# MAGIC %sql
# MAGIC -- Aggregate facility services summary with specialty and procedure counts
# MAGIC CREATE OR REPLACE TABLE workspace.credential_lookup.facility_services_summary AS
# MAGIC SELECT 
# MAGIC   f.unique_id,
# MAGIC   f.name AS facility_name,
# MAGIC   f.address_city,
# MAGIC   f.address_stateOrRegion AS state_region,
# MAGIC   f.address_country,
# MAGIC   f.organization_type,
# MAGIC   COALESCE(s.distinct_specialty_count, 0) AS distinct_specialty_count,
# MAGIC   COALESCE(s.top_specialties, array()) AS top_specialties,
# MAGIC   COALESCE(p.procedure_count, 0) AS procedure_count
# MAGIC FROM databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities f
# MAGIC LEFT JOIN (
# MAGIC   SELECT 
# MAGIC     unique_id,
# MAGIC     COUNT(DISTINCT specialty_name) AS distinct_specialty_count,
# MAGIC     collect_set(specialty_name) AS top_specialties
# MAGIC   FROM workspace.credential_lookup.facility_specialties
# MAGIC   GROUP BY unique_id
# MAGIC ) s ON f.unique_id = s.unique_id
# MAGIC LEFT JOIN (
# MAGIC   SELECT 
# MAGIC     unique_id,
# MAGIC     COUNT(*) AS procedure_count
# MAGIC   FROM workspace.credential_lookup.facility_procedures
# MAGIC   GROUP BY unique_id
# MAGIC ) p ON f.unique_id = p.unique_id

# COMMAND ----------

# DBTITLE 1,Data Quality Check: Facility Services Summary
# MAGIC %sql
# MAGIC -- Data quality checks for facility_services_summary
# MAGIC SELECT 
# MAGIC   'facility_services_summary' AS table_name,
# MAGIC   COUNT(*) AS total_rows,
# MAGIC   COUNT(DISTINCT unique_id) AS distinct_facilities,
# MAGIC   SUM(CASE WHEN distinct_specialty_count = 0 THEN 1 ELSE 0 END) AS facilities_no_specialties,
# MAGIC   SUM(CASE WHEN procedure_count = 0 THEN 1 ELSE 0 END) AS facilities_no_procedures,
# MAGIC   SUM(CASE WHEN distinct_specialty_count > 0 AND procedure_count > 0 THEN 1 ELSE 0 END) AS facilities_with_both,
# MAGIC   ROUND(AVG(distinct_specialty_count), 2) AS avg_specialty_count,
# MAGIC   ROUND(AVG(procedure_count), 2) AS avg_procedure_count,
# MAGIC   MAX(distinct_specialty_count) AS max_specialty_count,
# MAGIC   MAX(procedure_count) AS max_procedure_count
# MAGIC FROM workspace.credential_lookup.facility_services_summary

# COMMAND ----------

# DBTITLE 1,Specialty Distribution: Top 30
# MAGIC %sql
# MAGIC -- Top 30 specialties by facility count
# MAGIC SELECT 
# MAGIC   specialty_name,
# MAGIC   COUNT(DISTINCT unique_id) AS facility_count,
# MAGIC   COUNT(*) AS total_entries
# MAGIC FROM workspace.credential_lookup.facility_specialties
# MAGIC GROUP BY specialty_name
# MAGIC ORDER BY facility_count DESC, specialty_name
# MAGIC LIMIT 30

# COMMAND ----------

# DBTITLE 1,Example Queries
# MAGIC %sql
# MAGIC -- Example 1: Find all facilities offering Cardiology
# MAGIC SELECT 
# MAGIC   f.facility_name,
# MAGIC   f.address_city,
# MAGIC   f.state_region,
# MAGIC   f.address_country,
# MAGIC   f.specialty_name
# MAGIC FROM workspace.credential_lookup.facility_specialties f
# MAGIC WHERE LOWER(f.specialty_name) LIKE '%cardiology%'
# MAGIC ORDER BY f.facility_name, f.specialty_name
# MAGIC LIMIT 50;
# MAGIC
# MAGIC -- Example 2: Search procedures containing 'roboti'
# MAGIC SELECT 
# MAGIC   p.facility_name,
# MAGIC   p.address_city,
# MAGIC   p.state_region,
# MAGIC   p.procedure_text
# MAGIC FROM workspace.credential_lookup.facility_procedures p
# MAGIC WHERE LOWER(p.procedure_text) LIKE '%roboti%'
# MAGIC ORDER BY p.facility_name, p.procedure_text
# MAGIC LIMIT 50

