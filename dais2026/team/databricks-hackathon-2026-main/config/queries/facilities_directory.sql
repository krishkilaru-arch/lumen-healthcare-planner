-- Searchable facility directory.
--   :search   matches facility name or city (empty string = no filter)
--   :min_beds minimum reported bed capacity (0 = no filter)
-- Capped at 100 rows to keep the response payload small for the client table.
-- @param search STRING
-- @param min_beds INT
SELECT
  unique_id,
  name,
  COALESCE(NULLIF(address_city, ''), '—') AS city,
  TRY_CAST(numberDoctors AS INT)          AS doctors,
  TRY_CAST(capacity AS INT)               AS beds,
  officialPhone                           AS phone,
  email,
  officialWebsite                         AS website
FROM databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities
WHERE name IS NOT NULL
  AND name <> ''
  AND (
    :search = ''
    OR LOWER(name) LIKE LOWER(CONCAT('%', :search, '%'))
    OR LOWER(address_city) LIKE LOWER(CONCAT('%', :search, '%'))
  )
  AND (:min_beds = 0 OR TRY_CAST(capacity AS INT) >= :min_beds)
ORDER BY TRY_CAST(capacity AS INT) DESC NULLS LAST, name
LIMIT 100;
