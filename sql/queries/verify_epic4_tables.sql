-- Verify Epic 4 database tables, row counts, and key seeded values.

SELECT
    table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
      'suburb_demographics',
      'suburb_scores',
      'species_cache',
      'cats_behaviour_stats',
      'cat_ownership_rates'
  )
ORDER BY table_name;

SELECT
    'suburb_demographics' AS table_name,
    COUNT(*) AS row_count
FROM suburb_demographics
WHERE state = 'VIC'
UNION ALL
SELECT 'suburb_scores', COUNT(*) FROM suburb_scores
UNION ALL
SELECT 'species_cache', COUNT(*) FROM species_cache
UNION ALL
SELECT 'cats_behaviour_stats', COUNT(*) FROM cats_behaviour_stats
UNION ALL
SELECT 'cat_ownership_rates', COUNT(*) FROM cat_ownership_rates
ORDER BY table_name;

SELECT
    stat_name,
    stat_value,
    source
FROM cats_behaviour_stats
WHERE stat_name IN (
    'outdoor_cat_pct',
    'containment_gap_pct',
    'prey_median_monthly',
    'prey_per_day'
)
ORDER BY stat_name;

SELECT
    state,
    ownership_pct,
    source,
    updated_at
FROM cat_ownership_rates
ORDER BY state;

SELECT
    ss.postcode,
    sd.suburb_name,
    sd.lga_name,
    ss.wildlife_density_raw,
    ss.cat_density_raw,
    ss.total_impact_score
FROM suburb_scores AS ss
JOIN suburb_demographics AS sd
    ON sd.postcode = ss.postcode
WHERE ss.postcode IN ('3000', '3029', '3220', '3550')
ORDER BY ss.postcode;
