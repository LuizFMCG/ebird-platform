from __future__ import annotations

import folium
import geopandas as gpd
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from ebird_platform.io.loaders import (
    harmonize_pais_iso3,
    load_cubo_cidade_especie_total,
    load_dim_estado_conesul,
    load_dim_municipio_conesul,
    load_diversidade_estado_conesul_appstyle,
    load_diversidade_municipio_conesul,
    load_map_cidade_ebird_municipio,
)

ISO3_TO_ISO2 = {
    "ARG": "AR",
    "BOL": "BO",
    "BRA": "BR",
    "CHL": "CL",
    "COL": "CO",
    "ECU": "EC",
    "GUY": "GY",
    "GUF": "GF",
    "PRY": "PY",
    "PER": "PE",
    "SUR": "SR",
    "URY": "UY",
    "VEN": "VE",
    "PAN": "PA",
    "MEX": "MX",
    "BLZ": "BZ",
    "GTM": "GT",
    "HND": "HN",
    "SLV": "SV",
    "NIC": "NI",
    "CRI": "CR",
    "CUB": "CU",
    "DOM": "DO",
    "HTI": "HT",
    "PRI": "PR",
}


def _norm_txt(x: object) -> str:
    import re
    import unicodedata

    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = str(x).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


@st.cache_data(show_spinner=False)
def compute_diversidade_estado_from_cubo(pais_iso3: str) -> pd.DataFrame:
    iso2 = ISO3_TO_ISO2.get(pais_iso3)
    if not iso2:
        return pd.DataFrame(columns=[
            "pais_iso3", "id_estado", "n_registros_total",
            "n_especies_distintas_max_municipio", "id_municipio_max"
        ])

    cubo = load_cubo_cidade_especie_total()
    df = cubo[cubo["countryCode"] == iso2].copy()
    if df.empty:
        return pd.DataFrame(columns=[
            "pais_iso3", "id_estado", "n_registros_total",
            "n_especies_distintas_max_municipio", "id_municipio_max"
        ])

    df = df.dropna(subset=["stateProvince", "scientificName"]).copy()
    df["n_registros"] = pd.to_numeric(df["n_registros"], errors="coerce").fillna(0)

    st_sp = (
        df.groupby(["stateProvince", "scientificName"], as_index=False)
          .agg(n_registros=("n_registros", "sum"))
    )
    st_tot = (
        st_sp.groupby(["stateProvince"], as_index=False)
             .agg(n_registros_total=("n_registros", "sum"))
    )
    st_rich = (
        st_sp[st_sp["n_registros"] > 0]
        .groupby(["stateProvince"], as_index=False)
        .agg(n_especies=("scientificName", "nunique"))
    )

    met = st_tot.merge(st_rich, on="stateProvince", how="left")
    met["n_especies"] = met["n_especies"].fillna(0).astype(int)
    met["k"] = met["stateProvince"].map(_norm_txt)

    dim_est = load_dim_estado_conesul()
    dim_p = dim_est[dim_est["pais_iso3"] == pais_iso3][["id_estado", "pais_iso3", "nome_estado"]].drop_duplicates().copy()
    if dim_p.empty:
        return pd.DataFrame(columns=[
            "pais_iso3", "id_estado", "n_registros_total",
            "n_especies_distintas_max_municipio", "id_municipio_max"
        ])

    dim_p["k"] = dim_p["nome_estado"].map(_norm_txt)
    dim_key_to_id = dict(zip(dim_p["k"], dim_p["id_estado"]))
    dim_keys = list(dim_key_to_id.keys())

    def _map_to_id(k: str) -> int | None:
        if not k:
            return None
        if k in dim_key_to_id:
            return dim_key_to_id[k]
        cand = []
        for dk in dim_keys:
            if dk.startswith(k) or k.startswith(dk):
                cand.append((abs(len(dk) - len(k)), len(dk), dk))
        if not cand:
            return None
        _, _, best = sorted(cand)[0]
        return dim_key_to_id.get(best)

    met["id_estado"] = met["k"].apply(_map_to_id)
    met = met.dropna(subset=["id_estado"]).copy()
    if met.empty:
        return pd.DataFrame(columns=[
            "pais_iso3", "id_estado", "n_registros_total",
            "n_especies_distintas_max_municipio", "id_municipio_max"
        ])

    met["id_estado"] = met["id_estado"].astype(int)
    met["pais_iso3"] = pais_iso3
    out = met[["pais_iso3", "id_estado", "n_registros_total"]].copy()
    out["n_especies_distintas_max_municipio"] = met["n_especies"].astype(int).values
    out["id_municipio_max"] = pd.NA
    return out


@st.cache_data(show_spinner=False)
def compute_diversidade_municipio_from_cubo(pais_iso3: str) -> pd.DataFrame:
    iso2 = ISO3_TO_ISO2.get(pais_iso3)
    if not iso2:
        return pd.DataFrame(columns=["id_municipio", "pais_iso3", "n_registros", "n_especies_distintas"])

    cubo = load_cubo_cidade_especie_total()
    df = cubo[cubo["countryCode"] == iso2].copy()
    if df.empty:
        return pd.DataFrame(columns=["id_municipio", "pais_iso3", "n_registros", "n_especies_distintas"])

    mapa = load_map_cidade_ebird_municipio()
    if mapa.empty:
        return pd.DataFrame(columns=["id_municipio", "pais_iso3", "n_registros", "n_especies_distintas"])

    if "pais_iso3" in mapa.columns:
        mapa_p = mapa[mapa["pais_iso3"] == pais_iso3].copy()
    else:
        mapa_p = mapa[mapa["countryCode"] == iso2].copy() if "countryCode" in mapa.columns else mapa.copy()

    if mapa_p.empty:
        return pd.DataFrame(columns=["id_municipio", "pais_iso3", "n_registros", "n_especies_distintas"])

    df["n_registros"] = pd.to_numeric(df["n_registros"], errors="coerce").fillna(0)
    cols_map = [c for c in ["countryCode", "stateProvince", "county", "id_municipio"] if c in mapa_p.columns]
    mapa_slim = mapa_p[cols_map].drop_duplicates().copy()

    dfj = df.merge(mapa_slim, on=["countryCode", "stateProvince", "county"], how="left")
    dfj = dfj[dfj["id_municipio"].notna()].copy()
    if dfj.empty:
        return pd.DataFrame(columns=["id_municipio", "pais_iso3", "n_registros", "n_especies_distintas"])

    dfj = dfj.dropna(subset=["scientificName"]).copy()

    mun_sp = (
        dfj.groupby(["id_municipio", "scientificName"], as_index=False)
           .agg(n_registros=("n_registros", "sum"))
    )
    mun_tot = (
        mun_sp.groupby(["id_municipio"], as_index=False)
              .agg(n_registros=("n_registros", "sum"))
    )
    mun_rich = (
        mun_sp[mun_sp["n_registros"] > 0]
        .groupby(["id_municipio"], as_index=False)
        .agg(n_especies_distintas=("scientificName", "nunique"))
    )

    out = mun_tot.merge(mun_rich, on="id_municipio", how="left")
    out["n_especies_distintas"] = out["n_especies_distintas"].fillna(0).astype(int)
    out["pais_iso3"] = pais_iso3

    try:
        out["id_municipio"] = out["id_municipio"].astype(int)
    except Exception:
        pass

    return out[["id_municipio", "pais_iso3", "n_registros", "n_especies_distintas"]]


def construir_gdf_municipio_para_mapa(pais_iso3: str) -> gpd.GeoDataFrame:
    dim_mun = load_dim_municipio_conesul()
    div_mun = load_diversidade_municipio_conesul()
    div_p = div_mun[div_mun["pais_iso3"] == pais_iso3].copy()

    try:
        sum_rich = div_p["n_especies_distintas"].fillna(0).sum() if "n_especies_distintas" in div_p.columns else 0
        sum_reg = div_p["n_registros"].fillna(0).sum() if "n_registros" in div_p.columns else 0
    except Exception:
        sum_rich, sum_reg = 0, 0

    if div_p.empty or (sum_rich == 0 and sum_reg == 0):
        div_fb = compute_diversidade_municipio_from_cubo(pais_iso3)
        if not div_fb.empty:
            div_p = div_fb.copy()

    gdf_m = dim_mun[dim_mun["pais_iso3"] == pais_iso3].copy()
    if gdf_m.empty:
        return gdf_m

    gdf = gdf_m.merge(div_p, on=["id_municipio", "pais_iso3"], how="left")
    gdf = harmonize_pais_iso3(gdf)
    gdf["n_especies_distintas"] = gdf["n_especies_distintas"].fillna(0)
    gdf["n_registros"] = gdf["n_registros"].fillna(0)

    cols = ["id_municipio", "nome_municipio", "pais_iso3", "n_especies_distintas", "n_registros", "geometry"]
    cols = [c for c in cols if c in gdf.columns]
    gdf = gdf[cols].copy()

    if not gdf.empty:
        gdf["geometry"] = gdf["geometry"].simplify(0.01, preserve_topology=True)

    return gdf


def construir_gdf_estado_para_mapa(pais_iso3: str) -> gpd.GeoDataFrame:
    dim_est = load_dim_estado_conesul()
    df_est = load_diversidade_estado_conesul_appstyle()

    gdf_est = dim_est[dim_est["pais_iso3"] == pais_iso3].copy()
    df_est = df_est[df_est["pais_iso3"] == pais_iso3].copy()

    try:
        sum_rich = df_est["n_especies_distintas_max_municipio"].fillna(0).sum() if "n_especies_distintas_max_municipio" in df_est.columns else 0
        sum_reg = df_est["n_registros_total"].fillna(0).sum() if "n_registros_total" in df_est.columns else 0
    except Exception:
        sum_rich, sum_reg = 0, 0

    if df_est.empty or (sum_rich == 0 and sum_reg == 0):
        df_fb = compute_diversidade_estado_from_cubo(pais_iso3)
        if not df_fb.empty:
            df_est = df_fb.copy()

    gdf = gdf_est.merge(df_est, on=["pais_iso3", "id_estado"], how="left")
    gdf = harmonize_pais_iso3(gdf)
    gdf["n_especies_distintas_max_municipio"] = gdf["n_especies_distintas_max_municipio"].fillna(0)
    gdf["n_registros_total"] = gdf["n_registros_total"].fillna(0)

    cols = [
        "id_estado",
        "nome_estado",
        "pais_iso3",
        "n_registros_total",
        "n_especies_distintas_max_municipio",
        "id_municipio_max",
        "geometry",
    ]
    cols = [c for c in cols if c in gdf.columns]
    gdf = gdf[cols].copy()

    if not gdf.empty:
        gdf["geometry"] = gdf["geometry"].simplify(0.01, preserve_topology=True)

    return gdf


def desenhar_mapa_conesul() -> None:
    st.subheader("Mapa territorial — riqueza de espécies por Estado/Município")
    st.caption("Selecione países e a escala territorial para visualizar a riqueza de espécies com base em registros do eBird.")

    paises_sulamerica = ["ARG", "BOL", "BRA", "CHL", "COL", "ECU", "GUY", "GUF", "PRY", "PER", "SUR", "URY", "VEN"]
    pais_label_map = {
        "ARG": "Argentina",
        "BOL": "Bolívia",
        "BRA": "Brasil",
        "CHL": "Chile",
        "COL": "Colômbia",
        "ECU": "Equador",
        "GUY": "Guiana",
        "GUF": "Guiana Francesa",
        "PRY": "Paraguai",
        "PER": "Peru",
        "SUR": "Suriname",
        "URY": "Uruguai",
        "VEN": "Venezuela",
    }

    dim_est = load_dim_estado_conesul()
    dim_mun = load_dim_municipio_conesul()
    paises_disponiveis = sorted(set(dim_est["pais_iso3"].dropna().unique()) | set(dim_mun["pais_iso3"].dropna().unique()))
    paises_permitidos = [p for p in paises_sulamerica if p in paises_disponiveis]

    if not paises_permitidos:
        st.error("Não encontrei países da América do Sul nas dimensões territoriais (coluna pais_iso3).")
        return

    paises_sel = st.multiselect(
        "Países",
        options=paises_permitidos,
        default=(["BRA"] if "BRA" in paises_permitidos else [paises_permitidos[0]]),
        format_func=lambda x: pais_label_map.get(x, x),
    )
    nivel = st.radio("Escala territorial", options=["Estados", "Municípios"], horizontal=True)

    paises_est_set = set(dim_est["pais_iso3"].dropna().unique())
    paises_mun_set = set(dim_mun["pais_iso3"].dropna().unique())

    if nivel == "Municípios":
        missing = [p for p in paises_sel if p not in paises_mun_set]
        if missing:
            st.warning("Sem geometria municipal para: " + ", ".join(missing) + ". Eles serão ignorados no mapa de municípios.")
        paises_sel = [p for p in paises_sel if p in paises_mun_set]
    else:
        missing = [p for p in paises_sel if p not in paises_est_set]
        if missing:
            st.warning("Sem geometria estadual para: " + ", ".join(missing) + ". Eles serão ignorados no mapa de estados.")
        paises_sel = [p for p in paises_sel if p in paises_est_set]

    if not paises_sel:
        st.warning("Selecione ao menos um país.")
        return

    if nivel == "Municípios":
        gdfs = [construir_gdf_municipio_para_mapa(p) for p in paises_sel]
        gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs="EPSG:4326")
        metric_col = "n_especies_distintas"
        nome_col = "nome_municipio"
        id_col = "id_municipio"
        tooltip_aliases = ["Município:", "Riqueza (nº de espécies):"]
    else:
        gdfs = [construir_gdf_estado_para_mapa(p) for p in paises_sel]
        gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs="EPSG:4326")
        metric_col = "n_especies_distintas_max_municipio"
        nome_col = "nome_estado"
        id_col = "id_estado"
        tooltip_aliases = ["Estado:", "Riqueza máxima (municípios):"]

    if gdf.empty:
        st.warning("Não há dados para o país/escala selecionados.")
        return

    if metric_col not in gdf.columns:
        st.error(f"Coluna de métrica '{metric_col}' não encontrada no GeoDataFrame.")
        st.write("Colunas disponíveis:", list(gdf.columns))
        return

    try:
        centroid = gdf.geometry.union_all().centroid
        center_lat, center_lon = centroid.y, centroid.x
    except Exception:
        center_lat, center_lon = 0.0, 0.0

    m = folium.Map(location=[center_lat, center_lon], zoom_start=4, tiles=None, max_bounds=True)
    folium.TileLayer("cartodbpositron", name="Base", control=False, no_wrap=True).add_to(m)

    try:
        minx, miny, maxx, maxy = gdf.to_crs(epsg=4326).total_bounds
        m.fit_bounds([[miny, minx], [maxy, maxx]])
    except Exception:
        pass

    vals = pd.to_numeric(gdf[metric_col], errors="coerce").fillna(0.0)
    vmax = float(vals.max())
    vals_pos = vals[vals > 0]
    if len(vals_pos) > 0:
        vmin_color = float(np.percentile(vals_pos, 5))
        if vmin_color <= 0:
            vmin_color = float(vals_pos.min())
    else:
        vmin_color = 0.0

    if vmax <= vmin_color:
        vmax = vmin_color + 1.0

    import branca.colormap as cm
    colormap = cm.linear.Blues_09.scale(vmin_color, vmax)
    gdf_plot = gdf[[id_col, nome_col, metric_col, "geometry"]].copy().to_crs(epsg=4326)

    geojson = folium.GeoJson(
        gdf_plot.to_json(),
        name="territorio",
        style_function=lambda feature: {
            "fillColor": (
                "#e6e6e6"
                if (feature["properties"][metric_col] is None or feature["properties"][metric_col] == 0)
                else colormap(max(float(feature["properties"][metric_col]), vmin_color))
            ),
            "color": "black",
            "weight": 0.4,
            "fillOpacity": 0.7,
        },
        tooltip=folium.GeoJsonTooltip(fields=[nome_col, metric_col], aliases=tooltip_aliases, localize=True),
    )

    geojson.add_to(m)
    colormap.add_to(m)
    st_folium(m, width=None, height=600, key="map_conesul", returned_objects=[])
