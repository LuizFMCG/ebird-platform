from __future__ import annotations

import pandas as pd
import streamlit as st


def render_ecological_analysis(
    diversidade_total: pd.DataFrame,
    paises: list[str],
    default_paises: list[str],
) -> pd.DataFrame | None:
    countries_sel = st.multiselect(
        "PaÃ­s(es)",
        options=paises,
        default=default_paises,
        key="eco_countries_sel",
    )

    df_total = diversidade_total[diversidade_total["countryCode"].isin(countries_sel)].copy()
    if df_total.empty:
        st.warning("NÃ£o hÃ¡ dados de diversidade por cidade para os paÃ­ses selecionados.")
        return None

    estados = sorted(df_total["stateProvince"].dropna().unique())
    estados_opcoes = ["(Todos)"] + estados
    estado_escolhido = st.selectbox("Estado/ProvÃ­ncia", options=estados_opcoes, index=0)

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
        "countryCode": "PaÃ­s",
        "stateProvince": "Estado/ProvÃ­ncia",
        "county": "Cidade",
        "total_registros": "Total de registros",
        "richness": "Riqueza (nÂº de espÃ©cies)",
        "H_shannon": "Diversidade (Entropia de Shannon)",
        "evenness": "Equitabilidade",
    }

    df_mostrar_ui = df_mostrar.rename(columns=rotulos_pt)
    st.dataframe(df_mostrar_ui, use_container_width=True, hide_index=True)

    with st.expander("Notas metodolÃ³gicas (fÃ³rmulas e interpretaÃ§Ã£o)", expanded=True):
        st.markdown("As definiÃ§Ãµes abaixo seguem **a mesma ordem e nomes das colunas** da tabela.")
        st.markdown(
            "- **PaÃ­s:** cÃ³digo do paÃ­s (eBird: `countryCode`).\n"
            "- **Estado/ProvÃ­ncia:** unidade administrativa (eBird: `stateProvince`).\n"
            "- **Cidade:** localidade administrativa do eBird (campo `county`; pode ser municÃ­pio/condado/regiÃ£o dependendo do paÃ­s)."
        )

        st.divider()

        st.markdown(
            "**Total de registros:** total de registros/ocorrÃªncias na cidade no perÃ­odo considerado. "
            "Nas fÃ³rmulas, esse total Ã© representado por **N**."
        )
        st.latex(r"N = \sum_i n_i")

        st.markdown(
            "**Riqueza (nÂº de espÃ©cies):** nÃºmero de espÃ©cies distintas registradas na cidade. "
            "Nas fÃ³rmulas, a riqueza Ã© representada por **S**."
        )
        st.latex(r"S = \left|\left\{\, i \;:\; n_i > 0 \,\right\}\right|")

        st.caption("Onde: náµ¢ = nÃºmero de registros da espÃ©cie i na cidade; páµ¢ = náµ¢/N; usa log natural (ln).")

        st.markdown(
            "**Diversidade (Ãndice de Shannon, H):** medida baseada na distribuiÃ§Ã£o dos registros entre espÃ©cies "
            "(usa log natural, ln)."
        )
        st.latex(r"H = -\sum_i p_i \ln(p_i)")

        st.markdown(
            "**Equitabilidade:** mede quÃ£o uniformemente os registros se distribuem entre espÃ©cies. "
            "Ã‰ definida quando **S > 1**."
        )
        st.latex(r"J = \frac{H}{\ln(S)}")

        st.caption(
            "ObservaÃ§Ã£o: estes Ã­ndices refletem a distribuiÃ§Ã£o dos **registros** entre espÃ©cies "
            "(nÃ£o necessariamente abundÃ¢ncia real)."
        )

    return df_total
