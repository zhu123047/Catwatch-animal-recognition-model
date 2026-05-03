"""Runtime configuration for the EPIC 3 API."""

from dataclasses import dataclass
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_database: str = "echoes_of_earth"
    pg_user: str = "postgres"
    pg_password: str = "P@ssw0rd"
    max_upload_mb: int = 8
    default_top_k: int = 3
    classifier_backend: str = "auto"
    model_path: str | None = str(PROJECT_ROOT / "models" / "epic3" / "species_classifier.pt")
    labels_path: str | None = str(PROJECT_ROOT / "models" / "epic3" / "labels.json")
    cors_origins: tuple[str, ...] = ("*",)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def pg_dsn(self) -> dict[str, object]:
        return {
            "host": self.pg_host,
            "port": self.pg_port,
            "dbname": self.pg_database,
            "user": self.pg_user,
            "password": self.pg_password,
        }


def load_settings() -> Settings:
    return Settings(
        pg_host=os.getenv("PGHOST", "localhost"),
        pg_port=int(os.getenv("PGPORT", "5432")),
        pg_database=os.getenv("PGDATABASE", "echoes_of_earth"),
        pg_user=os.getenv("PGUSER", "postgres"),
        pg_password=os.getenv("PGPASSWORD", "P@ssw0rd"),
        max_upload_mb=int(os.getenv("EPIC3_MAX_UPLOAD_MB", "8")),
        default_top_k=int(os.getenv("EPIC3_TOP_K", "3")),
        classifier_backend=os.getenv("EPIC3_CLASSIFIER_BACKEND", "auto"),
        model_path=os.getenv("EPIC3_MODEL_PATH")
        or str(PROJECT_ROOT / "models" / "epic3" / "species_classifier.pt"),
        labels_path=os.getenv("EPIC3_LABELS_PATH")
        or str(PROJECT_ROOT / "models" / "epic3" / "labels.json"),
        cors_origins=tuple(
            origin.strip()
            for origin in os.getenv("EPIC3_CORS_ORIGINS", "*").split(",")
            if origin.strip()
        ),
    )

