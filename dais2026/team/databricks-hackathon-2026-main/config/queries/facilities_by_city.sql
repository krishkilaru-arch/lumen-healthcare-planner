-- Facilities by city (top 12), used for the regional distribution chart.
SELECT
  address_city AS city,
  COUNT(*)     AS facilities
FROM databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities
WHERE address_city IS NOT NULL
  AND address_city <> ''
GROUP BY address_city
ORDER BY facilities DESC
LIMIT 12;
