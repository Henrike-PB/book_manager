"""
book_dashboard.py
Streamlit dashboard portátil para gerenciar livros (custo / venda / lucro).
- Persistência em SQLite (books.db) na mesma pasta do executável/script.
- Índice exibido (1..N) separado do ID técnico (autoincremento).
- Adicionar / Editar / Excluir / Exportar CSV
- Gráficos grandes (Plotly) e design limpo (UX/UI).
- Para empacotar em .exe use as instruções abaixo com PyInstaller.

Requisitos: streamlit, pandas, plotly, pillow
"""

import os
import sys
from pathlib import Path
import sqlite3
import pandas as pd
import io
import base64
from PIL import Image
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

APP_TITLE = "Desapego Literário Dashboard"
DB_FILE = "books.db"
LOGO_FILE = "logo.png"  # opcional: coloque sua logo com esse nome na mesma pasta

# ---------- Helpers de caminho (para persistência com exe) ----------
def get_cwd_path(filename: str) -> Path:
    """
    Retorna o caminho onde o DB/arquivos devem ser criados:
    - se for exe (frozen), usamos o current working directory (onde o exe foi executado).
    - se for script, usamos o current working directory também.
    """
    return Path(os.getcwd()) / filename

DB_PATH = get_cwd_path(DB_FILE)
LOGO_PATH = get_cwd_path(LOGO_FILE)

# ---------- DB ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            cost REAL NOT NULL,
            price REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def fetch_books_df() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT id, title, cost, price FROM books ORDER BY id ASC", conn)
    conn.close()
    return df

def add_book_db(title: str, cost: float, price: float):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO books (title, cost, price) VALUES (?, ?, ?)", (title, cost, price))
    conn.commit()
    conn.close()

def update_book_db(book_id: int, title: str, cost: float, price: float):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE books SET title=?, cost=?, price=? WHERE id=?", (title, cost, price, book_id))
    conn.commit()
    conn.close()

def delete_book_db(book_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM books WHERE id=?", (book_id,))
    conn.commit()
    conn.close()

# ---------- UI helpers ----------
def load_logo_bytes(path: Path):
    if path.exists():
        try:
            return path.read_bytes()
        except:
            return None
    return None

def df_with_index_for_display(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    df2['Lucro (R$)'] = df2['price'] - df2['cost']
    df2['Índice'] = range(1, len(df2) + 1)
    if 'id' in df2.columns:
        df2 = df2[['Índice', 'id', 'title', 'cost', 'price', 'Lucro (R$)']]
        df2.columns = ['Índice', 'ID', 'Título', 'Custo (R$)', 'Venda (R$)', 'Lucro (R$)']
    else:
        df2 = pd.DataFrame(columns=['Índice', 'ID', 'Título', 'Custo (R$)', 'Venda (R$)', 'Lucro (R$)'])
    return df2


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, float_format="%.2f", encoding='utf-8-sig').encode('utf-8-sig')

# ---------- Inicialização ----------
init_db()

# ---------- Streamlit App ----------
st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="expanded")

# custom CSS for nicer look
st.markdown("""
<style>
/* container background */
.block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
}
/* card style em volta de seções */
.card {
    background: white;
    padding: 16px;
    border-radius: 12px;
    box-shadow: 0 8px 20px rgba(2,6,23,0.06);
}
.dark .card { background: #071022; color: #e6eef8; }
/* small muted */
.small-muted { color: #6b7280; font-size:13px; }
/* botão export */
.streamlit-expanderHeader {font-weight:600;}
</style>
""", unsafe_allow_html=True)

# Header (logo + title + actions)
col1, col2 = st.columns([0.12, 0.88])
with col1:
    logo_bytes = load_logo_bytes(LOGO_PATH)
    if logo_bytes:
        st.image(logo_bytes, width=96)
    else:
        # placeholder logo (nice colored square with HPB)
        st.markdown("<div style='width:96px;height:96px;border-radius:12px;background:linear-gradient(135deg,#2563eb,#10b981);display:flex;align-items:center;justify-content:center;color:white;font-weight:700;font-size:20px'>HPB</div>", unsafe_allow_html=True)

with col2:
    st.markdown(f"## {APP_TITLE}")
    st.markdown("Gerencie custos, preços e lucros — visual limpo, responsivo e fácil de usar.")
    st.markdown("---")

# Sidebar: formulário de adicionar/editar + filtros
st.sidebar.title("Ações")
mode = st.sidebar.selectbox("Modo", ["Adicionar livro", "Editar livro existente"])
st.sidebar.markdown("### Filtros / Export")
search = st.sidebar.text_input("Pesquisar por título")
filter_profit = st.sidebar.selectbox("Mostrar", ["Todos", "Lucro positivo", "Lucro negativo/zero"])
st.sidebar.markdown("### Exportar")
if st.sidebar.button("Exportar CSV (todos)"):
    df_export = fetch_books_df()
    if df_export.empty:
        st.sidebar.warning("Sem dados para exportar.")
    else:
        st.sidebar.success("Preparando download...")
        b = to_csv_bytes(df_export)
        st.sidebar.download_button("Baixar CSV", data=b, file_name="books_export.csv", mime="text/csv")

# main content: top = table, bottom = charts
df = fetch_books_df()
df_display = df_with_index_for_display(df)

# Apply search and filter (for display only)
def apply_filters(df_orig: pd.DataFrame) -> pd.DataFrame:
    df2 = df_orig.copy()
    if search:
        df2 = df2[df2['title'].str.contains(search, case=False, na=False)]
    if filter_profit != "Todos":
        df2['profit'] = df2['price'] - df2['cost']
        if filter_profit == "Lucro positivo":
            df2 = df2[df2['profit'] > 0]
        else:
            df2 = df2[df2['profit'] <= 0]
    return df2

df_filtered = apply_filters(df)

# Show table (with index visual). We'll use the display DF built from df_filtered
df_filtered_display = df_with_index_for_display(df_filtered)
st.markdown("### 📚 Lista de livros")
st.markdown('<div class="card">', unsafe_allow_html=True)
# show totals at top (summary)
total_cost = df['cost'].sum() if not df.empty else 0.0
total_price = df['price'].sum() if not df.empty else 0.0
total_profit = (df['price'] - df['cost']).sum() if not df.empty else 0.0

tcol1, tcol2, tcol3 = st.columns([1,1,1])
tcol1.metric("Custo total", f"R$ {total_cost:,.2f}")
tcol2.metric("Venda total", f"R$ {total_price:,.2f}")
tcol3.metric("Lucro total", f"R$ {total_profit:,.2f}")

st.markdown("---")
st.dataframe(df_filtered_display, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# Select a row for edit/delete using Índice mapping
st.markdown("### Ações rápidas")
if df_filtered.empty:
    st.info("Sem livros cadastrados (ou filtro resultou em vazio).")
else:
    # map index display -> book id
    mapping = df_filtered.reset_index(drop=True)[['title','cost','price','id']].copy()
    mapping['Índice_exib'] = range(1, len(mapping) + 1)
    # choice list
    choice_strs = mapping.apply(lambda r: f"{int(r['Índice_exib'])} — {r['title']} (Venda: R$ {r['price']:.2f})", axis=1).tolist()
    selected_choice = st.selectbox("Selecione um livro (para editar ou excluir)", ["— nenhum —"] + choice_strs)
    selected_book_id = None
    if selected_choice != "— nenhum —":
        idx = choice_strs.index(selected_choice)
        selected_book_id = int(mapping.loc[idx, 'id'])

# Form area (Adicionar / Editar)
st.markdown("### Formulário")
with st.form("book_form", clear_on_submit=False):
    if mode == "Adicionar livro":
        st.subheader("Adicionar novo livro")
        title = st.text_input("Título")
        cost = st.number_input("Custo (R$)", min_value=0.0, value=0.0, format="%.2f")
        price = st.number_input("Venda (R$)", min_value=0.0, value=0.0, format="%.2f")
        submitted = st.form_submit_button("Adicionar")
        if submitted:
            if not title.strip():
                st.error("Título não pode ficar vazio.")
            else:
                add_book_db(title.strip(), float(cost), float(price))
                st.success(f"Livro '{title.strip()}' adicionado.")
                st.experimental_rerun()
    else:
        st.subheader("Editar livro existente")
        if selected_book_id is None:
            st.warning("Selecione um livro acima para editar.")
        else:
            # load current values
            sel_row = df[df['id'] == selected_book_id].iloc[0]
            title_e = st.text_input("Título", value=sel_row['title'])
            cost_e = st.number_input("Custo (R$)", min_value=0.0, value=float(sel_row['cost']), format="%.2f", key="cost_e")
            price_e = st.number_input("Venda (R$)", min_value=0.0, value=float(sel_row['price']), format="%.2f", key="price_e")
            submitted_edit = st.form_submit_button("Salvar alterações")
            if submitted_edit:
                if not title_e.strip():
                    st.error("Título não pode ficar vazio.")
                else:
                    update_book_db(int(selected_book_id), title_e.strip(), float(cost_e), float(price_e))
                    st.success("Alterações salvas.")
                    st.experimental_rerun()

# Delete action (separado, com confirmação)
if selected_book_id is not None:
    if st.button("Excluir o livro selecionado", key="delbtn"):
        # confirmação
        if st.confirm(f"Confirmar exclusão do livro selecionado (ID {selected_book_id})?"):
            delete_book_db(selected_book_id)
            st.success("Livro excluído.")
            st.experimental_rerun()

# ---------- Charts section (grandes, responsivos) ----------
st.markdown("### 📊 Análise visual")
st.markdown('<div class="card">', unsafe_allow_html=True)

# Large bar chart for totals
totals = {
    "Custo": total_cost,
    "Venda": total_price,
    "Lucro": total_profit
}
bar_fig = go.Figure(data=[go.Bar(
    x=list(totals.keys()),
    y=list(totals.values()),
    marker=dict(color=["#FB7185", "#60A5FA", "#34D399"]),
    text=[f"R$ {v:,.2f}" for v in totals.values()],
    textposition='outside'
)])
bar_fig.update_layout(title="Totais: Custo / Venda / Lucro", yaxis_title="R$",
                      margin=dict(t=40,l=20,r=20,b=20), height=420)

# Pie chart: distribuição de lucro por livro (top)
if not df.empty:
    df['profit'] = df['price'] - df['cost']
    prof = df.set_index('title')['profit'].abs().sort_values(ascending=False)
    if len(prof) > 8:
        top = prof.iloc[:8]
        others = prof.iloc[8:].sum()
        labels = list(top.index) + ['Outros']
        vals = list(top.values) + [others]
    else:
        labels = list(prof.index)
        vals = list(prof.values)
    pie_fig = px.pie(values=vals, names=labels, title="Distribuição de lucro por livro")
    pie_fig.update_traces(textposition='inside', textinfo='percent+label')
    pie_fig.update_layout(margin=dict(t=30,l=10,r=10,b=10), height=420)
else:
    pie_fig = go.Figure()
    pie_fig.update_layout(title="Nenhum dado para distribuição", height=420)

c1, c2 = st.columns([2,1])
with c1:
    st.plotly_chart(bar_fig, use_container_width=True)
with c2:
    st.plotly_chart(pie_fig, use_container_width=True)

st.markdown("</div>", unsafe_allow_html=True)

# ---------- Footer ----------
st.markdown("---")
st.markdown("<div style='text-align:center' class='small-muted'>Dados salvos localmente em <code>books.db</code>. Para trocar a logo substitua <code>logo.png</code> na mesma pasta do executável.</div>", unsafe_allow_html=True)
