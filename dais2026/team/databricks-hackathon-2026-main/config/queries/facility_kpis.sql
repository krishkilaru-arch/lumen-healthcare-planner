-- Headline metrics across the Virtue Foundation healthcare facilities dataset. Returns a single row.
SELECT
  COUNT(*)                                                                            AS total_facilities,
  COUNT(DISTINCT NULLIF(address_city, ''))                                            AS cities,
  ROUND(AVG(TRY_CAST(numberDoctors AS DOUBLE)), 0)                                    AS avg_doctors,
  CAST(SUM(TRY_CAST(capacity AS DOUBLE)) AS BIGINT)                                   AS total_beds,
  ROUND(100.0 * SUM(CASE WHEN officialWebsite IS NOT NULL AND officialWebsite <> ''
                         THEN 1 ELSE 0 END) / COUNT(*), 0)                            AS pct_online
FROM databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities;
