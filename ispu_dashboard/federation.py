from __future__ import annotations

import pandas as pd

from .data import canonical_station


def federate_data(
    measurements: pd.DataFrame,
    stations: pd.DataFrame,
    categories: pd.DataFrame,
) -> pd.DataFrame:
    left = measurements.copy()
    left["station_key"] = left["stasiun"].map(canonical_station)

    station_ref = stations.copy()
    station_ref["station_key"] = station_ref["code"].map(canonical_station)
    station_ref["aliases"] = station_ref["aliases"].fillna("")
    aliases = station_ref[["station_key", "aliases"]].assign(
        alias_key=station_ref["aliases"].str.split("|")
    ).explode("alias_key")
    aliases["alias_key"] = aliases["alias_key"].map(canonical_station)
    aliases = aliases.loc[aliases["alias_key"].ne("")]
    alias_lookup = dict(zip(aliases["alias_key"], aliases["station_key"]))
    left["station_key"] = left["station_key"].map(lambda key: alias_lookup.get(key, key))

    merged = left.merge(
        station_ref.drop(columns="aliases"),
        on="station_key",
        how="left",
        validate="many_to_one",
    )
    merged["nama_stasiun_sumber"] = merged["stasiun"]
    merged["stasiun"] = merged["name"].combine_first(merged["stasiun"])
    category_ref = categories.rename(columns={"label": "kategori_ref"})
    merged = merged.merge(
        category_ref,
        left_on="kategori",
        right_on="kategori_ref",
        how="left",
        validate="many_to_one",
    )
    return merged.drop(columns=["station_key", "kategori_ref"])
