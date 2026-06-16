-- Facility coordinates for the map view. Returns every facility with usable
-- coordinates (~9,970 rows) so the client can plot pins and filter in-memory;
-- no per-keystroke refetch. Rows without valid coordinates are excluded so the
-- client never plots a null/0,0 pin. Capped to stay bounded.
-- Fetched as ARROW_STREAM (the full payload exceeds the analytics JSON limit).
SELECT
  unique_id,
  name,
  COALESCE(NULLIF(address_city, ''), '—') AS city,
  address_country                         AS country,
  latitude,
  longitude,
  TRY_CAST(capacity AS INT)               AS beds,
  TRY_CAST(numberDoctors AS INT)          AS doctors,
  officialWebsite                         AS website,
  officialPhone                           AS phone
FROM databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities
WHERE name IS NOT NULL
  AND name <> ''
  AND latitude BETWEEN -90 AND 90
  AND longitude BETWEEN -180 AND 180
  AND NOT (latitude = 0 AND longitude = 0)
ORDER BY TRY_CAST(capacity AS INT) DESC NULLS LAST, name
LIMIT 10000;
