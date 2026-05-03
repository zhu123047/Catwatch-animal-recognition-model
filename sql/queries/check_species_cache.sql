-- Check species_cache coverage and threatened-species counts by postcode.

SELECT
    COUNT(*) AS total_species_cache_rows,
    COUNT(DISTINCT postcode) AS postcodes_with_cache,
    MIN(cached_at) AS earliest_cached_at,
    MAX(cached_at) AS latest_cached_at
FROM species_cache;

SELECT
    state_conservation,
    COUNT(*) AS row_count,
    COUNT(DISTINCT postcode) AS postcode_count
FROM species_cache
GROUP BY state_conservation
ORDER BY row_count DESC, state_conservation;

SELECT
    sc.postcode,
    sd.suburb_name,
    sd.lga_name,
    COUNT(*) AS threatened_record_count,
    COUNT(DISTINCT sc.scientific_name) AS distinct_scientific_species,
    MIN(sc.cached_at) AS earliest_cached_at,
    MAX(sc.cached_at) AS latest_cached_at
FROM species_cache AS sc
LEFT JOIN suburb_demographics AS sd
    ON sd.postcode = sc.postcode
WHERE sc.state_conservation IN (
    'Endangered',
    'Vulnerable',
    'Critically Endangered'
)
GROUP BY
    sc.postcode,
    sd.suburb_name,
    sd.lga_name
ORDER BY
    threatened_record_count DESC,
    distinct_scientific_species DESC,
    sc.postcode
LIMIT 30;

SELECT
    sd.postcode,
    sd.suburb_name,
    sd.lga_name
FROM suburb_demographics AS sd
LEFT JOIN species_cache AS sc
    ON sc.postcode = sd.postcode
WHERE sd.state = 'VIC'
GROUP BY
    sd.postcode,
    sd.suburb_name,
    sd.lga_name
HAVING COUNT(sc.id) = 0
ORDER BY sd.postcode;
