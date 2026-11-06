import hashlib
import hmac
import io
import time

import pandas as pd
import streamlit as st
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
                             usecols=lambda field: field in columns or field == "Número")
        data = data.loc[data["Número"].notna(), columns]
    except (ValueError, KeyError, OSError):
        st.error("Confira a aba Dados e os cabeçalhos da planilha.")
        st.stop()
    st.warning("Base administrativa carregada nesta sessão.")
else:
    st.info("Demonstração com dados fictícios.")
    data = pd.DataFrame([
        ("Área A", "Feminino", "Categoria A", "Serviço A", "1990-01-01", "2025-07-15"),
        ("Área A", "Masculino", "Categoria B", "Serviço B", None, "2025-07-16"),
        ("Área B", "Feminino", None, "Serviço A", "2001-01-01", None),
        (None, None, "Categoria A", None, "1980-01-01", None),
    ], columns=columns)

bairro = data["Bairro"].astype("string").str.strip().replace("", pd.NA).fillna("Não informado")
selected = st.sidebar.multiselect("Bairro", sorted(bairro.unique()))
subset = data.loc[bairro.isin(selected)] if selected else data
st.metric("Cadastros no recorte", len(subset))
complete = subset.apply(lambda col: col.astype("string").str.strip().replace("", pd.NA).notna().sum())
st.subheader("Preenchimento por campo")
st.dataframe(complete.rename("Registros preenchidos"))
for column in ["Bairro", "Gênero", "Serviço"]:
    st.subheader(column)
    counts = subset[column].astype("string").str.strip().replace("", pd.NA).fillna("Não informado").value_counts()
    st.bar_chart(counts)
    st.dataframe(counts.rename("Cadastros"))
