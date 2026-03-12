from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import streamlit as st

from ebird_platform.settings import get_app_paths

APP_PATHS = get_app_paths()
DADOS_DIR = APP_PATHS.data_dir
ANALITICA_DIR = APP_PATHS.analitica_dir
DIMENSAO_DIR = APP_PATHS.dimensao_dir
OURO_DIR = APP_PATHS.ouro_dir


def get_data_path(*parts: str) -> Path:
    return DADOS_DIR.joinpath(*parts)


def ensure_column(df: pd.DataFrame, candidates, final_name, default=None):
    if not isinstance(final_name, str) and isinstance(candidates, str):
        default = final_name if default is None else default
        final_name = candidates
        candidates = [candidates]

    if isinstance(candidates, str):
        candidates = [candidates]
    else:
        candidates = list(candidates)

    if isinstance(final_name, str) and final_name in df.columns:
        return df

    for candidate in candidates:
        if isinstance(candidate, str) and candidate in df.columns:
            return df.rename(columns={candidate: final_name})

    df[final_name] = default
    return df


def harmonize_pais_iso3(df: pd.DataFrame, default="UNK"):
    pais_cols = [col for col in df.columns if "pais_iso3" in col]

    if not pais_cols:
        df["pais_iso3"] = default
        return df

    if "pais_iso3" not in df.columns:
        df["pais_iso3"] = None

    for col in pais_cols:
        df["pais_iso3"] = df["pais_iso3"].fillna(df[col])

    for col in pais_cols:
        if col != "pais_iso3":
            df = df.drop(columns=[col], errors="ignore")

    df["pais_iso3"] = df["pais_iso3"].fillna(default)
    return df


@st.cache_data(show_spinner=False)
def load_dim_estado_conesul() -> gpd.GeoDataFrame:
    path = DIMENSAO_DIR / "dim_estado_latam.parquet"
    gdf = gpd.read_parquet(path)
    gdf = ensure_column(gdf, ["shapeName", "nome_uf", "nome"], "nome_estado", default="(sem nome)")
    gdf = harmonize_pais_iso3(gdf)

    if "id_estado" not in gdf.columns:
        if "id" in gdf.columns:
            gdf = gdf.rename(columns={"id": "id_estado"})
        else:
            gdf = ensure_column(gdf, ["shapeID"], "id_estado", default=None)

    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    return gdf


@st.cache_data(show_spinner=False)
def load_dim_municipio_conesul() -> gpd.GeoDataFrame:
    path = DIMENSAO_DIR / "dim_municipio_latam.parquet"
    gdf = gpd.read_parquet(path)
    gdf = ensure_column(gdf, ["shapeName", "nome_mun", "nome"], "nome_municipio", default="(sem nome)")
    gdf = harmonize_pais_iso3(gdf)

    if "id_municipio" not in gdf.columns:
        if "id" in gdf.columns:
            gdf = gdf.rename(columns={"id": "id_municipio"})
        else:
            gdf = ensure_column(gdf, ["shapeID"], "id_municipio", default=None)

    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    return gdf


def load_diversidade_municipio_conesul() -> pd.DataFrame:
    path_pref = ANALITICA_DIR / "diversidade_municipio_latam_v3.parquet"
    path_legado = ANALITICA_DIR / "diversidade_municipio_conesul_v3.parquet"

    if path_pref.exists():
        path = path_pref
    elif path_legado.exists():
        path = path_legado
    else:
        raise FileNotFoundError(f"Nao encontrei diversidade de municipios em: {path_pref} ou {path_legado}")

    df = pd.read_parquet(path)
    if "id_municipio" not in df.columns:
        raise ValueError(f"{path.name} precisa da coluna 'id_municipio'.")

    df = harmonize_pais_iso3(df)

    if "n_registros" not in df.columns:
        df["n_registros"] = 0

    if "n_especies_distintas" not in df.columns:
        df = ensure_column(df, ["richness", "n_especies", "species_richness"], "n_especies_distintas", default=0)

    df["n_registros"] = pd.to_numeric(df["n_registros"], errors="coerce").fillna(0)
    df["n_especies_distintas"] = pd.to_numeric(df["n_especies_distintas"], errors="coerce").fillna(0)

    return (
        df.groupby(["id_municipio", "pais_iso3"], as_index=False)
        .agg(
            n_registros=("n_registros", "sum"),
            n_especies_distintas=("n_especies_distintas", "max"),
        )
    )


def load_diversidade_estado_conesul_appstyle() -> pd.DataFrame:
    base = ANALITICA_DIR
    path_pref = base / "diversidade_estado_latam_appstyle.parquet"
    run_glob = "diversidade_estado_latam_appstyle__run_*.parquet"
    path_legado = base / "diversidade_estado_latam_appstyle__run_20251224_000720.parquet"

    if path_pref.exists():
        path = path_pref
    else:
        runs = sorted(base.glob(run_glob), key=lambda p: p.stat().st_mtime, reverse=True)
        if runs:
            path = runs[0]
        elif path_legado.exists():
            path = path_legado
        else:
            raise FileNotFoundError(
                f"Nao encontrei diversidade de estados em: {path_pref}, {run_glob} ou {path_legado}"
            )

    df = pd.read_parquet(path)
    df = harmonize_pais_iso3(df)

    if "id_estado" not in df.columns:
        raise ValueError(f"{path.name} precisa da coluna 'id_estado'.")

    if "n_registros_total" not in df.columns:
        if "n_registros" in df.columns:
            df = df.rename(columns={"n_registros": "n_registros_total"})
        else:
            df["n_registros_total"] = 0

    if "n_especies_distintas_max_municipio" not in df.columns:
        df = ensure_column(
            df,
            ["n_especies_distintas", "n_especies", "richness"],
            "n_especies_distintas_max_municipio",
            default=0,
        )

    if "id_municipio_max" not in df.columns:
        df["id_municipio_max"] = pd.NA

    cols = [
        "pais_iso3",
        "id_estado",
        "n_registros_total",
        "n_especies_distintas_max_municipio",
        "id_municipio_max",
    ]
    cols = [col for col in cols if col in df.columns]
    return df[cols].drop_duplicates(subset=["pais_iso3", "id_estado"])


@st.cache_data(show_spinner=False)
def load_map_municipio_estado_conesul() -> pd.DataFrame:
    path_v2 = OURO_DIR / "map_municipio_estado_latam_v2.parquet"
    path_v1 = OURO_DIR / "map_municipio_estado_latam.parquet"

    if path_v2.exists():
        path = path_v2
    elif path_v1.exists():
        path = path_v1
    else:
        raise FileNotFoundError(
            f"Nao encontrei nenhum arquivo de mapa municipio->estado em:\n- {path_v2}\n- {path_v1}"
        )

    df = pd.read_parquet(path)
    needed = {"id_municipio", "id_estado"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} precisa de {needed}, mas faltam: {missing}")

    return df[["id_municipio", "id_estado"]].drop_duplicates()


@st.cache_data(show_spinner=False)
def load_diversidade_cidade_total() -> pd.DataFrame:
    return pd.read_parquet(ANALITICA_DIR / "diversidade_cidade_total.parquet")


@st.cache_data(show_spinner=False)
def load_diversidade_cidade_tempo() -> pd.DataFrame:
    return pd.read_parquet(ANALITICA_DIR / "diversidade_cidade_tempo.parquet")


@st.cache_data(show_spinner=False)
def load_cubo_cidade_especie_total() -> pd.DataFrame:
    df = pd.read_parquet(ANALITICA_DIR / "cubo_cidade_especie_total.parquet")

    if "n_registros" not in df.columns:
        for alt in ["count", "n", "n_observacoes", "total_registros", "n_registros_total"]:
            if alt in df.columns:
                df = df.rename(columns={alt: "n_registros"})
                break

    if "scientificName" not in df.columns:
        for alt in ["taxon_name", "acceptedScientificName", "species", "nome_cientifico"]:
            if alt in df.columns:
                df = df.rename(columns={alt: "scientificName"})
                break

    needed = {"countryCode", "stateProvince", "county", "scientificName", "n_registros"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(
            f"cubo_cidade_especie_total.parquet esta faltando colunas: {sorted(missing)}. "
            f"Colunas disponiveis: {list(df.columns)}"
        )

    return df


@st.cache_data(show_spinner=False)
def load_map_cidade_ebird_municipio() -> pd.DataFrame:
    return pd.read_parquet(DIMENSAO_DIR / "map_cidade_ebird_municipio_latam_v2.parquet")
