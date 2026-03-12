# app_streamlit_v2.py
# ---------------------------------------------------------
# Projeto eBird – Cone Sul (v2)
#
# Estrutura:
#   1) Mapa territorial Cone Sul (Estado/Município)
#   2) Análise informacional por cidade (versão original),
#      agora integrada com a dimensão de mapeamento
#      cidade eBird -> município territorial.
#
# Sem aba de "Exploração local".
# ---------------------------------------------------------

from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import streamlit as st
import altair as alt
import folium
import base64
import matplotlib.pyplot as plt
import html
import streamlit.components.v1 as components
from matplotlib.patches import Circle
from streamlit_folium import st_folium

from ebird_platform.app.ecological_analysis import render_ecological_analysis
from ebird_platform.app.similarity_analysis import render_similarity_analysis
from ebird_platform.app.territorial_map import desenhar_mapa_conesul as render_territorial_map
from ebird_platform.app.temporal_analysis import render_temporal_analysis


# ---------------------------------------------------------
# Configuração básica
# ---------------------------------------------------------

from pathlib import Path

from ebird_platform.io import loaders as data_loaders
from ebird_platform.settings import get_app_paths

APP_PATHS = get_app_paths()
BASE_DIR = APP_PATHS.project_root
ICON_PATH = APP_PATHS.icon_path

st.set_page_config(
    page_title="Biodiversidade de aves — análise geoespacial (eBird)",
    page_icon=str(ICON_PATH),  # ícone da aba (favicon)
    layout="wide",
)

DADOS_DIR = APP_PATHS.data_dir
ANALITICA_DIR = APP_PATHS.analitica_dir
DIMENSAO_DIR = APP_PATHS.dimensao_dir
OURO_DIR = APP_PATHS.ouro_dir

def set_bg_image(image_path: Path, overlay_alpha: float = 0.70):
    if not image_path.exists():
        st.warning(f"Imagem de fundo não encontrada: {image_path}")
        return

    b64 = base64.b64encode(image_path.read_bytes()).decode()

    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image:
              linear-gradient(rgba(0,0,0,{overlay_alpha}), rgba(0,0,0,{overlay_alpha})),
              url("data:image/jpeg;base64,{b64}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}

        [data-testid="stAppViewContainer"] {{
            background-image:
              linear-gradient(rgba(0,0,0,{overlay_alpha}), rgba(0,0,0,{overlay_alpha})),
              url("data:image/jpeg;base64,{b64}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}

        /* remove fundo sólido do header pra aparecer a imagem */
        [data-testid="stHeader"] {{
            background: rgba(0,0,0,0);
        }}

        /* sidebar levemente translúcida */
        [data-testid="stToolbar"] {{
            background: rgba(0,0,0,0);
        }}

        [data-testid="stSidebar"] > div:first-child {{
            background: rgba(0,0,0,0.55);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

BG_PATH = APP_PATHS.background_path
set_bg_image(BG_PATH, overlay_alpha=0.70)

# ---------------------------------------------------------
# Funções utilitárias
# ---------------------------------------------------------

def ensure_column(df: pd.DataFrame, candidates, final_name, default=None):
    """
    Garante que exista uma coluna `final_name` no df.

    Compatibilidade:
    - Forma correta: ensure_column(df, candidates, final_name, default=None)
    - Se alguém chamar errado (ex.: ensure_column(df, "pais_iso3", df.get("pais_iso3"))),
      tentamos corrigir automaticamente para evitar TypeError (unhashable Series).
    """
    # Corrige chamada invertida onde final_name vira Series/Index/array
    if not isinstance(final_name, str) and isinstance(candidates, str):
        # Interpreta como: ensure_column(df, <final_name_str>, <default_series>)
        default = final_name if default is None else default
        final_name = candidates
        candidates = [candidates]

    if isinstance(candidates, str):
        candidates = [candidates]
    else:
        candidates = list(candidates)

    if isinstance(final_name, str) and final_name in df.columns:
        return df

    for c in candidates:
        if isinstance(c, str) and c in df.columns:
            df = df.rename(columns={c: final_name})
            return df

    df[final_name] = default
    return df

def harmonize_pais_iso3(df: pd.DataFrame, default="UNK"):
    """Cria/normaliza coluna pais_iso3 (pode vir duplicada do merge)."""
    pais_cols = [c for c in df.columns if "pais_iso3" in c]

    if not pais_cols:
        df["pais_iso3"] = default
        return df

    # Usa a primeira coluna não nula disponível
    if "pais_iso3" not in df.columns:
        df["pais_iso3"] = None

    for c in pais_cols:
        df["pais_iso3"] = df["pais_iso3"].fillna(df[c])

    # Remove demais colunas auxiliares
    for c in pais_cols:
        if c != "pais_iso3":
            df = df.drop(columns=[c], errors="ignore")

    df["pais_iso3"] = df["pais_iso3"].fillna(default)
    return df


# ---------------------------------------------------------
# Carregamento de dados – camada territorial (Cone Sul)
# ---------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_dim_estado_conesul() -> gpd.GeoDataFrame:
    path = DIMENSAO_DIR / "dim_estado_latam.parquet"
    gdf = gpd.read_parquet(path)

    # Garante nome de estado e pais_iso3
    gdf = ensure_column(gdf, ["shapeName", "nome_uf", "nome"], "nome_estado", default="(sem nome)")
    gdf = harmonize_pais_iso3(gdf)
    # Garante id_estado
    if "id_estado" not in gdf.columns:
        # Preferimos o id canônico (scripts 15/16 criam id_estado como inteiro)
        if "id" in gdf.columns:
            gdf = gdf.rename(columns={"id": "id_estado"})
        else:
            # fallback: usa shapeID como id se necessário
            gdf = ensure_column(gdf, ["shapeID"], "id_estado", default=None)

    # Garante CRS geográfico
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    return gdf


@st.cache_data(show_spinner=False)
def load_dim_municipio_conesul() -> gpd.GeoDataFrame:
    path = DIMENSAO_DIR / "dim_municipio_latam.parquet"
    gdf = gpd.read_parquet(path)

    # Garante nome de município e pais_iso3
    gdf = ensure_column(gdf, ["shapeName", "nome_mun", "nome"], "nome_municipio", default="(sem nome)")
    gdf = harmonize_pais_iso3(gdf)
    # Garante id_municipio
    if "id_municipio" not in gdf.columns:
        # Preferimos o id canônico (scripts 15/16 criam id_municipio como inteiro)
        if "id" in gdf.columns:
            gdf = gdf.rename(columns={"id": "id_municipio"})
        else:
            # fallback: usa shapeID como id se necessário
            gdf = ensure_column(gdf, ["shapeID"], "id_municipio", default=None)

    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    return gdf


# ⚠️ Sem cache aqui de propósito para sempre ler a versão mais nova
#    de diversidade_municipio_conesul_x gerada pelos scripts.
# ⚠️ Sem cache aqui de propósito para sempre ler a versão mais nova
#    de diversidade_municipio_* gerada pelos scripts.
def load_diversidade_municipio_conesul() -> pd.DataFrame:
    # Preferimos a versão LATAM/SulAmérica (v3). Mantemos fallback para legado Cone Sul.
    path_pref = ANALITICA_DIR / "diversidade_municipio_latam_v3.parquet"
    path_legado = ANALITICA_DIR / "diversidade_municipio_conesul_v3.parquet"

    if path_pref.exists():
        path = path_pref
    elif path_legado.exists():
        path = path_legado
    else:
        raise FileNotFoundError(f"Não encontrei diversidade de municípios em: {path_pref} ou {path_legado}")

    df = pd.read_parquet(path)

    # Garante colunas essenciais
    if "id_municipio" not in df.columns:
        raise ValueError(f"{path.name} precisa da coluna 'id_municipio'.")

    df = harmonize_pais_iso3(df)

    if "n_registros" not in df.columns:
        df["n_registros"] = 0

    if "n_especies_distintas" not in df.columns:
        # fallback: se existir richness ou semelhante
        df = ensure_column(df, ["richness", "n_especies", "species_richness"], "n_especies_distintas", default=0)

    # uma linha por (id_municipio, pais_iso3)
    df["n_registros"] = pd.to_numeric(df["n_registros"], errors="coerce").fillna(0)
    df["n_especies_distintas"] = pd.to_numeric(df["n_especies_distintas"], errors="coerce").fillna(0)

    return (
        df.groupby(["id_municipio", "pais_iso3"], as_index=False)
          .agg(n_registros=("n_registros", "sum"),
               n_especies_distintas=("n_especies_distintas", "max"))
    )

# ⚠️ Sem cache aqui de propósito para sempre ler a versão mais nova
#    de diversidade_estado_conesul_appstyle gerada pelo script 23.
# ⚠️ Sem cache aqui de propósito para sempre ler a versão mais nova
#    de diversidade_estado_* gerada pelo script 23.
def load_diversidade_estado_conesul_appstyle() -> pd.DataFrame:
    base = ANALITICA_DIR

    # Preferidos (LATAM/SulAmérica)
    path_pref = base / "diversidade_estado_latam_appstyle.parquet"
    run_glob = "diversidade_estado_latam_appstyle__run_*.parquet"

    # Legado Cone Sul
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
                f"Não encontrei diversidade de estados em: {path_pref}, {run_glob} ou {path_legado}"
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
        # compat: alguns arquivos podem chamar diferente
        df = ensure_column(df, ["n_especies_distintas", "n_especies", "richness"], "n_especies_distintas_max_municipio", default=0)

    if "id_municipio_max" not in df.columns:
        df["id_municipio_max"] = pd.NA

    cols = [
        "pais_iso3",
        "id_estado",
        "n_registros_total",
        "n_especies_distintas_max_municipio",
        "id_municipio_max",
    ]
    cols = [c for c in cols if c in df.columns]
    return df[cols].drop_duplicates(subset=["pais_iso3", "id_estado"])

@st.cache_data(show_spinner=False)
def load_map_municipio_estado_conesul() -> pd.DataFrame:
    """
    Carrega o mapa município → estado.

    Tenta primeiro a versão canônica v2; se não existir, cai para a versão antiga.
    (Hoje essa função não é usada no cálculo do mapa de estados, mas fica
    disponível para diagnósticos futuros.)
    """
    path_v2 = OURO_DIR / "map_municipio_estado_latam_v2.parquet"
    path_v1 = OURO_DIR / "map_municipio_estado_latam.parquet"

    if path_v2.exists():
        path = path_v2
    elif path_v1.exists():
        path = path_v1
    else:
        raise FileNotFoundError(
            f"Não encontrei nenhum arquivo de mapa município→estado em:\n"
            f"- {path_v2}\n"
            f"- {path_v1}"
        )

    df = pd.read_parquet(path)

    # tenta garantir colunas básicas
    needed = {"id_municipio", "id_estado"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} precisa de {needed}, mas faltam: {missing}")

    return df[["id_municipio", "id_estado"]].drop_duplicates()


# ---------------------------------------------------------
# Carregamento de dados – análise informacional por cidade
# ---------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_diversidade_cidade_total() -> pd.DataFrame:
    path = ANALITICA_DIR / "diversidade_cidade_total.parquet"
    df = pd.read_parquet(path)
    return df


@st.cache_data(show_spinner=False)
def load_diversidade_cidade_tempo() -> pd.DataFrame:
    path = ANALITICA_DIR / "diversidade_cidade_tempo.parquet"
    df = pd.read_parquet(path)
    return df


@st.cache_data(show_spinner=False)
def load_cubo_cidade_especie_total() -> pd.DataFrame:
    path = ANALITICA_DIR / "cubo_cidade_especie_total.parquet"
    df = pd.read_parquet(path)

    # ---------------------------------------------------------
    # Compatibilidade de schema (evita KeyError no app)
    # O script 21 (Spark) grava o nome da espécie como 'taxon_name'.
    # Este app usa 'scientificName' (padrão eBird / legado do projeto).
    # ---------------------------------------------------------
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
            f"cubo_cidade_especie_total.parquet está faltando colunas: {sorted(missing)}. "
            f"Colunas disponíveis: {list(df.columns)}"
        )

    return df


@st.cache_data(show_spinner=False)
def load_map_cidade_ebird_municipio() -> pd.DataFrame:
    """
    Dimensão de mapeamento entre cidades eBird (countryCode/stateProvince/county)
    e municípios territoriais (id_municipio, nome_municipio, etc.).

    Agora usando a versão v2, construída a partir do map_ponto_municipio_conesul_v2
    com IDs de município alinhados à dimensão canônica.
    """
    path = DIMENSAO_DIR / "map_cidade_ebird_municipio_latam_v2.parquet"
    df = pd.read_parquet(path)
    return df


get_data_path = data_loaders.get_data_path
ensure_column = data_loaders.ensure_column
harmonize_pais_iso3 = data_loaders.harmonize_pais_iso3
load_dim_estado_conesul = data_loaders.load_dim_estado_conesul
load_dim_municipio_conesul = data_loaders.load_dim_municipio_conesul
load_diversidade_municipio_conesul = data_loaders.load_diversidade_municipio_conesul
load_diversidade_estado_conesul_appstyle = data_loaders.load_diversidade_estado_conesul_appstyle
load_map_municipio_estado_conesul = data_loaders.load_map_municipio_estado_conesul
load_diversidade_cidade_total = data_loaders.load_diversidade_cidade_total
load_diversidade_cidade_tempo = data_loaders.load_diversidade_cidade_tempo
load_cubo_cidade_especie_total = data_loaders.load_cubo_cidade_especie_total
load_map_cidade_ebird_municipio = data_loaders.load_map_cidade_ebird_municipio


# ---------------------------------------------------------
# Seção 1 – Mapa territorial Cone Sul
# ---------------------------------------------------------

def construir_gdf_municipio_para_mapa(pais_iso3: str) -> gpd.GeoDataFrame:
    dim_mun = load_dim_municipio_conesul()
    div_mun = load_diversidade_municipio_conesul()

    # Filtra só o país no DF de diversidade (mais barato)
    div_p = div_mun[div_mun["pais_iso3"] == pais_iso3].copy()

    # Fallback: se a diversidade por município estiver vazia/zerada nesse país,
    # tenta calcular direto do cubo (cidade×espécie) + mapa cidade->município.
    try:
        _sum_rich = div_p["n_especies_distintas"].fillna(0).sum() if "n_especies_distintas" in div_p.columns else 0
        _sum_reg = div_p["n_registros"].fillna(0).sum() if "n_registros" in div_p.columns else 0
    except Exception:
        _sum_rich, _sum_reg = 0, 0

    if div_p.empty or (_sum_rich == 0 and _sum_reg == 0):
        div_fb = compute_diversidade_municipio_from_cubo(pais_iso3)
        if not div_fb.empty:
            div_p = div_fb.copy()

    # Dimensão (geometrias) do país
    gdf_m = dim_mun[dim_mun["pais_iso3"] == pais_iso3].copy()

    # Se não existe geometria municipal para esse país, não dá para desenhar.
    if gdf_m.empty:
        return gdf_m  # vazio

    # Merge dimensão + diversidade
    gdf = gdf_m.merge(div_p, on=["id_municipio", "pais_iso3"], how="left")

    gdf = harmonize_pais_iso3(gdf)
    gdf["n_especies_distintas"] = gdf["n_especies_distintas"].fillna(0)
    gdf["n_registros"] = gdf["n_registros"].fillna(0)

    # Seleciona apenas colunas essenciais para o mapa
    cols = ["id_municipio", "nome_municipio", "pais_iso3",
            "n_especies_distintas", "n_registros", "geometry"]
    cols = [c for c in cols if c in gdf.columns]
    gdf = gdf[cols].copy()

    # Simplifica geometrias (para evitar MessageSizeError)
    if not gdf.empty:
        gdf["geometry"] = gdf["geometry"].simplify(0.01, preserve_topology=True)

    return gdf





# ---------------------------------------------------------
# Fallback de métricas por ESTADO direto do cubo (quando o
# pipeline município->estado não cobre bem um país).
# ---------------------------------------------------------

# Mapeamento ISO3 (geoBoundaries) -> ISO2 (eBird countryCode)
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
ISO2_TO_ISO3 = {v: k for k, v in ISO3_TO_ISO2.items()}


def _norm_txt(x: object) -> str:
    """
    Normaliza nomes (remove acentos, pontuação, normaliza espaços)
    para facilitar o match eBird stateProvince <-> geoBoundaries shapeName.
    """
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
    """
    Calcula métricas por estado direto do cubo:
      - n_registros_total (soma)
      - n_especies_distintas_max_municipio (aqui: riqueza por estado)
    e mapeia para id_estado via dim_estado_latam.
    """
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

    # Agrega por estado x espécie
    st_sp = (
        df.groupby(["stateProvince", "scientificName"], as_index=False)
          .agg(n_registros=("n_registros", "sum"))
    )

    # Total por estado
    st_tot = (
        st_sp.groupby(["stateProvince"], as_index=False)
             .agg(n_registros_total=("n_registros", "sum"))
    )

    # Riqueza por estado
    st_rich = (
        st_sp[st_sp["n_registros"] > 0]
        .groupby(["stateProvince"], as_index=False)
        .agg(n_especies=("scientificName", "nunique"))
    )

    met = st_tot.merge(st_rich, on="stateProvince", how="left")
    met["n_especies"] = met["n_especies"].fillna(0).astype(int)
    met["k"] = met["stateProvince"].map(_norm_txt)

    # Dimensão de estados do país (geoBoundaries)
    dim_est = load_dim_estado_conesul()
    dim_p = dim_est[dim_est["pais_iso3"] == pais_iso3][["id_estado", "pais_iso3", "nome_estado"]].drop_duplicates().copy()
    if dim_p.empty:
        return pd.DataFrame(columns=[
            "pais_iso3", "id_estado", "n_registros_total",
            "n_especies_distintas_max_municipio", "id_municipio_max"
        ])

    dim_p["k"] = dim_p["nome_estado"].map(_norm_txt)

    # Mapeia chaves com fallback por "prefixo" (ajuda quando eBird vem truncado)
    dim_key_to_id = dict(zip(dim_p["k"], dim_p["id_estado"]))
    dim_keys = list(dim_key_to_id.keys())

    def _map_to_id(k: str) -> int | None:
        if not k:
            return None
        if k in dim_key_to_id:
            return dim_key_to_id[k]
        # fallback: prefix match (dos dois lados)
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
    """
    Calcula métricas por município direto do cubo (cidade×espécie) usando
    o mapeamento cidade eBird -> id_municipio (map_cidade_ebird_municipio_latam_v2).

    Retorna:
      - pais_iso3
      - id_municipio
      - n_registros
      - n_especies_distintas
    """
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

    # Filtra o mapa por país (quando disponível)
    if "pais_iso3" in mapa.columns:
        mapa_p = mapa[mapa["pais_iso3"] == pais_iso3].copy()
    else:
        mapa_p = mapa[mapa["countryCode"] == iso2].copy() if "countryCode" in mapa.columns else mapa.copy()

    if mapa_p.empty:
        return pd.DataFrame(columns=["id_municipio", "pais_iso3", "n_registros", "n_especies_distintas"])

    df["n_registros"] = pd.to_numeric(df["n_registros"], errors="coerce").fillna(0)

    # Join cubo -> id_municipio
    cols_map = [c for c in ["countryCode", "stateProvince", "county", "id_municipio"] if c in mapa_p.columns]
    mapa_slim = mapa_p[cols_map].drop_duplicates().copy()

    dfj = df.merge(
        mapa_slim,
        on=["countryCode", "stateProvince", "county"],
        how="left",
    )

    dfj = dfj[dfj["id_municipio"].notna()].copy()
    if dfj.empty:
        return pd.DataFrame(columns=["id_municipio", "pais_iso3", "n_registros", "n_especies_distintas"])

    dfj = dfj.dropna(subset=["scientificName"]).copy()

    # Agrega por município x espécie
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

    # id_municipio como int quando possível
    try:
        out["id_municipio"] = out["id_municipio"].astype(int)
    except Exception:
        pass

    return out[["id_municipio", "pais_iso3", "n_registros", "n_especies_distintas"]]

def construir_gdf_estado_para_mapa(pais_iso3: str) -> gpd.GeoDataFrame:
    """
    Versão data-driven (sem recalcular sjoin no app):
    - Lê dim_estado_conesul (geometrias)
    - Lê diversidade_estado_conesul_appstyle.parquet (métricas prontas do script 23)
    - Faz merge e entrega o GDF final para o mapa
    """
    dim_est = load_dim_estado_conesul()
    df_est = load_diversidade_estado_conesul_appstyle()

    # Filtra país
    gdf_est = dim_est[dim_est["pais_iso3"] == pais_iso3].copy()
    df_est = df_est[df_est["pais_iso3"] == pais_iso3].copy()

    # Fallback: se o appstyle não cobre bem esse país (ou veio zerado),
    # calcula métricas direto do cubo e tenta casar com geoBoundaries (dim_estado).
    try:
        _sum_rich = df_est["n_especies_distintas_max_municipio"].fillna(0).sum() if "n_especies_distintas_max_municipio" in df_est.columns else 0
        _sum_reg = df_est["n_registros_total"].fillna(0).sum() if "n_registros_total" in df_est.columns else 0
    except Exception:
        _sum_rich, _sum_reg = 0, 0

    if df_est.empty or (_sum_rich == 0 and _sum_reg == 0):
        df_fb = compute_diversidade_estado_from_cubo(pais_iso3)
        if not df_fb.empty:
            df_est = df_fb.copy()

    # Merge (garante que todos os estados existam)
    gdf = gdf_est.merge(df_est, on=["pais_iso3", "id_estado"], how="left")
    gdf = harmonize_pais_iso3(gdf)

    # Fill métricas
    gdf["n_especies_distintas_max_municipio"] = gdf["n_especies_distintas_max_municipio"].fillna(0)
    gdf["n_registros_total"] = gdf["n_registros_total"].fillna(0)

    # Seleciona colunas essenciais (mantém id_municipio_max se existir)
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

    # Simplifica geometrias (para evitar MessageSizeError)
    if not gdf.empty:
        gdf["geometry"] = gdf["geometry"].simplify(0.01, preserve_topology=True)

    return gdf


def desenhar_mapa_conesul():
    st.subheader("Mapa territorial — riqueza de espécies por Estado/Município")
    st.caption("Selecione países e a escala territorial para visualizar a riqueza de espécies com base em registros do eBird.")

    # América do Sul (ISO3) — mantém nome bonitinho no select
    PAISES_SULAMERICA = ["ARG","BOL","BRA","CHL","COL","ECU","GUY","GUF","PRY","PER","SUR","URY","VEN"]

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

    # Lê dimensões só para checar quais dos 3 existem de fato
    dim_est = load_dim_estado_conesul()
    dim_mun = load_dim_municipio_conesul()

    paises_disponiveis = sorted(
        set(dim_est["pais_iso3"].dropna().unique()) | set(dim_mun["pais_iso3"].dropna().unique())
    )

    # filtra o que existe nos dados E é América do Sul
    paises_permitidos = [p for p in PAISES_SULAMERICA if p in paises_disponiveis]

    if not paises_permitidos:
        st.error("Não encontrei países da América do Sul nas dimensões territoriais (coluna pais_iso3).")
        return

    # --- seleção de países (linha 1) ---
    paises_sel = st.multiselect(
        "Países",
        options=paises_permitidos,
        default=(["BRA"] if "BRA" in paises_permitidos else [paises_permitidos[0]]),
        format_func=lambda x: pais_label_map.get(x, x),
    )

    # --- nível territorial (linha 2, abaixo) ---
    nivel = st.radio(
        "Escala territorial",
        options=["Estados", "Municípios"],
        horizontal=True,
    )


    paises_est_set = set(dim_est["pais_iso3"].dropna().unique())
    paises_mun_set = set(dim_mun["pais_iso3"].dropna().unique())

    # Quando o usuário seleciona países sem geometria no nível escolhido,
    # o mapa pode ficar "vazio". Aqui a gente avisa e ignora esses países.
    if nivel == "Municípios":
        missing = [p for p in paises_sel if p not in paises_mun_set]
        if missing:
            st.warning(
                "Sem geometria municipal para: "
                + ", ".join(missing)
                + ". Eles serão ignorados no mapa de municípios."
            )
        paises_sel = [p for p in paises_sel if p in paises_mun_set]
    else:
        missing = [p for p in paises_sel if p not in paises_est_set]
        if missing:
            st.warning(
                "Sem geometria estadual para: "
                + ", ".join(missing)
                + ". Eles serão ignorados no mapa de estados."
            )
        paises_sel = [p for p in paises_sel if p in paises_est_set]

    if not paises_sel:
        st.warning("Selecione ao menos um país.")
        return

    # --- monta o GDF conforme escala ---
    if nivel == "Municípios":
        gdfs = [construir_gdf_municipio_para_mapa(p) for p in paises_sel]
        gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs="EPSG:4326")

        metric_col = "n_especies_distintas"
        nome_col = "nome_municipio"
        id_col = "id_municipio"

        titulo_mapa = "Riqueza (n° de espécies) por município"
        tooltip_aliases = ["Município:", "Riqueza (nº de espécies):"]

    else:
        gdfs = [construir_gdf_estado_para_mapa(p) for p in paises_sel]
        gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs="EPSG:4326")

        metric_col = "n_especies_distintas_max_municipio"
        nome_col = "nome_estado"
        id_col = "id_estado"

        # texto mais “humano” e menos confuso
        titulo_mapa = "Riqueza (n° de espécies) dentro de cada estado"
        tooltip_aliases = ["Estado:", "Riqueza máxima (municípios):"]

    if len(paises_sel) > 1:
        titulo_mapa += " — países selecionados"

    if gdf.empty:
        st.warning("Não há dados para o país/escala selecionados.")
        return

    if metric_col not in gdf.columns:
        st.error(f"Coluna de métrica '{metric_col}' não encontrada no GeoDataFrame.")
        st.write("Colunas disponíveis:", list(gdf.columns))
        return

    # Centro do mapa
    try:
        # substitui unary_union (deprecated) por union_all
        centroid = gdf.geometry.union_all().centroid
        center_lat, center_lon = centroid.y, centroid.x
    except Exception:
        center_lat, center_lon = 0.0, 0.0

    # Mapa base (sem repetição horizontal)
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=4,
        tiles=None,
        max_bounds=True,
    )

    folium.TileLayer(
        "cartodbpositron",
        name="Base",
        control=False,
        no_wrap=True,
    ).add_to(m)


    # Enquadra o mapa nos limites do(s) país(es) selecionado(s)
    try:
        minx, miny, maxx, maxy = gdf.to_crs(epsg=4326).total_bounds  # [minx, miny, maxx, maxy]
        m.fit_bounds([[miny, minx], [maxy, maxx]])
    except Exception:
        pass

    # Normaliza valores
    data = gdf[[id_col, metric_col]].copy()
    vals = pd.to_numeric(data[metric_col], errors="coerce").fillna(0.0)

    vmax = float(vals.max())

    # --- vmin "visual": evita que valores baixos >0 fiquem quase brancos ---
    vals_pos = vals[vals > 0]
    if len(vals_pos) > 0:
        vmin_color = float(np.percentile(vals_pos, 5))  # ajuste: 5, 10, 15...
        # garante que vmin_color não seja 0 por arredondamento
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
        tooltip=folium.GeoJsonTooltip(
            fields=[nome_col, metric_col],
            aliases=tooltip_aliases,
            localize=True,
        ),
    )

    geojson.add_to(m)
    colormap.add_to(m)

    st_folium(
        m,
        width=None,
        height=600,
        key="map_conesul",
        returned_objects=[],
    )


# ---------------------------------------------------------
# Seção 2 – Análise informacional por cidade (versão original)
# ---------------------------------------------------------

def secao_analise_informacional():
    st.header("Análise ecológica e de similaridade por cidade")

    diversidade_total = load_diversidade_cidade_total()
    diversidade_tempo = load_diversidade_cidade_tempo()
    cubo_total = load_cubo_cidade_especie_total()
    _mapa_cidade_mun = load_map_cidade_ebird_municipio()  # mantido (caso você use depois)

    # -----------------------------
    # País(es) – agora MULTI no Tab 1
    # -----------------------------
    if "countryCode" not in diversidade_total.columns:
        st.error("diversidade_cidade_total.parquet precisa da coluna 'countryCode'.")
        return

    paises = sorted(diversidade_total["countryCode"].dropna().unique())
    if not paises:
        st.error("Não há países em diversidade_cidade_total.")
        return

    default_paises = ["BR"] if "BR" in paises else [paises[0]]

    tab_sim, tab_eco, tab_temp = st.tabs(
        ["Análise de similaridade entre cidades","Análise ecológica", "Análise temporal"]
    )

    # =========================================================
    # Aba 1 — Similaridade entre cidades
    # =========================================================
    with tab_sim:
        render_similarity_analysis(cubo_total)

    if False:
        with tab_sim:
            pass

        MIN_REGISTROS_CIDADE_SIM = 500

        # -----------------------------------------
        # Seletor único (Cidade — Estado/Província (País))
        # Mostra apenas cidades com >= MIN_REGISTROS_CIDADE_SIM
        # -----------------------------------------
        df_cidade_counts_all = (
            cubo_total.groupby(["countryCode", "stateProvince", "county"], as_index=False)["n_registros"]
            .sum()
        )
        df_cidade_counts_all = df_cidade_counts_all[df_cidade_counts_all["n_registros"] >= MIN_REGISTROS_CIDADE_SIM].copy()

        if df_cidade_counts_all.empty:
            st.warning(f"Não há cidades com pelo menos {MIN_REGISTROS_CIDADE_SIM} registros no cubo.")
            return

        df_cidade_counts_all["label"] = (
            df_cidade_counts_all["county"].astype(str)
            + " — "
            + df_cidade_counts_all["stateProvince"].astype(str)
            + " ("
            + df_cidade_counts_all["countryCode"].astype(str)
            + ")"
        )

        cidade_focal_label = st.selectbox(
            "Cidade focal (Cidade — Estado/Província)",
            options=df_cidade_counts_all["label"].sort_values().tolist(),
            key="sim_cidade_focal",
        )

        row_focal = df_cidade_counts_all[df_cidade_counts_all["label"] == cidade_focal_label].iloc[0]
        country_sim = row_focal["countryCode"]
        estado_focal = row_focal["stateProvince"]
        cidade_focal = row_focal["county"]

        # cubo do país da cidade focal
        df_cubo = cubo_total[cubo_total["countryCode"] == country_sim].copy()
        if df_cubo.empty:
            st.warning("Não há dados do cubo cidade × espécie para o país da cidade focal.")
            return

        # cidades bem amostradas apenas dentro do país focal
        df_cidade_counts = df_cidade_counts_all[df_cidade_counts_all["countryCode"] == country_sim].copy()

        # Restrição do cubo às cidades bem amostradas (no país)
        df_cubo_country = df_cubo.merge(
            df_cidade_counts[["countryCode", "stateProvince", "county"]],
            on=["countryCode", "stateProvince", "county"],
            how="inner",
        )

        # city_id e pivot
        df_cubo_country["city_id"] = df_cubo_country["stateProvince"].astype(str) + "||" + df_cubo_country["county"].astype(str)

        pivot = df_cubo_country.pivot_table(
            index="city_id",
            columns="scientificName",
            values="n_registros",
            aggfunc="sum",
            fill_value=0,
        )
        if pivot.empty:
            st.warning("Não foi possível construir a matriz cidade × espécie.")
            return

        city_id_focal = f"{estado_focal}||{cidade_focal}"
        if city_id_focal not in pivot.index:
            st.warning("Cidade focal não está na matriz (pode não alcançar o limiar de registros).")
            return

        # probabilidades
        counts = pivot.values.astype(float)
        row_sums = counts.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        probs = counts / row_sums

        idx_focal = pivot.index.get_loc(city_id_focal)
        p_focal = probs[idx_focal]

        def jensen_shannon_nats(p, q):
            m = 0.5 * (p + q)
            with np.errstate(divide="ignore", invalid="ignore"):
                kl_pm = np.where(p > 0, p * np.log(p / m), 0.0)
                kl_qm = np.where(q > 0, q * np.log(q / m), 0.0)
            return 0.5 * (kl_pm.sum() + kl_qm.sum())

        def jaccard_similarity(p, q):
            p_pres = p > 0
            q_pres = q > 0
            inter = np.logical_and(p_pres, q_pres).sum()
            union = np.logical_or(p_pres, q_pres).sum()
            return np.nan if union == 0 else inter / union

        # compara com todas as cidades
        results = []
        city_ids = pivot.index.tolist()
        for i, city_id in enumerate(city_ids):
            p = probs[i]
            js_nats = jensen_shannon_nats(p_focal, p)
            js_bits = js_nats / np.log(2.0)
            js_sim_norm = 1.0 - js_bits
            jac_sim = jaccard_similarity(p_focal, p)

            estado_i, cidade_i = city_id.split("||", 1)
            results.append(
                {
                    "countryCode": country_sim,
                    "stateProvince": estado_i,
                    "county": cidade_i,
                    "JS_sim_norm": js_sim_norm,
                    "Jaccard_sim": jac_sim,
                }
            )

        df_sim = pd.DataFrame(results)

        # junta registros e remove a focal
        df_sim = df_sim.merge(
            df_cidade_counts[["stateProvince", "county", "n_registros"]],
            on=["stateProvince", "county"],
            how="left",
        )
        df_sim = df_sim[
            ~((df_sim["stateProvince"] == estado_focal) & (df_sim["county"] == cidade_focal))
        ].copy()

        df_sim = df_sim.sort_values("JS_sim_norm", ascending=False)

        st.markdown(f"**Cidade focal:** {cidade_focal} — {estado_focal} ({country_sim})")

        # -----------------------------
        # Tabela
        # -----------------------------
         #st.subheader("Tabela")

        cols_tabela = ["stateProvince", "county", "n_registros", "JS_sim_norm", "Jaccard_sim"]
        cols_existentes = [c for c in cols_tabela if c in df_sim.columns]
        df_tab = df_sim[cols_existentes].copy()

        if "n_registros" in df_tab.columns:
            df_tab["n_registros"] = df_tab["n_registros"].fillna(0).round(0).astype(int)
        for c in ["JS_sim_norm", "Jaccard_sim"]:
            if c in df_tab.columns:
                df_tab[c] = df_tab[c].astype(float).round(4)

        rotulos_pt = {
            "stateProvince": "Estado/Província",
            "county": "Cidade",
            "n_registros": "Total de registros",
            "JS_sim_norm": "Similaridade (Jensen–Shannon)",
            "Jaccard_sim": "Similaridade (Jaccard)",
        }
        st.dataframe(df_tab.rename(columns=rotulos_pt), use_container_width=True,hide_index=True)

        # =========================================================
        # Top X (selecionável) — cidades mais similares + diagramas
        # =========================================================
        st.subheader("Top (selecionável) — cidades mais similares")

        if df_sim.empty:
            st.warning("Não há resultados de similaridade para exibir.")
        else:
            max_top = int(min(50, len(df_sim)))
            top_x = st.slider(
                "Top",
                min_value=5,
                max_value=max_top,
                value=min(20, max_top),
                step=1,
                key="sim_topx",
            )

            df_top = df_sim.head(top_x).copy()
            df_top["cidade_label"] = (
                df_top["county"].astype(str) + " — " + df_top["stateProvince"].astype(str)
            )

            cidade_comp_label = st.selectbox(
                "Escolha uma cidade do Top para visualizar os diagramas",
                options=df_top["cidade_label"].tolist(),
                index=0,
                key="sim_city_for_diagrams",
            )
            row_comp = df_top[df_top["cidade_label"] == cidade_comp_label].iloc[0]
            estado_comp = row_comp["stateProvince"]
            cidade_comp = row_comp["county"]

            city_id_comp = f"{estado_comp}||{cidade_comp}"
            if city_id_comp not in pivot.index:
                st.warning("Cidade escolhida não está na matriz cidade×espécie (pivot).")
            else:
                q = probs[pivot.index.get_loc(city_id_comp)]
                jac = jaccard_similarity(p_focal, q)

                st.markdown(
                    f"**Cidade focal:** {cidade_focal} — {estado_focal} ({country_sim})  \n"
                    f"**Cidade comparada:** {cidade_comp} — {estado_comp} ({country_sim})"
                )

                # -------------------------
                # Função SVG (Venn) — com legenda (evita nomes sobrepostos)
                # -------------------------
                def venn_svg_similarity(
                    score,
                    label_text="Similaridade",
                    left_title="Focal",
                    right_title="Comparada",
                    left_city="",
                    right_city="",
                ):
                    if score is None or (isinstance(score, float) and np.isnan(score)):
                        score = 0.0
                    score = float(np.clip(score, 0.0, 1.0))

                    # distância entre centros: maior score => mais sobreposição
                    d = 140 * (1.0 - score) + 10

                    # geometria (mantive a sua)
                    cx1, cy = 160, 120
                    cx2 = cx1 + d
                    r = 95

                    # -------- AJUSTES que interessam --------
                    # 1) “Focal/Comparada” 
                    title_y = 16
                    title_x1 = cx1 - 55
                    title_x2 = cx2 + 55

                    # 2) Jaccard fica 
                    score_x = 210
                    score_y = 238

                    # 3) Legenda: 
                    leg1_y = 252
                    leg2_y = 274

                    def short(s, n=44):
                        s = str(s) if s is not None else ""
                        return (s[: n - 1] + "…") if len(s) > n else s

                    left_city_s = short(left_city, 44)
                    right_city_s = short(right_city, 44)

                    return f"""
                    <div style="width:100%; display:flex; justify-content:center;">
                    <svg width="520" height="300" viewBox="0 0 520 300">
                        <circle cx="{cx1}" cy="{cy}" r="{r}"
                                fill="rgba(77,163,255,0.20)" stroke="rgba(77,163,255,0.95)" stroke-width="2"/>
                        <circle cx="{cx2}" cy="{cy}" r="{r}"
                                fill="rgba(160,210,255,0.16)" stroke="rgba(160,210,255,0.95)" stroke-width="2"/>

                        <!-- títulos (agora com folga do diagrama) -->
                        <text x="{title_x1}" y="{title_y}" text-anchor="middle" fill="#FAFAFA" font-size="14">{left_title}</text>
                        <text x="{title_x2}" y="{title_y}" text-anchor="middle" fill="#FAFAFA" font-size="14">{right_title}</text>

                        <!-- score (mantido) -->
                        <text x="{score_x}" y="{score_y}" text-anchor="middle" fill="#FAFAFA" font-size="14">
                        {label_text} = {score:.3f}
                        </text>

                        <!-- legenda (agora não corta) -->
                        <circle cx="150" cy="{leg1_y}" r="6" fill="rgba(77,163,255,0.95)"/>
                        <text x="165" y="{leg1_y + 4}" fill="#FAFAFA" font-size="13">{left_title}: {left_city_s}</text>

                        <circle cx="150" cy="{leg2_y}" r="6" fill="rgba(160,210,255,0.95)"/>
                        <text x="165" y="{leg2_y + 4}" fill="#FAFAFA" font-size="13">{right_title}: {right_city_s}</text>
                    </svg>
                    </div>
                    """


                # =========================================================
                # Jaccard — Venn (correto para presença/ausência)
                # =========================================================
                st.subheader("Jaccard")
                st.caption(
                    "O **Jaccard** mede semelhança **apenas pela presença/ausência** de espécies: "
                    "é a razão entre espécies em comum e o total de espécies observadas no conjunto das duas cidades "
                    "(não usa as quantidades de registros)."
                )

                # TROCA: st.markdown(...) -> components.html(...)
                components.html(
                    venn_svg_similarity(
                        jac,
                        label_text="Jaccard",
                        left_title="Focal",
                        right_title="Comparada",
                        left_city=f"{cidade_focal} — {estado_focal} ({country_sim})",
                        right_city=f"{cidade_comp} — {estado_comp} ({country_sim})",
                    ),
                    height=290,
                )

                # =========================================================
                # Jensen–Shannon — densidades sobrepostas (B)
                # =========================================================
                st.subheader("Divergência Jensen–Shannon")
                st.caption(
                    "A **divergência Jensen–Shannon** compara as cidades como **distribuições de probabilidade**: "
                    "cada espécie recebe a **proporção** de registros dentro da cidade. "
                    "Quanto mais parecidas as distribuições, maior a similaridade (aqui: **1 − JS(bits)**)."
                )

                js_nats = jensen_shannon_nats(p_focal, q)
                js_bits = js_nats / np.log(2.0)
                js_sim = 1.0 - js_bits
                st.metric("Similaridade (Jensen–Shannon)", f"{js_sim:.4f}")


                # =========================================================
                # Jensen–Shannon — gráficos interpretáveis (SEM matplotlib)
                # =========================================================

                # Base espécie-a-espécie
                df_prob = pd.DataFrame(
                    {
                        "Especie": pivot.columns.astype(str),
                        "p_focal": p_focal,
                        "p_comp": q,
                    }
                )

                # mantém só espécies presentes em pelo menos uma das cidades
                df_prob = df_prob[(df_prob["p_focal"] > 0) | (df_prob["p_comp"] > 0)].copy()

                if df_prob.empty:
                    st.warning("Não há espécies com probabilidade positiva para comparar.")
                else:
                    focal_label = f"{cidade_focal} — {estado_focal} ({country_sim})"
                    comp_label  = f"{cidade_comp} — {estado_comp} ({country_sim})"

                    # ---------- 1) Scatter log(p) vs log(q) ----------
                    st.markdown("**1) Espécie a espécie (escala log)**")
                    st.caption(
                        "Cada ponto é uma espécie. Se as duas cidades têm proporções parecidas por espécie, "
                        "os pontos ficam perto da diagonal. Desvios grandes (espécies dominantes diferentes) reduzem a similaridade JS."
                    )

                    # epsilon para permitir log sem estourar (mantém zeros fora, mas garante robustez)
                    eps = 1e-9
                    df_scatter = df_prob.copy()
                    df_scatter["log_p_focal"] = np.log10(df_scatter["p_focal"] + eps)
                    df_scatter["log_p_comp"]  = np.log10(df_scatter["p_comp"] + eps)

                    # domínio do gráfico (evita corte)
                    vmin = float(min(df_scatter["log_p_focal"].min(), df_scatter["log_p_comp"].min()))
                    vmax = float(max(df_scatter["log_p_focal"].max(), df_scatter["log_p_comp"].max()))
                    pad = 0.15 * (vmax - vmin + 1e-9)
                    dom_min, dom_max = vmin - pad, vmax + pad

                    df_diag = pd.DataFrame({"x": [dom_min, dom_max], "y": [dom_min, dom_max]})

                    diag = (
                        alt.Chart(df_diag)
                        .mark_line(strokeDash=[6, 6])
                        .encode(
                            x=alt.X("x:Q", title=f"log10(p) — Focal ({focal_label})",
                                    scale=alt.Scale(domain=[dom_min, dom_max], nice=False)),
                            y=alt.Y("y:Q", title=f"log10(p) — Comparada ({comp_label})",
                                    scale=alt.Scale(domain=[dom_min, dom_max], nice=False)),
                        )
                    )

                    pts = (
                        alt.Chart(df_scatter)
                        .mark_circle(size=40, opacity=0.45)
                        .encode(
                            x=alt.X("log_p_focal:Q", title=f"log10(p) — Focal ({focal_label})"),
                            y=alt.Y("log_p_comp:Q", title=f"log10(p) — Comparada ({comp_label})"),
                            tooltip=[
                                alt.Tooltip("Especie:N", title="Espécie"),
                                alt.Tooltip("p_focal:Q", title="p focal", format=".6f"),
                                alt.Tooltip("p_comp:Q", title="p comparada", format=".6f"),
                            ],
                        )
                    )

                    st.altair_chart(diag + pts, use_container_width=True)

                    # ---------- 2) Top-K espécies (barras lado a lado) ----------
                    st.markdown("**2) Top espécies que mais carregam probabilidade**")
                    st.caption(
                        "Mostra as espécies com maior peso (p) nas duas cidades. "
                        "Se o ‘peso’ está concentrado em espécies diferentes, a Similaridade JS cai."
                    )

                    k = st.slider("Top espécies (K)", 10, 50, 20, 5, key="js_topk_species")

                    # df_prob precisa ter: Especie, p_focal, p_comp
                    df_top = df_prob.copy()
                    df_top["peso"] = df_top["p_focal"] + df_top["p_comp"]
                    df_top = df_top.sort_values("peso", ascending=False).head(int(k)).copy()

                    # ---- Escolha a ordenação das espécies (descomente a que preferir) ----
                    # A) Ordena pelo "peso total" (p_focal + p_comp)  -> mais “ortodoxo” para JS
                    ordem = df_top.sort_values("peso", ascending=True)["Especie"].tolist()

                    # B) Ordena por p_focal (para “bater o olho” e ver focal como referência)
                    # ordem = df_top.sort_values("p_focal", ascending=True)["Especie"].tolist()

                    df_top_long = df_top.melt(
                        id_vars=["Especie"],
                        value_vars=["p_focal", "p_comp"],
                        var_name="Cidade_raw",
                        value_name="p",
                    )

                    # Nomes finais (os que vão aparecer na legenda)
                    cidade_focal = f"Focal: {focal_label}"
                    cidade_comp = f"Comparada: {comp_label}"

                    df_top_long["Cidade"] = df_top_long["Cidade_raw"].replace(
                        {"p_focal": cidade_focal, "p_comp": cidade_comp}
                    )

                    # (IMPORTANTE) garante que a ordem do xOffset seja: Focal à esquerda, Comparada à direita
                    ordem_cidades = [cidade_focal, cidade_comp]

                    # ordena espécies pela probabilidade da FOCAL (maiores no topo)
                    ordem = (
                        df_top.sort_values("p_focal", ascending=False)["Especie"]
                        .astype(str)
                        .tolist()
                    )

                    # garante que a coluna Cidade ainda está no formato bonito:
                    # "Focal: ..." e "Comparada: ..."
                    df_plot = df_top_long.copy()

                    # cria valor assinado: Focal negativo (vai pra esquerda), Comparada positivo (direita)
                    df_plot["p_signed"] = np.where(
                        df_plot["Cidade"].astype(str).str.startswith("Focal:"),
                        -df_plot["p"].astype(float),
                        df_plot["p"].astype(float),
                    )

                    # pra tooltip mostrar sempre positivo
                    df_plot["p_abs"] = df_plot["p"].astype(float)

                    # linha central (x=0)
                    zero_rule = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(strokeDash=[6, 4]).encode(x="x:Q")

                    bars = (
                        alt.Chart(df_plot)
                        .mark_bar(opacity=0.85)
                        .encode(
                            y=alt.Y("Especie:N", sort=ordem, title="Espécie"),
                            x=alt.X(
                                "p_signed:Q",
                                title="Proporção de registros (p) — Focal à esquerda | Comparada à direita",
                                axis=alt.Axis(format=".4f"),
                            ),
                            color=alt.Color("Cidade:N", title=""),
                            tooltip=[
                                alt.Tooltip("Cidade:N", title="Cidade"),
                                alt.Tooltip("Especie:N", title="Espécie"),
                                alt.Tooltip("p_abs:Q", title="p", format=".6f"),
                            ],
                        )
                    )

                    st.altair_chart(zero_rule + bars, use_container_width=True)



                    # ---------- (Opcional) 3) KDE como “extra”, desligado ----------
                    mostrar_kde = st.checkbox(
                        "Mostrar curva de densidade (extra — menos interpretável para JS)",
                        value=False,
                        key="js_show_kde_extra",
                    )
                    if mostrar_kde:
                        st.caption(
                            "Esta curva mostra a distribuição dos valores de p (não preserva quais espécies têm esses valores). "
                            "É útil para ver concentração perto de zero, mas não explica JS tão bem quanto os gráficos acima."
                        )

                        df_long = df_prob.melt(
                            id_vars=["Especie"],
                            value_vars=["p_focal", "p_comp"],
                            var_name="Cidade",
                            value_name="p",
                        )
                        df_long = df_long[df_long["p"] > 0].copy()

                        df_long["Cidade"] = df_long["Cidade"].replace(
                            {"p_focal": f"Focal: {focal_label}", "p_comp": f"Comparada: {comp_label}"}
                        )

                        pmax = float(df_long["p"].max())
                        if not np.isfinite(pmax) or pmax <= 0:
                            pmax = 1e-6

                        dens_area = (
                            alt.Chart(df_long)
                            .transform_density(
                                "p",
                                as_=["p", "density"],
                                groupby=["Cidade"],
                                extent=[0, pmax],
                            )
                            .mark_area(opacity=0.12)
                            .encode(
                                x=alt.X(
                                    "p:Q",
                                    title="Proporção de registros por espécie",
                                    axis=alt.Axis(format=".3f"),
                                    scale=alt.Scale(domain=[0, pmax], nice=False),
                                ),
                                y=alt.Y("density:Q", title="Densidade"),
                                color=alt.Color("Cidade:N", title=""),
                            )
                        )

                        dens_line = (
                            alt.Chart(df_long)
                            .transform_density(
                                "p",
                                as_=["p", "density"],
                                groupby=["Cidade"],
                                extent=[0, pmax],
                            )
                            .mark_line()
                            .encode(
                                x="p:Q",
                                y="density:Q",
                                color=alt.Color("Cidade:N", title=""),
                            )
                        )

                        st.altair_chart(dens_area + dens_line, use_container_width=True)


        # -----------------------------
        # Notas
        # -----------------------------
        with st.expander("Notas metodológicas (fórmulas e interpretação)", expanded=True):
                    st.markdown(
                        "- **Similaridade (Jensen-Shannon)** varia de 0 a 1 (1 = mais parecido) e é calculada a partir da divergência de Jensen–Shannon.\n"
                        "- **Similaridade (Jaccard)** varia de 0 a 1 e considera apenas presença/ausência de espécies.\n"
                        f"- A comparação é feita entre a cidade focal e cada outra cidade usando a distribuição de registros por espécie, apenas são incluídas cidades com **pelo menos {MIN_REGISTROS_CIDADE_SIM} registros**.\n"
                        "- Nas fórmulas abaixo, o índice **i** percorre as espécies."
                    )

                    st.markdown("**Distribuição por espécie (por cidade):**")
                    st.latex(r"p_i = \frac{n_i}{\sum_j n_j}")

                    st.markdown("**Divergência de Jensen–Shannon (JS):**")
                    st.latex(r"m = \frac{1}{2}(p+q)")
                    st.latex(r"JS_{\text{nats}}(p,q)=\frac{1}{2}KL(p\,||\,m)+\frac{1}{2}KL(q\,||\,m)")
                    st.latex(r"KL(p\,||\,m)=\sum_i p_i \ln\left(\frac{p_i}{m_i}\right)")

                    st.markdown("**JS em bits e a Similaridade (JS) mostrada na tabela:**")
                    st.latex(r"JS_{\text{bits}} = \frac{JS_{\text{nats}}}{\ln(2)}")
                    st.latex(r"\text{Similaridade(JS)} = 1 - JS_{\text{bits}}")

                    st.markdown("**Similaridade de Jaccard (presença/ausência):**")
                    st.latex(r"A=\{i:\,p_i>0\},\quad B=\{i:\,q_i>0\}")
                    st.latex(r"Jaccard(A,B)=\frac{|A\cap B|}{|A\cup B|}")

                    st.caption(
                        "Observação: JS usa a distribuição (proporções de registros). "
                        "Jaccard ignora abundâncias e considera apenas presença/ausência."
                    )
        st.divider()

    # =========================================================
    # Aba 2 — Análise ecológica por cidade
    # =========================================================
    with tab_eco:
        df_total = render_ecological_analysis(diversidade_total, paises, default_paises)

    if False:
        with tab_eco:
            pass
        countries_sel = st.multiselect(
            "País(es)",
            options=paises,
            default=default_paises,
            key="eco_countries_sel",  # evita colisão no futuro
        )

        df_total = diversidade_total[diversidade_total["countryCode"].isin(countries_sel)].copy()
        if df_total.empty:
            st.warning("Não há dados de diversidade por cidade para os países selecionados.")
            return

        # Estado/Província (mantém (Todos) e default)
        estados = sorted(df_total["stateProvince"].dropna().unique())
        estados_opcoes = ["(Todos)"] + estados
        estado_escolhido = st.selectbox("Estado/Província", options=estados_opcoes, index=0)

        if estado_escolhido != "(Todos)":
            df_total = df_total[df_total["stateProvince"] == estado_escolhido].copy()

        # -----------------------------
        # Tabela
        # -----------------------------
        #t.subheader("Tabela")

        cols_tabela = [
            "countryCode",
            "stateProvince",
            "county",
            "total_registros",
            "richness",
            "H_shannon",
            "evenness",
        ]
        cols_existentes = [c for c in cols_tabela if c in df_total.columns]

        df_mostrar = df_total[cols_existentes].sort_values(
            by=["countryCode", "stateProvince", "county"], na_position="last"
        )

        rotulos_pt = {
            "countryCode": "País",
            "stateProvince": "Estado/Província",
            "county": "Cidade",
            "total_registros": "Total de registros",
            "richness": "Riqueza (nº de espécies)",
            "H_shannon": "Diversidade (Entropia de Shannon)",
            "evenness": "Equitabilidade",
        }

        df_mostrar_ui = df_mostrar.rename(columns=rotulos_pt)
        st.dataframe(df_mostrar_ui, use_container_width=True, hide_index=True)

        # -----------------------------
        # Notas
        # -----------------------------
        with st.expander("Notas metodológicas (fórmulas e interpretação)", expanded=True):
            st.markdown("As definições abaixo seguem **a mesma ordem e nomes das colunas** da tabela.")

            # Metadados (sem fórmulas)
            st.markdown(
                "- **País:** código do país (eBird: `countryCode`).\n"
                "- **Estado/Província:** unidade administrativa (eBird: `stateProvince`).\n"
                "- **Cidade:** localidade administrativa do eBird (campo `county`; pode ser município/condado/região dependendo do país)."
            )

            st.divider()

            # Métricas (texto + fórmula logo abaixo)
            st.markdown(
                "**Total de registros:** total de registros/ocorrências na cidade no período considerado. "
                "Nas fórmulas, esse total é representado por **N**."
            )
            st.latex(r"N = \sum_i n_i")

            st.markdown(
                "**Riqueza (nº de espécies):** número de espécies distintas registradas na cidade. "
                "Nas fórmulas, a riqueza é representada por **S**."
            )
            st.latex(r"S = \left|\left\{\, i \;:\; n_i > 0 \,\right\}\right|")

            st.caption("Onde: nᵢ = número de registros da espécie i na cidade; pᵢ = nᵢ/N; usa log natural (ln).")

            st.markdown(
                "**Diversidade (Índice de Shannon, H):** medida baseada na distribuição dos registros entre espécies "
                "(usa log natural, ln)."
            )
            st.latex(r"H = -\sum_i p_i \ln(p_i)")

            st.markdown(
                "**Equitabilidade:** mede quão uniformemente os registros se distribuem entre espécies. "
                "É definida quando **S > 1**."
            )
            st.latex(r"J = \frac{H}{\ln(S)}")

            st.caption(
                "Observação: estes índices refletem a distribuição dos **registros** entre espécies "
                "(não necessariamente abundância real)."
            )
    # =========================================================
    # Aba 3 — Análise temporal
    # =========================================================
    with tab_temp:
        render_temporal_analysis(df_total, diversidade_tempo)
    if False:
        with tab_temp:
            pass
        # lista de cidades (evita ambiguidade com multi-país)
        cidades = (
            df_total[["countryCode", "stateProvince", "county"]]
            .dropna()
            .drop_duplicates()
            .sort_values(["countryCode", "stateProvince", "county"])
            .copy()
        )
        cidades["label"] = (
            cidades["county"].astype(str)
            + " — "
            + cidades["stateProvince"].astype(str)
            + " ("
            + cidades["countryCode"].astype(str)
            + ")"
        )

        cidade_label = st.selectbox(
            "Selecionar cidade (Cidade — Estado/Província)",
            options=cidades["label"].tolist(),
        )
        row_sel = cidades[cidades["label"] == cidade_label].iloc[0]
        country_focal = row_sel["countryCode"]
        estado_focal = row_sel["stateProvince"]
        cidade_focal = row_sel["county"]

        # série temporal da cidade selecionada
        df_temp = diversidade_tempo[
            (diversidade_tempo["countryCode"] == country_focal)
            & (diversidade_tempo["stateProvince"] == estado_focal)
            & (diversidade_tempo["county"] == cidade_focal)
        ].copy()

        if df_temp.empty:
            st.warning("Não há série temporal para a cidade selecionada.")
        else:
            # métricas-resumo
            total_registros_total = (
                df_temp["total_registros"].sum() if "total_registros" in df_temp.columns else np.nan
            )
            H_media = df_temp["H_shannon"].mean() if "H_shannon" in df_temp.columns else np.nan
            richness_max = df_temp["richness"].max() if "richness" in df_temp.columns else np.nan
            evenness_media = df_temp["evenness"].mean() if "evenness" in df_temp.columns else np.nan

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if not np.isnan(total_registros_total):
                    st.metric("Total de registros", f"{int(total_registros_total):,}".replace(",", "."))
            with c2:
                if not np.isnan(richness_max):
                    st.metric("Riqueza máxima", f"{int(richness_max):,}".replace(",", "."))
            with c3:
                if not np.isnan(H_media):
                    st.metric("Shannon médio", f"{H_media:.3f}")
            with c4:
                if not np.isnan(evenness_media):
                    st.metric("Equitabilidade média", f"{evenness_media:.3f}")

            # prepara eixo temporal
            if "year" in df_temp.columns and "month" in df_temp.columns:
                df_temp["date"] = pd.to_datetime(
                    dict(
                        year=df_temp["year"].astype(int),
                        month=df_temp["month"].astype(int),
                        day=1,
                    ),
                    errors="coerce",
                )
                df_temp = df_temp.dropna(subset=["date"]).sort_values("date")

                metrica_map = {
                    "Riqueza (nº de espécies)": ("richness", "Riqueza (espécies)"),
                    "Diversidade (Shannon)": ("H_shannon", "H (Shannon)"),
                    "Equitabilidade": ("evenness", "Equitabilidade"),
                }
                metrica_escolhida = st.selectbox(
                    "Métrica para série temporal",
                    options=list(metrica_map.keys()),
                    index=0,
                )
                col_y, titulo_y = metrica_map[metrica_escolhida]

                if col_y in df_temp.columns:
                    st.subheader(f"Série temporal — {cidade_focal} / {estado_focal} ({country_focal})")

                    chart = (
                        alt.Chart(df_temp)
                        .mark_line(point=True)
                        .encode(
                            x=alt.X(
                                "date:T",
                                title="Ano",
                                axis=alt.Axis(
                                    format="%Y",
                                    tickCount={"interval": "year", "step": 1},
                                    labelAngle=0,
                                ),
                            ),
                            y=alt.Y(f"{col_y}:Q", title=titulo_y),
                            tooltip=["date:T", col_y, "total_registros"],
                        )
                    )
                    st.altair_chart(chart, use_container_width=True)

def main():
    st.title("Biodiversidade de aves — análise geoespacial (eBird)")

    st.markdown(
        """
Painel para análise espacial e comparativa de registros do eBird: mapas por unidade administrativa, diversidade por cidade e similaridade (Jensen-Shannon/Jaccard).
"""
    )

    # Seção 1 – Mapa Cone Sul
    render_territorial_map()

    st.markdown("---")

    # Seção 2 – Análise informacional (original)
    secao_analise_informacional()


if __name__ == "__main__":
    main()


























































