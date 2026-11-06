import hashlib
import hmac
import io
import json
import re
from pathlib import Path
import unicodedata
import time

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit.errors import StreamlitSecretNotFoundError

st.set_page_config(page_title="Senso PCD de Ourinhos", layout="wide")
st.title("Senso PCD de Ourinhos")
st.caption("Painel administrativo")

try:
    accounts = st.secrets["usuarios"]
except (KeyError, StreamlitSecretNotFoundError):
    st.info("A administração precisa configurar as contas para habilitar o acesso.")
    st.stop()

if time.monotonic() >= st.session_state.get("expira", 0):
    st.session_state.pop("usuario", None)

if "usuario" not in st.session_state:
    with st.form("login", clear_on_submit=True):
        user = st.text_input("Usuário", max_chars=100)
        password = st.text_input("Senha", type="password", max_chars=256)
        submitted = st.form_submit_button("Entrar")
    if submitted:
        now = time.monotonic()
        if now < st.session_state.get("retry", 0):
            st.warning("Aguarde alguns segundos antes de tentar novamente.")
        else:
            account = accounts.get(user.strip().lower(), {})
            salt = bytes.fromhex(account.get("salt", "00" * 16))
            expected = account.get("hash", "00" * 32)
            actual = hashlib.scrypt(password.encode(), salt=salt, n=2**15,
                                    r=8, p=1, maxmem=64 * 1024**2).hex()
            if account and hmac.compare_digest(actual, expected):
                st.session_state.usuario = user.strip().lower()
                st.session_state.expira = now + 1800
                st.rerun()
            st.session_state.retry = now + 5
            st.error("Usuário ou senha inválidos.")
    st.stop()

if st.sidebar.button("Sair"):
    st.session_state.clear()
    st.rerun()

source = st.sidebar.file_uploader("Planilha Excel — uso local autorizado", type=["xlsx"]) if st.secrets.get("habilitar_importacao_local", False) else None
columns = ["Bairro", "Gênero", "Deficiência", "Serviço", "Data de nascimento", "Data do cadastro"]
if source:
    try:
        data = pd.read_excel(io.BytesIO(source.getvalue()), sheet_name="Dados",
                             usecols=lambda field: field in columns or field in {"Número", "Endereço"})
        data = data.loc[data["Número"].notna()].drop(columns="Número")
    except (ValueError, KeyError, OSError):
        st.error("Confira a aba Dados e os cabeçalhos da planilha.")
        st.stop()
    st.warning("Base administrativa carregada nesta sessão.")
else:
    st.info("Demonstração com dados fictícios.")
    data = pd.DataFrame([
        ("Centro", "Feminino", "Categoria A", "Serviço A", "1990-01-01", "2025-07-15"),
        ("Centro", "Masculino", "Categoria B", "Serviço B", None, "2025-07-16"),
        ("Vila Brasil", "Feminino", None, "Serviço A", "2001-01-01", None),
        ("Jardim Paulista", None, "Categoria A", None, "1980-01-01", None),
    ], columns=columns)

def chave_bairro(nome):
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(nome).strip().casefold())
        if not unicodedata.combining(c)
    )


# Public postal street-to-neighborhood references for Ourinhos.
BAIRRO_POR_RUA = {
    "jarbas alves de campos": "Vila Boa Esperança",
    "antonio henrique rolli": "Jardim Europa",
    "adao queiroz": "Jardim Eldorado",
    "adao queiros": "Jardim Eldorado",
    "stelio machado loureiro": "Vila Mano",
    "edvaldo ferreira da silva": "Núcleo Habitacional Choso Misato",
    "jornalista francisco de almeida": "Parque Minas Gerais",
    "andre gasparoto": "Jardim Beatriz",
    "angelo sedassi": "Vila Boa Esperança",
    "angelo sedassari": "Vila Boa Esperança",
    "marcelo borges moreira": "Residencial Ville de France",
    "padre bruno welter": "Conjunto Habitacional Helena Braz Vendramini"
}

def bairro_pelo_endereco(endereco):
    if pd.isna(endereco):
        return None
    rua = chave_bairro(re.split(r"[,;]|\s+\d", str(endereco), maxsplit=1)[0])
    rua = re.sub(r"^(?:rua|r\.?)\s+", "", rua)
    return BAIRRO_POR_RUA.get(" ".join(rua.split()))


arquivo = Path(__file__).with_name("bairros_ourinhos.json")
catalogo = json.loads(arquivo.read_text(encoding="utf-8"))
nomes_canonicos = catalogo.get("nomes_canonicos", {})
inferidos = 0
if "Endereço" in data:
    faltantes = data["Bairro"].astype("string").str.strip().fillna("").eq("")
    sugestoes = data.loc[faltantes, "Endereço"].map(bairro_pelo_endereco).dropna()
    data.loc[sugestoes.index, "Bairro"] = sugestoes
    inferidos = len(sugestoes)
    data = data.drop(columns="Endereço")
if inferidos:
    st.caption(f"{inferidos} cadastros sem bairro foram classificados pelo logradouro.")

data["Bairro"] = data["Bairro"].map(
    lambda nome: nomes_canonicos.get(chave_bairro(nome), nome) if pd.notna(nome) else nome
)
bairro = data["Bairro"].astype("string").str.strip().replace("", pd.NA).fillna("Não informado")
selected = st.sidebar.multiselect("Bairro", sorted(bairro.unique()))
subset = data.loc[bairro.isin(selected)] if selected else data
def contagens(coluna):
    return subset[coluna].astype("string").str.strip().replace("", pd.NA).fillna("Não informado").value_counts()


def mapa_bairros(totais, referencias, maior_contagem):
    pontos = []
    for nome, total in totais.items():
        coordenadas = referencias.get(chave_bairro(nome))
        if coordenadas is not None:
            pontos.append([*coordenadas, str(nome), int(total)])
    dados_js = json.dumps(pontos, ensure_ascii=True).replace("<", r"\u003c")
    components.html(f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>body{{margin:0;font:14px system-ui}}#map{{height:420px;border-radius:14px;background:#e2e8f0}}</style>
</head><body><div id="map" aria-label="Mapa de pontos agregados por bairro"></div>
<script>
const map = L.map('map').setView([-22.979,-49.871],13);
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
  {{attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}}).addTo(map);
for (const [lat, lon, nome, total] of {dados_js}) {{
  const circle = L.circleMarker([lat,lon],{{radius:30*Math.sqrt(total/{maior_contagem}),
    color:'#0e7490',weight:2,fillColor:'#2dd4bf',fillOpacity:.8}}).addTo(map);
  const tip = document.createElement('span');
  tip.textContent = nome + ' · ' + total + ' cadastro(s)';
  circle.bindTooltip(tip);
}}
</script></body></html>""", height=425)
    return sum(ponto[3] for ponto in pontos)


st.markdown("""<style>
[data-testid="stMetric"] {background:#ecfeff;border:1px solid #a5f3fc;border-radius:14px;padding:14px;color:#164e63}
[data-testid="stMetric"] [data-testid="stMetricLabel"] {color:#164e63}
[data-testid="stAppViewContainer"] h1 {color:#0e7490}
</style>""", unsafe_allow_html=True)
bairros = contagens("Bairro")
sem_bairro = int(bairros.get("Não informado", 0))
a, b, c = st.columns(3)
a.metric("Cadastros no recorte", len(subset))
b.metric("Bairros informados", len(bairros) - int(sem_bairro > 0))
c.metric("Cadastros sem bairro", sem_bairro)

territorio, perfil, qualidade = st.tabs(["🗺️ Território", "📊 Perfil", "📋 Qualidade"])
with territorio:
    st.subheader("Distribuição territorial · Ourinhos")
    referencias = catalogo["bairros"].copy()
    if source:
        referencia = st.file_uploader("Referência territorial CSV", type=["csv"],
                                     help="Colunas: Bairro, latitude, longitude. Use somente coordenadas agregadas e validadas.")
        if referencia:
            try:
                extras = {}
                tabela = pd.read_csv(referencia, sep=None, engine="python")
                for nome, lat, lon in tabela[["Bairro", "latitude", "longitude"]].itertuples(index=False, name=None):
                    lat, lon = float(lat), float(lon)
                    if pd.notna(nome) and -23.25 <= lat <= -22.70 and -50.15 <= lon <= -49.55:
                        extras[chave_bairro(nome)] = (lat, lon)
                referencias.update(extras)
            except (KeyError, ValueError, pd.errors.ParserError):
                st.error("Use um CSV com Bairro, latitude e longitude em graus decimais.")
    else:
        st.caption("Bairros reais de Ourinhos. As contagens da demonstração são fictícias.")
    total_por_bairro = bairro[bairro.ne("Não informado")].value_counts()
    maior_contagem = int(total_por_bairro.iloc[0]) if not total_por_bairro.empty else 1
    mapeados = mapa_bairros(
        bairros.drop(index="Não informado", errors="ignore"), referencias, maior_contagem
    )
    st.caption("OpenStreetMap · posições aproximadas por bairro, derivadas do Projeto Dengue. A área de cada círculo é proporcional ao número de cadastros.")
    st.caption(f"{mapeados} cadastros representados por pontos agregados · {len(subset) - mapeados} sem ponto no mapa.")
    sem_referencia = [str(nome) for nome in bairros.index if nome != "Não informado" and chave_bairro(nome) not in referencias]
    if sem_referencia:
        with st.expander("Bairros aguardando referência territorial"):
            st.write(", ".join(sem_referencia))
    st.subheader("Bairros com mais cadastros")
    top = bairros.drop(index="Não informado", errors="ignore").head(10)
    if not top.empty:
        st.bar_chart(top.rename("Cadastros").rename_axis("Bairro").reset_index(),
                     x="Bairro", y="Cadastros", horizontal=True, height=320, color="#0e7490")
    with st.expander("Ver tabela completa de bairros"):
        st.dataframe(bairros.rename("Cadastros"), height=300)

with perfil:
    for coluna, cor in [("Gênero", "#0e7490"), ("Serviço", "#7c3aed")]:
        st.subheader(coluna)
        contagem = contagens(coluna)
        if not contagem.empty:
            st.bar_chart(contagem.head(12).rename("Cadastros").rename_axis(coluna).reset_index(),
                         x=coluna, y="Cadastros", horizontal=True, height=280, color=cor)
        st.dataframe(contagem.rename("Cadastros"), height=240)

with qualidade:
    st.subheader("Preenchimento por campo")
    complete = subset.apply(lambda col: col.astype("string").str.strip().replace("", pd.NA).notna().sum())
    st.dataframe(complete.rename("Registros preenchidos"), height=260)
