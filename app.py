from __future__ import annotations

import logging
import os
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ispu_dashboard.data import (
    POLLUTANT_LABELS,
    load_reference_data,
    normalize_measurements,
)
from ispu_dashboard.database import load_measurements
from ispu_dashboard.federation import federate_data


logging.basicConfig(level=logging.INFO)

st.set_page_config(
    page_title="Napas Jakarta | Data ISPU terbaru",
    page_icon="🌫️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
    :root { --ink:#eaf1f5; --muted:#91a5b1; --panel:#111d25; --line:#263640; --mint:#68e0bd; }
    html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
    .stApp { background: radial-gradient(ellipse at 70% -20%, #193544 0, #0b141a 43%, #091116 100%); color:var(--ink); }
    [data-testid="stHeader"] { background:transparent; }
    [data-testid="stSidebar"] { background:#0d171d; border-right:1px solid #1e303a; }
    [data-testid="stMetric"] { background:linear-gradient(145deg,#14232c,#101a21); padding:18px 20px; border:1px solid #263a45; border-radius:16px; }
    [data-testid="stMetricLabel"] { color:#91a5b1; }
    [data-testid="stMetricValue"] { color:#edf5f5; font-family:'Manrope',sans-serif; }
    .hero { padding:18px 0 16px; }
    .eyebrow { color:#68e0bd; text-transform:uppercase; font-weight:700; letter-spacing:.16em; font-size:.73rem; }
    .hero h1 { font-family:'Manrope',sans-serif; font-size:clamp(2rem,4vw,3.2rem); line-height:1.04; letter-spacing:-.055em; margin:.6rem 0; color:#f0f7f7; }
    .hero p { color:#9cb0bb; font-size:1rem; max-width:750px; }
    .section-title { font-family:'Manrope',sans-serif; font-weight:700; color:#e7f1f2; font-size:1.05rem; margin:.45rem 0 .2rem; }
    .section-note { color:#869aa5; font-size:.82rem; margin-bottom:.8rem; }
    .source-note { border-top:1px solid #263640; padding-top:1rem; color:#91a5b1; font-size:.82rem; }
    a { color:#68e0bd !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

PALETTE = {
    "BAIK": "#62d6ab",
    "SEDANG": "#f0c66a",
    "TIDAK SEHAT": "#ef8b62",
    "SANGAT TIDAK SEHAT": "#da6680",
    "BERBAHAYA": "#a678da",
    "TIDAK ADA DATA": "#82929b",
    "Tidak diketahui": "#82929b",
}


def _read_secret(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    try:
        value = st.secrets.get(name)
        return str(value) if value else None
    except (FileNotFoundError, KeyError):
        return None


def _chart_layout(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=12, r=12, t=28, b=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, sans-serif", color="#b4c3ca", size=12),
        hoverlabel=dict(bgcolor="#16232b", bordercolor="#39515e", font_color="#edf5f5"),
        legend=dict(orientation="h", y=1.12, x=0, title=None),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor="#263640")
    fig.update_yaxes(gridcolor="#22313a", zeroline=False)
    return fig


def _chart_frame(title: str, note: str) -> None:
    st.markdown(f'<div class="section-title">{title}</div><div class="section-note">{note}</div>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _cached_reference_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    return load_reference_data()


st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">DKI Jakarta · pemantauan kualitas udara</div>
      <h1>Udara kota, terbaca.</h1>
      <p>Jelajahi data ISPU harian terbaru dari stasiun pemantau Jakarta—difederasikan dengan referensi stasiun dan kategori kualitas udara.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Napas Jakarta")
    st.caption("Dashboard ISPU · data terbaru")
    st.markdown("---")
    uploaded_file = st.file_uploader(
        "Pratinjau data CSV",
        type=["csv"],
        help="Opsional: muat CSV resmi untuk pratinjau lokal. Data ini tidak diunggah ke Supabase.",
    )
    st.markdown("---")
    st.caption("**Federasi data**")
    st.caption("Supabase PostgreSQL · pengukuran harian")
    st.caption("SQLite · referensi stasiun & kategori")
    st.caption("Join dilakukan di aplikasi.")

try:
    stations_ref, categories_ref = _cached_reference_data()
except Exception as exc:
    logging.exception("SQLite reference database could not be opened")
    st.error("Database referensi SQLite tidak dapat dibaca. Pastikan berkas `data/reference.db` tersedia.")
    st.stop()

measurements: pd.DataFrame
data_source_label: str
if uploaded_file is not None:
    try:
        measurements = normalize_measurements(pd.read_csv(uploaded_file))
        data_source_label = "CSV lokal (pratinjau)"
    except (ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        st.error(f"CSV tidak dapat dibaca: {exc}")
        st.stop()
else:
    database_url = _read_secret("DATABASE_URL") or _read_secret("SUPABASE_DB_URL")
    if not database_url:
        st.info(
            "Tambahkan `DATABASE_URL` Supabase pada Streamlit Secrets atau environment, "
            "atau unggah CSV resmi di panel kiri untuk melihat pratinjau."
        )
        st.caption("Lihat README proyek, bagian “Menjalankan dashboard”, untuk petunjuk konfigurasi.")
        st.stop()
    try:
        measurements = load_measurements(database_url)
    except Exception as exc:
        logging.exception("Could not load measurement records from PostgreSQL")
        st.error(
            "Koneksi ke PostgreSQL gagal. Periksa `DATABASE_URL`, jalankan "
            "`sql/schema.sql`, lalu impor data dengan `python -m ispu_dashboard.etl`."
        )
        with st.expander("Detail teknis"):
            st.code(str(exc))
        st.stop()
    data_source_label = "Supabase PostgreSQL"

if measurements.empty:
    st.warning("Belum ada data pengukuran ISPU. Impor dataset dari portal atau unggah CSV.")
    st.stop()

federated = federate_data(measurements, stations_ref, categories_ref)
known_categories = set(categories_ref["label"])
federated["kategori_normalized"] = federated["kategori"].where(
    federated["kategori"].isin(known_categories), "Tidak diketahui"
)

with st.sidebar:
    date_min = federated["tanggal"].min().date()
    date_max = federated["tanggal"].max().date()
    date_range = st.date_input(
        "Rentang tanggal",
        value=(date_min, date_max),
        min_value=date_min,
        max_value=date_max,
        format="DD/MM/YYYY",
    )
    station_options = sorted(federated["stasiun"].dropna().unique())
    selected_stations = st.multiselect("Stasiun", station_options, default=station_options)
    pollutant_key = st.selectbox("Parameter tren", list(POLLUTANT_LABELS), index=0)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = end_date = date_range
filtered = federated.loc[
    federated["tanggal"].dt.date.between(start_date, end_date)
    & federated["stasiun"].isin(selected_stations)
].copy()

if filtered.empty:
    st.warning("Tidak ada pengukuran yang sesuai dengan filter tanggal dan stasiun.")
    st.stop()

available_calendar_years = sorted(filtered["tanggal"].dt.year.unique().tolist())
with st.sidebar:
    calendar_year = st.selectbox(
        "Tahun kalender",
        available_calendar_years,
        index=len(available_calendar_years) - 1,
    )

latest_day = filtered["tanggal"].max()
latest_rows = filtered.loc[filtered["tanggal"].eq(latest_day)]
latest_with_values = latest_rows.dropna(subset=["nilai_maks"])
latest = (
    latest_with_values.loc[latest_with_values["nilai_maks"].idxmax()]
    if not latest_with_values.empty
    else latest_rows.iloc[0]
)
latest_category = latest["kategori_normalized"]
category_color = PALETTE.get(latest_category, PALETTE["Tidak diketahui"])
unique_days = filtered["tanggal"].dt.date.nunique()
station_count = filtered["stasiun"].nunique()
unknown_station_count = filtered.loc[filtered["wilayah"].isna(), "stasiun"].nunique()

if unknown_station_count:
    st.warning(
        f"{unknown_station_count} stasiun belum cocok dengan referensi SQLite. "
        "Data tetap ditampilkan, tetapi belum memiliki metadata wilayah/koordinat."
    )

k1, k2, k3, k4 = st.columns(4)
k1.metric("ISPU tertinggi pada hari terakhir", f"{latest['nilai_maks']:.0f}" if pd.notna(latest["nilai_maks"]) else "—")
k2.metric("Kategori", latest_category)
k3.metric("Hari terpantau", f"{unique_days:,}")
k4.metric("Stasiun terpilih", f"{station_count}")
st.caption(
    f"Sumber tampilan: **{data_source_label}** · "
    f"{start_date:%d %b %Y} — {end_date:%d %b %Y} · "
    f"{len(filtered):,} baris · database pengukuran dan referensi digabung di sisi aplikasi."
)

left, right = st.columns([1.55, 1], gap="large")
with left:
    _chart_frame("Perjalanan kualitas udara", f"Rata-rata harian {POLLUTANT_LABELS[pollutant_key]} · geser untuk menelusuri waktu")
    daily = (
        filtered.groupby("tanggal", as_index=False)[pollutant_key]
        .mean()
        .sort_values("tanggal")
    )
    trend = px.area(
        daily,
        x="tanggal",
        y=pollutant_key,
        color_discrete_sequence=["#68e0bd"],
        labels={"tanggal": "Tanggal", pollutant_key: POLLUTANT_LABELS[pollutant_key]},
    )
    trend.update_traces(
        line=dict(width=2.5),
        fillcolor="rgba(104,224,189,.13)",
        hovertemplate="%{x|%d %b %Y}<br>%{y:.1f}<extra></extra>",
    )
    trend.update_xaxes(rangeslider_visible=True, rangeselector=dict(buttons=[
        dict(count=1, label="1 bln", step="month", stepmode="backward"),
        dict(count=3, label="3 bln", step="month", stepmode="backward"),
        dict(step="all", label="Semua"),
    ]))
    st.plotly_chart(_chart_layout(trend, 390), width="stretch")

with right:
    _chart_frame("Indeks hari terakhir", "Nilai maksimum ISPU pada pengukuran terbaru di filter aktif")
    gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=float(latest["nilai_maks"]) if pd.notna(latest["nilai_maks"]) else 0,
        number={"font": {"size": 46, "color": "#edf5f5"}, "suffix": ""},
        title={"text": f"{latest_category} · {latest['tanggal']:%d %B %Y}", "font": {"size": 14, "color": category_color}},
        gauge={
            "axis": {"range": [0, 500], "tickwidth": 1, "tickcolor": "#62747c", "tickfont": {"color": "#9cb0bb"}},
            "bar": {"color": category_color, "thickness": .22},
            "bgcolor": "#101a21",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 50], "color": "rgba(98,214,171,.12)"},
                {"range": [50, 100], "color": "rgba(240,198,106,.13)"},
                {"range": [100, 200], "color": "rgba(239,139,98,.13)"},
                {"range": [200, 300], "color": "rgba(218,102,128,.13)"},
                {"range": [300, 500], "color": "rgba(166,120,218,.15)"},
            ],
        },
    ))
    st.plotly_chart(_chart_layout(gauge, 390), width="stretch")

left, right = st.columns([1.15, 1], gap="large")
with left:
    _chart_frame("Kalender kualitas udara", f"{POLLUTANT_LABELS[pollutant_key]} · semakin terang, semakin tinggi")
    year_start = date(int(calendar_year), 1, 1)
    year_end = date(int(calendar_year), 12, 31)
    first_monday = year_start - timedelta(days=year_start.weekday())
    week_count = (year_end - first_monday).days // 7 + 1
    weekday_labels = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
    heat_values: list[list[float | None]] = [[None] * week_count for _ in weekday_labels]
    heat_dates = [[""] * week_count for _ in weekday_labels]
    daily_values = filtered.assign(hari=filtered["tanggal"].dt.date).groupby("hari")[pollutant_key].mean()
    current_day = first_monday
    while current_day <= year_end:
        week_index = (current_day - first_monday).days // 7
        weekday_index = current_day.weekday()
        if current_day.year == calendar_year:
            heat_dates[weekday_index][week_index] = current_day.strftime("%d %b %Y")
            value = daily_values.get(current_day)
            heat_values[weekday_index][week_index] = float(value) if pd.notna(value) else None
        current_day += timedelta(days=1)
    month_names = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    month_ticks = [
        (date(int(calendar_year), month, 1) - first_monday).days // 7
        for month in range(1, 13)
    ]
    heat_fig = go.Figure(go.Heatmap(
        z=heat_values,
        x=list(range(week_count)),
        y=weekday_labels,
        customdata=heat_dates,
        coloraxis="coloraxis",
        hovertemplate="%{customdata}<br>%{z:.1f}<extra></extra>",
        xgap=3,
        ygap=3,
    ))
    heat_fig.update_layout(
        coloraxis={
            "colorscale": ["#17252c", "#286653", "#68e0bd", "#f0c66a", "#ef8b62"],
            "colorbar": {"thickness": 8, "outlinewidth": 0, "title": POLLUTANT_LABELS[pollutant_key]},
        }
    )
    heat_fig.update_xaxes(tickmode="array", tickvals=month_ticks, ticktext=month_names, side="top")
    heat_fig.update_yaxes(autorange="reversed", title=None)
    st.plotly_chart(_chart_layout(heat_fig, 275), width="stretch")

with right:
    _chart_frame("Perbandingan stasiun", "Rata-rata ISPU harian menurut stasiun · urut dari tertinggi")
    station_summary = (
        filtered.groupby("stasiun", as_index=False)["nilai_maks"]
        .mean()
        .sort_values("nilai_maks", ascending=True)
    )
    bar = px.bar(
        station_summary,
        x="nilai_maks",
        y="stasiun",
        orientation="h",
        color="nilai_maks",
        color_continuous_scale=["#62d6ab", "#f0c66a", "#ef8b62", "#a678da"],
        labels={"nilai_maks": "Rata-rata ISPU", "stasiun": ""},
    )
    bar.update_coloraxes(showscale=False)
    bar.update_traces(hovertemplate="%{y}<br>Rata-rata %{x:.1f}<extra></extra>")
    st.plotly_chart(_chart_layout(bar, 355), width="stretch")

_chart_frame("Stasiun pemantau", "Titik menunjukkan lokasi wilayah stasiun (perkiraan), bukan koordinat sensor presisi.")
mapped = filtered.dropna(subset=["latitude", "longitude"])
if mapped.empty:
    st.info("Tidak ada stasiun terpilih dengan koordinat referensi. Tambahkan metadata lokasi pada `data/reference.db`.")
else:
    map_summary = (
        mapped.sort_values("tanggal")
        .groupby(["code", "stasiun", "wilayah", "latitude", "longitude"], as_index=False)
        .agg(nilai_maks=("nilai_maks", "mean"), kategori=("kategori_normalized", "last"))
    )
    map_fig = px.scatter_map(
        map_summary,
        lat="latitude",
        lon="longitude",
        color="kategori",
        color_discrete_map=PALETTE,
        size="nilai_maks",
        size_max=30,
        hover_name="stasiun",
        hover_data={"wilayah": True, "nilai_maks": ":.1f", "latitude": False, "longitude": False},
        zoom=9.4,
        center={"lat": -6.2, "lon": 106.84},
        map_style="open-street-map",
    )
    map_fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=440, paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(map_fig, width="stretch")

with st.expander("Ringkasan kategori ISPU & saran umum"):
    st.dataframe(
        categories_ref[["label", "nilai_min", "nilai_max", "saran"]],
        hide_index=True,
        width="stretch",
    )
    st.caption("Kategori dan rentang mengacu pada Permen LHK No. 14 Tahun 2020. Saran bersifat informatif, bukan nasihat medis.")

with st.expander("Lihat data hasil federasi"):
    display_columns = [
        "tanggal", "stasiun", "nama_stasiun_sumber", "wilayah", "nilai_maks", "kategori_normalized",
        "parameter_kritis", *POLLUTANT_LABELS,
    ]
    st.dataframe(
        filtered[display_columns].sort_values(["tanggal", "stasiun"], ascending=[False, True]),
        hide_index=True,
        width="stretch",
    )

st.markdown(
    f"""
    <div class="source-note">
      <b>Sumber pengukuran:</b>
      <a href="https://satudata.jakarta.go.id/open-data/detail?kategori=dataset&amp;page_url=data-indeks-standar-pencemar-udara-ispu-di-provinsi-dki-jakarta&amp;data_no=1" target="_blank">Satu Data Jakarta — Data ISPU DKI Jakarta</a>.
      Referensi kategori: Permen LHK No. 14 Tahun 2020. Lokasi peta: OpenStreetMap/Nominatim, ditampilkan sebagai perkiraan area.
      Data sumber dimuat dari {data_source_label}.
    </div>
    """,
    unsafe_allow_html=True,
)
