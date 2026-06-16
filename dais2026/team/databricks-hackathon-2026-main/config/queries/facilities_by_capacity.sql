-- Distribution of facilities by reported bed-capacity band (facilities with a reported capacity only).
SELECT
  CASE
    WHEN TRY_CAST(capacity AS DOUBLE) < 50  THEN 'Under 50'
    WHEN TRY_CAST(capacity AS DOUBLE) < 200 THEN '50-199'
    WHEN TRY_CAST(capacity AS DOUBLE) < 500 THEN '200-499'
    ELSE '500+'
  END      AS band,
  COUNT(*) AS facilities
FROM databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities
WHERE TRY_CAST(capacity AS DOUBLE) IS NOT NULL
GROUP BY band
ORDER BY MIN(TRY_CAST(capacity AS DOUBLE));
