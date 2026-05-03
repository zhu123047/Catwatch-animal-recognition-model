"""
Import and compute Epic 4 suburb score data for echoes_of_earth.

This file is the saved version of the temporary Python heredoc that was
previously run from the terminal. It is intentionally idempotent:

- creates cat_ownership_rates and suburb_scores if missing
- inserts missing reference rows without overwriting existing values
- inserts missing suburb_demographics rows without overwriting existing rows
- recomputes suburb_scores from existing species_cache data

Expected seed CSV:
    /tmp/fit5120_epic4_data/vic_postcodes_seed.csv
"""

import csv
import os
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import psycopg2


DB_CONFIG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "5432")),
    "dbname": os.getenv("PGDATABASE", "echoes_of_earth"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "P@ssw0rd"),
}

SEED_PATH = Path(
    os.getenv("EPIC4_SEED_CSV", "/tmp/fit5120_epic4_data/vic_postcodes_seed.csv")
)


def read_seed_rows() -> list[dict[str, str]]:
    if not SEED_PATH.exists():
        raise FileNotFoundError(
            f"Seed CSV not found: {SEED_PATH}. "
            "Expected the generated VIC postcode seed file."
        )

    with SEED_PATH.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def decimal_2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def main() -> None:
    seed_rows = read_seed_rows()

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cat_ownership_rates (
                state CHAR(3) PRIMARY KEY,
                ownership_pct DECIMAL(5,2) NOT NULL,
                source VARCHAR(255),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS suburb_scores (
                postcode CHAR(4) PRIMARY KEY REFERENCES suburb_demographics(postcode),
                containment_gap_raw DECIMAL(5,2) NOT NULL DEFAULT 0,
                containment_gap_score DECIMAL(5,2) NOT NULL DEFAULT 0,
                wildlife_density_raw INTEGER NOT NULL DEFAULT 0,
                wildlife_density_score DECIMAL(5,2) NOT NULL DEFAULT 0,
                cat_density_raw INTEGER NOT NULL DEFAULT 0,
                cat_density_score DECIMAL(5,2) NOT NULL DEFAULT 0,
                total_impact_score DECIMAL(5,2) NOT NULL DEFAULT 0,
                lga_percentile_rank DECIMAL(6,4),
                last_updated TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_suburb_scores_total
            ON suburb_scores(total_impact_score DESC)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_suburb_scores_lga_rank
            ON suburb_scores(lga_percentile_rank)
            """
        )

        # Required reference data. ON CONFLICT protects existing source values.
        cur.execute(
            """
            INSERT INTO cats_behaviour_stats (stat_name, stat_value, source)
            VALUES (%s, %s, %s)
            ON CONFLICT (stat_name) DO NOTHING
            """,
            (
                "outdoor_cat_pct",
                Decimal("71.0"),
                "Legge et al. 2020 Wildlife Research - doi.org/10.1071/WR19174",
            ),
        )
        cur.execute(
            """
            INSERT INTO cats_behaviour_stats (stat_name, stat_value, source)
            VALUES (%s, %s, %s)
            ON CONFLICT (stat_name) DO NOTHING
            """,
            (
                "containment_gap_pct",
                Decimal("38.0"),
                "SA Cat Containment Survey 2024 - data.sa.gov.au",
            ),
        )
        cur.execute(
            """
            INSERT INTO cat_ownership_rates (state, ownership_pct, source)
            VALUES (%s, %s, %s)
            ON CONFLICT (state) DO NOTHING
            """,
            ("VIC", Decimal("34.0"), "Pets in Australia Survey 2025"),
        )

        inserted_suburbs = 0
        for row in seed_rows:
            cur.execute(
                """
                INSERT INTO suburb_demographics
                  (postcode, suburb_name, centroid_lat, centroid_lng,
                   household_count, population, lga_name, state)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (postcode) DO NOTHING
                """,
                (
                    row["postcode"],
                    row["suburb_name"] or row["postcode"],
                    Decimal(row["centroid_lat"]),
                    Decimal(row["centroid_lng"]),
                    int(row["household_count"] or 0),
                    int(row["population"] or 0),
                    row["lga_name"] or None,
                    "VIC",
                ),
            )
            inserted_suburbs += cur.rowcount

        cur.execute(
            """
            SELECT stat_value
            FROM cats_behaviour_stats
            WHERE stat_name = 'containment_gap_pct'
            """
        )
        containment_gap_raw = Decimal(cur.fetchone()[0])
        containment_gap_score = decimal_2(
            containment_gap_raw / Decimal("100") * Decimal("45")
        )

        cur.execute(
            """
            SELECT postcode, COUNT(*)
            FROM species_cache
            WHERE state_conservation IN (
                'Endangered',
                'Vulnerable',
                'Critically Endangered'
            )
            GROUP BY postcode
            """
        )
        wildlife_by_postcode = {pc.strip(): int(cnt) for pc, cnt in cur.fetchall()}

        cur.execute(
            """
            SELECT postcode, household_count
            FROM suburb_demographics
            WHERE state = 'VIC'
            """
        )
        suburb_rows = cur.fetchall()

        ownership_rate = Decimal("0.34")
        outdoor_rate = Decimal("0.71")
        score_rows = []

        for postcode, household_count in suburb_rows:
            pc = postcode.strip()
            wildlife_raw = wildlife_by_postcode.get(pc, 0)
            wildlife_score = decimal_2(
                min(
                    Decimal(wildlife_raw) / Decimal("50") * Decimal("35"),
                    Decimal("35"),
                )
            )

            cat_density_raw = int(
                (Decimal(household_count) * ownership_rate * outdoor_rate).to_integral_value(
                    rounding=ROUND_HALF_UP
                )
            )
            cat_density_score = decimal_2(
                min(
                    Decimal(cat_density_raw) / Decimal("3000") * Decimal("20"),
                    Decimal("20"),
                )
            )
            total_score = decimal_2(
                containment_gap_score + wildlife_score + cat_density_score
            )

            score_rows.append(
                (
                    pc,
                    containment_gap_raw,
                    containment_gap_score,
                    wildlife_raw,
                    wildlife_score,
                    cat_density_raw,
                    cat_density_score,
                    total_score,
                )
            )

        cur.executemany(
            """
            INSERT INTO suburb_scores
              (postcode, containment_gap_raw, containment_gap_score,
               wildlife_density_raw, wildlife_density_score,
               cat_density_raw, cat_density_score, total_impact_score, last_updated)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())
            ON CONFLICT (postcode) DO UPDATE SET
              containment_gap_raw = EXCLUDED.containment_gap_raw,
              containment_gap_score = EXCLUDED.containment_gap_score,
              wildlife_density_raw = EXCLUDED.wildlife_density_raw,
              wildlife_density_score = EXCLUDED.wildlife_density_score,
              cat_density_raw = EXCLUDED.cat_density_raw,
              cat_density_score = EXCLUDED.cat_density_score,
              total_impact_score = EXCLUDED.total_impact_score,
              last_updated = NOW()
            """,
            score_rows,
        )

        cur.execute(
            """
            UPDATE suburb_scores ss
            SET lga_percentile_rank = sub.pr
            FROM (
              SELECT
                ss2.postcode,
                PERCENT_RANK() OVER (
                  PARTITION BY sd.lga_name
                  ORDER BY ss2.total_impact_score DESC
                ) AS pr
              FROM suburb_scores ss2
              JOIN suburb_demographics sd ON ss2.postcode = sd.postcode
              WHERE sd.state = 'VIC'
            ) sub
            WHERE ss.postcode = sub.postcode
            """
        )

        conn.commit()
        print(f"inserted_missing_suburbs: {inserted_suburbs}")
        print(f"upserted_scores: {len(score_rows)}")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
