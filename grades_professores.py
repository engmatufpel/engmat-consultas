"""Funções de apresentação reutilizadas da consulta pública."""
import html
import pandas as pd
import streamlit as st

def agrupar_turmas(m):
    """Agrupa turmas coincidentes apenas para exibição pública."""
    if m.empty:
        return m

    chaves = [
        "codigo", "disciplina", "professor",
        "sala", "dia_codigo", "slot"
    ]

    registros = []

    for _, grupo in m.groupby(chaves, sort=False, dropna=False):
        registro = grupo.iloc[0].copy()

        turmas = list(dict.fromkeys(
            str(t).strip()
            for t in grupo["turma"]
            if str(t).strip()
        ))

        registro["turma"] = "/".join(turmas)
        registros.append(registro)

    return pd.DataFrame(registros).reset_index(drop=True)


def grade(df):
    if df.empty:
        st.info("Nenhum horário encontrado.")
        return

    css = """
    <style>
    .grade-publica {
        width: 100%;
        table-layout: fixed;
        border-collapse: collapse;
        font-size: .86rem;
    }
    .grade-publica th, .grade-publica td {
        border: 1px solid #8885;
        padding: 8px;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        vertical-align: top;
    }
    .grade-publica th:first-child { width: 115px; }
    </style>
    """

    headers = "".join(
        "<th>" + html.escape(str(c)) + "</th>"
        for c in df.columns
    )
    body = "".join(
        "<tr>"
        + "".join(
            "<td>" + html.escape(str(v)) + "</td>"
            for v in row
        )
        + "</tr>"
        for row in df.itertuples(index=False, name=None)
    )

    st.html(
        css
        + '<div style="overflow-x:auto">'
        + '<table class="grade-publica"><thead><tr>'
        + headers
        + '</tr></thead><tbody>'
        + body
        + '</tbody></table></div>',
    )

