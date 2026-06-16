from fastapi import FastAPI, Form, Request, Response, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy import create_engine, text
from starlette.middleware.sessions import SessionMiddleware
from datetime import datetime, date
import json
import urllib.parse
import os
import shutil
import requests
import re

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="jpms_solucoes_gestao_2026_seguro")

# Conexão com o Banco de Dados do Railway
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:GNlZnHiuKAcFnpgXhwILfigqKCNkaHqx@interchange.proxy.rlwy.net:44559/railway")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Pasta para salvar o certificado digital enviado pelo usuário
UPLOAD_DIR = "certificados"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Criação das tabelas do sistema JPMS / Steel Goose
with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL, status TEXT DEFAULT 'ATIVO');
        CREATE TABLE IF NOT EXISTS produtos (id SERIAL PRIMARY KEY, codigo_barras TEXT UNIQUE, nome TEXT NOT NULL, categoria TEXT DEFAULT 'OUTROS', preco DECIMAL(10,2) DEFAULT 0.00, estoque INT DEFAULT 0);
        CREATE TABLE IF NOT EXISTS comandas (id SERIAL PRIMARY KEY, numero_comanda TEXT NOT NULL, total_conta DECIMAL(10,2) DEFAULT 0.00, status TEXT DEFAULT 'ABERTA', forma_pagamento TEXT, data_fechamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP, nfe_solicitada BOOLEAN DEFAULT FALSE, cpf_nota TEXT);
        CREATE TABLE IF NOT EXISTS vendas_itens (id SERIAL PRIMARY KEY, comanda_num TEXT, item_nome TEXT, valor DECIMAL(10,2), data_venda DATE DEFAULT CURRENT_DATE, hora_venda TIME DEFAULT CURRENT_TIME, status TEXT DEFAULT 'ABERTA');
        CREATE TABLE IF NOT EXISTS fila_impressao (id SERIAL PRIMARY KEY, conteudo TEXT, status TEXT DEFAULT 'PENDENTE', data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS historico_estoque (id SERIAL PRIMARY KEY, produto_nome TEXT, qtd_adicionada INT, data_entrada DATE DEFAULT CURRENT_DATE);
        CREATE TABLE IF NOT EXISTS configuracoes_nfe (id SERIAL PRIMARY KEY, token_focus TEXT, ambiente TEXT DEFAULT 'HOMOLOGACAO', senha_certificado TEXT, nome_arquivo_cert TEXT);
    """))

# Migrações seguras e adição do STATUS nos usuários antigos
MIGRACOES = [
    "ALTER TABLE comandas ALTER COLUMN status SET DEFAULT 'ABERTA';",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'ATIVO';"
]
for mig in MIGRACOES:
    try:
        with engine.begin() as conn: conn.execute(text(mig))
    except Exception: pass

# Cria o Admin Padrão e linha fiscal
try:
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO usuarios (username, password, role, status) VALUES ('admin', '1234', 'admin', 'ATIVO') ON CONFLICT (username) DO NOTHING"))
        cfg_exist = conn.execute(text("SELECT id FROM configuracoes_nfe LIMIT 1")).fetchone()
        if not cfg_exist:
            conn.execute(text("INSERT INTO configuracoes_nfe (token_focus, ambiente) VALUES ('', 'HOMOLOGACAO')"))
except Exception: pass

# ==========================================
# IDENTIDADE VISUAL: STEEL GOOSE MOTO GROUP
# ==========================================
COR_FUNDO = "#121214"      
COR_CARD = "#000000"       
COR_AMARELO = "#F3BA16"    
COR_VERMELHO = "#C82828"   
COR_TEXTO = "#E0E0E0"      
COR_BORDA = "#222225"      
COR_INPUT = "#141416"      

IMG_URL = "/logo.png"

CSS = f"""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>Steel Goose - Sistema</title>
<style>
    * {{ box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }}
    body {{ margin: 0; background: {COR_FUNDO}; color: {COR_TEXTO}; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}
    
    h1, h2, h3, h4 {{ color: {COR_AMARELO}; text-transform: uppercase; margin-top: 0; letter-spacing: 1px; }}
    
    .btn-acao {{ display: block; width: 100%; padding: 15px; margin-bottom: 8px; border: none; border-radius: 5px; font-weight: bold; color: #000; cursor: pointer; text-align: center; text-decoration: none; font-size: 14px; background: {COR_AMARELO}; transition: 0.3s; text-transform: uppercase; }}
    .btn-acao:hover {{ opacity: 0.9; transform: scale(0.98); box-shadow: 0 0 12px rgba(243, 186, 22, 0.4); }}
    
    .btn-dark {{ background: #1A1A1A; color: {COR_AMARELO}; border: 1px solid {COR_AMARELO}; }}
    .btn-dark:hover {{ background: {COR_AMARELO}; color: #000; }}
    .btn-red {{ background: {COR_VERMELHO}; color: white; }}
    .btn-red:hover {{ box-shadow: 0 0 12px rgba(200, 40, 40, 0.5); }}
    
    .container-center {{ display: flex; align-items: center; justify-content: center; height: 100vh; padding: 20px; overflow-y: auto; }}
    .card-center {{ background: {COR_CARD}; color: {COR_TEXTO}; padding: 30px; border-radius: 15px; width: 100%; max-width: 650px; text-align: center; box-shadow: 0 12px 40px rgba(0,0,0,0.9); margin: auto; border: 1px solid {COR_BORDA}; }}
    
    .input-padrao {{ width: 100%; padding: 12px; margin: 8px 0; border: 1px solid {COR_BORDA}; border-radius: 5px; font-size: 16px; box-sizing: border-box; background: {COR_INPUT}; color: {COR_AMARELO}; font-weight: bold; }}
    .input-padrao:focus {{ outline: none; border-color: {COR_AMARELO}; box-shadow: 0 0 5px rgba(243, 186, 22, 0.3); }}
    
    table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
    th, td {{ padding: 10px; border-bottom: 1px solid {COR_BORDA}; text-align: left; vertical-align: middle; }}
    th {{ color: {COR_AMARELO}; text-transform: uppercase; font-size: 14px; }}
    
    .logo-peq {{ width: 220px; max-width: 100%; height: auto; margin-bottom: 15px; border-radius: 8px; mix-blend-mode: screen; }}
    
    .grid-dash {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; width: 100%; margin-bottom: 20px; }} 
    .card-kpi {{ background: {COR_INPUT}; padding: 20px; border-radius: 10px; color: {COR_TEXTO}; box-shadow: 0 4px 6px rgba(0,0,0,0.6); border-left: 5px solid {COR_AMARELO}; border-top: 1px solid {COR_BORDA}; }} 
    .card-kpi p {{ margin: 10px 0 0; font-size: 28px; font-weight: bold; color: {COR_AMARELO}; }} 
    
    .chart-container {{ background: {COR_CARD}; padding: 25px; border-radius: 10px; width: 100%; box-shadow: 0 4px 6px rgba(0,0,0,0.6); margin-bottom:20px; text-align: left; border: 1px solid {COR_BORDA}; }} 
    .item-linha {{ display: flex; justify-content: space-between; font-size: 16px; margin-bottom: 10px; border-bottom: 1px dashed {COR_BORDA}; padding-bottom: 5px; align-items: center; color: #BBB; }}
    
    .filtro-box {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; background: #0A0A0A; padding: 15px; border-radius: 8px; border: 1px solid {COR_BORDA}; width: 100%; text-align: left; }}
    .filtro-box label {{ font-size: 12px; color: #777; font-weight: bold; text-transform: uppercase; }}
    
    .grid-produtos {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; max-height: 500px; overflow-y: auto; padding-right: 5px; }}
    .card-produto {{ background: {COR_INPUT}; border: 1px solid {COR_BORDA}; border-radius: 8px; padding: 12px; text-align: center; cursor: pointer; transition: 0.2s; }}
    .card-produto:hover {{ border-color: {COR_AMARELO}; background: #222; }}
    .badge-estoque {{ display: block; font-size: 11px; color: #888; margin-top: 4px; }}
</style>
"""
IMG_LOGO_PEQ = f"<div style='display:flex; justify-content:center; margin-bottom:15px;'><img src='{IMG_URL}' class='logo-peq'></div>"

@app.get("/logo.png")
async def exibir_logo(): 
    for filename in ["logo.jpg", "stell goose.jpeg", "logo.png"]:
        if os.path.exists(filename):
            return FileResponse(filename)
    return Response(status_code=404)

@app.get("/", response_class=HTMLResponse)
async def login_page(): 
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'>{IMG_LOGO_PEQ}<h2>SISTEMA DE GESTÃO</h2><form action='/login' method='post'><input class='input-padrao' name='user' placeholder='Usuário' required><input class='input-padrao' name='pw' type='password' placeholder='Senha' required><button class='btn-acao' style='padding:15px; font-size:18px; margin-top: 15px;'>ENTRAR NO SISTEMA</button></form></div></div></body></html>"

@app.post("/login")
async def login(request: Request):
    f = await request.form()
    with engine.connect() as conn:
        user = conn.execute(text("SELECT username, role, status FROM usuarios WHERE username = :u AND password = :p"), {"u": f.get("user", "").strip().lower(), "p": f.get("pw", "")}).fetchone()
        if user:
            # TRAVA DE STATUS DO LOGIN AQUI
            if user.status == 'BLOQUEADO':
                return HTMLResponse("<script>alert('Acesso Bloqueado! Procure o Administrador ou Gerente.'); window.location.href='/';</script>")
                
            request.session["user"], request.session["role"] = user.username, user.role
            return RedirectResponse(url="/central", status_code=303)
    return HTMLResponse("<script>alert('Acesso Negado! Verifique as credenciais.'); window.location.href='/';</script>")

@app.get("/logout")
async def logout(request: Request): 
    request.session.clear()
    return RedirectResponse("/")

@app.get("/central", response_class=HTMLResponse)
async def central(request: Request):
    user, role = request.session.get("user"), request.session.get("role")
    if not user: return RedirectResponse(url="/")
    
    botoes = """
    <a href='/pdv' class='btn-acao' style='font-size: 20px; padding: 25px;'>🛒 PAINEL DE VENDAS (COMANDAS)</a>
    <a href='/baixar_conector' class='btn-acao btn-dark'>🖨️ BAIXAR CONECTOR DE IMPRESSORA</a>
    """
    
    if role in ["admin", "gerente"]:
        botoes += """
        <a href='/estoque' class='btn-acao btn-dark' style='font-size: 20px; padding: 25px;'>📦 GESTÃO DE ESTOQUE</a>
        <a href='/dashboard' class='btn-acao btn-red'>📊 RELATÓRIOS E FECHAMENTO</a>
        <a href='/usuarios' class='btn-acao' style='background:#222; color:#AAA;'>👥 CONTROLE DE ACESSOS (CAIXAS)</a>
        """
        
    if role == "admin":
        botoes += """
        <a href='/config_fiscal' class='btn-acao' style='background:#222; color:#AAA;'>⚙️ CONFIGURAÇÕES FISCAIS (NFC-e)</a>
        """
        
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'>{IMG_LOGO_PEQ}<p style='color:#888;'>Operador: <b style='color:{COR_AMARELO};'>{user.upper()}</b></p><div style='display:flex; flex-direction:column; gap:15px; margin-top:20px;'>{botoes}</div><br><a href='/logout' style='color:#C82828; font-weight:bold;'>[ SAIR ]</a></div></div></body></html>"


# ==========================================
# PAINEL DE COMANDAS COM FILTRO LIVE E CORREÇÃO DO BANCO
# ==========================================
@app.get("/pdv", response_class=HTMLResponse)
async def pdv_painel(request: Request):
    if not request.session.get("user"): return RedirectResponse(url="/")
    
    linhas_comandas = ""
    with engine.connect() as conn:
        comandas_abertas = conn.execute(text("SELECT numero_comanda, total_conta FROM comandas WHERE status = 'ABERTA' ORDER BY id DESC")).fetchall()
        for c in comandas_abertas:
            linhas_comandas += f"""
            <div class='card-comanda-item' data-nome='{c.numero_comanda}' style='background:{COR_INPUT}; border:1px solid {COR_BORDA}; border-radius:8px; padding:15px; display:flex; justify-content:space-between; align-items:center;'>
                <div>
                    <span style='font-size:18px; font-weight:bold; color:{COR_AMARELO};'>📋 {c.numero_comanda.upper()}</span><br>
                    <small style='color:#888;'>Consumo Parcial</small>
                </div>
                <div style='text-align:right;'>
                    <span style='font-size:20px; font-weight:bold; color:#FFF;'>R$ {float(c.total_conta or 0):.2f}</span><br>
                    <a href='/pdv/comanda/{urllib.parse.quote(c.numero_comanda)}' class='btn-acao' style='padding:5px 12px; margin:5px 0 0 0; font-size:12px; display:inline-block; width:auto;'>Lançar / Fechar</a>
                </div>
            </div>
            """

    if not linhas_comandas:
        linhas_comandas = "<p id='sem-comandas' style='color:#555; grid-column: 1/-1; text-align:center;'>Nenhuma comanda aberta no momento. Clique acima para iniciar.</p>"

    js_busca = """
    <script>
        function filtrarComandas() {
            let input = document.getElementById('busca-comanda');
            let filter = input.value.toLowerCase().trim();
            let container = document.getElementById('lista-comandas-grid');
            let items = container.getElementsByClassName('card-comanda-item');
            
            for (let i = 0; i < items.length; i++) {
                let nomeComanda = items[i].getAttribute('data-nome').toLowerCase();
                if (nomeComanda.includes(filter)) {
                    items[i].style.display = "flex";
                } else {
                    items[i].style.display = "none";
                }
            }
        }
    </script>
    """

    return f"<html><head>{CSS}{js_busca}</head><body style='background:{COR_FUNDO}; overflow-y:auto;'><div class='container-center' style='height:auto; padding:40px 20px;'><div class='card-center' style='max-width:900px;'>{IMG_LOGO_PEQ}<h2>🛒 Controle de Vendas</h2><div style='background:#0A0A0A; padding:20px; border-radius:10px; border:1px solid {COR_BORDA}; margin-bottom:25px;'><h3 style='margin-bottom:15px;'>⚡ GERENCIAR ATENDIMENTO</h3><div style='display:flex; gap:15px; flex-wrap:wrap;'><button class='btn-acao' style='flex:1; font-size:18px; padding:20px;' onclick='document.getElementById(\"box-comanda\").style.display=\"block\";'>📋 ABRIR COMANDA</button><form action='/pdv/abrir_avulso' method='post' style='flex:1; margin:0;'><button class='btn-acao btn-dark' style='width:100%; font-size:18px; padding:20px;'>🛒 VENDA AVULSA</button></form></div><div id='box-comanda' style='display:none; margin-top:20px; border-top:1px dashed {COR_BORDA}; padding-top:15px;'><form action='/pdv/abrir_comanda' method='post'><label style='font-size:14px; color:#AAA;'>Identificação da Comanda (Nome do Irmão ou Nº):</label><input class='input-padrao' name='nome_comanda' placeholder='Ex: Pará, Mesa 3, Comanda 12...' required autocomplete='off'><button class='btn-acao' style='width:200px; margin-top:5px;'>INICIAR COMANDA</button></form></div></div><div style='margin-bottom: 15px; text-align: left;'><label style='font-size: 12px; color: #777; font-weight: bold;'>🔍 BUSCAR COMANDA ATIVA:</label><input type='text' id='busca-comanda' oninput='filtrarComandas()' class='input-padrao' placeholder='Comece a digitar o nome da comanda...' autocomplete='off'></div><h3>📋 Comandas Ativas no Painel</h3><div id='lista-comandas-grid' style='display:grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap:15px; text-align:left; margin-top:15px;'>{linhas_comandas}</div><br><br><a href='/central' class='btn-acao btn-dark' style='width:150px; margin:auto;'>Voltar ao Menu</a></div></div></body></html>"

@app.post("/pdv/abrir_comanda")
async def abrir_comanda(nome_comanda: str = Form(...)):
    nome_limpo = nome_comanda.strip().replace("/", "-")
    try:
        with engine.begin() as conn:
            existe = conn.execute(text("SELECT id FROM comandas WHERE numero_comanda = :c AND status = 'ABERTA' LIMIT 1"), {"c": nome_limpo}).fetchone()
            if not existe:
                conn.execute(text("INSERT INTO comandas (numero_comanda, total_conta, status) VALUES (:c, 0.00, 'ABERTA')"), {"c": nome_limpo})
    except Exception as e:
        print(f"Erro no banco: {e}")
    return RedirectResponse(url=f"/pdv/comanda/{urllib.parse.quote(nome_limpo)}", status_code=303)

@app.post("/pdv/abrir_avulso")
async def abrir_avulso():
    id_avulso = "AVULSO-" + datetime.now().strftime("%H%M%S")
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO comandas (numero_comanda, total_conta, status) VALUES (:c, 0.00, 'ABERTA')"), {"c": id_avulso})
    except: pass
    return RedirectResponse(url=f"/pdv/comanda/{id_avulso}", status_code=303)


# ==========================================
# TELA DE LANÇAMENTO DA COMANDA 
# ==========================================
@app.get("/pdv/comanda/{numero_comanda}", response_class=HTMLResponse)
async def tela_comanda_detalhe(numero_comanda: str, request: Request):
    if not request.session.get("user"): return RedirectResponse(url="/")
    
    with engine.connect() as conn:
        comanda = conn.execute(text("SELECT numero_comanda, total_conta, status FROM comandas WHERE numero_comanda = :c AND status = 'ABERTA' ORDER BY id DESC LIMIT 1"), {"c": numero_comanda}).fetchone()
        if not comanda: return RedirectResponse(url="/pdv")
        
        itens_lançados = conn.execute(text("SELECT id, item_nome, valor FROM vendas_itens WHERE comanda_num = :c AND status = 'ABERTA' ORDER BY id DESC"), {"c": numero_comanda}).fetchall()
        
        html_itens = ""
        for it in itens_lançados:
            html_itens += f"""
            <div style='display:flex; justify-content:space-between; padding:10px; border-bottom:1px dashed {COR_BORDA}; color:#FFF; align-items:center;'>
                <span>{it.item_nome}</span>
                <span>R$ {float(it.valor):.2f} 
                    <form action='/pdv/remover_item' method='post' style='display:inline; margin-left:15px;'>
                        <input type='hidden' name='item_id' value='{it.id}'>
                        <input type='hidden' name='num_comanda' value='{numero_comanda}'>
                        <button style='background:none; border:none; color:{COR_VERMELHO}; cursor:pointer; font-size:18px;'>☒</button>
                    </form>
                </span>
            </div>
            """
        
        produtos_db = conn.execute(text("SELECT id, nome, preco, estoque FROM produtos ORDER BY nome")).fetchall()
        html_produtos = ""
        for p in produtos_db:
            html_produtos += f"""
            <div class='card-produto' onclick='adicionarItem({p.id})'>
                <span style='font-weight:bold; color:{COR_AMARELO}; display:block; font-size:15px;'>{p.nome.upper()}</span>
                <span style='color:#FFF; font-weight:bold; font-size:14px; display:block; margin-top:5px;'>R$ {float(p.preco):.2f}</span>
                <span class='badge-estoque'>Estoque: {int(p.estoque or 0)} un</span>
            </div>
            """

    js_inject = f"""
    <script>
        function adicionarItem(prodId) {{
            let form = document.createElement('form');
            form.method = 'POST'; form.action = '/pdv/adicionar_item';
            form.innerHTML = `<input type="hidden" name="comanda_num" value="{numero_comanda}">
                              <input type="hidden" name="produto_id" value="${{prodId}}">`;
            document.body.appendChild(form);
            form.submit();
        }}
    </script>
    """

    return f"<html><head>{CSS}{js_inject}</head><body style='background:{COR_FUNDO};'><div style='display:flex; height:100vh; width:100%; overflow:hidden;'><div style='flex:1.3; padding:20px; display:flex; flex-direction:column; background:{COR_CARD}; border-right:2px solid {COR_BORDA}; overflow-y:auto;'><h2>🍺 Selecione os Itens</h2><div class='grid-produtos'>{html_produtos}</div></div><div style='flex:1; padding:20px; display:flex; flex-direction:column; justify-content:space-between; background:#080808; overflow-y:auto;'><div><h2 style='color:#FFF; margin-bottom:5px;'>📋 {comanda.numero_comanda.upper()}</h2><span style='color:#666;'>Consumo acumulado da conta</span><div style='background:#000; border:1px solid {COR_BORDA}; border-radius:8px; padding:10px; margin-top:15px; max-height:220px; overflow-y:auto;'>{html_itens if html_itens else '<p style=\"color:#444; text-align:center;\">Nenhum item lançado ainda.</p>'}</div></div><div style='background:#111; padding:20px; border-radius:8px; margin-top:20px; border:1px solid {COR_BORDA};'><div style='color:#888; font-size:14px; text-transform:uppercase;'>TOTAL DA CONTA</div><div style='color:{COR_AMARELO}; font-size:40px; font-weight:bold; margin-bottom:15px;'>R$ {float(comanda.total_conta or 0):.2f}</div><form action='/pdv/finalizar_comanda' method='post'><input type='hidden' name='comanda_num' value='{comanda.numero_comanda}'><label style='font-size:12px; color:#aaa;'>FORMA DE PAGAMENTO:</label><select name='pagamento' class='input-padrao' style='font-size:16px; padding:12px; margin-bottom:12px;'><option value='01'>💵 DINHEIRO</option><option value='17'>💠 PIX</option><option value='03'>💳 CARTÃO CRÉDITO</option><option value='04'>💳 CARTÃO DÉBITO</option></select><div style='background:#050505; padding:12px; border-radius:8px; margin-bottom:15px; border:1px solid {COR_BORDA};'><div style='display:flex; align-items:center; justify-content:space-between;'><span style='font-weight:bold; color:{COR_VERMELHO}; font-size:14px;'>🧾 Emitir Cupom Fiscal?</span><input type='checkbox' name='nfe' value='true' onchange='document.getElementById(\"box-cpf-det\").style.display = this.checked ? \"block\" : \"none\"' style='transform: scale(1.3); cursor: pointer;'></div><div id='box-cpf-det' style='display:none; margin-top:8px;'><input type='text' name='cpf_nota' class='input-padrao' placeholder='CPF do Cliente (Opcional)' style='font-size:14px; padding:8px;'></div></div><button class='btn-acao' style='font-size:18px; padding:15px;'>🏁 FECHAR CONTA E IMPRIMIR</button></form><a href='/pdv' class='btn-acao btn-dark' style='margin-top:5px; padding:10px; font-size:12px;'>⬅️ VOLTAR AO PAINEL</a></div></div></div></body></html>"


# ==========================================
# ENDPOINTS LOGÍSTICOS
# ==========================================
@app.post("/pdv/adicionar_item")
async def pdv_adicionar_item(comanda_num: str = Form(...), produto_id: int = Form(...)):
    with engine.begin() as conn:
        prod = conn.execute(text("SELECT nome, preco FROM produtos WHERE id = :id"), {"id": produto_id}).fetchone()
        if prod:
            conn.execute(text("INSERT INTO vendas_itens (comanda_num, item_nome, valor, status) VALUES (:c, :n, :v, 'ABERTA')"), {"c": comanda_num, "n": prod.nome, "v": prod.preco})
            conn.execute(text("UPDATE comandas SET total_conta = total_conta + :v WHERE numero_comanda = :c AND status = 'ABERTA'"), {"v": prod.preco, "c": comanda_num})
            conn.execute(text("UPDATE produtos SET estoque = GREATEST(estoque - 1, 0) WHERE id = :id"), {"id": produto_id})
            
    return RedirectResponse(url=f"/pdv/comanda/{urllib.parse.quote(comanda_num)}", status_code=303)

@app.post("/pdv/remover_item")
async def pdv_remover_item(item_id: int = Form(...), num_comanda: str = Form(...)):
    with engine.begin() as conn:
        item = conn.execute(text("SELECT item_nome, valor FROM vendas_itens WHERE id = :id"), {"id": item_id}).fetchone()
        if item:
            conn.execute(text("UPDATE comandas SET total_conta = GREATEST(total_conta - :v, 0.00) WHERE numero_comanda = :c AND status = 'ABERTA'"), {"v": item.valor, "c": num_comanda})
            conn.execute(text("DELETE FROM vendas_itens WHERE id = :id"), {"id": item_id})
            conn.execute(text("UPDATE produtos SET estoque = estoque + 1 WHERE nome = :n"), {"n": item.item_nome})
            
    return RedirectResponse(url=f"/pdv/comanda/{urllib.parse.quote(num_comanda)}", status_code=303)

@app.post("/pdv/finalizar_comanda")
async def finalizar_comanda(request: Request, comanda_num: str = Form(...), pagamento: str = Form(...), nfe: str = Form("false"), cpf_nota: str = Form("")):
    nomes_pag = {"01": "DINHEIRO", "17": "PIX", "03": "C. CREDITO", "04": "C. DEBITO"}
    nome_pagamento = nomes_pag.get(pagamento, "OUTROS")
    nfe_solicitada = nfe == "true"
    usuario = request.session.get("user", "Caixa")
    
    with engine.begin() as conn:
        comanda = conn.execute(text("SELECT total_conta FROM comandas WHERE numero_comanda = :c AND status = 'ABERTA' ORDER BY id DESC LIMIT 1"), {"c": comanda_num}).fetchone()
        if not comanda: return RedirectResponse(url="/pdv", status_code=303)
        
        itens = conn.execute(text("SELECT item_nome, valor FROM vendas_itens WHERE comanda_num = :c AND status = 'ABERTA'"), {"c": comanda_num}).fetchall()
        
        conn.execute(text("UPDATE comandas SET status = 'FECHADA', forma_pagamento = :p, nfe_solicitada = :nfe, cpf_nota = :cpf, data_fechamento = CURRENT_TIMESTAMP WHERE numero_comanda = :c AND status = 'ABERTA'"), {"p": nome_pagamento, "nfe": nfe_solicitada, "cpf": cpf_nota, "c": comanda_num})
        conn.execute(text("UPDATE vendas_itens SET status = 'FECHADA' WHERE comanda_num = :c AND status = 'ABERTA'"), {"c": comanda_num})
        
        txt = f"--------------------------------\n   STEEL GOOSE MOTO GROUP\nPLANALTO-DF\n--------------------------------\nCOMANDA: {comanda_num.upper()}\nOPERADOR: {usuario.upper()}\nDATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n--------------------------------\n"
        for idx, item in enumerate(itens):
            txt += f"1x {item.item_nome[:20]:<20} R$ {float(item.valor):.2f}\n"
        txt += f"--------------------------------\nTOTAL: R$ {float(comanda.total_conta):.2f}\nPAGTO: {nome_pagamento}\n--------------------------------\n"
        
        if nfe_solicitada:
            txt += "EMISSAO DE NFC-e SOLICITADA\n"
            if cpf_nota: txt += f"CPF/CNPJ: {cpf_nota}\n"
            
            cfg = conn.execute(text("SELECT token_focus, ambiente FROM configuracoes_nfe LIMIT 1")).fetchone()
            if cfg and cfg.token_focus:
                url_api = "https://api.focusnfe.com.br/v2/nfce"
                payload = {
                    "natureza_operacao": "VENDA",
                    "presenca_comprador": "1",
                    "itens": [
                        {
                            "numero_item": str(i+1), 
                            "codigo_produto": "999", 
                            "descricao": it.item_nome, 
                            "cfop": "5102", 
                            "unidade_comercial": "UN", 
                            "quantidade_comercial": "1", 
                            "valor_unitario_comercial": str(it.valor), 
                            "valor_bruto": str(it.valor), 
                            "icms_origem": "0", 
                            "icms_situacao_tributaria": "102"
                        } for i, it in enumerate(itens)
                    ],
                    "pagamentos": [{"forma_pagamento": pagamento, "valor_pagamento": str(comanda.total_conta)}]
                }
                if cpf_nota: payload["cpf_cnpj_destinatario"] = re.sub(r'[^0-9]', '', cpf_nota)
                try:
                    resp = requests.post(url_api, json=payload, auth=(cfg.token_focus, ""))
                    if resp.status_code in [200, 202]:
                        txt += f"\n✅ COMUNICACAO SEFAZ OK!\n"
                    else:
                        txt += f"\n⚠️ RETORNO SEFAZ (ERRO)\n"
                except Exception: pass
        txt += " Obrigado pela parceria! 🦅\n--------------------------------\n"
        
        conn.execute(text("INSERT INTO fila_impressao (conteudo) VALUES (:txt)"), {"txt": txt})

    return HTMLResponse(f"<script>alert('Conta {comanda_num} fechada com sucesso!'); window.location.href='/pdv';</script>")


# ==========================================
# MÓDULO 3: GESTÃO DE ESTOQUE COM EDIÇÃO
# ==========================================
@app.get("/estoque", response_class=HTMLResponse)
async def tela_estoque(request: Request):
    if request.session.get("role") not in ["admin", "gerente"]: return RedirectResponse(url="/central")
    linhas = ""
    with engine.connect() as conn:
        prods_db = conn.execute(text("SELECT id, nome, categoria, preco, estoque FROM produtos ORDER BY nome")).fetchall()
        for r in prods_db:
            nome_seguro = r.nome.replace('"', '').replace("'", "")
            acoes = f"""
            <div style='display:flex; gap:5px;'>
                <form action='/att_estoque' method='post' style='margin:0; display:flex;'>
                    <input type='hidden' name='id' value='{r.id}'>
                    <input type='number' name='q' class='input-padrao' style='width:60px; padding:5px; margin:0; text-align:center;' placeholder='+Qtd' required>
                    <button class='btn-acao' style='padding:8px; margin:0;' title='Adicionar Estoque'>➕</button>
                </form>
                <button type='button' class='btn-acao btn-dark' style='padding:8px; margin:0;' onclick='abrirModal({r.id}, "{nome_seguro}", "{r.categoria}", {float(r.preco or 0)})' title='Editar Produto'>✏️</button>
                <form action='/excluir_produto' method='post' style='margin:0;' onsubmit='return confirm(\"Excluir item?\");'>
                    <input type='hidden' name='id' value='{r.id}'>
                    <button class='btn-acao btn-red' style='padding:8px; margin:0;' title='Excluir Produto'>🗑️</button>
                </form>
            </div>
            """
            linhas += f"<tr><td style='color:#FFF; font-weight:bold;'>{r.nome.upper()}</td><td style='color:{COR_AMARELO}; font-weight:bold;'>R$ {float(r.preco or 0):.2f}</td><td style='color:#FFF; font-weight:bold; font-size:18px; text-align:center;'>{int(r.estoque or 0)} un</td><td>{acoes}</td></tr>"
            
    add_form = f"<div style='background:#0A0A0A; padding:20px; border-radius:10px; margin-bottom:20px; text-align:left; border:1px solid {COR_BORDA};'><h3>➕ CADASTRAR PRODUTO NO BAR</h3><form action='/novo_produto' method='post' style='display:flex; flex-wrap:wrap; gap:10px;'><input name='nome' placeholder='Nome da Bebida / Patch / Item' class='input-padrao' style='flex:2; min-width:200px;' required><select name='cat' class='input-padrao' style='flex:1; min-width:120px;' required><option value='BEBIDAS'>BEBIDAS GÉLIDAS</option><option value='ALIMENTOS'>PETISCOS / COZINHA</option><option value='VESTUARIO'>PATCHES / ACESSÓRIOS</option><option value='OUTROS'>OUTROS</option></select><input name='preco' placeholder='Preço de Venda' step='0.01' type='number' class='input-padrao' style='width:120px;' required><input name='qtd' type='number' placeholder='Qtd Estoque' class='input-padrao' style='width:100px;' required><button class='btn-acao' style='width:100%; font-size:18px;'>SALVAR NO ESTOQUE</button></form></div>"
    
    modal_edit = f"""
    <div id='editModal' style='display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:1000; align-items:center; justify-content:center;'>
        <div class='card-center' style='position:relative; width:90%; max-width:400px; padding:20px; background:#121214; border:1px solid {COR_BORDA}; text-align:left;'>
            <span onclick='fecharModal()' style='position:absolute; top:10px; right:15px; cursor:pointer; font-size:24px; color:#FFF;'>&times;</span>
            <h3 style='margin-top:0; color:{COR_AMARELO};'>✏️ EDITAR PRODUTO</h3>
            <form action='/editar_produto' method='post' style='display:flex; flex-direction:column; gap:10px;'>
                <input type='hidden' name='id' id='edit_id'>
                <div>
                    <label style='font-size:12px; color:#aaa; font-weight:bold;'>NOME DO PRODUTO:</label>
                    <input name='nome' id='edit_nome' class='input-padrao' required autocomplete='off'>
                </div>
                <div>
                    <label style='font-size:12px; color:#aaa; font-weight:bold;'>CATEGORIA:</label>
                    <select name='cat' id='edit_cat' class='input-padrao' required>
                        <option value='BEBIDAS'>BEBIDAS GÉLIDAS</option>
                        <option value='ALIMENTOS'>PETISCOS / COZINHA</option>
                        <option value='VESTUARIO'>PATCHES / ACESSÓRIOS</option>
                        <option value='OUTROS'>OUTROS</option>
                    </select>
                </div>
                <div>
                    <label style='font-size:12px; color:#aaa; font-weight:bold;'>NOVO PREÇO (R$):</label>
                    <input name='preco' id='edit_preco' type='number' step='0.01' class='input-padrao' required>
                </div>
                <button class='btn-acao' style='margin-top:10px; font-size:16px;'>SALVAR ALTERAÇÕES</button>
            </form>
        </div>
    </div>
    """

    js_modal = """
    <script>
        function abrirModal(id, nome, cat, preco) {
            document.getElementById('edit_id').value = id;
            document.getElementById('edit_nome').value = nome;
            document.getElementById('edit_cat').value = cat;
            document.getElementById('edit_preco').value = preco;
            document.getElementById('editModal').style.display = 'flex';
        }
        function fecharModal() {
            document.getElementById('editModal').style.display = 'none';
        }
    </script>
    """

    return f"<html><head>{CSS}{js_modal}</head><body>{modal_edit}<div class='container-center'><div class='card-center' style='max-width:800px;'>{IMG_LOGO_PEQ}<h2>📦 Gestão de Estoque</h2>{add_form}<div style='max-height:400px; overflow-y:auto; border:1px solid {COR_BORDA};'><table><tr><th>Produto</th><th>Preço</th><th>Qtd Atual</th><th>Ações</th></tr>{linhas}</table></div><br><a href='/central' class='btn-acao btn-dark' style='width:200px; margin:auto;'>Voltar ao Menu</a></div></div></body></html>"

@app.post("/novo_produto")
async def novo_produto(request: Request):
    if request.session.get("role") not in ["admin", "gerente"]: return RedirectResponse(url="/central")
    f = await request.form()
    nome_prod = f.get("nome").strip().upper()
    try:
        with engine.begin() as conn: 
            conn.execute(text("INSERT INTO produtos (codigo_barras, nome, categoria, preco, estoque) VALUES (:cb, :n, :c, :p, :q) ON CONFLICT (codigo_barras) DO NOTHING"), {"cb": "SG-" + datetime.now().strftime("%f"), "n": nome_prod, "c": f.get("cat"), "p": float(f.get("preco").replace(",", ".")), "q": int(f.get("qtd"))})
    except Exception: pass
    return RedirectResponse(url="/estoque", status_code=303)

@app.post("/att_estoque")
async def att_estoque(request: Request):
    if request.session.get("role") not in ["admin", "gerente"]: return RedirectResponse(url="/central")
    f = await request.form()
    try:
        with engine.begin() as conn: conn.execute(text("UPDATE produtos SET estoque = COALESCE(estoque, 0) + :q WHERE id = :id"), {"id": f.get("id"), "q": int(f.get("q", "0"))})
    except: pass
    return RedirectResponse(url="/estoque", status_code=303)

@app.post("/editar_produto")
async def editar_produto(request: Request):
    if request.session.get("role") not in ["admin", "gerente"]: return RedirectResponse(url="/central")
    f = await request.form()
    try:
        with engine.begin() as conn: 
            conn.execute(text("UPDATE produtos SET nome = :n, categoria = :c, preco = :p WHERE id = :id"), {"n": f.get("nome").strip().upper(), "c": f.get("cat"), "p": float(f.get("preco").replace(",", ".")), "id": f.get("id")})
    except Exception: pass
    return RedirectResponse(url="/estoque", status_code=303)

@app.post("/excluir_produto")
async def excluir_produto(request: Request):
    if request.session.get("role") not in ["admin", "gerente"]: return RedirectResponse(url="/central")
    f = await request.form()
    try:
        with engine.begin() as conn: conn.execute(text("DELETE FROM produtos WHERE id = :id"), {"id": f.get("id")})
    except: pass
    return RedirectResponse(url="/estoque", status_code=303)


# ==========================================
# MÓDULO 4: RELATÓRIOS COM NOVA TABELA DE PRODUTOS VENDIDOS
# ==========================================
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, inicio: str = "", fim: str = "", tipo_venda: str = "TODOS"):
    if request.session.get("role") not in ["admin", "gerente"]: return RedirectResponse(url="/central")
    hoje_str = date.today().strftime("%Y-%m-%d")
    dt_inicio = inicio if inicio else hoje_str
    dt_fim = fim if fim else hoje_str

    where_clause = "status = 'FECHADA' AND CAST(data_fechamento AS DATE) BETWEEN CAST(:inicio AS DATE) AND CAST(:fim AS DATE)"
    params = {"inicio": dt_inicio, "fim": dt_fim}
    if tipo_venda and tipo_venda != "TODOS":
        where_clause += " AND forma_pagamento = :tipo"
        params["tipo"] = tipo_venda

    with engine.connect() as conn:
        kpi = conn.execute(text(f"SELECT SUM(total_conta) as total FROM comandas WHERE {where_clause}"), params).fetchone()
        faturamento_filtrado = float(kpi.total or 0)
        
        pag_q = conn.execute(text(f"SELECT forma_pagamento, SUM(total_conta) as total FROM comandas WHERE {where_clause} GROUP BY forma_pagamento"), params).fetchall()
        totais_pag = {"DINHEIRO": 0.0, "PIX": 0.0, "C. CREDITO": 0.0, "C. DEBITO": 0.0}
        for p in pag_q: 
            if p.forma_pagamento in totais_pag: totais_pag[p.forma_pagamento] = float(p.total or 0)
            
        itens_db = conn.execute(text(f"SELECT item_nome, COUNT(*) as qtd, SUM(valor) as total_valor FROM vendas_itens WHERE status = 'FECHADA' AND comanda_num IN (SELECT numero_comanda FROM comandas WHERE {where_clause}) GROUP BY item_nome ORDER BY qtd DESC"), params).fetchall()
        
        linhas_tabela = ""
        for it in itens_db:
            linhas_tabela += f"<tr><td style='color:#FFF; font-weight:bold;'>{it.item_nome}</td><td style='color:{COR_AMARELO}; text-align:center; font-weight:bold;'>{it.qtd}</td><td style='color:#FFF; text-align:right;'>R$ {float(it.total_valor or 0):.2f}</td></tr>"

    opcoes_select = f"<option value='TODOS' {'selected' if tipo_venda == 'TODOS' else ''}>⚙️ TODOS OS TIPOS</option><option value='DINHEIRO' {'selected' if tipo_venda == 'DINHEIRO' else ''}>💵 DINHEIRO</option><option value='PIX' {'selected' if tipo_venda == 'PIX' else ''}>💠 PIX</option><option value='C. CREDITO' {'selected' if tipo_venda == 'C. CREDITO' else ''}>💳 CARTÃO CRÉDITO</option><option value='C. DEBITO' {'selected' if tipo_venda == 'C. DEBITO' else ''}>💳 CARTÃO DÉBITO</option>"
    
    return f"""<html><head>{CSS}</head><body><div class='container-center'><div class='card-center' style='max-width:800px;'>
        {IMG_LOGO_PEQ}<h2>📊 Relatório Financeiro</h2>
        
        <form method='get' class='filtro-box'>
            <div style='flex:1; min-width:140px;'><label>Data Inicial:</label><br><input type='date' name='inicio' value='{dt_inicio}' class='input-padrao' style='margin:5px 0 0 0; padding:8px;'></div>
            <div style='flex:1; min-width:140px;'><label>Data Final:</label><br><input type='date' name='fim' value='{dt_fim}' class='input-padrao' style='margin:5px 0 0 0; padding:8px;'></div>
            <div style='flex:1; min-width:160px;'><label>Tipo:</label><br><select name='tipo_venda' class='input-padrao' style='margin:5px 0 0 0; padding:8px;'>{opcoes_select}</select></div>
            <div style='display:flex; align-items:flex-end; min-width:100px;'><button class='btn-acao' style='margin:0; height:41px;'>FILTRAR</button></div>
        </form>
        
        <div class='grid-dash'><div class='card-kpi'><h3>Faturamento do Período</h3><p>R$ {faturamento_filtrado:.2f}</p></div></div>
        <div style='display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px; margin-bottom:20px;'>
            <div style='background:#111; padding:15px; border-radius:8px; border-left:4px solid {COR_AMARELO}; flex:1;'><b>💵 Dinheiro:</b><br><span style='color:#FFF;'>R$ {totais_pag['DINHEIRO']:.2f}</span></div>
            <div style='background:#111; padding:15px; border-radius:8px; border-left:4px solid {COR_AMARELO}; flex:1;'><b>💠 PIX:</b><br><span style='color:#FFF;'>R$ {totais_pag['PIX']:.2f}</span></div>
            <div style='background:#111; padding:15px; border-radius:8px; border-left:4px solid {COR_AMARELO}; flex:1;'><b>💳 Cartões:</b><br><span style='color:#FFF;'>R$ {(totais_pag['C. CREDITO'] + totais_pag['C. DEBITO']):.2f}</span></div>
        </div>
        
        <div class='chart-container' style='padding: 15px;'>
            <h3 style='border-bottom:2px solid {COR_BORDA}; padding-bottom:5px; margin-top:0;'>📋 LISTA DE ITENS VENDIDOS</h3>
            <div style='max-height:300px; overflow-y:auto;'>
                <table style='margin-top:0;'>
                    <thead style='background:#0A0A0A; position:sticky; top:0; box-shadow: 0 2px 4px rgba(0,0,0,0.8);'>
                        <tr>
                            <th style='color:{COR_AMARELO};'>Produto</th>
                            <th style='color:{COR_AMARELO}; text-align:center;'>Qtd</th>
                            <th style='color:{COR_AMARELO}; text-align:right;'>Total Arrecadado (R$)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {linhas_tabela if linhas_tabela else "<tr><td colspan='3' style='color:#777; text-align:center;'>Nenhuma venda encontrada no período.</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
        
        <br><a href='/central' class='btn-acao btn-dark' style='width:200px; margin:auto;'>VOLTAR AO PAINEL</a>
    </div></div></body></html>"""


# ==========================================
# MÓDULO 5: GERENCIAR USUÁRIOS COM SISTEMA DE BLOQUEIO
# ==========================================
@app.get("/usuarios", response_class=HTMLResponse)
async def tela_usuarios(request: Request):
    role_session = request.session.get("role")
    if role_session not in ["admin", "gerente"]: return RedirectResponse(url="/central")
    
    linhas = ""
    with engine.connect() as conn:
        users_db = conn.execute(text("SELECT id, username, role, status FROM usuarios ORDER BY role, username")).fetchall()
        for r in users_db:
            acoes = ""
            if r.username != "admin":
                # Botão de Bloqueio/Desbloqueio (Verde se tiver bloqueado, Laranja se estiver Ativo)
                if r.status in ['ATIVO', None]:
                    btn_block = f"<form action='/toggle_usuario' method='post' style='margin:0;'><input type='hidden' name='id' value='{r.id}'><button class='btn-acao' style='background:#f59e0b; padding:8px; margin:0; width:40px;' title='Bloquear Acesso'>🔒</button></form>"
                else:
                    btn_block = f"<form action='/toggle_usuario' method='post' style='margin:0;'><input type='hidden' name='id' value='{r.id}'><button class='btn-acao' style='background:#10b981; padding:8px; margin:0; width:40px;' title='Liberar Acesso'>🔓</button></form>"
                
                btn_del = f"<form action='/excluir_usuario' method='post' style='margin:0;' onsubmit='return confirm(\"Excluir Operador?\");'><input type='hidden' name='id' value='{r.id}'><button class='btn-acao btn-red' style='padding:8px; margin:0; width:40px;' title='Excluir Permanentemente'>🗑️</button></form>"
                
                # Regra: Admin mexe em todos, Gerente só mexe em Caixa
                if role_session == "admin" or (role_session == "gerente" and r.role == "caixa"):
                    acoes = f"<div style='display:flex; gap:5px; justify-content:center;'>{btn_block}{btn_del}</div>"
                else:
                    acoes = f"<span style='color:#777; font-size:12px;'>Bloqueado pelo Admin</span>"
            
            # Formatação do Status
            if r.status in ['ATIVO', None]:
                status_badge = f"<span style='color:#10b981; font-weight:bold; font-size:12px;'>ATIVO</span>"
            else:
                status_badge = f"<span style='color:{COR_VERMELHO}; font-weight:bold; font-size:12px;'>BLOQUEADO</span>"

            linhas += f"<tr><td>{r.username.upper()}</td><td style='color:{COR_AMARELO};'>{r.role.upper()}</td><td>{status_badge}</td><td style='text-align:center;'>{acoes}</td></tr>"
            
    options_role = "<option value='caixa'>CAIXA</option>"
    if role_session == "admin": options_role = "<option value='gerente'>GERENTE</option><option value='caixa'>CAIXA</option>"
            
    add_form = f"<div style='background:#0A0A0A; padding:20px; border-radius:10px; margin-bottom:20px; text-align:left; border:1px solid {COR_BORDA};'><h3>➕ NOVO OPERADOR</h3><form action='/novo_usuario' method='post' style='display:flex; flex-wrap:wrap; gap:10px;'><input name='u' placeholder='Login' class='input-padrao' style='flex:1;' required><input name='p' type='password' placeholder='Senha' class='input-padrao' style='flex:1;' required><select name='r' class='input-padrao' style='flex:1;'>{options_role}</select><button class='btn-acao' style='width:100%;'>CRIAR ACESSO</button></form></div>"
    
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center' style='max-width:800px;'>{IMG_LOGO_PEQ}<h2>Controle de Acessos</h2>{add_form}<div style='max-height:400px; overflow-y:auto; border:1px solid {COR_BORDA};'><table><tr><th>Login</th><th>Cargo</th><th>Status</th><th style='text-align:center;'>Ações</th></tr>{linhas}</table></div><br><a href='/central' class='btn-acao btn-dark' style='width:200px; margin:auto;'>Voltar ao Menu</a></div></div></body></html>"

@app.post("/toggle_usuario")
async def toggle_usuario(request: Request):
    role_session = request.session.get("role")
    if role_session not in ["admin", "gerente"]: return RedirectResponse(url="/central")
    f = await request.form()
    user_id = f.get("id")
    try:
        with engine.begin() as conn:
            target = conn.execute(text("SELECT username, role, status FROM usuarios WHERE id = :id"), {"id": user_id}).fetchone()
            if target and target.username != 'admin':
                if role_session == "gerente" and target.role != "caixa":
                    pass # Gerente não pode bloquear outro gerente ou admin
                else:
                    novo_status = 'BLOQUEADO' if target.status in ['ATIVO', None] else 'ATIVO'
                    conn.execute(text("UPDATE usuarios SET status = :s WHERE id = :id"), {"s": novo_status, "id": user_id})
    except: pass
    return RedirectResponse(url="/usuarios", status_code=303)

@app.post("/novo_usuario")
async def novo_usuario(request: Request):
    role_session = request.session.get("role")
    if role_session not in ["admin", "gerente"]: return RedirectResponse(url="/central")
    f = await request.form()
    new_role = f.get("r")
    if role_session == "gerente" and new_role != "caixa":
        new_role = "caixa" # Força ser caixa se um gerente tentar burlar o formulário
    try:
        with engine.begin() as conn: 
            conn.execute(text("INSERT INTO usuarios (username, password, role, status) VALUES (:u, :p, :r, 'ATIVO') ON CONFLICT (username) DO NOTHING"), {"u": f.get("u").lower(), "p": f.get("p"), "r": new_role})
    except: pass
    return RedirectResponse(url="/usuarios", status_code=303)

@app.post("/excluir_usuario")
async def excluir_usuario(request: Request):
    role_session = request.session.get("role")
    if role_session not in ["admin", "gerente"]: return RedirectResponse(url="/central")
    f = await request.form()
    user_id = f.get("id")
    try:
        with engine.begin() as conn:
            target = conn.execute(text("SELECT username, role FROM usuarios WHERE id = :id"), {"id": user_id}).fetchone()
            if target and target.username != 'admin':
                if role_session == "gerente" and target.role != "caixa":
                    pass
                else:
                    conn.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": user_id})
    except: pass
    return RedirectResponse(url="/usuarios", status_code=303)

@app.get("/api/pendentes")
async def api_pendentes():
    with engine.connect() as conn:
        r = conn.execute(text("SELECT id, conteudo FROM fila_impressao WHERE status = 'PENDENTE' LIMIT 1")).fetchone()
        return {"jobs": [{"id": r.id, "conteudo": r.conteudo}]} if r else {"jobs": []}

@app.post("/api/impresso/{j_id}")
async def api_impresso(j_id: int):
    with engine.begin() as conn: conn.execute(text("UPDATE fila_impressao SET status='IMPRESSO' WHERE id=:i"), {"i": j_id})
    return {"ok": True}

@app.get("/baixar_conector")
async def baixar_conector(request: Request):
    if request.session.get("role") not in ["admin", "gerente"]: return RedirectResponse(url="/central")
    base_url = str(request.base_url).rstrip('/')
    script_content = f"""import time
import requests
import win32print

API_URL = "{base_url}"

def imprimir_ticket(texto):
    impressora_padrao = win32print.GetDefaultPrinter()
    try:
        hPrinter = win32print.OpenPrinter(impressora_padrao)
        hJob = win32print.StartDocPrinter(hPrinter, 1, ("Ticket Steel Goose", None, "RAW"))
        win32print.StartPagePrinter(hPrinter)
        win32print.WritePrinter(hPrinter, texto.encode("utf-8"))
        win32print.WritePrinter(hPrinter, b"\\n\\n\\n\\n\\x1B\\x6D")
        win32print.EndPagePrinter(hPrinter)
        win32print.EndDocPrinter(hPrinter)
        win32print.ClosePrinter(hPrinter)
        print("✔️ Cupom Impresso!")
    except Exception as e:
        print(f"❌ Erro: {{e}}")

print("=========================================")
print("🚀 CONECTOR DE IMPRESSORA INICIADO")
print("=========================================\\n")

while True:
    try:
        resposta = requests.get(f"{{API_URL}}/api/pendentes", timeout=5)
        if resposta.status_code == 200:
            dados = resposta.json()
            for job in dados.get("jobs", []):
                imprimir_ticket(job['conteudo'])
                requests.post(f"{{API_URL}}/api/impresso/{{job['id']}}", timeout=5)
    except: pass
    time.sleep(2)
"""
    return Response(content=script_content, media_type="text/x-python", headers={"Content-Disposition": "attachment; filename=conector_impressao_jpms.py"})
