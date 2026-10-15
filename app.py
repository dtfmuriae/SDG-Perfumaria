import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import urllib.parse
import os
import google.generativeai as genai

# Configuração da página
st.set_page_config(page_title="Gestão Perfumaria & Cosméticos", page_icon="✨", layout="wide")

# Configurar Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Função auxiliar para formatar texto de data do banco para DD/MM/AAAA
def formatar_data_br(data_str):
    if not data_str:
        return ""
    try:
        dt = datetime.strptime(str(data_str).split()[0], "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return data_str

# Inicializar Banco de Dados SQLite local
def init_db():
    conn = sqlite3.connect("perfumaria.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    telefone TEXT NOT NULL,
                    nascimento DATE,
                    preferencias TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS produtos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    categoria TEXT,
                    duracao_dias INTEGER,
                    preco REAL)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS vendas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente_id INTEGER,
                    produto_id INTEGER,
                    data_venda DATE,
                    valor REAL,
                    tipo_pagamento TEXT,
                    status_pagamento TEXT,
                    vencimento DATE,
                    mensagem_ia TEXT,
                    FOREIGN KEY(cliente_id) REFERENCES clientes(id),
                    FOREIGN KEY(produto_id) REFERENCES produtos(id))''')
    conn.commit()
    conn.close()

init_db()

def get_connection():
    return sqlite3.connect("perfumaria.db")

# Função para chamar o Gemini
def gerar_texto_gemini(prompt):
    if not GEMINI_API_KEY:
        return "Configure a chave GEMINI_API_KEY nas variáveis de ambiente."
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Erro na IA: {str(e)}"

# Menu Lateral
st.sidebar.title("✨ Menu Principal")
menu = st.sidebar.radio("Navegar para:", [
    "🔔 Central de Avisos & IA",
    "💳 Vendas a Prazo / Crediário",
    "🛍️ Nova Venda",
    "👥 Cadastrar Clientes",
    "📦 Cadastrar Produtos"
])

# ----------------- 1. CENTRAL DE AVISOS -----------------
if menu == "🔔 Central de Avisos & IA":
    st.header("🔔 Central Inteligente de Avisos (Gemini AI)")
    tab1, tab2 = st.tabs(["Produtos Quase Acabando", "🎂 Aniversariantes"])
    
    conn = get_connection()
    
    with tab1:
        st.subheader("Clientes com produtos na reta final")
        query_vendas = '''
            SELECT v.id, c.nome, c.telefone, c.preferencias, p.nome as produto, p.duracao_dias, v.data_venda, v.mensagem_ia
            FROM vendas v
            JOIN clientes c ON v.cliente_id = c.id
            JOIN produtos p ON v.produto_id = p.id
        '''
        df_v = pd.read_sql_query(query_vendas, conn)
        
        if not df_v.empty:
            hoje = date.today()
            alertas = []
            for _, row in df_v.iterrows():
                dt_venda = datetime.strptime(row['data_venda'], "%Y-%m-%d").date()
                dt_termino = dt_venda + timedelta(days=int(row['duracao_dias']))
                dias_restantes = (dt_termino - hoje).days
                
                # Alerta se faltar 15 dias ou menos para acabar
                if 0 <= dias_restantes <= 15:
                    alertas.append({**row, "dias_restantes": dias_restantes, "dt_termino": dt_termino})
            
            if alertas:
                for item in alertas:
                    data_compra_br = formatar_data_br(item['data_venda'])
                    data_termino_br = item['dt_termino'].strftime("%d/%m/%Y")
                    
                    with st.expander(f"📦 {item['nome']} - {item['produto']} (Término previsto: {data_termino_br} | Faltam ~{item['dias_restantes']} dias)"):
                        st.write(f"*Data da Compra:* {data_compra_br} | *Telefone:* {item['telefone']}")
                        st.write(f"*Preferências:* {item['preferencias'] or 'Não informado'}")
                        
                        msg = item['mensagem_ia']
                        if not msg:
                            if st.button("Gerar Mensagem com Gemini", key=f"btn_ia_{item['id']}"):
                                prompt = (f"Escreva uma mensagem curta, acolhedora e calorosa de WhatsApp para a cliente {item['nome']}. "
                                          f"Ela comprou o produto {item['produto']} em {data_compra_br} e a previsão de término é por agora. "
                                          f"Preferências dela: {item['preferencias']}. Sugira a reposição com carinho. Máximo 3 frases, use emojis sutis.")
                                msg = gerar_texto_gemini(prompt)
                                c = conn.cursor()
                                c.execute("UPDATE vendas SET mensagem_ia = ? WHERE id = ?", (msg, item['id']))
                                conn.commit()
                                st.rerun()
                        else:
                            st.info(msg)
                            tel_limpo = "".join(filter(str.isdigit, item['telefone']))
                            link_zap = f"https://wa.me/55{tel_limpo}?text={urllib.parse.quote(msg)}"
                            st.link_button("👉 Abrir WhatsApp com a Mensagem", link_zap)
            else:
                st.success("Nenhum produto com previsão de término para os próximos 15 dias.")
        else:
            st.info("Nenhuma venda cadastrada ainda.")

    with tab2:
        st.subheader("Aniversariantes de Hoje")
        df_c = pd.read_sql_query("SELECT * FROM clientes", conn)
        hoje = date.today()
        aniversariantes = []
        
        for _, row in df_c.iterrows():
            if row['nascimento']:
                dt_nasc = datetime.strptime(row['nascimento'], "%Y-%m-%d").date()
                if dt_nasc.month == hoje.month and dt_nasc.day == hoje.day:
                    aniversariantes.append(row)
        
        if aniversariantes:
            for item in aniversariantes:
                nasc_br = formatar_data_br(item['nascimento'])
                st.write(f"🎉 *{item['nome']}* faz aniversário hoje! (Nascimento: {nasc_br})")
                prompt_niver = (f"Crie uma mensagem muito carinhosa e elegante de parabéns no WhatsApp para a cliente {item['nome']}. "
                                f"Ela é cliente da nossa loja de perfumaria e cosméticos. Dê um desconto ou mimo de presente na semana do aniversário dela. Máximo 3 frases.")
                if st.button("Gerar Mensagem de Aniversário", key=f"niver_{item['id']}"):
                    texto_niver = gerar_texto_gemini(prompt_niver)
                    st.text_area("Mensagem:", texto_niver)
                    tel_limpo = "".join(filter(str.isdigit, item['telefone']))
                    link_zap = f"https://wa.me/55{tel_limpo}?text={urllib.parse.quote(texto_niver)}"
                    st.link_button("👉 Enviar Parabéns no WhatsApp", link_zap)
        else:
            st.write("Nenhum cliente fazendo aniversário hoje.")
    conn.close()

# ----------------- 2. VENDAS A PRAZO / CREDIÁRIO -----------------
elif menu == "💳 Vendas a Prazo / Crediário":
    st.header("💳 Controle de Crediário e Contas a Receber")
    conn = get_connection()
    query = '''
        SELECT v.id, c.nome as cliente, c.telefone, p.nome as produto, v.valor, v.vencimento, v.status_pagamento
        FROM vendas v
        JOIN clientes c ON v.cliente_id = c.id
        JOIN produtos p ON v.produto_id = p.id
        WHERE v.tipo_pagamento = 'A Prazo'
    '''
    df_crediario = pd.read_sql_query(query, conn)
    
    if not df_crediario.empty:
        total_pendente = df_crediario[df_crediario['status_pagamento'] == 'Pendente']['valor'].sum()
        st.metric("Total em Aberto / A Receber", f"R$ {total_pendente:,.2f}")
        
        for _, row in df_crediario.iterrows():
            venc_br = formatar_data_br(row['vencimento'])
            
            col1, col2, col3, col4 = st.columns([3, 2, 2, 3])
            col1.write(f"*{row['cliente']}* ({row['produto']})")
            col2.write(f"R$ {row['valor']:.2f}")
            col3.write(f"Venc: {venc_br} ({row['status_pagamento']})")
            
            with col4:
                if row['status_pagamento'] == 'Pendente':
                    if st.button("Marcar como Pago", key=f"pago_{row['id']}"):
                        c = conn.cursor()
                        c.execute("UPDATE vendas SET status_pagamento = 'Pago' WHERE id = ?", (row['id'],))
                        conn.commit()
                        st.rerun()
                    
                    tel = "".join(filter(str.isdigit, row['telefone']))
                    msg_cob = (f"Olá, {row['cliente']}! Tudo bem? Passando para lembrar da sua parcela de R$ {row['valor']:.2f} "
                               f"com vencimento em {venc_br}. Segue nossa chave Pix para sua comodidade. ✨")
                    link = f"https://wa.me/55{tel}?text={urllib.parse.quote(msg_cob)}"
                    st.link_button("Lembrete WhatsApp", link)
                else:
                    st.success("✅ Liquidado")
    else:
        st.info("Nenhuma venda a prazo registrada.")
    conn.close()

# ----------------- 3. NOVA VENDA -----------------
elif menu == "🛍️ Nova Venda":
    st.header("🛍️ Registrar Venda")
    conn = get_connection()
    clientes = pd.read_sql_query("SELECT id, nome FROM clientes", conn)
    produtos = pd.read_sql_query("SELECT id, nome, preco FROM produtos", conn)
    
    if clientes.empty or produtos.empty:
        st.warning("Cadastre ao menos 1 cliente e 1 produto antes de registrar vendas.")
    else:
        with st.form("form_venda"):
            cliente_sel = st.selectbox("Cliente", clientes['nome'].tolist())
            produto_sel = st.selectbox("Produto", produtos['nome'].tolist())
            
            # Calendário no formato DD/MM/YYYY
            data_venda = st.date_input("Data da Venda", date.today(), format="DD/MM/YYYY")
            
            prod_info = produtos[produtos['nome'] == produto_sel].iloc[0]
            valor = st.number_input("Valor Total (R$)", value=float(prod_info['preco']))
            
            tipo_pagamento = st.radio("Condição de Pagamento", ["À Vista", "A Prazo"])
            
            # Vencimento no formato DD/MM/YYYY
            vencimento = st.date_input("Data de Vencimento (se a prazo)", date.today() + timedelta(days=30), format="DD/MM/YYYY")
            
            submit = st.form_submit_button("Salvar Venda")
            if submit:
                c_id = int(clientes[clientes['nome'] == cliente_sel].iloc[0]['id'])
                p_id = int(produtos[produtos['nome'] == produto_sel].iloc[0]['id'])
                status = "Pendente" if tipo_pagamento == "A Prazo" else "Pago"
                
                c = conn.cursor()
                c.execute('''INSERT INTO vendas (cliente_id, produto_id, data_venda, valor, tipo_pagamento, status_pagamento, vencimento)
                             VALUES (?, ?, ?, ?, ?, ?, ?)''',
                          (c_id, p_id, data_venda.strftime("%Y-%m-%d"), valor, tipo_pagamento, status, vencimento.strftime("%Y-%m-%d")))
                conn.commit()
                st.success("Venda cadastrada com sucesso!")
    conn.close()

# ----------------- 4. CADASTRO DE CLIENTES -----------------
elif menu == "👥 Cadastrar Clientes":
    st.header("👥 Cadastro de Clientes")
    with st.form("form_cliente"):
        nome = st.text_input("Nome Completo")
        telefone = st.text_input("WhatsApp (ex: 32999998888)")
        
# Calendário de nascimento no formato DD/MM/YYYY
       st.write("Data de Nascimento")
col_d, col_m, col_a = st.columns(3)
dia_nasc = col_d.number_input("Dia", min_value=1, max_value=31, value=1)
mes_nasc = col_m.number_input("Mês", min_value=1, max_value=12, value=1)
ano_nasc = col_a.number_input("Ano", min_value=1900, max_value=date.today().year, value=1990)

try:
    nascimento = date(int(ano_nasc), int(mes_nasc), int(dia_nasc))
except ValueError:
    nascimento = date(1990, 1, 1)
        preferencias = st.text_area("Preferências / Perfil (ex: fragrâncias doces, pele seca)")
        
        if st.form_submit_button("Cadastrar"):
            if nome and telefone:
                conn = get_connection()
                c = conn.cursor()
                c.execute("INSERT INTO clientes (nome, telefone, nascimento, preferencias) VALUES (?, ?, ?, ?)",
                          (nome, telefone, nascimento.strftime("%Y-%m-%d"), preferencias))
                conn.commit()
                conn.close()
                st.success("Cliente cadastrado com sucesso!")
            else:
                st.error("Preencha nome e WhatsApp.")

# ----------------- 5. CADASTRO DE PRODUTOS -----------------
elif menu == "📦 Cadastrar Produtos":
    st.header("📦 Cadastro de Produtos e Cosméticos")
    with st.form("form_produto"):
        nome = st.text_input("Nome do Produto (ex: Malbec Black 100ml)")
        categoria = st.selectbox("Categoria", ["Perfume", "Hidratante", "Maquiagem", "Cabelo", "Skincare"])
        duracao = st.number_input("Duração Média Estimada (dias de uso)", value=90)
        preco = st.number_input("Preço de Venda (R$)", value=149.90)
        
        if st.form_submit_button("Salvar Produto"):
            if nome:
                conn = get_connection()
                c = conn.cursor()
                c.execute("INSERT INTO produtos (nome, categoria, duracao_dias, preco) VALUES (?, ?, ?, ?)",
                          (nome, categoria, duracao, preco))
                conn.commit()
                conn.close()
                st.success("Produto cadastrado com sucesso!")
