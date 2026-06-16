-- Top medical specialties across all facilities, parsed from the specialties JSON array column.
SELECT
  s        AS specialty,
  COUNT(*) AS facilities
FROM databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities
LATERAL VIEW explode(from_json(specialties, 'array<string>')) t AS s
WHERE specialties LIKE '[%'
  AND s IS NOT NULL
  AND s <> ''
GROUP BY s
ORDER BY facilities DESC
LIMIT 12;
