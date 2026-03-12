from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from ebird_platform.app.ecological_analysis import render_ecological_analysis
from ebird_platform.app.similarity_analysis import render_similarity_analysis
from ebird_platform.app.temporal_analysis import render_temporal_analysis
from ebird_platform.app.territorial_map import desenhar_mapa_conesul as render_territorial_map
from ebird_platform.io.loaders import (
    load_cubo_cidade_especie_total,
    load_diversidade_cidade_tempo,
    load_diversidade_cidade_total,
    load_map_cidade_ebird_municipio,
)
from ebird_platform.settings import get_app_paths

APP_PATHS = get_app_paths()


def set_bg_image(image_path: Path, overlay_alpha: float = 0.70) -> None:
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

        [data-testid="stHeader"] {{
            background: rgba(0,0,0,0);
        }}

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


st.set_page_config(
    page_title="Biodiversidade de aves — análise geoespacial (eBird)",
    page_icon=str(APP_PATHS.icon_path),
    layout="wide",
)
set_bg_image(APP_PATHS.background_path, overlay_alpha=0.70)


def render_city_analysis() -> None:
    st.header("Análise ecológica e de similaridade por cidade")

    diversidade_total = load_diversidade_cidade_total()
    diversidade_tempo = load_diversidade_cidade_tempo()
    cubo_total = load_cubo_cidade_especie_total()
    _mapa_cidade_mun = load_map_cidade_ebird_municipio()

    if "countryCode" not in diversidade_total.columns:
        st.error("diversidade_cidade_total.parquet precisa da coluna 'countryCode'.")
        return

    paises = sorted(diversidade_total["countryCode"].dropna().unique())
    if not paises:
        st.error("Não há países em diversidade_cidade_total.")
        return

    default_paises = ["BR"] if "BR" in paises else [paises[0]]
    tab_sim, tab_eco, tab_temp = st.tabs(
        ["Análise de similaridade entre cidades", "Análise ecológica", "Análise temporal"]
    )

    with tab_sim:
        render_similarity_analysis(cubo_total)

    st.divider()

    with tab_eco:
        df_total = render_ecological_analysis(diversidade_total, paises, default_paises)

    with tab_temp:
        if df_total is None:
            st.warning("Selecione países com dados na aba ecológica para ver a série temporal.")
        else:
            render_temporal_analysis(df_total, diversidade_tempo)


def main() -> None:
    st.title("Biodiversidade de aves — análise geoespacial (eBird)")
    st.markdown(
        """
Painel para análise espacial e comparativa de registros do eBird: mapas por unidade administrativa, diversidade por cidade e similaridade (Jensen-Shannon/Jaccard).
"""
    )

    render_territorial_map()
    st.markdown("---")
    render_city_analysis()
