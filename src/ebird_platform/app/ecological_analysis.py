from __future__ import annotations

import pandas as pd
import streamlit as st


def render_ecological_analysis(
    diversidade_total: pd.DataFrame,
    paises: list[str],
    default_paises: list[str],
) -> pd.DataFrame | None:
    countries_sel = st.multiselect(
        "País(es)",
        options=paises,
        default=default_paises,
        key="eco_countries_sel",
    )

    df_total = diversidade_total[diversidade_total["countryCode"].isin(countries_sel)].copy()
    if df_total.empty:
        st.warning("Não há dados de diversidade por cidade para os países selecionados.")
        return None

    estados = sorted(df_total["stateProvince"].dropna().unique())
    estados_opcoes = ["(Todos)"] + estados
    estado_escolhido = st.selectbox("Estado/Província", options=estados_opcoes, index=0)

    if estado_escolhido != "(Todos)":
        df_total = df_total[df_total["stateProvince"] == estado_escolhido].copy()

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

    with st.expander("Notas metodológicas (fórmulas e interpretação)", expanded=True):
        st.markdown("As definições abaixo seguem **a mesma ordem e nomes das colunas** da tabela.")
        st.markdown(
            "- **País:** código do país (eBird: `countryCode`).\n"
            "- **Estado/Província:** unidade administrativa (eBird: `stateProvince`).\n"
            "- **Cidade:** localidade administrativa do eBird (campo `county`; pode ser município/condado/região dependendo do país)."
        )

        st.divider()

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

        st.caption("Onde: n_i = número de registros da espécie i na cidade; p_i = n_i/N; usa log natural (ln).")

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

    return df_total
