from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from sqlalchemy import create_engine, text

from .data import normalize_measurements
from .database import _normalize_database_url


OFFICIAL_SOURCE_URL = (
    "https://ws.jakarta.go.id/gateway/DataPortalSatuDataJakarta/1.0/satudata"
    "?kategori=dataset&tipe=detail&url="
    "data-indeks-standar-pencemar-udara-ispu-di-provinsi-dki-jakarta"
)


def read_source(source: str) -> pd.DataFrame:
    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        response = requests.get(source, timeout=(10, 90))
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        body = response.content
        if "json" in content_type or body.lstrip().startswith((b"{", b"[")):
            payload = json.loads(body.decode("utf-8-sig"))
            if isinstance(payload, dict):
                for key in ("data", "results", "records", "value"):
                    if key in payload and isinstance(payload[key], list):
                        payload = payload[key]
                        break
            if not isinstance(payload, list):
                raise ValueError("Respons JSON tidak berisi daftar pengukuran.")
            return pd.DataFrame(payload)
        return pd.read_csv(pd.io.common.BytesIO(body))
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(f"Berkas sumber tidak ditemukan: {path}")
    return pd.read_csv(path)


def replace_measurements(database_url: str, frame: pd.DataFrame) -> int:
    if frame.empty:
        raise ValueError("Tidak ada baris valid untuk diimpor setelah pembersihan.")
    engine = create_engine(_normalize_database_url(database_url), pool_pre_ping=True, connect_args={"connect_timeout": 10})
    try:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM ispu_harian"))
            frame.to_sql("ispu_harian", connection, if_exists="append", index=False, method="multi", chunksize=500)
    finally:
        engine.dispose()
    return len(frame)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Impor snapshot terbaru ISPU DKI Jakarta ke Supabase PostgreSQL.")
    parser.add_argument(
        "--source",
        default=os.getenv("ISPU_SOURCE_URL") or OFFICIAL_SOURCE_URL,
        help="URL resmi JSON/CSV atau path CSV lokal (default: endpoint dataset ISPU terbaru Satu Data Jakarta).",
    )
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL"))
    args = parser.parse_args(argv)
    if not args.source:
        parser.error("Gunakan --source URL_ATAU_CSV atau set ISPU_SOURCE_URL.")
    if not args.database_url:
        parser.error("Gunakan --database-url atau set DATABASE_URL.")
    raw = read_source(args.source)
    clean = normalize_measurements(raw)
    if clean.empty:
        raise ValueError("Sumber tidak menghasilkan pengukuran dengan tanggal dan stasiun yang valid.")
    count = replace_measurements(args.database_url, clean)
    print(
        f"Impor selesai: {count} baris ISPU dari "
        f"{clean['tanggal'].min():%Y-%m-%d} sampai {clean['tanggal'].max():%Y-%m-%d} ke PostgreSQL."
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Impor gagal: {exc}", file=sys.stderr)
        sys.exit(1)
