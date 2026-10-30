from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "reference.db"

STATIONS = [
    ("DKI1", "Bundaran HI", "Bundaran HI|Bunderan HI|Bunderan HI Jakarta Pusat", "Jakarta Pusat", -6.1949853, 106.8226741,
     "Perkiraan area Bundaran HI dari OpenStreetMap Nominatim; bukan titik sensor."),
    ("DKI2", "Kelapa Gading", "Kelapa Gading Jakarta Utara", "Jakarta Utara", -6.1599379, 106.9024826,
     "Perkiraan area Kelapa Gading dari OpenStreetMap Nominatim; bukan titik sensor."),
    ("DKI3", "Jagakarsa", "Jagakarsa Jakarta Selatan", "Jakarta Selatan", -6.3301011, 106.8222371,
     "Perkiraan area Jagakarsa dari OpenStreetMap Nominatim; bukan titik sensor."),
    ("DKI4", "Lubang Buaya", "Lubang Buaya Jakarta Timur", "Jakarta Timur", -6.2928737, 106.9030865,
     "Perkiraan area Lubang Buaya dari OpenStreetMap Nominatim; bukan titik sensor."),
    ("DKI5", "Kebon Jeruk", "Kebon Jeruk Jakarta Barat", "Jakarta Barat", -6.1925720, 106.7697255,
     "Perkiraan area Kebon Jeruk dari OpenStreetMap Nominatim; bukan titik sensor."),
]

CATEGORIES = [
    ("BAIK", 0, 50, "#62d6ab", "Kualitas udara baik; aktivitas luar ruangan normal."),
    ("SEDANG", 51, 100, "#f0c66a", "Kelompok sensitif dapat mempertimbangkan mengurangi aktivitas berat di luar ruangan."),
    ("TIDAK SEHAT", 101, 200, "#ef8b62", "Kelompok sensitif sebaiknya membatasi aktivitas luar ruangan yang lama atau berat."),
    ("SANGAT TIDAK SEHAT", 201, 300, "#da6680", "Kurangi aktivitas luar ruangan; kelompok sensitif sebaiknya menghindari paparan."),
    ("BERBAHAYA", 301, None, "#a678da", "Hindari aktivitas luar ruangan dan ikuti arahan otoritas kesehatan."),
    ("TIDAK ADA DATA", None, None, "#82929b", "Tidak ada pengukuran yang tersedia untuk periode ini."),
]


def build_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS stasiun_spku (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                aliases TEXT NOT NULL DEFAULT '',
                wilayah TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                coordinate_note TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS kategori_ispu (
                label TEXT PRIMARY KEY,
                nilai_min INTEGER,
                nilai_max INTEGER,
                warna TEXT NOT NULL,
                saran TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sumber_referensi (
                nama TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                catatan TEXT NOT NULL
            );
            """
        )
        category_columns = {
            row[1]: row[3]
            for row in connection.execute("PRAGMA table_info(kategori_ispu)")
        }
        if category_columns.get("nilai_max"):
            connection.execute("DROP TABLE kategori_ispu")
            connection.execute(
                """
                CREATE TABLE kategori_ispu (
                    label TEXT PRIMARY KEY,
                    nilai_min INTEGER,
                    nilai_max INTEGER,
                    warna TEXT NOT NULL,
                    saran TEXT NOT NULL
                )
                """
            )
        connection.executemany(
            "INSERT OR REPLACE INTO stasiun_spku VALUES (?, ?, ?, ?, ?, ?, ?)",
            STATIONS,
        )
        connection.executemany(
            "INSERT OR REPLACE INTO kategori_ispu VALUES (?, ?, ?, ?, ?)",
            CATEGORIES,
        )
        connection.executemany(
            "INSERT OR REPLACE INTO sumber_referensi VALUES (?, ?, ?)",
            [
                (
                    "Satu Data Jakarta ISPU 2023",
                    "https://satudata.jakarta.go.id/open-data/detail?kategori=dataset&page_url=data-indeks-standar-pencemar-udara-ispu-di-provinsi-dki-jakarta-2023&data_no=1",
                    "Sumber primer untuk data pengukuran dan identitas stasiun.",
                ),
                (
                    "Permen LHK No. 14 Tahun 2020",
                    "https://peraturan.bpk.go.id/Details/163460/permen-lhk-no-14-tahun-2020",
                    "Acuan kategori dan rentang ISPU yang digunakan pada dashboard.",
                ),
                (
                    "OpenStreetMap Nominatim",
                    "https://nominatim.openstreetmap.org/",
                    "Geocoding kawasan administratif sebagai titik perkiraan; lokasi bukan koordinat presisi SPKU.",
                ),
            ],
        )


if __name__ == "__main__":
    build_database()
    print(f"SQLite reference database ready: {DB_PATH}")
