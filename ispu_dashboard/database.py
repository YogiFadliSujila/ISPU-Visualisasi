from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from .data import normalize_measurements


def _normalize_database_url(url: str) -> str:
    parsed = make_url(url)
    if parsed.drivername == "postgresql":
        parsed = parsed.set(drivername="postgresql+psycopg")
    return parsed.render_as_string(hide_password=False)


def load_measurements(database_url: str) -> pd.DataFrame:
    engine = create_engine(_normalize_database_url(database_url), pool_pre_ping=True, connect_args={"connect_timeout": 10})
    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(
                text(
                    """
                    SELECT tanggal, periode_data, stasiun, pm25, pm10, co, so2, no2, o3,
                           nilai_maks, kategori, parameter_kritis
                    FROM ispu_harian
                    ORDER BY tanggal, stasiun
                    """
                ),
                connection,
            )
    finally:
        engine.dispose()
    return normalize_measurements(frame)
