# Databricks notebook source
# DBTITLE 1,Configuration - Catalog & Schema
# Configuration - Update these values for your environment
CATALOG = "workspace"  # Change to your catalog name
SCHEMA = "default"  # Change to your schema name

# Source table (Bronze)
SOURCE_TABLE = "databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.nfhs_5_district_health_indicators"

# Target tables
SILVER_TABLE = f"{CATALOG}.{SCHEMA}.silver_nfhs_5_district_health_indicators"
GOLD_STATE_SUMMARY = f"{CATALOG}.{SCHEMA}.gold_nfhs_5_state_health_summary"
GOLD_DISTRICT_RANKINGS = f"{CATALOG}.{SCHEMA}.gold_nfhs_5_district_health_rankings"
GOLD_MATERNAL_CHILD = f"{CATALOG}.{SCHEMA}.gold_nfhs_5_maternal_child_health"

print("✅ Configuration loaded")
print(f"Source: {SOURCE_TABLE}")
print(f"Silver: {SILVER_TABLE}")
print(f"Gold Tables:")
print(f"  - {GOLD_STATE_SUMMARY}")
print(f"  - {GOLD_DISTRICT_RANKINGS}")
print(f"  - {GOLD_MATERNAL_CHILD}")

# COMMAND ----------

# DBTITLE 1,Introduction & Overview
# MAGIC %md
# MAGIC # NFHS-5 District Health Indicators - Medallion Architecture Pipeline
# MAGIC
# MAGIC ## 📊 Dataset Overview
# MAGIC
# MAGIC This notebook implements a **Medallion Architecture** (Bronze → Silver → Gold) for the NFHS-5 (National Family Health Survey) District Health Indicators dataset, transforming raw survey data into analytics-ready health metrics tables.
# MAGIC
# MAGIC ### Dataset Details
# MAGIC * **Source:** `databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.nfhs_5_district_health_indicators`
# MAGIC * **Total Records:** 706 districts across India
# MAGIC * **Columns:** 109 health and demographic indicators
# MAGIC * **Coverage:** 36 states/UTs, 698 unique districts
# MAGIC * **Data Collection:** NFHS-5 survey (2019-2021)
# MAGIC
# MAGIC ### Key Indicators Included
# MAGIC * **Demographics:** Population, sex ratio, literacy, education
# MAGIC * **Infrastructure:** Electricity, water, sanitation, clean fuel
# MAGIC * **Maternal Health:** ANC visits, institutional births, postnatal care
# MAGIC * **Child Health:** Immunization, nutrition, stunting, wasting
# MAGIC * **Family Planning:** Contraceptive use, unmet need
# MAGIC * **Health Coverage:** Insurance, healthcare access
# MAGIC
# MAGIC ### Pipeline Architecture
# MAGIC
# MAGIC **Bronze (Source):**  
# MAGIC Raw NFHS-5 data with mixed data types, special characters, and quality indicators
# MAGIC
# MAGIC **Silver (Cleaned):**  
# MAGIC * Converted 48 STRING percentage columns to DOUBLE
# MAGIC * Handled special characters (*, parentheses)
# MAGIC * Added data quality tracking columns
# MAGIC * Normalized missing values
# MAGIC
# MAGIC **Gold (Aggregated):**  
# MAGIC 1. **State Health Summary** - State-level aggregated metrics
# MAGIC 2. **District Health Rankings** - Top/bottom performing districts by indicator
# MAGIC 3. **Maternal & Child Health** - Focused metrics for M&C health programs

# COMMAND ----------

# DBTITLE 1,SECTION 2: Data Analysis & Exploration
# Comprehensive Data Analysis of NFHS-5 District Health Indicators
import pyspark.sql.functions as F
from pyspark.sql.window import Window

print("=" * 80)
print("LOADING DATA")
print("=" * 80)

# Read the bronze table
df = spark.table(SOURCE_TABLE)

print(f"✅ Loaded {df.count():,} records from {SOURCE_TABLE}")
print(f"✅ Columns: {len(df.columns)}")

# Schema
print("\n" + "=" * 80)
print("SCHEMA")
print("=" * 80)
df.printSchema()

# Sample data
print("\n" + "=" * 80)
print("SAMPLE DATA (First 5 rows)")
print("=" * 80)
display(df.limit(5))

# COMMAND ----------

# DBTITLE 1,Data Quality Analysis - Data Types & Special Characters
# Data Quality Analysis

print("=" * 80)
print("DATA TYPE ISSUES")
print("=" * 80)

# Identify STRING columns that should be numeric
string_cols_to_clean = []
for field in df.schema.fields:
    if field.dataType.simpleString() == 'string':
        col_name = field.name
        if col_name not in ['district_name', 'state_ut']:
            if col_name.endswith('_pct') or 'ratio' in col_name.lower():
                string_cols_to_clean.append(col_name)

print(f"\n⚠️ Found {len(string_cols_to_clean)} STRING columns that should be numeric:")
for i, col in enumerate(string_cols_to_clean[:10], 1):
    print(f"  {i}. {col}")
if len(string_cols_to_clean) > 10:
    print(f"  ... and {len(string_cols_to_clean) - 10} more")

print("\n" + "=" * 80)
print("SPECIAL CHARACTERS CHECK")
print("=" * 80)

# Check for special characters in one sample column
sample_col = 'sex_ratio_at_birth_5y_f_per_1000_m'
special_chars = df.select(
    F.count('*').alias('total'),
    F.sum(F.when(F.col(sample_col).like('%*%'), 1).otherwise(0)).alias('has_asterisk'),
    F.sum(F.when(F.col(sample_col).like('%(%'), 1).otherwise(0)).alias('has_parentheses')
).collect()[0]

print(f"\nColumn: {sample_col}")
print(f"  Total values: {special_chars['total']:,}")
print(f"  With '*' (suppressed): {special_chars['has_asterisk']:,}")
print(f"  With '()' (low reliability): {special_chars['has_parentheses']:,}")

# COMMAND ----------

# DBTITLE 1,Geographic Coverage Analysis
# Geographic Coverage

print("=" * 80)
print("GEOGRAPHIC COVERAGE")
print("=" * 80)

print("\nDistricts by State/UT:")
state_dist = df.groupBy('state_ut').agg(
    F.count('*').alias('district_count')
).orderBy(F.desc('district_count'))
display(state_dist)

print("\nSample sizes by state:")
sample_sizes = df.groupBy('state_ut').agg(
    F.avg('households_surveyed').alias('avg_households'),
    F.avg('women_15_49_interviewed').alias('avg_women'),
    F.avg('men_15_54_interviewed').alias('avg_men')
).orderBy('state_ut')
display(sample_sizes.limit(10))

# COMMAND ----------

# DBTITLE 1,SECTION 3: Silver Tier - Data Cleaning
# MAGIC %md
# MAGIC # SECTION 3: Silver Tier - Data Cleaning & Normalization
# MAGIC
# MAGIC ## 🧼 Transformation Goals
# MAGIC
# MAGIC The Silver tier applies the following transformations to create a clean, analytics-ready dataset:
# MAGIC
# MAGIC ### Data Type Corrections
# MAGIC * Convert 48 STRING percentage/ratio columns to DOUBLE
# MAGIC * Handle special characters:
# MAGIC   - `*` = missing/suppressed data → NULL
# MAGIC   - `(value)` = low reliability estimate → extract numeric value
# MAGIC   - Trailing spaces → trim
# MAGIC
# MAGIC ### Data Quality Tracking
# MAGIC * `low_reliability_indicators` - array of column names with parenthesized values
# MAGIC * `suppressed_indicators` - array of column names with asterisk markers
# MAGIC
# MAGIC ### Benefits
# MAGIC * All percentage columns now support mathematical operations
# MAGIC * Missing data properly represented as NULL
# MAGIC * Quality flags enable filtering unreliable estimates

# COMMAND ----------

# DBTITLE 1,Create Silver Table with Cleaning Logic
# SILVER TIER: Clean and Normalized NFHS-5 Health Indicators
import re

# Define cleaning function
def clean_numeric_value(value):
    """
    Clean numeric values by handling special characters.
    Returns: (cleaned_value, is_parenthesized, is_asterisk)
    """
    if value is None:
        return (None, False, False)
    
    value_str = str(value).strip()
    
    if value_str == '*' or value_str == '':
        return (None, False, True)
    
    is_parenthesized = False
    if value_str.startswith('(') and value_str.endswith(')'):
        is_parenthesized = True
        value_str = value_str[1:-1].strip()
    
    try:
        numeric_str = re.sub(r'[^0-9.\-]', '', value_str)
        if numeric_str:
            return (float(numeric_str), is_parenthesized, False)
        else:
            return (None, False, False)
    except:
        return (None, False, False)

# Register UDF
from pyspark.sql.types import StructType, StructField, DoubleType, BooleanType

clean_schema = StructType([
    StructField("value", DoubleType(), True),
    StructField("is_parenthesized", BooleanType(), False),
    StructField("is_asterisk", BooleanType(), False)
])

clean_udf = F.udf(clean_numeric_value, clean_schema)

print("✅ Cleaning function registered")

# COMMAND ----------

# DBTITLE 1,Apply Transformations and Create Silver Table
# Apply cleaning transformations
df_cleaned = df

# Strip spaces from identifier columns
df_cleaned = df_cleaned.withColumn('district_name', F.trim(F.col('district_name')))
df_cleaned = df_cleaned.withColumn('state_ut', F.trim(F.col('state_ut')))

# Track quality issues
low_reliability_cols = []
suppressed_cols = []

# Clean each STRING column that should be numeric
for col_name in string_cols_to_clean:
    cleaned_struct = clean_udf(F.col(col_name))
    
    df_cleaned = df_cleaned.withColumn(
        col_name, 
        cleaned_struct.getField("value")
    )
    
    low_reliability_cols.append(
        F.when(cleaned_struct.getField("is_parenthesized"), F.lit(col_name))
    )
    
    suppressed_cols.append(
        F.when(cleaned_struct.getField("is_asterisk"), F.lit(col_name))
    )

# Add quality tracking columns
df_cleaned = df_cleaned.withColumn(
    "low_reliability_indicators",
    F.array_compact(F.array(*low_reliability_cols))
)

df_cleaned = df_cleaned.withColumn(
    "suppressed_indicators",
    F.array_compact(F.array(*suppressed_cols))
)

# Write to Silver table
df_cleaned.write \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable(SILVER_TABLE)

print(f"✅ Silver table created: {SILVER_TABLE}")
print(f"   Rows: {df_cleaned.count():,}")
print(f"   Columns: {len(df_cleaned.columns)}")

# COMMAND ----------

# DBTITLE 1,Verify Silver Table Quality
# Verify Silver Table Quality
df_silver = spark.table(SILVER_TABLE)

print("=" * 80)
print("SILVER TABLE VERIFICATION")
print("=" * 80)

total_rows = df_silver.count()
rows_with_low_reliability = df_silver.filter(
    F.size(F.col("low_reliability_indicators")) > 0
).count()

rows_with_suppressed = df_silver.filter(
    F.size(F.col("suppressed_indicators")) > 0
).count()

print(f"\nTotal districts: {total_rows:,}")
print(f"Districts with low reliability indicators: {rows_with_low_reliability:,} ({rows_with_low_reliability/total_rows*100:.1f}%)")
print(f"Districts with suppressed indicators: {rows_with_suppressed:,} ({rows_with_suppressed/total_rows*100:.1f}%)")

print("\n=== Sample Cleaned Data ===")
display(df_silver.select(
    'district_name', 'state_ut',
    'sex_ratio_at_birth_5y_f_per_1000_m',
    'institutional_birth_5y_pct',
    'child_12_23m_who_have_received_the_first_dose_of_mcv_mcv_pct'
).limit(5))

# COMMAND ----------

# DBTITLE 1,SECTION 4: Gold Tier - Business Aggregations
# MAGIC %md
# MAGIC # SECTION 4: Gold Tier - Business Aggregations
# MAGIC
# MAGIC ## 🎯 Gold Layer Purpose
# MAGIC
# MAGIC The Gold tier creates business-ready aggregated tables optimized for specific analytics use cases:
# MAGIC
# MAGIC ### 1. **gold_nfhs_5_state_health_summary**
# MAGIC State-level health metrics aggregated across districts:
# MAGIC * Demographics (avg sex ratio, literacy)
# MAGIC * Infrastructure access (electricity, water, sanitation)
# MAGIC * Maternal health (institutional births, ANC)
# MAGIC * Child health (immunization, nutrition)
# MAGIC * Family planning indicators
# MAGIC
# MAGIC ### 2. **gold_nfhs_5_district_health_rankings**
# MAGIC Top and bottom performing districts for key health indicators:
# MAGIC * Institutional births
# MAGIC * Child immunization
# MAGIC * Clean fuel usage
# MAGIC * Health insurance coverage
# MAGIC
# MAGIC ### 3. **gold_nfhs_5_maternal_child_health**
# MAGIC Focused maternal and child health metrics for program monitoring

# COMMAND ----------

# DBTITLE 1,Gold Table 1: State Health Summary
# GOLD TABLE 1: State Health Summary
# State-level aggregations for policy makers

spark.sql(f"""
DROP TABLE IF EXISTS {GOLD_STATE_SUMMARY}
""")

spark.sql(f"""
CREATE TABLE {GOLD_STATE_SUMMARY}
USING DELTA
AS
SELECT 
  state_ut,
  COUNT(*) as district_count,
  
  -- Demographics
  ROUND(AVG(sex_ratio_total_f_per_1000_m), 1) as avg_sex_ratio,
  ROUND(AVG(women_age_15_49_who_are_literate_pct), 1) as avg_female_literacy_pct,
  ROUND(AVG(population_below_age_15_years_pct), 1) as avg_child_population_pct,
  
  -- Infrastructure
  ROUND(AVG(hh_electricity_pct), 1) as avg_electricity_access_pct,
  ROUND(AVG(hh_improved_water_pct), 1) as avg_improved_water_pct,
  ROUND(AVG(hh_use_improved_sanitation_pct), 1) as avg_improved_sanitation_pct,
  ROUND(AVG(households_using_clean_fuel_for_cooking_pct), 1) as avg_clean_fuel_pct,
  
  -- Health Coverage
  ROUND(AVG(hh_member_covered_health_insurance_pct), 1) as avg_health_insurance_pct,
  
  -- Maternal Health
  ROUND(AVG(institutional_birth_5y_pct), 1) as avg_institutional_birth_pct,
  ROUND(AVG(mothers_who_had_at_least_4_anc_visits_lb5y_pct), 1) as avg_anc_4plus_visits_pct,
  
  -- Child Health
  ROUND(AVG(child_12_23m_who_have_received_the_first_dose_of_mcv_mcv_pct), 1) as avg_mcv_immunization_pct,
  ROUND(AVG(child_u5_who_are_stunted_height_for_age_18_pct), 1) as avg_child_stunting_pct,
  
  -- Family Planning
  ROUND(AVG(fp_cm_w15_49_modern_method_pct), 1) as avg_modern_contraceptive_pct
  
FROM {SILVER_TABLE}
GROUP BY state_ut
ORDER BY state_ut
""")

print(f"✅ Created: {GOLD_STATE_SUMMARY}")
display(spark.table(GOLD_STATE_SUMMARY).limit(10))

# COMMAND ----------

# DBTITLE 1,Gold Table 2: District Health Rankings
# GOLD TABLE 2: District Health Rankings
# Top and bottom performing districts by key indicators

spark.sql(f"""
DROP TABLE IF EXISTS {GOLD_DISTRICT_RANKINGS}
""")

spark.sql(f"""
CREATE TABLE {GOLD_DISTRICT_RANKINGS}
USING DELTA
AS
WITH ranked_districts AS (
  SELECT 
    district_name,
    state_ut,
    institutional_birth_5y_pct,
    RANK() OVER (ORDER BY institutional_birth_5y_pct DESC) as institutional_birth_rank,
    
    child_12_23m_who_have_received_the_first_dose_of_mcv_mcv_pct,
    RANK() OVER (ORDER BY child_12_23m_who_have_received_the_first_dose_of_mcv_mcv_pct DESC) as mcv_rank,
    
    households_using_clean_fuel_for_cooking_pct,
    RANK() OVER (ORDER BY households_using_clean_fuel_for_cooking_pct DESC) as clean_fuel_rank,
    
    hh_member_covered_health_insurance_pct,
    RANK() OVER (ORDER BY hh_member_covered_health_insurance_pct DESC) as insurance_rank
    
  FROM {SILVER_TABLE}
  WHERE institutional_birth_5y_pct IS NOT NULL
)
SELECT * FROM ranked_districts
WHERE institutional_birth_rank <= 20 
   OR institutional_birth_rank > (SELECT COUNT(*) - 20 FROM ranked_districts)
ORDER BY institutional_birth_rank
""")

print(f"✅ Created: {GOLD_DISTRICT_RANKINGS}")
display(spark.table(GOLD_DISTRICT_RANKINGS).limit(10))

# COMMAND ----------

# DBTITLE 1,Gold Table 3: Maternal & Child Health Focus
# GOLD TABLE 3: Maternal & Child Health Focused Metrics
# Specialized table for M&C health programs

spark.sql(f"""
DROP TABLE IF EXISTS {GOLD_MATERNAL_CHILD}
""")

spark.sql(f"""
CREATE TABLE {GOLD_MATERNAL_CHILD}
USING DELTA
AS
SELECT 
  district_name,
  state_ut,
  
  -- Maternal Health Indicators
  institutional_birth_5y_pct,
  institutional_birth_in_public_facility_5y_pct,
  mothers_who_had_an_anc_visit_in_the_first_trimester_lb5y_pct,
  mothers_who_had_at_least_4_anc_visits_lb5y_pct,
  mothers_who_consumed_ifa_for_100_days_or_more_when_they_wer_pct as ifa_100_days_pct,
  mothers_who_received_pnc_from_a_doctor_nurse_lhv_anm_midwif_pct as postnatal_care_pct,
  
  -- Child Health Indicators
  child_12_23m_who_have_received_the_first_dose_of_mcv_mcv_pct as mcv_first_dose_pct,
  child_12_23m_fully_immunized_based_on_information_from_eith_pct as fully_immunized_pct,
  child_u5_who_are_stunted_height_for_age_18_pct as stunting_pct,
  child_u5_who_are_wasted_weight_for_height_18_pct as wasting_pct,
  child_u5_who_are_underweight_weight_for_age_pct as underweight_pct,
  
  -- Birth Registration & Demographics
  child_u5_whose_birth_was_civil_reg_pct as birth_registration_pct,
  sex_ratio_at_birth_5y_f_per_1000_m as sex_ratio_at_birth,
  
  -- Family Planning
  fp_cm_w15_49_modern_method_pct as modern_contraceptive_pct,
  fp_unmet_total_cm_w15_49_7_pct as unmet_fp_need_pct,
  
  -- Quality Flags
  low_reliability_indicators,
  suppressed_indicators
  
FROM {SILVER_TABLE}
ORDER BY state_ut, district_name
""")

print(f"✅ Created: {GOLD_MATERNAL_CHILD}")
display(spark.table(GOLD_MATERNAL_CHILD).limit(10))

# COMMAND ----------

# DBTITLE 1,Pipeline Summary & Validation
# Pipeline Summary
print("=" * 80)
print("MEDALLION PIPELINE SUMMARY")
print("=" * 80)

# Bronze
df_bronze = spark.table(SOURCE_TABLE)
print(f"\n🪨 BRONZE (Source):")
print(f"   Table: {SOURCE_TABLE}")
print(f"   Rows: {df_bronze.count():,}")
print(f"   Columns: {len(df_bronze.columns)}")

# Silver
df_silver = spark.table(SILVER_TABLE)
print(f"\n🥈 SILVER (Cleaned):")
print(f"   Table: {SILVER_TABLE}")
print(f"   Rows: {df_silver.count():,}")
print(f"   Columns: {len(df_silver.columns)}")

# Gold
print(f"\n🥇 GOLD (Aggregated):")

df_state = spark.table(GOLD_STATE_SUMMARY)
print(f"   1. {GOLD_STATE_SUMMARY}")
print(f"      Rows: {df_state.count():,} (states)")

df_rankings = spark.table(GOLD_DISTRICT_RANKINGS)
print(f"   2. {GOLD_DISTRICT_RANKINGS}")
print(f"      Rows: {df_rankings.count():,} (top/bottom districts)")

df_mc = spark.table(GOLD_MATERNAL_CHILD)
print(f"   3. {GOLD_MATERNAL_CHILD}")
print(f"      Rows: {df_mc.count():,} (districts with M&C metrics)")

print("\n" + "=" * 80)
print("✅ PIPELINE COMPLETED SUCCESSFULLY!")
print("=" * 80)

