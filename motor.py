import io
import re
import unicodedata
from collections import defaultdict
import pandas as pd

DIAS = {'2':'Segunda','3':'Terça','4':'Quarta','5':'Quinta','6':'Sexta'}
SLOTS = {'11':'08:00–08:50','12':'08:50–09:40','13':'10:00–10:50','14':'10:50–11:40','15':'11:40–12:30','21':'13:30–14:20','22':'14:20–15:10','23':'15:10–16:00','24':'16:00–16:50','25':'17:10–18:00','31':'19:00–19:50','32':'19:50–20:40','33':'20:50–21:40','34':'21:40–22:30'}
REQUIRED = ['semestre','codigo','disciplina','turma','professor','creditos'] + [f'horario {i}' for i in range(1,7)] + [f'sala {i}' for i in range(1,7)]

def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFD',str(s).strip().lower()) if unicodedata.category(c) != 'Mn')

def read_csv(source):
    raw = source.read() if hasattr(source,'read') else open(source,'rb').read()
    if isinstance(raw,str): raw=raw.encode('utf-8')
    for enc in ('utf-8-sig','latin-1'):
        try:
            d=pd.read_csv(io.BytesIO(raw),sep=None,engine='python',dtype=str,encoding=enc,keep_default_na=False)
            d.columns=[norm(c) for c in d.columns]
            return d
        except UnicodeError: continue
    raise ValueError('Não foi possível ler o CSV.')

def clean(df):
    d=df.copy().fillna('')
    d.columns=[norm(c) for c in d.columns]
    for c in d.columns: d[c]=d[c].astype(str).str.strip().replace({'nan':'','None':''})
    return d

def group(v,period):
    try: n=int(float(v))
    except (ValueError,TypeError): return 'Sem classificação'
    if n==88:return 'Optativas'
    if n==11:return 'Oferta para outros cursos'
    parity=int(period.split('-')[1])%2
    return f'{n}º semestre' if n in range(1 if parity==1 else 2,11,2) else 'Reofertas'

def meetings(df):
    out=[]
    for idx,r in clean(df).iterrows():
        for i in range(1,7):
            h=r.get(f'horario {i}','')
            if not h:continue
            if len(h)!=3 or h[0] not in DIAS or h[1:] not in SLOTS:continue
            out.append({'linha':idx+2,'semestre':r.get('semestre',''),'codigo':r.get('codigo',''),'disciplina':r.get('disciplina',''),'turma':r.get('turma',''),'professor':r.get('professor',''),'sala':r.get(f'sala {i}',''),'dia':DIAS[h[0]],'dia_codigo':h[0],'slot':h[1:],'horario':SLOTS[h[1:]],'alunos':r.get('alunos','')})
    return pd.DataFrame(out)

def validate(df):
    d=clean(df); errors=[]
    for c in REQUIRED:
        if c not in d.columns: errors.append({'tipo':'Estrutura','linha':'—','detalhe':f'Coluna obrigatória ausente: {c}'})
    if errors:return pd.DataFrame(errors)
    for ix,r in d.iterrows():
        line=ix+2
        for c in ('semestre','codigo','disciplina'):
            if not r[c]:errors.append({'tipo':'Campo obrigatório','linha':line,'detalhe':f'{c} vazio'})
        for i in range(1,7):
            h=r[f'horario {i}']
            if h and (len(h)!=3 or h[0] not in DIAS or h[1:] not in SLOTS):
                errors.append({'tipo':'Horário inválido','linha':line,'detalhe':f'horario {i}: {h}'})
    m=meetings(d)
    if m.empty:return pd.DataFrame(errors,columns=['tipo','linha','detalhe'])
    def conflict(kind,key,value):
        if not value or norm(value) in ('a definir','-'):return
        for (day,slot),rows in m.groupby(['dia_codigo','slot']):
            selected=rows[rows[key].apply(lambda x: value in [z.strip() for z in x.split(',')] if kind=='Professor' else x==value)]
            identities=set(zip(selected['codigo'],selected['turma']))
            if len(identities)>1:
                errors.append({'tipo':f'Conflito de {kind.lower()}','linha':', '.join(map(str,selected['linha'])),'detalhe':f'{value} — {DIAS[day]} {SLOTS[slot]}'})
    for p in sorted({x.strip() for s in m['professor'] for x in s.split(',') if x.strip()}):conflict('Professor','professor',p)
    for sala in sorted(set(m['sala'])):conflict('Sala','sala',sala)
    for (day,slot),rows in m.groupby(['dia_codigo','slot']):
        seen=defaultdict(set)
        for _,r in rows.iterrows():
            for a in r['alunos'].split(','):
                a=a.strip()
                if a:seen[a].add((r['codigo'],r['turma']))
        for a,classes in seen.items():
            if len(classes)>1:errors.append({'tipo':'Conflito de aluno','linha':'—','detalhe':f'Matrícula {a} — {DIAS[day]} {SLOTS[slot]}'})
    return pd.DataFrame(errors,columns=['tipo','linha','detalhe']).drop_duplicates()

def timetable(m):
    if m.empty:return pd.DataFrame()
    data=[]
    for slot,label in SLOTS.items():
        row={'Horário':label}
        for dc,dn in DIAS.items():
            items=m[(m['slot']==slot)&(m['dia_codigo']==dc)]
            row[dn]='\n\n'.join(f"{r.codigo}-{r.turma} · {r.disciplina}\n{r.professor} · Sala {r.sala or 'a definir'}" for r in items.itertuples())
        data.append(row)
    return pd.DataFrame(data)
