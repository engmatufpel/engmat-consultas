"""Consulta pública de horários por semestre, reofertas e optativas."""
import html
import json
import os
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from motor import meetings, timetable

PUBLIC_DB = (
    Path(
        os.environ.get(
            "HORARIOS_PUBLIC_DIR",
            str(Path(__file__).resolve().parent / "publicado"),
        )
    ).resolve()
    / "horarios-publicos.sqlite3"
)

st.set_page_config(
    page_title="Horários · Engenharia de Materiais",
    layout="wide",
)

st.title("Horários · Engenharia de Materiais")
st.caption("CDTec / UFPel · Consulta pública aos horários publicados")


@st.cache_data(ttl=30)
def carregar_periodos():
    if not PUBLIC_DB.is_file():
        return []
    with sqlite3.connect(f"file:{PUBLIC_DB}?mode=ro", uri=True) as con:
        return con.execute(
            "SELECT periodo, publicado_em "
            "FROM publicacoes ORDER BY periodo DESC"
        ).fetchall()


@st.cache_data(ttl=30)
def carregar_horarios(periodo):
    with sqlite3.connect(f"file:{PUBLIC_DB}?mode=ro", uri=True) as con:
        registros = con.execute(
            "SELECT dados FROM horarios WHERE periodo=?",
            (periodo,),
        ).fetchall()
    return pd.DataFrame([json.loads(r[0]) for r in registros])


def classificar(semestre, periodo):
    """Classifica uma oferta conforme o período letivo consultado."""
    try:
        numero = int(str(semestre).strip())
        periodo_letivo = int(periodo.rsplit("-", 1)[1])
    except (ValueError, TypeError, IndexError):
        return None

    if numero == 88:
        return "Optativas"

    if numero < 1 or numero > 10:
        return None

    if numero % 2 != periodo_letivo % 2:
        return "Reofertas"

    return f"{numero}º semestre"



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


try:
    publicacoes = carregar_periodos()
except (sqlite3.DatabaseError, OSError):
    st.error("Não foi possível carregar os períodos publicados.")
    st.stop()

if not publicacoes:
    st.info("Ainda não há horários publicados.")
    st.stop()

periodos = dict(publicacoes)
periodo = st.selectbox("Período letivo", list(periodos))
st.caption(f"Publicado em {periodos[periodo]} (UTC)")

try:
    df = carregar_horarios(periodo)
except (sqlite3.DatabaseError, OSError, ValueError, TypeError):
    st.error("Não foi possível carregar os horários publicados.")
    st.stop()

if df.empty:
    st.info("Não há turmas publicadas para este período.")
    st.stop()

df["grupo"] = df["semestre"].apply(
    lambda s: classificar(s, periodo)
)

# Semestres regulares aparecem em ordem crescente.
regular = sorted(
    (g for g in df["grupo"].dropna().unique()
     if g.endswith("º semestre")),
    key=lambda g: int(g.split("º")[0]),
)

grupos = regular + [
    g for g in ("Reofertas", "Optativas")
    if g in df["grupo"].values
]

if not grupos:
    st.warning("Nenhuma oferta possui classificação reconhecida.")
    st.stop()

grupo = st.selectbox("Clique aqui para selecionar a turma ou semestre:", grupos)

# Filtra antes de remover duplicações entre PPCs.
selecionado = df[df["grupo"] == grupo].copy()

# Uma mesma turma compartilhada entre PPCs aparece uma vez no grupo.
operacionais = [
    c for c in selecionado.columns
    if c not in ("ppc", "semestre", "grupo")
]
selecionado = selecionado.drop_duplicates(subset=operacionais)

st.subheader(grupo)
st.caption(f"{len(selecionado)} turma(s) publicada(s) neste grupo.")

colunas = [
    c for c in ("codigo", "disciplina", "turma", "professor")
    if c in selecionado.columns
]

st.dataframe(
    selecionado[colunas],
    hide_index=True,
    use_container_width=True,
)

m = meetings(selecionado)

if not m.empty:
    m = agrupar_turmas(m)
    grade(timetable(m))
else:
    st.info("As turmas selecionadas ainda não possuem horários definidos.")
