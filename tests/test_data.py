from __future__ import annotations

import unittest

import pandas as pd

from ispu_dashboard.data import canonical_station, normalize_measurements
from ispu_dashboard.federation import federate_data


class NormalizeMeasurementsTests(unittest.TestCase):
    def test_normalizes_full_dates_across_years(self) -> None:
        raw = pd.DataFrame(
            [
                {
                    "periode_data": "202302",
                    "tanggal": "2023-02-25",
                    "stasiun": "DKI5  Kebon Jeruk  Jakarta Barat",
                    "pm_sepuluh": "35",
                    "pm_duakomalima": "-",
                    "sulfur_dioksida": "13",
                    "karbon_monoksida": "12",
                    "ozon": "31",
                    "nitrogen_dioksida": "18",
                    "max": "35",
                    "parameter_pencemar_kritis": "PM10",
                    "kategori": "BAIK",
                },
                {
                    "periode_data": "202401",
                    "tanggal": "2024-01-01",
                    "stasiun": "DKI1 Bundaran HI",
                    "pm_sepuluh": "20",
                    "max": "20",
                    "kategori": "BAIK",
                },
            ]
        )
        result = normalize_measurements(raw)
        self.assertEqual(len(result), 2)
        self.assertEqual(result.loc[0, "stasiun"], "DKI5  Kebon Jeruk  Jakarta Barat")
        self.assertEqual(result.loc[0, "pm10"], 35)
        self.assertTrue(pd.isna(result.loc[0, "pm25"]))
        self.assertEqual(result.loc[0, "nilai_maks"], 35)
        self.assertEqual(result.loc[0, "parameter_kritis"], "PM10")
        self.assertEqual(result.loc[1, "tanggal"], pd.Timestamp("2024-01-01"))

    def test_builds_dates_from_period_and_day_and_discards_invalid_calendar_dates(self) -> None:
        raw = pd.DataFrame(
            [
                {
                    "periode_data": "202511",
                    "tanggal": "30",
                    "stasiun": "DKI5 Kebon Jeruk",
                    "max": "84",
                    "kategori": "SEDANG",
                },
                {
                    "periode_data": "202509",
                    "tanggal": "31",
                    "stasiun": "DKI5 Kebon Jeruk",
                    "max": "N/A",
                    "kategori": "N/A",
                },
                {
                    "periode_data": "202401",
                    "tanggal": "21",
                    "stasiun": "DKI3 Jagakarsa",
                    "max": "79",
                    "kategori": "SEDANG",
                },
            ]
        )
        result = normalize_measurements(raw)
        self.assertEqual(len(result), 2)
        self.assertEqual(result["tanggal"].tolist(), [pd.Timestamp("2025-11-30"), pd.Timestamp("2024-01-21")])

    def test_rejects_missing_required_columns(self) -> None:
        with self.assertRaisesRegex(ValueError, "tanggal"):
            normalize_measurements(pd.DataFrame({"stasiun": ["DKI1"]}))

    def test_deduplicates_station_day(self) -> None:
        raw = pd.DataFrame(
            [
                {"tanggal": "2023-01-01", "stasiun": "DKI1", "max": "10"},
                {"tanggal": "2023-01-01", "stasiun": "DKI1", "max": "12"},
            ]
        )
        result = normalize_measurements(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.loc[0, "nilai_maks"], 12)


class CanonicalStationTests(unittest.TestCase):
    def test_extracts_station_code_despite_spacing_and_spelling(self) -> None:
        self.assertEqual(canonical_station("DKI5  Kebon Jeruk  Jakarta Barat"), "DKI5")
        self.assertEqual(canonical_station("DKI1 Bunderan HI"), "DKI1")


class FederationTests(unittest.TestCase):
    def test_joins_reference_station_and_category_in_application(self) -> None:
        measurements = normalize_measurements(
            pd.DataFrame(
                [
                    {
                        "tanggal": "2023-02-25",
                        "stasiun": "DKI5  Kebon Jeruk  Jakarta Barat",
                        "max": "35",
                        "kategori": "BAIK",
                    },
                    {
                        "tanggal": "2023-02-26",
                        "stasiun": "DKI5 Kebon Jeruk",
                        "max": "40",
                        "kategori": "BAIK",
                    },
                    {
                        "tanggal": "2023-02-25",
                        "stasiun": "Unknown station",
                        "max": "75",
                        "kategori": "SEDANG",
                    },
                ]
            )
        )
        stations = pd.DataFrame(
            [
                {
                    "code": "DKI5",
                    "name": "Kebon Jeruk",
                    "aliases": "Kebon Jeruk Jakarta Barat",
                    "wilayah": "Jakarta Barat",
                    "latitude": -6.19,
                    "longitude": 106.77,
                    "coordinate_note": "Approximate area",
                }
            ]
        )
        categories = pd.DataFrame(
            [
                {"label": "BAIK", "nilai_min": 0, "nilai_max": 50, "warna": "#00ff00", "saran": "Saran"},
                {"label": "SEDANG", "nilai_min": 51, "nilai_max": 100, "warna": "#ffff00", "saran": "Saran"},
            ]
        )
        result = federate_data(measurements, stations, categories)
        self.assertEqual(result.loc[0, "wilayah"], "Jakarta Barat")
        self.assertEqual(result.loc[0, "stasiun"], "Kebon Jeruk")
        self.assertEqual(result.loc[0, "nama_stasiun_sumber"], "DKI5  Kebon Jeruk  Jakarta Barat")
        self.assertEqual(result.loc[0, "nilai_min"], 0)
        unknown = result.loc[result["nama_stasiun_sumber"] == "Unknown station"].iloc[0]
        self.assertTrue(pd.isna(unknown["wilayah"]))
        self.assertEqual(unknown["nilai_min"], 51)
        self.assertEqual(result.loc[1, "stasiun"], "Kebon Jeruk")


if __name__ == "__main__":
    unittest.main()
