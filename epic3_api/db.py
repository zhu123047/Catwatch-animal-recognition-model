"""Read-only PostgreSQL access for EPIC 3 species insights."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from typing import Any

from .schemas import Prediction, SpeciesInsight


SUBURB_SQL = """
SELECT suburb_name, lga_name
FROM suburb_demographics
WHERE postcode = %s
LIMIT 1
"""

SPECIES_CONTEXT_SQL = """
WITH matched AS (
    SELECT
        sc.postcode,
        sc.state_conservation,
        sc.cached_at,
        sd.suburb_name,
        sd.lga_name
    FROM species_cache AS sc
    LEFT JOIN suburb_demographics AS sd
        ON sd.postcode = sc.postcode
    WHERE lower(sc.scientific_name) = lower(%s)
       OR lower(sc.vernacular_name) = lower(%s)
)
SELECT
    COALESCE(
        MAX(NULLIF(state_conservation, '')),
        'Unknown'
    ) AS conservation_status,
    COUNT(*) FILTER (WHERE postcode = %s) AS local_sighting_count,
    COUNT(*) FILTER (WHERE lga_name = %s) AS lga_sighting_count,
    COUNT(*) AS victoria_sighting_count,
    MAX(cached_at) FILTER (WHERE postcode = %s) AS latest_local_cached_at,
    MAX(cached_at) AS latest_victoria_cached_at
FROM matched
"""


@dataclass(frozen=True)
class DatabaseConfig:
    dsn: dict[str, object]


class ReadOnlySpeciesRepository:
    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config

    def get_species_insights(
        self, postcode: str, predictions: list[Prediction]
    ) -> list[SpeciesInsight]:
        with closing(self._connect()) as conn:
            with conn.cursor() as cur:
                suburb = self._get_suburb(cur, postcode)
                return [
                    self._get_prediction_context(cur, postcode, suburb, prediction)
                    for prediction in predictions
                ]

    def _connect(self) -> Any:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(**self.config.dsn, cursor_factory=RealDictCursor)
        conn.set_session(readonly=True, autocommit=True)
        return conn

    def _get_suburb(self, cur: Any, postcode: str) -> dict[str, Any]:
        cur.execute(SUBURB_SQL, (postcode,))
        return cur.fetchone() or {"suburb_name": None, "lga_name": None}

    def _get_prediction_context(
        self,
        cur: Any,
        postcode: str,
        suburb: dict[str, Any],
        prediction: Prediction,
    ) -> SpeciesInsight:
        cur.execute(
            SPECIES_CONTEXT_SQL,
            (
                prediction.scientific_name,
                prediction.common_name or "",
                postcode,
                suburb.get("lga_name"),
                postcode,
            ),
        )
        row = cur.fetchone() or {}
        return SpeciesInsight(
            prediction=prediction,
            conservation_status=row.get("conservation_status"),
            local_sighting_count=int(row.get("local_sighting_count") or 0),
            lga_sighting_count=int(row.get("lga_sighting_count") or 0),
            victoria_sighting_count=int(row.get("victoria_sighting_count") or 0),
            latest_local_cached_at=row.get("latest_local_cached_at"),
            latest_victoria_cached_at=row.get("latest_victoria_cached_at"),
            suburb_name=suburb.get("suburb_name"),
            lga_name=suburb.get("lga_name"),
        )

