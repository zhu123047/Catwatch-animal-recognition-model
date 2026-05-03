-- Get the pre-computed Cat Impact Score for one postcode.
-- Usage in psql:
--   \set postcode '3029'
--   \i sql/queries/get_suburb_score.sql

SELECT
    ss.postcode,
    sd.suburb_name,
    sd.lga_name,
    sd.household_count,
    ss.containment_gap_raw,
    ss.containment_gap_score,
    ss.wildlife_density_raw,
    ss.wildlife_density_score,
    ss.cat_density_raw,
    ss.cat_density_score,
    ss.total_impact_score,
    ss.lga_percentile_rank,
    ss.last_updated
FROM suburb_scores AS ss
JOIN suburb_demographics AS sd
    ON sd.postcode = ss.postcode
WHERE ss.postcode = :'postcode';
