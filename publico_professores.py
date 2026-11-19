"""Consulta pública dos horários e indicadores dos professores."""

import json
import os
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from motor import meetings, timetable
from grades_professores import agrupar_turmas, grade

PUBLIC_DIR = Path(
    os.environ.get(
        'HORARIOS_PUBLIC_DIR',
        str(Path(__file__).resolve().parent / 'dados_publicos')
    )
).resolve()

DB = PUBLIC_DIR / 'horarios-publicos.sqlite3'

st.set_page_config(
    page_title='Horários dos Professores · Engenharia de Materiais',
    layout='wide',
)

st.title('Horários dos Professores · Engenharia de Materiais')
st.caption('CDTec / UFPel · Consulta aos horários publicados e indicadores de planejamento')


@st.cache_data(ttl=30)
def carregar_periodos():
    with sqlite3.connect(f'file:{DB}?mode=ro', uri=True) as con:
        return con.execute(
            'SELECT periodo, publicado_em FROM publicacoes ORDER BY periodo DESC'
        ).fetchall()


@st.cache_data(ttl=30)
def carregar_dados(periodo):
    with sqlite3.connect(f'file:{DB}?mode=ro', uri=True) as con:
        indicador = con.execute(
            'SELECT dados FROM indicadores WHERE periodo=?', (periodo,)
        ).fetchone()

        ofertas = con.execute(
            'SELECT dados FROM oferta_demanda WHERE periodo=? ORDER BY ordem',
            (periodo,)
        ).fetchall()

        professores = con.execute(
            'SELECT dados FROM resumo_professores WHERE periodo=? ORDER BY professor',
            (periodo,)
        ).fetchall()

        horarios = con.execute(
            'SELECT dados FROM horarios WHERE periodo=?',
            (periodo,)
        ).fetchall()

    return (
        json.loads(indicador[0]) if indicador else {},
        pd.DataFrame([json.loads(r[0]) for r in ofertas]),
        pd.DataFrame([json.loads(r[0]) for r in professores]),
        pd.DataFrame([json.loads(r[0]) for r in horarios]),
    )


if not DB.is_file():
    st.error('Banco público de horários não encontrado.')
    st.stop()

try:
    publicacoes = carregar_periodos()
except (sqlite3.DatabaseError, OSError):
    st.error('Não foi possível carregar os períodos.')
    st.stop()

if not publicacoes:
    st.info('Nenhum período publicado.')
    st.stop()

periodos = dict(publicacoes)
periodo = st.selectbox('Período letivo', list(periodos))
st.caption(f'Publicado em {periodos[periodo]} (UTC)')

try:
    indicadores, ofertas, professores, horarios = carregar_dados(periodo)
except (sqlite3.DatabaseError, ValueError, TypeError, KeyError):
    st.error('Não foi possível carregar os dados publicados.')
    st.stop()

if not indicadores:
    st.warning('Ainda não existem indicadores publicados para este período.')
    st.stop()

st.subheader('Indicadores gerais')

nomes = [
    'Turmas distintas',
    'Disciplinas distintas',
    'Estudantes com sugestões',
    'Matrículas previstas',
    'Vagas informadas',
    'Turmas sem professor',
    'Turmas sem horário',
    'Turmas com demanda acima das vagas',
]

for inicio in (0, 4):
    colunas = st.columns(4)
    for coluna, nome in zip(colunas, nomes[inicio:inicio + 4]):
        coluna.metric(nome, indicadores.get(nome, 0))

st.caption(
    'Matrículas previstas representam sugestões administrativas, '
    'não matrículas oficiais. Estudantes distintos são contados uma única vez.'
)

st.divider()
st.subheader('Oferta e demanda por turma')

if ofertas.empty:
    st.info('Nenhuma oferta consolidada.')
else:
    st.dataframe(ofertas, hide_index=True, use_container_width=True)

st.divider()
st.subheader('Resumo por professor')

if professores.empty:
    st.info('Nenhum professor definido.')
else:
    st.dataframe(professores, hide_index=True, use_container_width=True)

st.caption(
    'Créditos associados não representam encargos docentes oficiais. '
    'Quando uma turma possui mais de um professor, os créditos são '
    'associados a cada um deles.'
)

st.divider()
st.subheader('Consulta individual dos professores')

if professores.empty or horarios.empty:
    st.info('Não existem dados suficientes para a consulta individual.')
    st.stop()

opcoes = professores['Professor'].dropna().astype(str).tolist()

professor = st.selectbox(
    'Clique aqui para selecionar o professor:',
    opcoes,
)

resumo = professores[professores['Professor'] == professor].iloc[0]

st.markdown('**Resumo individual**')
a, b, c = st.columns(3)
a.metric('Disciplinas', int(resumo['Disciplinas']))
b.metric('Créditos associados', resumo['Créditos associados'])
c.metric('Matrículas previstas', int(resumo['Matrículas previstas']))

st.markdown('**Grade semanal**')

# Elimina ofertas idênticas compartilhadas entre PPCs.
operacionais = [
    coluna for coluna in horarios.columns
    if coluna not in ('ppc', 'semestre')
]
horarios = horarios.drop_duplicates(subset=operacionais)

# Seleciona ofertas atribuídas ao docente, inclusive em co-docência.
selecionados = horarios[
    horarios['professor'].fillna('').astype(str).apply(
        lambda valor: professor in [
            nome.strip() for nome in valor.split(',')
        ]
    )
].copy()

if selecionados.empty:
    st.info('Nenhuma turma encontrada para este professor.')
else:
    encontros = meetings(selecionados)

    if encontros.empty:
        st.info('Não existem horários definidos para este professor.')
    else:
        encontros = agrupar_turmas(encontros)
        grade(timetable(encontros))
