from __future__ import annotations

import pandas as pd
import streamlit as st


def render_ecological_analysis(
    diversidade_total: pd.DataFrame,
    paises: list[str],
    default_paises: list[str],
) -> pd.DataFrame | None:
    countries_sel = st.multiselect(
        "Pais(es)",
        options=paises,
        default=default_paises,
        key="eco_countries_sel",
    )

    df_total = diversidade_total[diversidade_total["countryCode"].isin(countries_sel)].copy()
    if df_total.empty:
        st.warning("Nao ha dados de diversidade por cidade para os paises selecionados.")
        return None

    estados = sorted(df_total["stateProvince"].dropna().unique())
    estados_opcoes = ["(Todos)"] + estados
    estado_escolhido = st.selectbox("Estado/Provincia", options=estados_opcoes, index=0)

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
        "countryCode": "Pais",
        "stateProvince": "Estado/Provincia",
        "county": "Cidade",
        "total_registros": "Total de registros",
        "richness": "Riqueza (numero de especies)",
        "H_shannon": "Diversidade (Entropia de Shannon)",
        "evenness": "Equitabilidade",
    }

    df_mostrar_ui = df_mostrar.rename(columns=rotulos_pt)
    st.dataframe(df_mostrar_ui, use_container_width=True, hide_index=True)

    with st.expander("Notas metodologicas (formulas e interpretacao)", expanded=True):
        st.markdown("As definicoes abaixo seguem **a mesma ordem e nomes das colunas** da tabela.")
        st.markdown(
            "- **Pais:** codigo do pais (eBird: `countryCode`).\n"
            "- **Estado/Provincia:** unidade administrativa (eBird: `stateProvince`).\n"
            "- **Cidade:** localidade administrativa do eBird (campo `county`; pode ser municipio/condado/regiao dependendo do pais)."
        )

        st.divider()

        st.markdown(
            "**Total de registros:** total de registros/ocorrencias na cidade no periodo considerado. "
            "Nas formulas, esse total e representado por **N**."
        )
        st.latex(r"N = \sum_i n_i")

        st.markdown(
            "**Riqueza (numero de especies):** numero de especies distintas registradas na cidade. "
            "Nas formulas, a riqueza e representada por **S**."
        )
        st.latex(r"S = \left|\left\{\, i \;:\; n_i > 0 \,\right\}\right|")

        st.caption("Onde: n_i = numero de registros da especie i na cidade; p_i = n_i/N; usa log natural (ln).")

        st.markdown(
            "**Diversidade (Indice de Shannon, H):** medida baseada na distribuicao dos registros entre especies "
            "(usa log natural, ln)."
        )
        st.latex(r"H = -\sum_i p_i \ln(p_i)")

        st.markdown(
            "**Equitabilidade:** mede quao uniformemente os registros se distribuem entre especies. "
            "E definida quando **S > 1**."
        )
        st.latex(r"J = \frac{H}{\ln(S)}")

        st.caption(
            "Observacao: estes indices refletem a distribuicao dos **registros** entre especies "
            "(nao necessariamente abundancia real)."
        )

    return df_total
