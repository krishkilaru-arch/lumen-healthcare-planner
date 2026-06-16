# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# DBTITLE 1,Configuration - Catalog & Schema
# Configuration - Update these values for your environment
CATALOG = "workspace"  # Change to your catalog name
SCHEMA = "default"  # Change to your schema name

# Source table (Bronze)
SOURCE_TABLE = "databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.india_post_pincode_directory"

# Target tables
SILVER_TABLE = f"{CATALOG}.{SCHEMA}.india_post_silver_pincode_directory"
GOLD_PINCODE_SUMMARY = f"{CATALOG}.{SCHEMA}.gold_pincode_summary"
GOLD_STATE_DISTRICT = f"{CATALOG}.{SCHEMA}.gold_state_district_analysis"
GOLD_GEOGRAPHIC_HIERARCHY = f"{CATALOG}.{SCHEMA}.gold_geographic_hierarchy"
GOLD_DELIVERY_NETWORK = f"{CATALOG}.{SCHEMA}.gold_delivery_network"
GOLD_GEOSPATIAL = f"{CATALOG}.{SCHEMA}.gold_geospatial_valid_coords"

print(f"✅ Configuration set:")
print(f"   Source: {SOURCE_TABLE}")
print(f"   Silver: {SILVER_TABLE}")
print(f"   Gold tables in: {CATALOG}.{SCHEMA}")

# COMMAND ----------

# DBTITLE 1,Introduction & Overview
# MAGIC %md
# MAGIC # India Post Pincode Directory - Medallion Architecture Pipeline
# MAGIC
# MAGIC ## 📊 Dataset Overview
# MAGIC
# MAGIC This notebook implements a **Medallion Architecture** (Bronze → Silver → Gold) for the India Post Pincode Directory dataset, transforming raw postal data into analytics-ready tables.
# MAGIC
# MAGIC ### Dataset Details
# MAGIC * **Source:** `databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.india_post_pincode_directory`
# MAGIC * **Total Records:** 165,627 post office records
# MAGIC * **Columns:** 11 (circlename, regionname, divisionname, officename, pincode, officetype, delivery, district, statename, latitude, longitude)
# MAGIC * **Coverage:** 37 states, 750 districts, 19,586 unique pincodes
# MAGIC
# MAGIC ### Key Findings from Analysis
# MAGIC * ✅ **Excellent Data Quality:** No NULL values in any column
# MAGIC * ✅ **Minimal Duplicates:** Only 2 duplicate records identified
# MAGIC * 📍 **Office Distribution:**
# MAGIC   - Branch Offices (BO): 84.7%
# MAGIC   - Post Offices (PO): 14.8%
# MAGIC   - Head Offices (HO): 0.5%
# MAGIC * 📦 **Delivery Coverage:** 95.3% Delivery, 4.7% Non-Delivery
# MAGIC * ⚠️ **Data Issue:** Latitude/Longitude stored as STRING with "NA" values (needs cleaning)
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## 🏗️ Architecture
# MAGIC
# MAGIC ### **Bronze Tier** (Raw Data)
# MAGIC Source table containing unmodified data from India Post
# MAGIC
# MAGIC ### **Silver Tier** (Cleaned & Normalized)
# MAGIC * Convert lat/long to DOUBLE (handle "NA" as NULL)
# MAGIC * Add surrogate keys and quality flags
# MAGIC * Standardize text formatting
# MAGIC * Remove duplicates
# MAGIC * Add derived fields (pincode_prefix, offices_per_pincode)
# MAGIC * Partition by state for query optimization
# MAGIC
# MAGIC ### **Gold Tier** (Business Aggregations)
# MAGIC 5 specialized tables for different analytics use cases:
# MAGIC 1. **gold_pincode_summary** - Pincode-level metrics
# MAGIC 2. **gold_state_district_analysis** - Geographic infrastructure analysis
# MAGIC 3. **gold_geographic_hierarchy** - Hierarchical rollups (circle/region/division)
# MAGIC 4. **gold_delivery_network** - Delivery capability metrics
# MAGIC 5. **gold_geospatial_valid_coords** - Mapping-ready dataset
# MAGIC
# MAGIC ---

# COMMAND ----------

# DBTITLE 1,SECTION 2: Data Analysis & Exploration
# Comprehensive Data Analysis of India Post Pincode Directory
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

# DBTITLE 1,Data Quality Analysis - Missing Values & Duplicates
# Data Quality Analysis

print("=" * 80)
print("DATA QUALITY: MISSING VALUES")
print("=" * 80)

# Check for missing values
missing_data = df.select([
    F.count(F.when(F.col(c).isNull(), c)).alias(c) 
    for c in df.columns
])
display(missing_data)

print("\n" + "=" * 80)
print("UNIQUE VALUE COUNTS")
print("=" * 80)

for col in df.columns:
    unique_count = df.select(col).distinct().count()
    print(f"  {col:20s}: {unique_count:>10,}")

print("\n" + "=" * 80)
print("DUPLICATE RECORDS CHECK")
print("=" * 80)

duplicate_count = df.groupBy(df.columns).count().filter(F.col('count') > 1).count()
print(f"  Total duplicate records: {duplicate_count}")

if duplicate_count > 0:
    print("\n  Showing duplicate records:")
    duplicates = df.groupBy(df.columns).count().filter(F.col('count') > 1)
    display(duplicates)

# COMMAND ----------

# DBTITLE 1,Categorical Distributions
# Categorical Column Analysis

print("=" * 80)
print("CATEGORICAL DISTRIBUTIONS")
print("=" * 80)

categorical_cols = ['officetype', 'delivery', 'circlename', 'regionname']

for col in categorical_cols:
    print(f"\n{col.upper()} Distribution:")
    dist = df.groupBy(col).count().orderBy(F.desc('count'))
    
    if col in ['officetype', 'delivery']:
        # Show all for small categories
        display(dist)
    else:
        # Show top 10 for large categories
        display(dist.limit(10))

# COMMAND ----------

# DBTITLE 1,Geographic Coverage Analysis
# Geographic Coverage

print("=" * 80)
print("GEOGRAPHIC COVERAGE")
print("=" * 80)

print("\nTop 10 States by Office Count:")
state_dist = df.groupBy('statename').count().orderBy(F.desc('count')).limit(10)
display(state_dist)

print("\nTop 10 Districts by Office Count:")
district_dist = df.groupBy('district').count().orderBy(F.desc('count')).limit(10)
display(district_dist)

print("\nTop 10 Circles by Office Count:")
circle_dist = df.groupBy('circlename').count().orderBy(F.desc('count')).limit(10)
display(circle_dist)

# COMMAND ----------

# DBTITLE 1,Pincode Analysis
# Pincode Analysis

print("=" * 80)
print("PINCODE ANALYSIS")
print("=" * 80)

pincode_stats = df.select(
    F.count('pincode').alias('total_pincodes'),
    F.countDistinct('pincode').alias('unique_pincodes'),
    F.min('pincode').alias('min_pincode'),
    F.max('pincode').alias('max_pincode')
).collect()[0]

print(f"  Total Pincodes: {pincode_stats['total_pincodes']:,}")
print(f"  Unique Pincodes: {pincode_stats['unique_pincodes']:,}")
print(f"  Min Pincode: {pincode_stats['min_pincode']}")
print(f"  Max Pincode: {pincode_stats['max_pincode']}")
print(f"  Avg Offices per Pincode: {pincode_stats['total_pincodes'] / pincode_stats['unique_pincodes']:.2f}")

print("\nPincodes with Most Offices (Top 10):")
pincode_office_count = df.groupBy('pincode').count().orderBy(F.desc('count')).limit(10)
display(pincode_office_count)

print("\nPincode Distribution Analysis:")
pincode_dist = df.groupBy('pincode').count() \
    .groupBy('count').agg(F.count('*').alias('num_pincodes')) \
    .orderBy('count')

print("  Distribution of offices per pincode:")
display(pincode_dist.limit(20))

# COMMAND ----------

# DBTITLE 1,Geolocation Quality Analysis
# Geolocation Analysis

print("=" * 80)
print("GEOLOCATION QUALITY ANALYSIS")
print("=" * 80)

print("\nSample Latitude/Longitude values:")
lat_long_sample = df.select('officename', 'pincode', 'latitude', 'longitude').limit(10)
display(lat_long_sample)

# Check for "NA" values (stored as string)
na_coords = df.filter(
    (F.col('latitude') == 'NA') | 
    (F.col('longitude') == 'NA')
).count()

empty_coords = df.filter(
    (F.col('latitude') == '') | 
    (F.col('longitude') == '')
).count()

valid_coords = df.filter(
    (F.col('latitude') != 'NA') & 
    (F.col('longitude') != 'NA') &
    (F.col('latitude') != '') &
    (F.col('longitude') != '')
).count()

total = df.count()

print(f"\n  Total Records: {total:,}")
print(f"  Valid Coordinates: {valid_coords:,} ({valid_coords/total*100:.1f}%)")
print(f"  'NA' Coordinates: {na_coords:,} ({na_coords/total*100:.1f}%)")
print(f"  Empty Coordinates: {empty_coords:,} ({empty_coords/total*100:.1f}%)")

print("\n  States with Best Coordinate Coverage:")
coord_coverage_by_state = df.withColumn(
    'has_coords',
    F.when((F.col('latitude') != 'NA') & (F.col('longitude') != 'NA'), 1).otherwise(0)
).groupBy('statename').agg(
    F.count('*').alias('total_offices'),
    F.sum('has_coords').alias('offices_with_coords')
).withColumn(
    'coverage_pct',
    (F.col('offices_with_coords') / F.col('total_offices') * 100)
).orderBy(F.desc('coverage_pct')).limit(10)

display(coord_coverage_by_state)

# COMMAND ----------

# DBTITLE 1,Analysis Summary
# MAGIC %md
# MAGIC ## 📋 Analysis Summary
# MAGIC
# MAGIC ### Key Insights
# MAGIC
# MAGIC **Data Quality:**
# MAGIC * ✅ Zero NULL values across all columns
# MAGIC * ✅ Only 2 duplicate records (99.999% unique)
# MAGIC * ⚠️ Coordinates stored as strings with "NA" for missing values
# MAGIC
# MAGIC **Coverage:**
# MAGIC * 19,586 unique pincodes serving 165,627 post offices
# MAGIC * Average of 8.5 offices per pincode
# MAGIC * Some pincodes serve 100+ offices (rural areas with multiple branch offices)
# MAGIC
# MAGIC **Office Infrastructure:**
# MAGIC * Branch Offices dominate (140,270 BOs vs 24,546 POs)
# MAGIC * Most offices provide delivery services (95.3%)
# MAGIC * Geographic distribution mirrors population density
# MAGIC
# MAGIC **Data Cleaning Needs:**
# MAGIC 1. Convert latitude/longitude from STRING to DOUBLE
# MAGIC 2. Handle "NA" values as NULL
# MAGIC 3. Remove 2 duplicate records
# MAGIC 4. Standardize text casing
# MAGIC 5. Add derived fields for analytics
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## 🔄 Next Steps: Silver Tier Transformation
# MAGIC
# MAGIC We'll now create the cleaned Silver tier table with:
# MAGIC * Proper data types
# MAGIC * Quality flags
# MAGIC * Derived dimensions
# MAGIC * Optimized partitioning

# COMMAND ----------

# DBTITLE 1,SECTION 3: Silver Tier - Data Cleaning & Normalization
# MAGIC %md
# MAGIC # SECTION 3: Silver Tier - Data Cleaning & Normalization
# MAGIC
# MAGIC ## 🧼 Transformation Goals
# MAGIC
# MAGIC The Silver tier applies the following transformations to create a clean, analytics-ready dataset:
# MAGIC
# MAGIC ### Data Type Corrections
# MAGIC * Convert `latitude` and `longitude` from STRING to DOUBLE
# MAGIC * Handle "NA" string values as NULL
# MAGIC
# MAGIC ### Data Standardization
# MAGIC * Trim whitespace from all string columns
# MAGIC * Standardize text to Title Case for readability
# MAGIC * Remove 2 duplicate records identified in analysis
# MAGIC
# MAGIC ### Data Enrichment
# MAGIC * Add `postal_office_id` (UUID surrogate key)
# MAGIC * Add `has_valid_coordinates` (boolean quality flag)
# MAGIC * Calculate `offices_per_pincode` (window function)
# MAGIC * Extract `pincode_prefix` (first 3 digits for regional grouping)
# MAGIC * Add `load_timestamp` for data lineage
# MAGIC
# MAGIC ### Optimization
# MAGIC * Partition by `statename` for query performance
# MAGIC * Delta format with optimized storage

# COMMAND ----------

# DBTITLE 1,Create Silver Table
# SILVER TIER: Clean and Normalized Pincode Directory
# Dropping if exists for rerunability

spark.sql(f"""
DROP TABLE IF EXISTS {SILVER_TABLE}
""")

spark.sql(f"""
CREATE TABLE {SILVER_TABLE}
USING DELTA
PARTITIONED BY (statename)
AS
WITH deduplicated AS (
  -- Remove duplicates using ROW_NUMBER
  SELECT 
    *,
    ROW_NUMBER() OVER (
      PARTITION BY circlename, regionname, divisionname, officename, 
                   pincode, officetype, delivery, district, statename, 
                   latitude, longitude 
      ORDER BY circlename
    ) as row_num
  FROM databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.india_post_pincode_directory
),
offices_per_pincode_calc AS (
  -- Calculate offices per pincode
  SELECT 
    pincode,
    COUNT(*) as offices_count
  FROM deduplicated
  WHERE row_num = 1
  GROUP BY pincode
)
SELECT 
  -- Surrogate Key
  uuid() as postal_office_id,
  
  -- Original columns with standardization
  TRIM(INITCAP(d.circlename)) as circlename,
  TRIM(INITCAP(d.regionname)) as regionname,
  TRIM(INITCAP(d.divisionname)) as divisionname,
  TRIM(INITCAP(d.officename)) as officename,
  d.pincode,
  UPPER(TRIM(d.officetype)) as officetype,
  INITCAP(TRIM(d.delivery)) as delivery,
  TRIM(INITCAP(d.district)) as district,
  UPPER(TRIM(d.statename)) as statename,
  
  -- Converted geographic coordinates (handle "NA" as NULL and malformed values)
  CASE 
    WHEN TRIM(d.latitude) = 'NA' OR TRIM(d.latitude) = '' THEN NULL 
    ELSE TRY_CAST(TRIM(d.latitude) AS DOUBLE) 
  END as latitude,
  CASE 
    WHEN TRIM(d.longitude) = 'NA' OR TRIM(d.longitude) = '' THEN NULL 
    ELSE TRY_CAST(TRIM(d.longitude) AS DOUBLE) 
  END as longitude,
  
  -- Quality flags
  CASE 
    WHEN TRIM(d.latitude) != 'NA' AND TRIM(d.latitude) != '' 
     AND TRIM(d.longitude) != 'NA' AND TRIM(d.longitude) != ''
    THEN TRUE 
    ELSE FALSE 
  END as has_valid_coordinates,
  
  -- Derived dimensions
  SUBSTRING(CAST(d.pincode AS STRING), 1, 3) as pincode_prefix,
  opp.offices_count as offices_per_pincode,
  
  -- Metadata
  current_timestamp() as load_timestamp
  
FROM deduplicated d
LEFT JOIN offices_per_pincode_calc opp ON d.pincode = opp.pincode
WHERE d.row_num = 1
""")

# Optimize the table
spark.sql(f"OPTIMIZE {SILVER_TABLE}")

# Show results
result = spark.sql(f"""
SELECT 
  COUNT(*) as total_records,
  COUNT(DISTINCT pincode) as unique_pincodes,
  SUM(CASE WHEN has_valid_coordinates THEN 1 ELSE 0 END) as records_with_coords,
  COUNT(DISTINCT statename) as unique_states
FROM {SILVER_TABLE}
""")

display(result)

# COMMAND ----------

# DBTITLE 1,Verify Silver Table
# Verify Silver Table Quality
quality_metrics = spark.sql(f"""
SELECT 
  'Total Records' as metric,
  COUNT(*) as value
FROM {SILVER_TABLE}

UNION ALL

SELECT 
  'Records with Valid Coordinates',
  SUM(CASE WHEN has_valid_coordinates THEN 1 ELSE 0 END)
FROM {SILVER_TABLE}

UNION ALL

SELECT 
  'Unique Pincodes',
  COUNT(DISTINCT pincode)
FROM {SILVER_TABLE}

UNION ALL

SELECT 
  'Unique States',
  COUNT(DISTINCT statename)
FROM {SILVER_TABLE}
""")

display(quality_metrics)

# Sample of cleaned data
print("\nSample of cleaned data:")
sample_data = spark.sql(f"""
SELECT *
FROM {SILVER_TABLE}
LIMIT 5
""")

display(sample_data)

# COMMAND ----------

# DBTITLE 1,SECTION 4: Gold Tier - Aggregation Tables
# MAGIC %md
# MAGIC # SECTION 4: Gold Tier - Business Aggregations
# MAGIC
# MAGIC ## 🎯 Gold Layer Purpose
# MAGIC
# MAGIC The Gold tier creates business-ready aggregated tables optimized for specific analytics use cases:
# MAGIC
# MAGIC ### 1. **gold_pincode_summary**
# MAGIC Pincode-level metrics for location-based analysis
# MAGIC
# MAGIC ### 2. **gold_state_district_analysis**
# MAGIC Geographic infrastructure analysis by state and district
# MAGIC
# MAGIC ### 3. **gold_geographic_hierarchy**
# MAGIC Hierarchical rollups across organizational structure
# MAGIC
# MAGIC ### 4. **gold_delivery_network**
# MAGIC Delivery capability and infrastructure metrics
# MAGIC
# MAGIC ### 5. **gold_geospatial_valid_coords**
# MAGIC Mapping-ready dataset with valid coordinates only

# COMMAND ----------

# DBTITLE 1,Gold Table 1: Pincode Summary
# GOLD TABLE 1: Pincode Summary
# Pincode-level aggregations for location-based analytics

spark.sql(f"""
DROP TABLE IF EXISTS {GOLD_PINCODE_SUMMARY}
""")

spark.sql(f"""
CREATE TABLE {GOLD_PINCODE_SUMMARY}
USING DELTA
AS
SELECT 
  pincode,
  pincode_prefix,
  
  -- Geographic Information (take first occurrence)
  FIRST(statename) as statename,
  FIRST(district) as district,
  FIRST(divisionname) as divisionname,
  FIRST(regionname) as regionname,
  FIRST(circlename) as circlename,
  
  -- Office Counts
  COUNT(*) as total_offices,
  SUM(CASE WHEN officetype = 'HO' THEN 1 ELSE 0 END) as head_offices,
  SUM(CASE WHEN officetype = 'PO' THEN 1 ELSE 0 END) as post_offices,
  SUM(CASE WHEN officetype = 'BO' THEN 1 ELSE 0 END) as branch_offices,
  
  -- Delivery Metrics
  SUM(CASE WHEN delivery = 'Delivery' THEN 1 ELSE 0 END) as delivery_offices,
  SUM(CASE WHEN delivery = 'Non Delivery' THEN 1 ELSE 0 END) as non_delivery_offices,
  ROUND(SUM(CASE WHEN delivery = 'Delivery' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as delivery_coverage_pct,
  
  -- Coordinate Quality
  SUM(CASE WHEN has_valid_coordinates THEN 1 ELSE 0 END) as offices_with_coords,
  ROUND(SUM(CASE WHEN has_valid_coordinates THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as coord_coverage_pct,
  
  -- Geographic Centroid (average of valid coordinates)
  AVG(CASE WHEN has_valid_coordinates THEN latitude END) as centroid_latitude,
  AVG(CASE WHEN has_valid_coordinates THEN longitude END) as centroid_longitude,
  
  -- Urban/Rural Classification (HO/PO suggests urban)
  CASE 
    WHEN SUM(CASE WHEN officetype IN ('HO', 'PO') THEN 1 ELSE 0 END) > 0 THEN 'Urban'
    ELSE 'Rural'
  END as classification,
  
  current_timestamp() as load_timestamp
  
FROM {SILVER_TABLE}
GROUP BY pincode, pincode_prefix
""")

# Optimize
spark.sql(f"OPTIMIZE {GOLD_PINCODE_SUMMARY}")

# Sample results
result = spark.sql(f"""
SELECT *
FROM {GOLD_PINCODE_SUMMARY}
ORDER BY total_offices DESC
LIMIT 10
""")

display(result)

# COMMAND ----------

# DBTITLE 1,Gold Table 2: State District Analysis
# GOLD TABLE 2: State & District Analysis
# Geographic infrastructure analysis

spark.sql(f"""
DROP TABLE IF EXISTS {GOLD_STATE_DISTRICT}
""")

spark.sql(f"""
CREATE TABLE {GOLD_STATE_DISTRICT}
USING DELTA
AS
SELECT 
  statename,
  district,
  
  -- Office Infrastructure
  COUNT(*) as total_offices,
  COUNT(DISTINCT pincode) as unique_pincodes,
  SUM(CASE WHEN officetype = 'HO' THEN 1 ELSE 0 END) as head_offices,
  SUM(CASE WHEN officetype = 'PO' THEN 1 ELSE 0 END) as post_offices,
  SUM(CASE WHEN officetype = 'BO' THEN 1 ELSE 0 END) as branch_offices,
  
  -- Delivery Coverage
  SUM(CASE WHEN delivery = 'Delivery' THEN 1 ELSE 0 END) as delivery_offices,
  SUM(CASE WHEN delivery = 'Non Delivery' THEN 1 ELSE 0 END) as non_delivery_offices,
  ROUND(SUM(CASE WHEN delivery = 'Delivery' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as delivery_coverage_pct,
  
  -- Geographic Quality
  SUM(CASE WHEN has_valid_coordinates THEN 1 ELSE 0 END) as offices_with_coords,
  ROUND(SUM(CASE WHEN has_valid_coordinates THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as coord_quality_pct,
  
  -- Service Density Metrics
  ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT pincode), 2) as avg_offices_per_pincode,
  
  -- Urban/Rural Mix
  ROUND(SUM(CASE WHEN officetype IN ('HO', 'PO') THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as urban_office_pct,
  CASE 
    WHEN SUM(CASE WHEN officetype IN ('HO', 'PO') THEN 1 ELSE 0 END) * 100.0 / COUNT(*) > 20 THEN 'Urban'
    WHEN SUM(CASE WHEN officetype IN ('HO', 'PO') THEN 1 ELSE 0 END) * 100.0 / COUNT(*) > 10 THEN 'Semi-Urban'
    ELSE 'Rural'
  END as district_classification,
  
  current_timestamp() as load_timestamp
  
FROM {SILVER_TABLE}
GROUP BY statename, district
""")

# Optimize
spark.sql(f"OPTIMIZE {GOLD_STATE_DISTRICT}")

# Show top districts by infrastructure
result = spark.sql(f"""
SELECT *
FROM {GOLD_STATE_DISTRICT}
ORDER BY total_offices DESC
LIMIT 10
""")

display(result)

# COMMAND ----------

# DBTITLE 1,Gold Table 3: Geographic Hierarchy
# GOLD TABLE 3: Geographic Hierarchy
# Hierarchical rollups across Circle -> Region -> Division

spark.sql(f"""
DROP TABLE IF EXISTS {GOLD_GEOGRAPHIC_HIERARCHY}
""")

spark.sql(f"""
CREATE TABLE {GOLD_GEOGRAPHIC_HIERARCHY}
USING DELTA
AS
SELECT 
  circlename,
  regionname,
  divisionname,
  
  -- Coverage Metrics
  COUNT(DISTINCT statename) as states_covered,
  COUNT(DISTINCT district) as districts_covered,
  COUNT(DISTINCT pincode) as pincodes_covered,
  COUNT(*) as total_offices,
  
  -- Office Type Distribution
  SUM(CASE WHEN officetype = 'HO' THEN 1 ELSE 0 END) as head_offices,
  SUM(CASE WHEN officetype = 'PO' THEN 1 ELSE 0 END) as post_offices,
  SUM(CASE WHEN officetype = 'BO' THEN 1 ELSE 0 END) as branch_offices,
  
  -- Delivery Infrastructure
  SUM(CASE WHEN delivery = 'Delivery' THEN 1 ELSE 0 END) as delivery_offices,
  ROUND(SUM(CASE WHEN delivery = 'Delivery' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as delivery_coverage_pct,
  
  -- Data Quality
  SUM(CASE WHEN has_valid_coordinates THEN 1 ELSE 0 END) as offices_with_coords,
  ROUND(SUM(CASE WHEN has_valid_coordinates THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as coord_coverage_pct,
  
  current_timestamp() as load_timestamp
  
FROM {SILVER_TABLE}
GROUP BY circlename, regionname, divisionname
""")

# Optimize
spark.sql(f"OPTIMIZE {GOLD_GEOGRAPHIC_HIERARCHY}")

# Show largest divisions
result = spark.sql(f"""
SELECT *
FROM {GOLD_GEOGRAPHIC_HIERARCHY}
ORDER BY total_offices DESC
LIMIT 10
""")

display(result)

# COMMAND ----------

# DBTITLE 1,Gold Table 4: Delivery Network
# GOLD TABLE 4: Delivery Network Analysis
# Focus on delivery capabilities and infrastructure

spark.sql(f"""
DROP TABLE IF EXISTS {GOLD_DELIVERY_NETWORK}
""")

spark.sql(f"""
CREATE TABLE {GOLD_DELIVERY_NETWORK}
USING DELTA
AS
SELECT 
  statename,
  
  -- Total Infrastructure
  COUNT(*) as total_offices,
  COUNT(DISTINCT pincode) as unique_pincodes,
  COUNT(DISTINCT district) as districts,
  
  -- Office Type Breakdown
  SUM(CASE WHEN officetype = 'HO' THEN 1 ELSE 0 END) as head_offices,
  SUM(CASE WHEN officetype = 'PO' THEN 1 ELSE 0 END) as post_offices,
  SUM(CASE WHEN officetype = 'BO' THEN 1 ELSE 0 END) as branch_offices,
  
  -- Delivery Capability
  SUM(CASE WHEN delivery = 'Delivery' AND officetype = 'HO' THEN 1 ELSE 0 END) as delivery_head_offices,
  SUM(CASE WHEN delivery = 'Delivery' AND officetype = 'PO' THEN 1 ELSE 0 END) as delivery_post_offices,
  SUM(CASE WHEN delivery = 'Delivery' AND officetype = 'BO' THEN 1 ELSE 0 END) as delivery_branch_offices,
  
  -- Non-Delivery
  SUM(CASE WHEN delivery = 'Non Delivery' THEN 1 ELSE 0 END) as non_delivery_offices,
  
  -- Coverage Percentages
  ROUND(SUM(CASE WHEN delivery = 'Delivery' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as overall_delivery_pct,
  ROUND(SUM(CASE WHEN officetype = 'HO' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as head_office_pct,
  ROUND(SUM(CASE WHEN officetype = 'PO' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as post_office_pct,
  ROUND(SUM(CASE WHEN officetype = 'BO' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as branch_office_pct,
  
  -- Service Metrics
  ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT pincode), 2) as avg_offices_per_pincode,
  ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT district), 2) as avg_offices_per_district,
  
  current_timestamp() as load_timestamp
  
FROM {SILVER_TABLE}
GROUP BY statename
""")

# Optimize
spark.sql(f"OPTIMIZE {GOLD_DELIVERY_NETWORK}")

# Show states ranked by delivery infrastructure
result = spark.sql(f"""
SELECT 
  statename,
  total_offices,
  unique_pincodes,
  overall_delivery_pct,
  head_offices + post_offices as primary_offices,
  branch_offices
FROM {GOLD_DELIVERY_NETWORK}
ORDER BY total_offices DESC
""")

display(result)

# COMMAND ----------

# DBTITLE 1,Gold Table 5: Geospatial Valid Coordinates
# GOLD TABLE 5: Geospatial Dataset (Valid Coordinates Only)
# Optimized for mapping and proximity analysis

spark.sql(f"""
DROP TABLE IF EXISTS {GOLD_GEOSPATIAL}
""")

spark.sql(f"""
CREATE TABLE {GOLD_GEOSPATIAL}
USING DELTA
AS
SELECT 
  postal_office_id,
  officename,
  pincode,
  pincode_prefix,
  officetype,
  delivery,
  district,
  statename,
  divisionname,
  regionname,
  circlename,
  
  -- Geographic Coordinates
  latitude,
  longitude,
  
  -- Context
  offices_per_pincode,
  
  -- Classification for visualization
  CASE 
    WHEN officetype = 'HO' THEN 'Head Office'
    WHEN officetype = 'PO' THEN 'Post Office'
    WHEN officetype = 'BO' THEN 'Branch Office'
  END as office_type_label,
  
  CASE 
    WHEN delivery = 'Delivery' THEN 'Delivery'
    ELSE 'Non-Delivery'
  END as delivery_status,
  
  load_timestamp
  
FROM {SILVER_TABLE}
WHERE has_valid_coordinates = TRUE
  AND latitude IS NOT NULL
  AND longitude IS NOT NULL
""")

# Optimize
spark.sql(f"OPTIMIZE {GOLD_GEOSPATIAL}")

# Summary statistics
result = spark.sql(f"""
SELECT 
  COUNT(*) as total_records_with_coords,
  COUNT(DISTINCT pincode) as unique_pincodes,
  COUNT(DISTINCT statename) as states_covered,
  MIN(latitude) as min_latitude,
  MAX(latitude) as max_latitude,
  MIN(longitude) as min_longitude,
  MAX(longitude) as max_longitude
FROM {GOLD_GEOSPATIAL}
""")

display(result)

# COMMAND ----------

# DBTITLE 1,SECTION 5: Data Quality Validation
# MAGIC %md
# MAGIC # SECTION 5: Data Quality Validation
# MAGIC
# MAGIC ## ✅ Quality Checks
# MAGIC
# MAGIC Validate data integrity across all tiers:
# MAGIC * Row count reconciliation
# MAGIC * Duplicate verification
# MAGIC * Coordinate quality assessment
# MAGIC * Geographic coverage validation
# MAGIC * Referential integrity checks

# COMMAND ----------

# DBTITLE 1,Row Count Reconciliation
# MAGIC %sql
# MAGIC -- ROW COUNT RECONCILIATION ACROSS TIERS
# MAGIC SELECT 
# MAGIC   'Bronze (Source)' as tier,
# MAGIC   COUNT(*) as record_count
# MAGIC FROM databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.india_post_pincode_directory
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT 
# MAGIC   'Silver (Cleaned)',
# MAGIC   COUNT(*)
# MAGIC FROM ${SILVER_TABLE}
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT 
# MAGIC   'Gold: Pincode Summary',
# MAGIC   COUNT(*)
# MAGIC FROM ${GOLD_PINCODE_SUMMARY}
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT 
# MAGIC   'Gold: State District',
# MAGIC   COUNT(*)
# MAGIC FROM ${GOLD_STATE_DISTRICT}
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT 
# MAGIC   'Gold: Geographic Hierarchy',
# MAGIC   COUNT(*)
# MAGIC FROM ${GOLD_GEOGRAPHIC_HIERARCHY}
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT 
# MAGIC   'Gold: Delivery Network',
# MAGIC   COUNT(*)
# MAGIC FROM ${GOLD_DELIVERY_NETWORK}
# MAGIC
# MAGIC UNION ALL
# MAGIC
# MAGIC SELECT 
# MAGIC   'Gold: Geospatial',
# MAGIC   COUNT(*)
# MAGIC FROM ${GOLD_GEOSPATIAL};

# COMMAND ----------

# DBTITLE 1,Data Quality Checks
# COMPREHENSIVE DATA QUALITY CHECKS

result = spark.sql(f"""
-- 1. Duplicate Check in Silver
SELECT 
  'Duplicate Records in Silver' as check_name,
  COUNT(*) as issue_count
FROM (
  SELECT 
    circlename, regionname, divisionname, officename, pincode,
    COUNT(*) as cnt
  FROM {SILVER_TABLE}
  GROUP BY circlename, regionname, divisionname, officename, pincode
  HAVING COUNT(*) > 1
)

UNION ALL

-- 2. NULL Pincode Check
SELECT 
  'Records with NULL Pincode',
  COUNT(*)
FROM {SILVER_TABLE}
WHERE pincode IS NULL

UNION ALL

-- 3. Invalid Pincode Format (not 6 digits)
SELECT 
  'Invalid Pincode Format',
  COUNT(*)
FROM {SILVER_TABLE}
WHERE LENGTH(CAST(pincode AS STRING)) != 6

UNION ALL

-- 4. Missing Coordinates
SELECT 
  'Records Missing Coordinates',
  COUNT(*)
FROM {SILVER_TABLE}
WHERE has_valid_coordinates = FALSE

UNION ALL

-- 5. Records with Coordinates
SELECT 
  'Records with Valid Coordinates',
  COUNT(*)
FROM {SILVER_TABLE}
WHERE has_valid_coordinates = TRUE
""")

display(result)

# COMMAND ----------

# DBTITLE 1,Geographic Coverage Validation
# GEOGRAPHIC COVERAGE VALIDATION

result = spark.sql(f"""
SELECT 
  'Total States' as metric,
  COUNT(DISTINCT statename) as value
FROM {SILVER_TABLE}

UNION ALL

SELECT 
  'Total Districts',
  COUNT(DISTINCT district)
FROM {SILVER_TABLE}

UNION ALL

SELECT 
  'Total Pincodes',
  COUNT(DISTINCT pincode)
FROM {SILVER_TABLE}

UNION ALL

SELECT 
  'Total Divisions',
  COUNT(DISTINCT divisionname)
FROM {SILVER_TABLE}

UNION ALL

SELECT 
  'Total Regions',
  COUNT(DISTINCT regionname)
FROM {SILVER_TABLE}

UNION ALL

SELECT 
  'Total Circles',
  COUNT(DISTINCT circlename)
FROM {SILVER_TABLE}
""")

display(result)

# COMMAND ----------

# DBTITLE 1,Coordinate Quality by State
# COORDINATE QUALITY BY STATE

result = spark.sql(f"""
SELECT 
  statename,
  COUNT(*) as total_offices,
  SUM(CASE WHEN has_valid_coordinates THEN 1 ELSE 0 END) as offices_with_coords,
  ROUND(SUM(CASE WHEN has_valid_coordinates THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as coord_coverage_pct
FROM {SILVER_TABLE}
GROUP BY statename
ORDER BY coord_coverage_pct DESC
""")

display(result)

# COMMAND ----------

# DBTITLE 1,SECTION 6: Sample Analytics Queries
# MAGIC %md
# MAGIC # SECTION 6: Sample Analytics Queries
# MAGIC
# MAGIC ## 📊 Business Intelligence Use Cases
# MAGIC
# MAGIC Example queries demonstrating how to leverage the Gold tier tables for analytics:
# MAGIC * Top performing regions
# MAGIC * Service coverage analysis
# MAGIC * Infrastructure planning insights
# MAGIC * Delivery network optimization

# COMMAND ----------

# DBTITLE 1,Query 1: Top States by Office Count
# QUERY 1: Top 10 States by Office Infrastructure

result = spark.sql(f"""
SELECT 
  statename,
  total_offices,
  unique_pincodes,
  districts,
  head_offices,
  post_offices,
  branch_offices,
  overall_delivery_pct,
  avg_offices_per_pincode
FROM {GOLD_DELIVERY_NETWORK}
ORDER BY total_offices DESC
LIMIT 10
""")

display(result)

# COMMAND ----------

# DBTITLE 1,Query 2: Pincodes with Most Offices
# QUERY 2: Pincodes with Highest Office Concentration

result = spark.sql(f"""
SELECT 
  pincode,
  statename,
  district,
  total_offices,
  head_offices,
  post_offices,
  branch_offices,
  delivery_coverage_pct,
  classification,
  centroid_latitude,
  centroid_longitude
FROM {GOLD_PINCODE_SUMMARY}
ORDER BY total_offices DESC
LIMIT 20
""")

display(result)

# COMMAND ----------

# DBTITLE 1,Query 3: Delivery Coverage by State
# QUERY 3: States Ranked by Delivery Coverage

result = spark.sql(f"""
SELECT 
  statename,
  total_offices,
  delivery_branch_offices + delivery_post_offices + delivery_head_offices as total_delivery_offices,
  non_delivery_offices,
  overall_delivery_pct,
  CASE 
    WHEN overall_delivery_pct >= 98 THEN 'Excellent'
    WHEN overall_delivery_pct >= 95 THEN 'Good'
    WHEN overall_delivery_pct >= 90 THEN 'Average'
    ELSE 'Needs Improvement'
  END as coverage_rating
FROM {GOLD_DELIVERY_NETWORK}
ORDER BY overall_delivery_pct DESC
""")

display(result)

# COMMAND ----------

# DBTITLE 1,Query 4: Best Coordinate Coverage States
# QUERY 4: States with Best Geolocation Data Quality

result = spark.sql(f"""
SELECT 
  d.statename,
  d.total_offices,
  g.geospatial_records,
  ROUND(g.geospatial_records * 100.0 / d.total_offices, 2) as coord_coverage_pct
FROM {GOLD_DELIVERY_NETWORK} d
LEFT JOIN (
  SELECT 
    statename,
    COUNT(*) as geospatial_records
  FROM {GOLD_GEOSPATIAL}
  GROUP BY statename
) g ON d.statename = g.statename
ORDER BY coord_coverage_pct DESC
""")

display(result)

# COMMAND ----------

# DBTITLE 1,Query 5: Urban vs Rural Distribution
# QUERY 5: Urban vs Rural Office Distribution by State

result = spark.sql(f"""
SELECT 
  statename,
  SUM(CASE WHEN classification = 'Urban' THEN total_offices ELSE 0 END) as urban_offices,
  SUM(CASE WHEN classification = 'Rural' THEN total_offices ELSE 0 END) as rural_offices,
  COUNT(*) as total_pincodes,
  ROUND(SUM(CASE WHEN classification = 'Urban' THEN total_offices ELSE 0 END) * 100.0 / 
        SUM(total_offices), 2) as urban_pct
FROM {GOLD_PINCODE_SUMMARY}
GROUP BY statename
ORDER BY urban_pct DESC
""")

display(result)

# COMMAND ----------

# DBTITLE 1,Query 6: Circle Performance Overview
# QUERY 6: Circle-Level Performance Analysis

result = spark.sql(f"""
SELECT 
  circlename,
  COUNT(DISTINCT divisionname) as divisions,
  states_covered,
  districts_covered,
  pincodes_covered,
  total_offices,
  head_offices,
  post_offices,
  branch_offices,
  delivery_coverage_pct,
  coord_coverage_pct
FROM {GOLD_GEOGRAPHIC_HIERARCHY}
WHERE regionname = 'DivReportingCircle'
GROUP BY circlename, states_covered, districts_covered, pincodes_covered, 
         total_offices, head_offices, post_offices, branch_offices, 
         delivery_coverage_pct, coord_coverage_pct
ORDER BY total_offices DESC
""")

display(result)

# COMMAND ----------

# DBTITLE 1,Pipeline Summary & Next Steps
# MAGIC %md
# MAGIC # ✨ Pipeline Execution Complete!
# MAGIC
# MAGIC ## 🏆 What We Built
# MAGIC
# MAGIC This medallion architecture pipeline transforms the India Post Pincode Directory through three layers:
# MAGIC
# MAGIC ### Bronze Tier (Source)
# MAGIC * Raw data: 165,627 records
# MAGIC * Unmodified source table
# MAGIC
# MAGIC ### Silver Tier (Cleaned)
# MAGIC * **Table:** `india_post_silver_pincode_directory`
# MAGIC * Data type corrections (lat/long to DOUBLE)
# MAGIC * Duplicate removal (2 records)
# MAGIC * Text standardization (Title Case)
# MAGIC * Quality flags and derived fields
# MAGIC * Partitioned by state for performance
# MAGIC
# MAGIC ### Gold Tier (Aggregated)
# MAGIC 5 business-ready tables:
# MAGIC 1. **gold_pincode_summary** - 19,586 pincode-level records
# MAGIC 2. **gold_state_district_analysis** - District infrastructure metrics
# MAGIC 3. **gold_geographic_hierarchy** - Organizational hierarchy rollups
# MAGIC 4. **gold_delivery_network** - State-level delivery capabilities
# MAGIC 5. **gold_geospatial_valid_coords** - Mapping-ready coordinates
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## 🚀 Next Steps
# MAGIC
# MAGIC ### Immediate Actions
# MAGIC 1. **Run all cells** to create the complete pipeline
# MAGIC 2. **Verify table creation** using the validation queries
# MAGIC 3. **Update catalog/schema** in the configuration cell if needed
# MAGIC
# MAGIC ### Production Considerations
# MAGIC 1. **Scheduling:** Convert to Lakeflow Spark Declarative Pipeline for automated refreshes
# MAGIC 2. **Monitoring:** Add data quality alerts for coordinate coverage drops
# MAGIC 3. **Optimization:** Enable Auto Optimize and Liquid Clustering on Gold tables
# MAGIC 4. **Security:** Apply appropriate Unity Catalog permissions
# MAGIC 5. **Documentation:** Add table comments and column descriptions in Unity Catalog
# MAGIC
# MAGIC ### Analytics Use Cases
# MAGIC * **Location Intelligence:** Use geospatial table for mapping and proximity analysis
# MAGIC * **Infrastructure Planning:** Identify underserved districts for expansion
# MAGIC * **Delivery Optimization:** Analyze delivery vs non-delivery coverage gaps
# MAGIC * **Urban Planning:** Urban/rural classification for targeted services
# MAGIC * **Data Quality Monitoring:** Track coordinate coverage improvements over time
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## 📚 Resources
# MAGIC * [Delta Lake Best Practices](https://docs.databricks.com/delta/best-practices.html)
# MAGIC * [Medallion Architecture](https://www.databricks.com/glossary/medallion-architecture)
# MAGIC * [Unity Catalog](https://docs.databricks.com/data-governance/unity-catalog/index.html)
# MAGIC * [Lakeflow Spark Declarative Pipelines](https://docs.databricks.com/workflows/delta-live-tables/index.html)

