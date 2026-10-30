from __future__ import annotations

import re
import sqlite3
import unicodedata
import logging
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DB = ROOT / "data" / "reference.db"
LOGGER = logging.getLogger(__name__)

POLLUTANT_LABELS = {
    "pm25": "PM₂.₅",
    "pm10": "PM₁₀",
    "co": "CO",
    "so2": "SO₂",
    "no2": "NO₂",
    "o3": "O₃",
}

COLUMN_ALIASES = {
    "tanggal": ("tanggal", "date", "measurement_date"),
    "periode_data": ("periode_data", "periode", "period"),
    "stasiun": ("stasiun", "station", "nama_stasiun"),
    "pm25": ("pm25", "pm2.5", "pm_duakomalima", "pm_2_5", "pm25_value"),
    "pm10": ("pm10", "pm_sepuluh", "pm_10", "pm10_value"),
    "co": ("co", "karbon_monoksida", "carbon_monoxide"),
    "so2": ("so2", "sulfur_dioksida", "sulfur_dioxide"),
    "no2": ("no2", "nitrogen_dioksida", "nitrogen_dioxide"),
    "o3": ("o3", "ozon", "ozone"),
    "nilai_maks": ("nilai_maks", "max", "ispu", "nilai_ispu"),
    "kategori": ("kategori", "category"),
    "parameter_kritis": ("parameter_kritis", "parameter_pencemar_kritis", "critical_parameter"),
}


def canonical_station(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    code = re.search(r"\bDKI\s*[-_]?\s*(\d+)\b", text, re.IGNORECASE)
    if code:
        return f"DKI{int(code.group(1))}"
    text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return re.sub(r"\s+", " ", text)


def _coerce_number(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.strip().replace(
        {"": pd.NA, "-": pd.NA, "—": pd.NA, "nan": pd.NA, "None": pd.NA}
    )
    return pd.to_numeric(cleaned, errors="coerce")


def normalize_measurements(frame: pd.DataFrame) -> pd.DataFrame:
    output_columns = [
        "tanggal", "periode_data", "stasiun", "pm25", "pm10", "co", "so2", "no2", "o3",
        "nilai_maks", "kategori", "parameter_kritis",
    ]
    if frame.empty:
        return pd.DataFrame(columns=output_columns)

    renamed: dict[str, str] = {}
    source_columns = {str(column).strip().lower(): column for column in frame.columns}
    for target, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias.lower() in source_columns:
                renamed[source_columns[alias.lower()]] = target
                break

    normalized = frame.rename(columns=renamed).copy()
    missing = {"tanggal", "stasiun"} - set(normalized.columns)
    if missing:
        raise ValueError(f"Kolom wajib tidak ditemukan: {', '.join(sorted(missing))}")

    for column in COLUMN_ALIASES:
        if column not in normalized:
            normalized[column] = pd.NA

    raw_dates = normalized["tanggal"].astype("string").str.strip()
    full_date_mask = raw_dates.str.match(
        r"^(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:[ T].*)?|\d{8})$",
        na=False,
    )
    full_dates = pd.to_datetime(
        raw_dates.where(full_date_mask),
        format="mixed",
        errors="coerce",
    )

    periods = normalized["periode_data"].astype("string").str.strip()
    period_parts = periods.str.extract(r"^(?P<year>\d{4})\D?(?P<month>\d{1,2})$")
    day_parts = raw_dates.str.extract(r"^(?P<day>\d{1,2})(?:\.0+)?$")
    partial_date_strings = (
        period_parts["year"].str.zfill(4)
        + "-"
        + period_parts["month"].str.zfill(2)
        + "-"
        + day_parts["day"].str.zfill(2)
    )
    partial_dates = pd.to_datetime(partial_date_strings, errors="coerce")
    normalized["tanggal"] = full_dates.fillna(partial_dates)
    normalized["stasiun"] = normalized["stasiun"].astype("string").str.strip()
    invalid_date_count = int(normalized["tanggal"].isna().sum())
    if invalid_date_count:
        LOGGER.warning(
            "Discarding %d ISPU rows with missing or invalid calendar dates.",
            invalid_date_count,
        )
    normalized = normalized.dropna(subset=["tanggal", "stasiun"]).copy()
    for column in (*POLLUTANT_LABELS.keys(), "nilai_maks"):
        normalized[column] = _coerce_number(normalized[column])
    normalized["kategori"] = (
        normalized["kategori"].astype("string").str.strip().str.upper()
        .replace({"": pd.NA, "N/A": pd.NA, "NULL": pd.NA, "NAN": pd.NA})
    )
    normalized["parameter_kritis"] = normalized["parameter_kritis"].astype("string").str.strip()
    normalized["periode_data"] = normalized["periode_data"].astype("string").str.strip()
    normalized["_station_key"] = normalized["stasiun"].map(canonical_station)
    normalized = normalized.drop_duplicates(
        subset=["tanggal", "_station_key"],
        keep="last",
    ).drop(columns="_station_key")
    return normalized[output_columns].reset_index(drop=True)


def load_reference_data(db_path: Path = REFERENCE_DB) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite reference database does not exist: {db_path}")
    with sqlite3.connect(db_path) as connection:
        stations = pd.read_sql_query(
            "SELECT code, name, aliases, wilayah, latitude, longitude, coordinate_note FROM stasiun_spku",
            connection,
        )
        categories = pd.read_sql_query(
            "SELECT label, nilai_min, nilai_max, warna, saran FROM kategori_ispu ORDER BY nilai_min",
            connection,
        )
    return stations, categories
