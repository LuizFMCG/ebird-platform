from __future__ import annotations

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st


def render_temporal_analysis(df_total: pd.DataFrame, diversidade_tempo: pd.DataFrame) -> None:
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

    df_temp = diversidade_tempo[
        (diversidade_tempo["countryCode"] == country_focal)
        & (diversidade_tempo["stateProvince"] == estado_focal)
        & (diversidade_tempo["county"] == cidade_focal)
    ].copy()

    if df_temp.empty:
        st.warning("Não há série temporal para a cidade selecionada.")
        return

    total_registros_total = df_temp["total_registros"].sum() if "total_registros" in df_temp.columns else np.nan
    h_media = df_temp["H_shannon"].mean() if "H_shannon" in df_temp.columns else np.nan
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
        if not np.isnan(h_media):
            st.metric("Shannon médio", f"{h_media:.3f}")
    with c4:
        if not np.isnan(evenness_media):
            st.metric("Equitabilidade média", f"{evenness_media:.3f}")

    if "year" not in df_temp.columns or "month" not in df_temp.columns:
        return

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

    if col_y not in df_temp.columns:
        return

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
