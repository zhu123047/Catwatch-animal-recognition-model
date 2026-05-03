-- Show suburbs/postcodes with the highest Cat Impact Scores.
-- Usage in psql:
--   \set limit 20
--   \i sql/queries/top_impact_suburbs.sql

SELECT
    ss.postcode,
    sd.suburb_name,
    sd.lga_name,
    ss.total_impact_score,
    ss.containment_gap_score,
    ss.wildlife_density_raw,
    ss.wildlife_density_score,
    ss.cat_density_raw,
    ss.cat_density_score,
    ss.lga_percentile_rank,
    ss.last_updated
FROM suburb_scores AS ss
JOIN suburb_demographics AS sd
    ON sd.postcode = ss.postcode
WHERE sd.state = 'VIC'
ORDER BY
    ss.total_impact_score DESC,
    ss.wildlife_density_raw DESC,
    ss.cat_density_raw DESC,
    ss.postcode
LIMIT :limit;
