CREATE TABLE IF NOT EXISTS ispu_harian (
    tanggal DATE NOT NULL,
    periode_data TEXT,
    stasiun TEXT NOT NULL,
    pm25 DOUBLE PRECISION,
    pm10 DOUBLE PRECISION,
    co DOUBLE PRECISION,
    so2 DOUBLE PRECISION,
    no2 DOUBLE PRECISION,
    o3 DOUBLE PRECISION,
    nilai_maks DOUBLE PRECISION,
    kategori TEXT,
    parameter_kritis TEXT,
    CONSTRAINT ispu_harian_tanggal_stasiun_key UNIQUE (tanggal, stasiun)
);

CREATE INDEX IF NOT EXISTS ispu_harian_tanggal_idx ON ispu_harian (tanggal);
CREATE INDEX IF NOT EXISTS ispu_harian_stasiun_tanggal_idx ON ispu_harian (stasiun, tanggal);
