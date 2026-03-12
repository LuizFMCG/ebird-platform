from __future__ import annotations

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


def render_similarity_analysis(cubo_total: pd.DataFrame) -> None:
    min_registros_cidade_sim = 500

    df_cidade_counts_all = (
        cubo_total.groupby(["countryCode", "stateProvince", "county"], as_index=False)["n_registros"]
        .sum()
    )
    df_cidade_counts_all = df_cidade_counts_all[
        df_cidade_counts_all["n_registros"] >= min_registros_cidade_sim
    ].copy()

    if df_cidade_counts_all.empty:
        st.warning(f"Não há cidades com pelo menos {min_registros_cidade_sim} registros no cubo.")
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

    df_cubo = cubo_total[cubo_total["countryCode"] == country_sim].copy()
    if df_cubo.empty:
        st.warning("Não há dados do cubo cidade × espécie para o país da cidade focal.")
        return

    df_cidade_counts = df_cidade_counts_all[df_cidade_counts_all["countryCode"] == country_sim].copy()
    df_cubo_country = df_cubo.merge(
        df_cidade_counts[["countryCode", "stateProvince", "county"]],
        on=["countryCode", "stateProvince", "county"],
        how="inner",
    )
    df_cubo_country["city_id"] = (
        df_cubo_country["stateProvince"].astype(str) + "||" + df_cubo_country["county"].astype(str)
    )

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

    results = []
    for i, city_id in enumerate(pivot.index.tolist()):
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
    st.dataframe(df_tab.rename(columns=rotulos_pt), use_container_width=True, hide_index=True)

    st.subheader("Top (selecionável) — cidades mais similares")
    if df_sim.empty:
        st.warning("Não há resultados de similaridade para exibir.")
    else:
        max_top = int(min(50, len(df_sim)))
        top_x = st.slider("Top", min_value=5, max_value=max_top, value=min(20, max_top), step=1, key="sim_topx")
        df_top = df_sim.head(top_x).copy()
        df_top["cidade_label"] = df_top["county"].astype(str) + " — " + df_top["stateProvince"].astype(str)

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

            def venn_svg_similarity(score, label_text="Similaridade", left_title="Focal", right_title="Comparada", left_city="", right_city=""):
                if score is None or (isinstance(score, float) and np.isnan(score)):
                    score = 0.0
                score = float(np.clip(score, 0.0, 1.0))
                d = 140 * (1.0 - score) + 10
                cx1, cy = 160, 120
                cx2 = cx1 + d
                r = 95
                title_y = 16
                title_x1 = cx1 - 55
                title_x2 = cx2 + 55
                score_x = 210
                score_y = 238
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
                    <circle cx="{cx1}" cy="{cy}" r="{r}" fill="rgba(77,163,255,0.20)" stroke="rgba(77,163,255,0.95)" stroke-width="2"/>
                    <circle cx="{cx2}" cy="{cy}" r="{r}" fill="rgba(160,210,255,0.16)" stroke="rgba(160,210,255,0.95)" stroke-width="2"/>
                    <text x="{title_x1}" y="{title_y}" text-anchor="middle" fill="#FAFAFA" font-size="14">{left_title}</text>
                    <text x="{title_x2}" y="{title_y}" text-anchor="middle" fill="#FAFAFA" font-size="14">{right_title}</text>
                    <text x="{score_x}" y="{score_y}" text-anchor="middle" fill="#FAFAFA" font-size="14">{label_text} = {score:.3f}</text>
                    <circle cx="150" cy="{leg1_y}" r="6" fill="rgba(77,163,255,0.95)"/>
                    <text x="165" y="{leg1_y + 4}" fill="#FAFAFA" font-size="13">{left_title}: {left_city_s}</text>
                    <circle cx="150" cy="{leg2_y}" r="6" fill="rgba(160,210,255,0.95)"/>
                    <text x="165" y="{leg2_y + 4}" fill="#FAFAFA" font-size="13">{right_title}: {right_city_s}</text>
                </svg>
                </div>
                """

            st.subheader("Jaccard")
            st.caption(
                "O **Jaccard** mede semelhança **apenas pela presença/ausência** de espécies: "
                "é a razão entre espécies em comum e o total de espécies observadas no conjunto das duas cidades "
                "(não usa as quantidades de registros)."
            )
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

            df_prob = pd.DataFrame({"Especie": pivot.columns.astype(str), "p_focal": p_focal, "p_comp": q})
            df_prob = df_prob[(df_prob["p_focal"] > 0) | (df_prob["p_comp"] > 0)].copy()
            if df_prob.empty:
                st.warning("Não há espécies com probabilidade positiva para comparar.")
            else:
                focal_label = f"{cidade_focal} — {estado_focal} ({country_sim})"
                comp_label = f"{cidade_comp} — {estado_comp} ({country_sim})"

                st.markdown("**1) Espécie a espécie (escala log)**")
                st.caption(
                    "Cada ponto é uma espécie. Se as duas cidades têm proporções parecidas por espécie, "
                    "os pontos ficam perto da diagonal. Desvios grandes reduzem a similaridade JS."
                )

                eps = 1e-9
                df_scatter = df_prob.copy()
                df_scatter["log_p_focal"] = np.log10(df_scatter["p_focal"] + eps)
                df_scatter["log_p_comp"] = np.log10(df_scatter["p_comp"] + eps)
                vmin = float(min(df_scatter["log_p_focal"].min(), df_scatter["log_p_comp"].min()))
                vmax = float(max(df_scatter["log_p_focal"].max(), df_scatter["log_p_comp"].max()))
                pad = 0.15 * (vmax - vmin + 1e-9)
                dom_min, dom_max = vmin - pad, vmax + pad

                df_diag = pd.DataFrame({"x": [dom_min, dom_max], "y": [dom_min, dom_max]})
                diag = (
                    alt.Chart(df_diag)
                    .mark_line(strokeDash=[6, 6])
                    .encode(
                        x=alt.X("x:Q", title=f"log10(p) — Focal ({focal_label})", scale=alt.Scale(domain=[dom_min, dom_max], nice=False)),
                        y=alt.Y("y:Q", title=f"log10(p) — Comparada ({comp_label})", scale=alt.Scale(domain=[dom_min, dom_max], nice=False)),
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

                st.markdown("**2) Top espécies que mais carregam probabilidade**")
                st.caption(
                    "Mostra as espécies com maior peso (p) nas duas cidades. "
                    "Se o peso está concentrado em espécies diferentes, a Similaridade JS cai."
                )

                k = st.slider("Top espécies (K)", 10, 50, 20, 5, key="js_topk_species")
                df_top = df_prob.copy()
                df_top["peso"] = df_top["p_focal"] + df_top["p_comp"]
                df_top = df_top.sort_values("peso", ascending=False).head(int(k)).copy()

                df_top_long = df_top.melt(
                    id_vars=["Especie"],
                    value_vars=["p_focal", "p_comp"],
                    var_name="Cidade_raw",
                    value_name="p",
                )

                cidade_focal_label = f"Focal: {focal_label}"
                cidade_comp_label = f"Comparada: {comp_label}"
                df_top_long["Cidade"] = df_top_long["Cidade_raw"].replace(
                    {"p_focal": cidade_focal_label, "p_comp": cidade_comp_label}
                )
                ordem = df_top.sort_values("p_focal", ascending=False)["Especie"].astype(str).tolist()
                df_plot = df_top_long.copy()
                df_plot["p_signed"] = np.where(
                    df_plot["Cidade"].astype(str).str.startswith("Focal:"),
                    -df_plot["p"].astype(float),
                    df_plot["p"].astype(float),
                )
                df_plot["p_abs"] = df_plot["p"].astype(float)

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

                mostrar_kde = st.checkbox(
                    "Mostrar curva de densidade (extra — menos interpretável para JS)",
                    value=False,
                    key="js_show_kde_extra",
                )
                if mostrar_kde:
                    st.caption(
                        "Esta curva mostra a distribuição dos valores de p. "
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
                        .transform_density("p", as_=["p", "density"], groupby=["Cidade"], extent=[0, pmax])
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
                        .transform_density("p", as_=["p", "density"], groupby=["Cidade"], extent=[0, pmax])
                        .mark_line()
                        .encode(x="p:Q", y="density:Q", color=alt.Color("Cidade:N", title=""))
                    )
                    st.altair_chart(dens_area + dens_line, use_container_width=True)

    with st.expander("Notas metodológicas (fórmulas e interpretação)", expanded=True):
        st.markdown(
            "- **Similaridade (Jensen-Shannon)** varia de 0 a 1 (1 = mais parecido) e é calculada a partir da divergência de Jensen–Shannon.\n"
            "- **Similaridade (Jaccard)** varia de 0 a 1 e considera apenas presença/ausência de espécies.\n"
            f"- A comparação é feita entre a cidade focal e cada outra cidade usando a distribuição de registros por espécie, apenas são incluídas cidades com **pelo menos {min_registros_cidade_sim} registros**.\n"
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
