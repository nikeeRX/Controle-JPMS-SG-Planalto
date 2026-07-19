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

# Criação das tabelas do sistema Steel Goose
with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL, status TEXT DEFAULT 'ATIVO');
        CREATE TABLE IF NOT EXISTS produtos (id SERIAL PRIMARY KEY, codigo_barras TEXT UNIQUE, nome TEXT NOT NULL, categoria TEXT DEFAULT 'OUTROS', preco DECIMAL(10,2) DEFAULT 0.00, estoque INT DEFAULT 0);
        CREATE TABLE IF NOT EXISTS comandas (id SERIAL PRIMARY KEY, numero_comanda TEXT NOT NULL, total_conta DECIMAL(10,2) DEFAULT 0.00, status TEXT DEFAULT 'ABERTA', forma_pagamento TEXT, data_fechamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP, nfe_solicitada BOOLEAN DEFAULT FALSE, cpf_nota TEXT);
        CREATE TABLE IF NOT EXISTS vendas_itens (id SERIAL PRIMARY KEY, comanda_num TEXT, item_nome TEXT, valor DECIMAL(10,2), data_venda DATE DEFAULT CURRENT_DATE, hora_venda TIME DEFAULT CURRENT_TIME, status TEXT DEFAULT 'ABERTA');
        CREATE TABLE IF NOT EXISTS fila_impressao (id SERIAL PRIMARY KEY, conteudo TEXT, status TEXT DEFAULT 'PENDENTE', data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS historico_estoque (id SERIAL PRIMARY KEY, produto_nome TEXT, qtd_adicionada INT, data_entrada DATE DEFAULT CURRENT_DATE, valor_custo DECIMAL(10,2) DEFAULT 0.00);
        CREATE TABLE IF NOT EXISTS configuracoes_nfe (id SERIAL PRIMARY KEY, token_focus TEXT, ambiente TEXT DEFAULT 'HOMOLOGACAO', senha_certificado TEXT, nome_arquivo_cert TEXT);
    """))

# Migrações seguras
MIGRACOES = [
    "ALTER TABLE comandas ALTER COLUMN status SET DEFAULT 'ABERTA';",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'ATIVO';",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email TEXT;",
    "ALTER TABLE historico_estoque ADD COLUMN IF NOT EXISTS valor_custo DECIMAL(10,2) DEFAULT 0.00;"
]
for mig in MIGRACOES:
    try:
        with engine.begin() as conn: conn.execute(text(mig))
    except Exception: pass

# Cria o Admin Padrão
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
    .btn-locked {{ width: 100%; padding: 25px; margin-bottom: 8px; font-size: 16px; background: #0A0A0A; color: #444; border: 1px dashed #333; border-radius: 5px; font-weight: bold; text-transform: uppercase; cursor: not-allowed; text-align: center; }}
    .container-center {{ display: flex; align-items: center; justify-content: center; height: 100vh; padding: 20px; overflow-y: auto; }}
    .card-center {{ background: {COR_CARD}; color: {COR_TEXTO}; padding: 30px; border-radius: 15px; width: 100%; max-width: 650px; text-align: center; box-shadow: 0 12px 40px rgba(0,0,0,0.9); margin: auto; border: 1px solid {COR_BORDA}; }}
    .input-padrao {{ width: 100%; padding: 12px; margin: 8px 0; border: 1px solid {COR_BORDA}; border-radius: 5px; font-size: 16px; box-sizing: border-box; background: {COR_INPUT}; color: {COR_AMARELO}; font-weight: bold; }}
    .input-padrao:focus {{ outline: none; border-color: {COR_AMARELO}; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
    th, td {{ padding: 10px; border-bottom: 1px solid {COR_BORDA}; text-align: left; vertical-align: middle; }}
    th {{ color: {COR_AMARELO}; text-transform: uppercase; font-size: 14px; }}
    .logo-peq {{ width: 220px; max-width: 100%; height: auto; margin-bottom: 15px; border-radius: 8px; mix-blend-mode: screen; }}
    .grid-dash {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; width: 100%; margin-bottom: 20px; }} 
    .card-kpi {{ background: {COR_INPUT}; padding: 20px; border-radius: 10px; color: {COR_TEXTO}; border-left: 5px solid {COR_AMARELO}; border-top: 1px solid {COR_BORDA}; }} 
    .card-kpi p {{ margin: 10px 0 0; font-size: 28px; font-weight: bold; color: {COR_AMARELO}; }} 
    .chart-container {{ background: {COR_CARD}; padding: 25px; border-radius: 10px; width: 100%; margin-bottom:20px; text-align: left; border: 1px solid {COR_BORDA}; }} 
    .filtro-box {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; background: #0A0A0A; padding: 15px; border-radius: 8px; border: 1px solid {COR_BORDA}; width: 100%; text-align: left; }}
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
        if os.path.exists(filename): return FileResponse(filename)
    return Response(status_code=404)

# ==========================================
# ROTAS DE LOGIN E CADASTRO
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def login_page(): 
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'>{IMG_LOGO_PEQ}<h2>PORTARIA DIGITAL</h2><form action='/login' method='post'><input class='input-padrao' name='user' placeholder='Usuário' required><input class='input-padrao' name='pw' type='password' placeholder='Senha' required><button class='btn-acao' style='padding:15px; font-size:18px; margin-top: 15px;'>ENTRAR NO SISTEMA</button></form><br><hr style='border: 0; border-top: 1px dashed {COR_BORDA}; margin: 20px 0;'><a href='/cadastro' class='btn-acao btn-dark' style='text-decoration:none;'>SOLICITAR ACESSO (CADASTRO)</a></div></div></body></html>"

@app.get("/cadastro", response_class=HTMLResponse)
async def tela_cadastro():
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'>{IMG_LOGO_PEQ}<h2>CADASTRO DE INTEGRANTE</h2><p style='color:#888; font-size:14px;'>Seu acesso passará por aprovação da Diretoria.</p><form action='/registrar' method='post' style='text-align:left;'><label style='color:#AAA; font-size:13px;'>Nome de Usuário (Login):</label><input class='input-padrao' name='u' placeholder='Ex: Para123' required autocomplete='off'><label style='color:#AAA; font-size:13px;'>E-mail:</label><input class='input-padrao' name='e' type='email' placeholder='seuemail@email.com' required autocomplete='off'><label style='color:#AAA; font-size:13px;'>Senha:</label><input class='input-padrao' name='p' type='password' placeholder='Crie uma senha segura' required><button class='btn-acao' style='padding:15px; font-size:18px; margin-top: 20px;'>ENVIAR SOLICITAÇÃO</button></form><a href='/' style='color:{COR_AMARELO}; font-size:14px; text-decoration:none;'>⬅️ Voltar ao Login</a></div></div></body></html>"

@app.post("/registrar")
async def registrar(u: str = Form(...), e: str = Form(...), p: str = Form(...)):
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO usuarios (username, email, password, role, status) VALUES (:u, :e, :p, 'membro', 'BLOQUEADO') ON CONFLICT (username) DO NOTHING"), {"u": u.strip().lower(), "e": e.strip().lower(), "p": p})
        return HTMLResponse("<script>alert('Cadastro realizado com sucesso! Aguarde a aprovação da Diretoria para fazer login.'); window.location.href='/';</script>")
    except Exception:
        return HTMLResponse(f"<script>alert('Erro ao cadastrar: Usuário já existe ou erro no sistema.'); window.location.href='/cadastro';</script>")

@app.post("/login")
async def login(request: Request):
    f = await request.form()
    with engine.connect() as conn:
        user = conn.execute(text("SELECT username, role, status FROM usuarios WHERE username = :u AND password = :p"), {"u": f.get("user", "").strip().lower(), "p": f.get("pw", "")}).fetchone()
        if user:
            if user.status == 'BLOQUEADO':
                return HTMLResponse("<script>alert('Acesso Pendente ou Bloqueado! Aguarde a liberação da Diretoria.'); window.location.href='/';</script>")
            request.session["user"], request.session["role"] = user.username, user.role
            return RedirectResponse(url="/central", status_code=303)
    return HTMLResponse("<script>alert('Acesso Negado! Usuário ou senha incorretos.'); window.location.href='/';</script>")

@app.get("/logout")
async def logout(request: Request): 
    request.session.clear()
    return RedirectResponse("/")

# ==========================================
# O NOVO HUB CENTRAL LIMPO 
# ==========================================
@app.get("/central", response_class=HTMLResponse)
async def central(request: Request):
    user, role = request.session.get("user"), request.session.get("role")
    if not user: return RedirectResponse(url="/")
    
    botoes = "<a href='/modulo/steelgoose' class='btn-acao btn-dark' style='padding:25px; font-size:16px;'>🦅 STEEL GOOSE</a>"
    if role in ["admin", "diretoria", "secretario"]:
        botoes += "<a href='/modulo/secretaria' class='btn-acao btn-dark' style='padding:25px; font-size:16px;'>🗄️ SECRETARIA</a>"
    if role in ["admin", "diretoria", "tesoureiro"]:
        botoes += "<a href='/tesouraria' class='btn-acao btn-dark' style='padding:25px; font-size:16px;'>💰 TESOURARIA (CLUBE)</a>"
    if role in ["admin", "diretoria", "rp"]:
        botoes += "<a href='/modulo/rp' class='btn-acao btn-dark' style='padding:25px; font-size:16px;'>📸 RELAÇÕES PÚBLICAS</a>"
    if role in ["admin", "diretoria"]:
        botoes += "<a href='/diretoria' class='btn-acao btn-red' style='padding:25px; font-size:16px;'>👔 DIRETORIA</a>"
        
    botoes += "<a href='/modulo/ouvidoria' class='btn-acao btn-dark' style='padding:25px; font-size:16px;'>📢 OUVIDORIA</a>"

    if role in ["admin", "diretoria", "old_goose", "caixa"]:
        botoes += "<a href='/oldgoose' class='btn-acao' style='padding:25px; font-size:16px; grid-column: 1 / -1; box-shadow: 0 0 15px rgba(243, 186, 22, 0.2);'>🦉 OLD GOOSE (BAR)</a>"

    botoes_grid = f"<div style='display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:15px; margin-top:20px;'>{botoes}</div>"
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center' style='max-width:850px;'>{IMG_LOGO_PEQ}<p style='color:#888;'>Painel de Controle: <b style='color:{COR_AMARELO}; text-transform:uppercase;'>{user} ({role})</b></p>{botoes_grid}<br><a href='/logout' style='color:#C82828; font-weight:bold; text-decoration:none;'>[ SAIR DO SISTEMA ]</a></div></div></body></html>"

# ==========================================
# ROTEADORES DOS MÓDULOS
# ==========================================
@app.get("/oldgoose", response_class=HTMLResponse)
async def menu_oldgoose(request: Request):
    role = request.session.get("role")
    if not role or role not in ["admin", "diretoria", "old_goose", "caixa"]: return RedirectResponse("/central")
    botoes = "<a href='/pdv' class='btn-acao' style='font-size: 18px; padding: 20px;'>🛒 PAINEL DE VENDAS (COMANDAS)</a>"
    if role in ["admin", "diretoria", "old_goose"]:
        botoes += "<a href='/estoque' class='btn-acao btn-dark' style='font-size: 18px; padding: 20px;'>📦 GESTÃO DE ESTOQUE E COMPRAS</a>"
        botoes += "<a href='/dashboard' class='btn-acao btn-red' style='font-size: 18px; padding: 20px;'>📊 RELATÓRIOS DO BAR</a>"
    botoes += "<a href='/baixar_conector' class='btn-acao btn-dark' style='padding: 15px;'>🖨️ BAIXAR CONECTOR DE IMPRESSORA</a>"
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'>{IMG_LOGO_PEQ}<h2>🦉 MÓDULO OLD GOOSE (BAR)</h2><div style='display:flex; flex-direction:column; gap:12px; margin-top:20px;'>{botoes}</div><br><a href='/central' style='color:#777; text-decoration:none;'>⬅️ Voltar ao Hub Central</a></div></div></body></html>"

@app.get("/diretoria", response_class=HTMLResponse)
async def menu_diretoria(request: Request):
    role = request.session.get("role")
    if not role or role not in ["admin", "diretoria"]: return RedirectResponse("/central")
    botoes = "<a href='/usuarios' class='btn-acao' style='font-size: 18px; padding: 20px;'>👥 CONTROLE DE MEMBROS E ACESSOS</a>"
    if role == "admin": botoes += "<a href='/config_fiscal' class='btn-acao btn-dark' style='padding: 20px;'>⚙️ CONFIGURAÇÕES FISCAIS (NFC-e)</a>"
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'>{IMG_LOGO_PEQ}<h2>👔 MÓDULO DIRETORIA</h2><div style='display:flex; flex-direction:column; gap:12px; margin-top:20px;'>{botoes}</div><br><a href='/central' style='color:#777; text-decoration:none;'>⬅️ Voltar ao Hub Central</a></div></div></body></html>"

@app.get("/tesouraria", response_class=HTMLResponse)
async def menu_tesouraria(request: Request):
    role = request.session.get("role")
    if not role or role not in ["admin", "diretoria", "tesoureiro"]: return RedirectResponse("/central")
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'>{IMG_LOGO_PEQ}<h2>💰 Tesouraria do Clube</h2><p style='color:#888; font-size:18px; margin: 40px 0;'>🚧 Área em Construção 🚧<br><br>As mensalidades e anuidades do clube estarão disponíveis aqui em breve.</p><a href='/central' class='btn-acao btn-dark' style='width:250px; margin:auto;'>⬅️ VOLTAR AO MENU</a></div></div></body></html>"

@app.get("/modulo/{nome}", response_class=HTMLResponse)
async def modulo_em_construcao(request: Request, nome: str):
    if not request.session.get("user"): return RedirectResponse("/")
    titulos = {"steelgoose": "Steel Goose", "secretaria": "Secretaria", "rp": "Relações Públicas", "ouvidoria": "Ouvidoria"}
    titulo = titulos.get(nome, "Em Construção")
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'>{IMG_LOGO_PEQ}<h2>Módulo {titulo}</h2><p style='color:#888; font-size:18px; margin: 40px 0;'>🚧 Área em Construção 🚧</p><a href='/central' class='btn-acao btn-dark' style='width:250px; margin:auto;'>⬅️ VOLTAR AO MENU</a></div></div></body></html>"

# ==========================================
# PAINEL DE COMANDAS DO OLD GOOSE (BAR / PDV)
# ==========================================
@app.get("/pdv", response_class=HTMLResponse)
async def pdv_painel(request: Request):
    if request.session.get("role") not in ["admin", "diretoria", "old_goose", "caixa"]: return RedirectResponse(url="/central")
    linhas_comandas = ""
    with engine.connect() as conn:
        comandas_abertas = conn.execute(text("SELECT numero_comanda, total_conta FROM comandas WHERE status = 'ABERTA' ORDER BY id DESC")).fetchall()
        for c in comandas_abertas:
            linhas_comandas += f"<div class='card-comanda-item' data-nome='{c.numero_comanda}' style='background:{COR_INPUT}; border:1px solid {COR_BORDA}; border-radius:8px; padding:15px; display:flex; justify-content:space-between; align-items:center;'><div><span style='font-size:18px; font-weight:bold; color:{COR_AMARELO};'>📋 {c.numero_comanda.upper()}</span><br><small style='color:#888;'>Consumo Parcial</small></div><div style='text-align:right;'><span style='font-size:20px; font-weight:bold; color:#FFF;'>R$ {float(c.total_conta or 0):.2f}</span><br><a href='/pdv/comanda/{urllib.parse.quote(c.numero_comanda)}' class='btn-acao' style='padding:5px 12px; margin:5px 0 0 0; font-size:12px; display:inline-block; width:auto;'>Lançar / Fechar</a></div></div>"
    if not linhas_comandas: linhas_comandas = "<p id='sem-comandas' style='color:#555; grid-column: 1/-1; text-align:center;'>Nenhuma comanda aberta.</p>"
    js_busca = "<script>function filtrarComandas() { let input = document.getElementById('busca-comanda'); let filter = input.value.toLowerCase().trim(); let container = document.getElementById('lista-comandas-grid'); let items = container.getElementsByClassName('card-comanda-item'); for (let i = 0; i < items.length; i++) { let nomeComanda = items[i].getAttribute('data-nome').toLowerCase(); if (nomeComanda.includes(filter)) { items[i].style.display = 'flex'; } else { items[i].style.display = 'none'; } } }</script>"
    return f"<html><head>{CSS}{js_busca}</head><body style='background:{COR_FUNDO}; overflow-y:auto;'><div class='container-center' style='height:auto; padding:40px 20px;'><div class='card-center' style='max-width:900px;'>{IMG_LOGO_PEQ}<h2>🛒 Controle do Bar</h2><div style='background:#0A0A0A; padding:20px; border-radius:10px; border:1px solid {COR_BORDA}; margin-bottom:25px;'><h3 style='margin-bottom:15px;'>⚡ GERENCIAR ATENDIMENTO</h3><div style='display:flex; gap:15px; flex-wrap:wrap;'><button class='btn-acao' style='flex:1; font-size:18px; padding:20px;' onclick='document.getElementById(\"box-comanda\").style.display=\"block\";'>📋 ABRIR COMANDA</button><form action='/pdv/abrir_avulso' method='post' style='flex:1; margin:0;'><button class='btn-acao btn-dark' style='width:100%; font-size:18px; padding:20px;'>🛒 VENDA AVULSA</button></form></div><div id='box-comanda' style='display:none; margin-top:20px; border-top:1px dashed {COR_BORDA}; padding-top:15px;'><form action='/pdv/abrir_comanda' method='post'><label style='font-size:14px; color:#AAA;'>Comanda (Nome/Nº):</label><input class='input-padrao' name='nome_comanda' placeholder='Ex: Pará...' required autocomplete='off'><button class='btn-acao' style='width:200px; margin-top:5px;'>INICIAR</button></form></div></div><div style='margin-bottom: 15px; text-align: left;'><label style='font-size: 12px; color: #777; font-weight: bold;'>🔍 BUSCAR COMANDA:</label><input type='text' id='busca-comanda' oninput='filtrarComandas()' class='input-padrao' placeholder='Digitar...' autocomplete='off'></div><h3>📋 Comandas Ativas</h3><div id='lista-comandas-grid' style='display:grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap:15px; text-align:left; margin-top:15px;'>{linhas_comandas}</div><br><a href='/oldgoose' class='btn-acao btn-dark' style='width:200px; margin:auto;'>⬅️ Voltar ao Old Goose</a></div></div></body></html>"

@app.post("/pdv/abrir_comanda")
async def abrir_comanda(nome_comanda: str = Form(...)):
    nome_limpo = nome_comanda.strip().replace("/", "-")
    try:
        with engine.begin() as conn:
            existe = conn.execute(text("SELECT id FROM comandas WHERE numero_comanda = :c AND status = 'ABERTA' LIMIT 1"), {"c": nome_limpo}).fetchone()
            if not existe: conn.execute(text("INSERT INTO comandas (numero_comanda, total_conta, status) VALUES (:c, 0.00, 'ABERTA')"), {"c": nome_limpo})
    except: pass
    return RedirectResponse(url=f"/pdv/comanda/{urllib.parse.quote(nome_limpo)}", status_code=303)

@app.post("/pdv/abrir_avulso")
async def abrir_avulso():
    id_avulso = "AVULSO-" + datetime.now().strftime("%H%M%S")
    try:
        with engine.begin() as conn: conn.execute(text("INSERT INTO comandas (numero_comanda, total_conta, status) VALUES (:c, 0.00, 'ABERTA')"), {"c": id_avulso})
    except: pass
    return RedirectResponse(url=f"/pdv/comanda/{id_avulso}", status_code=303)

@app.get("/pdv/comanda/{numero_comanda}", response_class=HTMLResponse)
async def tela_comanda_detalhe(numero_comanda: str, request: Request):
    if request.session.get("role") not in ["admin", "diretoria", "old_goose", "caixa"]: return RedirectResponse(url="/central")
    with engine.connect() as conn:
        comanda = conn.execute(text("SELECT numero_comanda, total_conta FROM comandas WHERE numero_comanda = :c AND status = 'ABERTA' ORDER BY id DESC LIMIT 1"), {"c": numero_comanda}).fetchone()
        if not comanda: return RedirectResponse(url="/pdv")
        
        # Puxa apenas os itens que não foram estornados
        itens_lançados = conn.execute(text("SELECT id, item_nome, valor FROM vendas_itens WHERE comanda_num = :c AND status = 'ABERTA' ORDER BY id DESC"), {"c": numero_comanda}).fetchall()
        html_itens = "".join([f"<div style='display:flex; justify-content:space-between; padding:10px; border-bottom:1px dashed {COR_BORDA}; color:#FFF; align-items:center;'><span>{it.item_nome}</span><span>R$ {float(it.valor):.2f} <form action='/pdv/remover_item' method='post' style='display:inline; margin-left:15px;'><input type='hidden' name='item_id' value='{it.id}'><input type='hidden' name='num_comanda' value='{numero_comanda}'><button style='background:none; border:none; color:{COR_VERMELHO}; cursor:pointer; font-size:18px;' title='Estornar Item'>☒</button></form></span></div>" for it in itens_lançados])
        
        produtos_db = conn.execute(text("SELECT id, nome, preco, estoque FROM produtos ORDER BY nome")).fetchall()
        html_produtos = ""
        for p in produtos_db:
            # TRAVA DE ESTOQUE: Se for <= 0, fica vermelho e não clica
            if p.estoque > 0:
                html_produtos += f"<div class='card-produto' onclick='adicionarItem({p.id})'><span style='font-weight:bold; color:{COR_AMARELO}; display:block; font-size:15px;'>{p.nome.upper()}</span><span style='color:#FFF; font-weight:bold; font-size:14px; display:block; margin-top:5px;'>R$ {float(p.preco):.2f}</span><span class='badge-estoque'>Estoque: {int(p.estoque)} un</span></div>"
            else:
                html_produtos += f"<div class='card-produto' style='border-color:{COR_VERMELHO}; opacity:0.6; cursor:not-allowed;'><span style='font-weight:bold; color:{COR_VERMELHO}; display:block; font-size:15px; text-decoration: line-through;'>{p.nome.upper()}</span><span style='color:#FFF; font-weight:bold; font-size:14px; display:block; margin-top:5px;'>R$ {float(p.preco):.2f}</span><span class='badge-estoque' style='color:{COR_VERMELHO}; font-weight:bold;'>ESGOTADO</span></div>"

    js_inject = f"<script>function adicionarItem(prodId) {{ let form = document.createElement('form'); form.method = 'POST'; form.action = '/pdv/adicionar_item'; form.innerHTML = `<input type='hidden' name='comanda_num' value='{numero_comanda}'><input type='hidden' name='produto_id' value='${{prodId}}'>`; document.body.appendChild(form); form.submit(); }}</script>"
    return f"<html><head>{CSS}{js_inject}</head><body style='background:{COR_FUNDO};'><div style='display:flex; height:100vh; width:100%; overflow:hidden;'><div style='flex:1.3; padding:20px; display:flex; flex-direction:column; background:{COR_CARD}; border-right:2px solid {COR_BORDA}; overflow-y:auto;'><h2>🍺 Itens do Bar</h2><div class='grid-produtos'>{html_produtos}</div></div><div style='flex:1; padding:20px; display:flex; flex-direction:column; justify-content:space-between; background:#080808; overflow-y:auto;'><div><h2 style='color:#FFF; margin-bottom:5px;'>📋 {comanda.numero_comanda.upper()}</h2><div style='background:#000; border:1px solid {COR_BORDA}; border-radius:8px; padding:10px; margin-top:15px; max-height:220px; overflow-y:auto;'>{html_itens if html_itens else '<p style=\"color:#444; text-align:center;\">Nenhum item lançado ainda.</p>'}</div></div><div style='background:#111; padding:20px; border-radius:8px; margin-top:20px; border:1px solid {COR_BORDA};'><div style='color:#888; font-size:14px;'>TOTAL DA CONTA</div><div style='color:{COR_AMARELO}; font-size:40px; font-weight:bold; margin-bottom:15px;'>R$ {float(comanda.total_conta or 0):.2f}</div><form action='/pdv/finalizar_comanda' method='post'><input type='hidden' name='comanda_num' value='{comanda.numero_comanda}'><select name='pagamento' class='input-padrao' style='font-size:16px; padding:12px; margin-bottom:12px;'><option value='01'>💵 DINHEIRO</option><option value='17'>💠 PIX</option><option value='03'>💳 CRÉDITO</option><option value='04'>💳 DÉBITO</option></select><button class='btn-acao' style='font-size:18px; padding:15px;'>🏁 FECHAR CONTA</button></form><a href='/pdv' class='btn-acao btn-dark' style='margin-top:5px; padding:10px; font-size:12px;'>⬅️ VOLTAR AO PAINEL</a></div></div></div></body></html>"

@app.post("/pdv/adicionar_item")
async def pdv_adicionar_item(comanda_num: str = Form(...), produto_id: int = Form(...)):
    with engine.begin() as conn:
        prod = conn.execute(text("SELECT nome, preco, estoque FROM produtos WHERE id = :id"), {"id": produto_id}).fetchone()
        # Trava de backend: só deixa lançar se o estoque for maior que 0
        if prod and prod.estoque > 0:
            conn.execute(text("INSERT INTO vendas_itens (comanda_num, item_nome, valor, status) VALUES (:c, :n, :v, 'ABERTA')"), {"c": comanda_num, "n": prod.nome, "v": prod.preco})
            conn.execute(text("UPDATE comandas SET total_conta = total_conta + :v WHERE numero_comanda = :c AND status = 'ABERTA'"), {"v": prod.preco, "c": comanda_num})
            conn.execute(text("UPDATE produtos SET estoque = estoque - 1 WHERE id = :id"), {"id": produto_id})
    return RedirectResponse(url=f"/pdv/comanda/{urllib.parse.quote(comanda_num)}", status_code=303)

@app.post("/pdv/remover_item")
async def pdv_remover_item(item_id: int = Form(...), num_comanda: str = Form(...)):
    with engine.begin() as conn:
        item = conn.execute(text("SELECT item_nome, valor FROM vendas_itens WHERE id = :id AND status = 'ABERTA'"), {"id": item_id}).fetchone()
        if item:
            # Subtrai o valor da comanda
            conn.execute(text("UPDATE comandas SET total_conta = GREATEST(total_conta - :v, 0.00) WHERE numero_comanda = :c AND status = 'ABERTA'"), {"v": item.valor, "c": num_comanda})
            # Marca o item como ESTORNADO no lugar de apagar do banco
            conn.execute(text("UPDATE vendas_itens SET status = 'ESTORNADO' WHERE id = :id"), {"id": item_id})
            # Devolve 1 pro estoque
            conn.execute(text("UPDATE produtos SET estoque = estoque + 1 WHERE nome = :n"), {"n": item.item_nome})
    return RedirectResponse(url=f"/pdv/comanda/{urllib.parse.quote(num_comanda)}", status_code=303)

@app.post("/pdv/finalizar_comanda")
async def finalizar_comanda(request: Request, comanda_num: str = Form(...), pagamento: str = Form(...)):
    nomes_pag = {"01": "DINHEIRO", "17": "PIX", "03": "C. CREDITO", "04": "C. DEBITO"}
    nome_pagamento = nomes_pag.get(pagamento, "OUTROS")
    usuario = request.session.get("user", "Caixa")
    with engine.begin() as conn:
        comanda = conn.execute(text("SELECT total_conta FROM comandas WHERE numero_comanda = :c AND status = 'ABERTA' ORDER BY id DESC LIMIT 1"), {"c": comanda_num}).fetchone()
        if not comanda: return RedirectResponse(url="/pdv", status_code=303)
        itens = conn.execute(text("SELECT item_nome, valor FROM vendas_itens WHERE comanda_num = :c AND status = 'ABERTA'"), {"c": comanda_num}).fetchall()
        
        conn.execute(text("UPDATE comandas SET status = 'FECHADA', forma_pagamento = :p, data_fechamento = CURRENT_TIMESTAMP WHERE numero_comanda = :c AND status = 'ABERTA'"), {"p": nome_pagamento, "c": comanda_num})
        # Fecha apenas os que estavam ABERTA, mantendo os ESTORNADO quietos
        conn.execute(text("UPDATE vendas_itens SET status = 'FECHADA' WHERE comanda_num = :c AND status = 'ABERTA'"), {"c": comanda_num})
        
        txt = f"--------------------------------\n   STEEL GOOSE MOTO GROUP\nPLANALTO-DF\n--------------------------------\nCOMANDA: {comanda_num.upper()}\nOPERADOR: {usuario.upper()}\nDATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n--------------------------------\n"
        for idx, item in enumerate(itens): txt += f"1x {item.item_nome[:20]:<20} R$ {float(item.valor):.2f}\n"
        txt += f"--------------------------------\nTOTAL: R$ {float(comanda.total_conta):.2f}\nPAGTO: {nome_pagamento}\n Obrigado pela parceria! 🦅\n--------------------------------\n"
        conn.execute(text("INSERT INTO fila_impressao (conteudo) VALUES (:txt)"), {"txt": txt})
    return HTMLResponse(f"<script>alert('Conta {comanda_num} fechada!'); window.location.href='/pdv';</script>")

# ==========================================
# GESTÃO DE ESTOQUE E COMPRAS (OLD GOOSE)
# ==========================================
@app.get("/estoque", response_class=HTMLResponse)
async def tela_estoque(request: Request):
    if request.session.get("role") not in ["admin", "diretoria", "old_goose"]: return RedirectResponse(url="/central")
    linhas = ""
    with engine.connect() as conn:
        prods_db = conn.execute(text("SELECT id, nome, categoria, preco, estoque FROM produtos ORDER BY nome")).fetchall()
        for r in prods_db:
            n_seguro = r.nome.replace('"', '').replace("'", "")
            acoes = f"<div style='display:flex; gap:5px;'><button type='button' class='btn-acao' style='padding:8px; margin:0; background:#10b981; color:#000;' onclick='abrirModalEntrada({r.id}, \"{n_seguro}\")' title='Registrar Compra / Entrada'>➕</button><button type='button' class='btn-acao btn-dark' style='padding:8px; margin:0;' onclick='abrirModal({r.id}, \"{n_seguro}\", \"{r.categoria}\", {float(r.preco or 0)})' title='Editar Produto'>✏️</button><form action='/excluir_produto' method='post' style='margin:0;' onsubmit='return confirm(\"Excluir item?\");'><input type='hidden' name='id' value='{r.id}'><button class='btn-acao btn-red' style='padding:8px; margin:0;'>🗑️</button></form></div>"
            linhas += f"<tr><td style='color:#FFF; font-weight:bold;'>{r.nome.upper()}</td><td style='color:{COR_AMARELO};'>R$ {float(r.preco or 0):.2f}</td><td style='color:#FFF; text-align:center;'>{int(r.estoque or 0)} un</td><td>{acoes}</td></tr>"
            
    add_form = f"<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;'><h3>📦 Produtos</h3><a href='/historico_compras' class='btn-acao btn-dark' style='width:auto; margin:0; padding:10px 15px; font-size:12px;'>📜 VER HISTÓRICO DE COMPRAS</a></div><div style='background:#0A0A0A; padding:20px; border-radius:10px; margin-bottom:20px; border:1px solid {COR_BORDA};'><h3>➕ CADASTRAR NOVO PRODUTO</h3><form action='/novo_produto' method='post' style='display:flex; flex-wrap:wrap; gap:10px;'><input name='nome' placeholder='Nome da Bebida / Item' class='input-padrao' style='flex:2;' required><select name='cat' class='input-padrao' style='flex:1;'><option value='BEBIDAS'>BEBIDAS</option><option value='ALIMENTOS'>ALIMENTOS</option><option value='VESTUARIO'>VESTUARIO</option></select><input name='preco' placeholder='Preço de Venda' step='0.01' type='number' class='input-padrao' style='width:120px;' required><input name='qtd' type='number' placeholder='Qtd Estoque Inicial' class='input-padrao' style='width:150px;' required><button class='btn-acao' style='width:100%;'>SALVAR NO ESTOQUE</button></form></div>"
    
    modal_edit = f"<div id='editModal' style='display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:1000; align-items:center; justify-content:center;'><div class='card-center' style='position:relative; width:90%; max-width:400px; padding:20px; background:#121214;'><span onclick='fecharModal()' style='position:absolute; top:10px; right:15px; cursor:pointer; font-size:24px; color:#FFF;'>&times;</span><h3 style='margin-top:0;'>✏️ EDITAR PRODUTO</h3><form action='/editar_produto' method='post' style='display:flex; flex-direction:column; gap:10px;'><input type='hidden' name='id' id='edit_id'><input name='nome' id='edit_nome' class='input-padrao' required><select name='cat' id='edit_cat' class='input-padrao' required><option value='BEBIDAS'>BEBIDAS</option><option value='ALIMENTOS'>ALIMENTOS</option><option value='VESTUARIO'>VESTUARIO</option></select><input name='preco' id='edit_preco' type='number' step='0.01' class='input-padrao' required><button class='btn-acao' style='margin-top:10px;'>SALVAR ALTERAÇÕES</button></form></div></div>"
    
    modal_entrada = f"""
    <div id='entradaModal' style='display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:1000; align-items:center; justify-content:center;'>
        <div class='card-center' style='position:relative; width:90%; max-width:400px; padding:20px; background:#121214; border:1px solid {COR_BORDA};'>
            <span onclick='fecharModalEntrada()' style='position:absolute; top:10px; right:15px; cursor:pointer; font-size:24px; color:#FFF;'>&times;</span>
            <h3 style='margin-top:0; color:#10b981;'>📥 REGISTRAR COMPRA</h3>
            <form action='/att_estoque' method='post' style='display:flex; flex-direction:column; gap:10px;'>
                <input type='hidden' name='id' id='entrada_id'>
                <p style='color:#FFF; text-align:left; margin:0;'>Produto: <b id='entrada_nome' style='color:#10b981; text-transform:uppercase;'></b></p>
                <div>
                    <label style='font-size:12px; color:#aaa; font-weight:bold;'>QUANTIDADE COMPRADA (UN):</label>
                    <input name='q' type='number' class='input-padrao' required autocomplete='off'>
                </div>
                <div>
                    <label style='font-size:12px; color:#aaa; font-weight:bold;'>VALOR TOTAL PAGO (R$):</label>
                    <input name='custo' type='number' step='0.01' class='input-padrao' placeholder='Ex: 150.00' required>
                </div>
                <button class='btn-acao' style='background:#10b981; margin-top:10px;'>SALVAR ENTRADA</button>
            </form>
        </div>
    </div>
    """

    js_modal = "<script>function abrirModal(id, nome, cat, preco) { document.getElementById('edit_id').value = id; document.getElementById('edit_nome').value = nome; document.getElementById('edit_cat').value = cat; document.getElementById('edit_preco').value = preco; document.getElementById('editModal').style.display = 'flex'; } function fecharModal() { document.getElementById('editModal').style.display = 'none'; } function abrirModalEntrada(id, nome) { document.getElementById('entrada_id').value = id; document.getElementById('entrada_nome').innerText = nome; document.getElementById('entradaModal').style.display = 'flex'; } function fecharModalEntrada() { document.getElementById('entradaModal').style.display = 'none'; }</script>"
    return f"<html><head>{CSS}{js_modal}</head><body>{modal_edit}{modal_entrada}<div class='container-center'><div class='card-center' style='max-width:800px;'>{IMG_LOGO_PEQ}<h2>📦 Estoque</h2>{add_form}<div style='max-height:400px; overflow-y:auto; border:1px solid {COR_BORDA};'><table><tr><th>Produto</th><th>Preço</th><th>Qtd Atual</th><th>Ações</th></tr>{linhas}</table></div><br><a href='/oldgoose' class='btn-acao btn-dark' style='width:200px; margin:auto;'>⬅️ Voltar ao Old Goose</a></div></div></body></html>"

@app.post("/novo_produto")
async def novo_produto(request: Request):
    if request.session.get("role") not in ["admin", "diretoria", "old_goose"]: return RedirectResponse(url="/central")
    f = await request.form()
    try:
        with engine.begin() as conn: conn.execute(text("INSERT INTO produtos (codigo_barras, nome, categoria, preco, estoque) VALUES (:cb, :n, :c, :p, :q)"), {"cb": "SG-"+datetime.now().strftime("%f"), "n": f.get("nome").upper(), "c": f.get("cat"), "p": float(f.get("preco").replace(",", ".")), "q": int(f.get("qtd"))})
    except: pass
    return RedirectResponse(url="/estoque", status_code=303)

@app.post("/att_estoque")
async def att_estoque(request: Request):
    if request.session.get("role") not in ["admin", "diretoria", "old_goose"]: return RedirectResponse(url="/central")
    f = await request.form()
    prod_id = f.get("id")
    qtd = int(f.get("q", "0"))
    custo = float(f.get("custo", "0").replace(",", "."))
    try:
        with engine.begin() as conn: 
            prod = conn.execute(text("SELECT nome FROM produtos WHERE id = :id"), {"id": prod_id}).fetchone()
            if prod:
                conn.execute(text("UPDATE produtos SET estoque = COALESCE(estoque, 0) + :q WHERE id = :id"), {"id": prod_id, "q": qtd})
                conn.execute(text("INSERT INTO historico_estoque (produto_nome, qtd_adicionada, valor_custo, data_entrada) VALUES (:n, :q, :c, CURRENT_DATE)"), {"n": prod.nome, "q": qtd, "c": custo})
    except: pass
    return RedirectResponse(url="/estoque", status_code=303)

@app.get("/historico_compras", response_class=HTMLResponse)
async def historico_compras(request: Request):
    if request.session.get("role") not in ["admin", "diretoria", "old_goose"]: return RedirectResponse(url="/central")
    linhas = ""
    with engine.connect() as conn:
        hist = conn.execute(text("SELECT produto_nome, qtd_adicionada, valor_custo, data_entrada FROM historico_estoque ORDER BY id DESC LIMIT 100")).fetchall()
        for r in hist:
            custo_unit = float(r.valor_custo)/r.qtd_adicionada if r.qtd_adicionada > 0 else 0
            linhas += f"<tr><td style='color:#FFF; font-weight:bold;'>{r.produto_nome}</td><td style='color:{COR_AMARELO}; text-align:center;'>{r.qtd_adicionada}</td><td style='color:#FFF; text-align:right;'>R$ {float(r.valor_custo):.2f}<br><small style='color:#888;'>R$ {custo_unit:.2f}/un</small></td><td style='color:#888; text-align:right;'>{r.data_entrada.strftime('%d/%m/%Y') if hasattr(r.data_entrada, 'strftime') else str(r.data_entrada)}</td></tr>"
            
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center' style='max-width:800px;'>{IMG_LOGO_PEQ}<h2>📜 Histórico de Compras</h2><div style='max-height:500px; overflow-y:auto; border:1px solid {COR_BORDA};'><table><thead style='background:#0A0A0A; position:sticky; top:0;'><tr><th>Produto</th><th style='text-align:center;'>Qtd Comprada</th><th style='text-align:right;'>Custo Total</th><th style='text-align:right;'>Data</th></tr></thead><tbody>{linhas if linhas else '<tr><td colspan=\"4\" style=\"text-align:center; color:#777;\">Nenhum registro encontrado.</td></tr>'}</tbody></table></div><br><a href='/estoque' class='btn-acao btn-dark' style='width:200px; margin:auto;'>⬅️ Voltar ao Estoque</a></div></div></body></html>"

@app.post("/editar_produto")
async def editar_produto(request: Request):
    if request.session.get("role") not in ["admin", "diretoria", "old_goose"]: return RedirectResponse(url="/central")
    f = await request.form()
    try:
        with engine.begin() as conn: conn.execute(text("UPDATE produtos SET nome = :n, categoria = :c, preco = :p WHERE id = :id"), {"n": f.get("nome").upper(), "c": f.get("cat"), "p": float(f.get("preco").replace(",", ".")), "id": f.get("id")})
    except: pass
    return RedirectResponse(url="/estoque", status_code=303)

@app.post("/excluir_produto")
async def excluir_produto(request: Request):
    if request.session.get("role") not in ["admin", "diretoria", "old_goose"]: return RedirectResponse(url="/central")
    f = await request.form()
    try:
        with engine.begin() as conn: conn.execute(text("DELETE FROM produtos WHERE id = :id"), {"id": f.get("id")})
    except: pass
    return RedirectResponse(url="/estoque", status_code=303)


# ==========================================
# DASHBOARD: RELATÓRIOS DO BAR (COM ESTORNOS)
# ==========================================
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, inicio: str = "", fim: str = ""):
    if request.session.get("role") not in ["admin", "diretoria", "old_goose"]: return RedirectResponse(url="/central")
    dt_inicio = inicio if inicio else date.today().strftime("%Y-%m-%d")
    dt_fim = fim if fim else date.today().strftime("%Y-%m-%d")
    
    where_clause = "status = 'FECHADA' AND CAST(data_fechamento AS DATE) BETWEEN CAST(:inicio AS DATE) AND CAST(:fim AS DATE)"
    where_estorno = "status = 'ESTORNADO' AND CAST(data_venda AS DATE) BETWEEN CAST(:inicio AS DATE) AND CAST(:fim AS DATE)"
    
    with engine.connect() as conn:
        # Faturamento das Vendas Fechadas
        kpi = conn.execute(text(f"SELECT SUM(total_conta) as total FROM comandas WHERE {where_clause}"), {"inicio": dt_inicio, "fim": dt_fim}).fetchone()
        faturamento = float(kpi.total or 0)
        
        # Puxando o total de itens estornados no período
        estornos_kpi = conn.execute(text(f"SELECT COUNT(*) as qtd, SUM(valor) as total FROM vendas_itens WHERE {where_estorno}"), {"inicio": dt_inicio, "fim": dt_fim}).fetchone()
        total_estornado = float(estornos_kpi.total or 0)
        qtd_estornada = int(estornos_kpi.qtd or 0)
        
        # Itens Vendidos (Tabela)
        itens_db = conn.execute(text(f"SELECT item_nome, COUNT(*) as qtd, SUM(valor) as t FROM vendas_itens WHERE status = 'FECHADA' AND comanda_num IN (SELECT numero_comanda FROM comandas WHERE {where_clause}) GROUP BY item_nome ORDER BY qtd DESC"), {"inicio": dt_inicio, "fim": dt_fim}).fetchall()
        linhas_tabela = "".join([f"<tr><td style='color:#FFF;'>{it.item_nome}</td><td style='color:{COR_AMARELO}; text-align:center;'>{it.qtd}</td><td style='color:#FFF; text-align:right;'>R$ {float(it.t):.2f}</td></tr>" for it in itens_db])
        
    return f"""<html><head>{CSS}</head><body><div class='container-center'><div class='card-center' style='max-width:800px;'>
        {IMG_LOGO_PEQ}<h2>📊 Relatório do Bar</h2>
        <form method='get' class='filtro-box'>
            <div style='flex:1;'><label>Data Início:</label><br><input type='date' name='inicio' value='{dt_inicio}' class='input-padrao'></div>
            <div style='flex:1;'><label>Data Fim:</label><br><input type='date' name='fim' value='{dt_fim}' class='input-padrao'></div>
            <div style='display:flex; align-items:flex-end;'><button class='btn-acao' style='margin:0; height:48px;'>FILTRAR</button></div>
        </form>
        
        <div class='grid-dash'>
            <div class='card-kpi'>
                <h3>Faturamento do Período</h3>
                <p>R$ {faturamento:.2f}</p>
            </div>
            <div class='card-kpi' style='border-left-color:{COR_VERMELHO};'>
                <h3>Total Estornado (Cancelado)</h3>
                <p style='color:{COR_VERMELHO};'>R$ {total_estornado:.2f} <small style='font-size:14px; color:#888;'>({qtd_estornada} itens)</small></p>
            </div>
        </div>
        
        <div class='chart-container'>
            <h3>📋 ITENS VENDIDOS</h3>
            <table style='margin-top:0;'>
                <thead><tr><th style='color:{COR_AMARELO};'>Produto</th><th style='color:{COR_AMARELO}; text-align:center;'>Qtd</th><th style='color:{COR_AMARELO}; text-align:right;'>Arrecadado</th></tr></thead>
                <tbody>{linhas_tabela if linhas_tabela else "<tr><td colspan='3' style='text-align:center;'>Nenhuma venda.</td></tr>"}</tbody>
            </table>
        </div>
        <br><a href='/oldgoose' class='btn-acao btn-dark' style='width:250px; margin:auto;'>⬅️ Voltar ao Old Goose</a>
    </div></div></body></html>"""


# ==========================================
# MÓDULO DIRETORIA: CONTROLE DE USUÁRIOS E ACESSOS
# ==========================================
@app.get("/usuarios", response_class=HTMLResponse)
async def tela_usuarios(request: Request):
    role_session = request.session.get("role")
    if role_session not in ["admin", "diretoria"]: return RedirectResponse(url="/central")
    linhas = ""
    with engine.connect() as conn:
        users_db = conn.execute(text("SELECT id, username, email, role, status FROM usuarios ORDER BY status DESC, role, username")).fetchall()
        for r in users_db:
            acoes = ""
            if r.username != "admin":
                if r.status == 'BLOQUEADO': btn_block = f"<form action='/toggle_usuario' method='post' style='margin:0;'><input type='hidden' name='id' value='{r.id}'><button class='btn-acao' style='background:#10b981; padding:8px; margin:0;' title='Aprovar Acesso'>🔓</button></form>"
                else: btn_block = f"<form action='/toggle_usuario' method='post' style='margin:0;'><input type='hidden' name='id' value='{r.id}'><button class='btn-acao' style='background:#f59e0b; padding:8px; margin:0;' title='Bloquear'>🔒</button></form>"
                
                btn_edit_acesso = f"<button type='button' class='btn-acao btn-dark' style='padding:8px; margin:0;' onclick='abrirModalAcesso({r.id}, \"{r.username}\", \"{r.role}\")' title='Alterar Cargo do Membro'>⚙️</button>"
                
                btn_del = f"<form action='/excluir_usuario' method='post' style='margin:0;' onsubmit='return confirm(\"Excluir?\");'><input type='hidden' name='id' value='{r.id}'><button class='btn-acao btn-red' style='padding:8px; margin:0;'>🗑️</button></form>"
                acoes = f"<div style='display:flex; gap:5px;'>{btn_block}{btn_edit_acesso}{btn_del}</div>"
            st_badge = f"<span style='color:#10b981; font-weight:bold;'>ATIVO</span>" if r.status == 'ATIVO' else f"<span style='color:{COR_VERMELHO}; font-weight:bold;'>PENDENTE/BLOQ.</span>"
            linhas += f"<tr><td><b style='color:#FFF;'>{r.username.upper()}</b><br><small style='color:#888;'>{r.email or 'S/ Email'}</small></td><td style='color:{COR_AMARELO}; font-weight:bold;'>{r.role.upper().replace('_', ' ')}</td><td>{st_badge}</td><td>{acoes}</td></tr>"
            
    opcoes_cargos = "<option value='candidato'>CANDIDATO</option><option value='membro'>MEMBRO</option><option value='secretario'>SECRETÁRIO</option><option value='tesoureiro'>TESOUREIRO</option><option value='rp'>RELAÇÕES PÚBLICAS</option><option value='diretoria'>DIRETORIA</option><option value='ouvidoria'>OUVIDORIA</option><option value='old_goose'>OLD GOOSE</option><option value='caixa'>CAIXA DO BAR</option>"
    add_form = f"<div style='background:#0A0A0A; padding:20px; border-radius:10px; margin-bottom:20px; border:1px solid {COR_BORDA};'><h3>➕ CRIAR ACESSO MANUAL</h3><form action='/novo_usuario_direto' method='post' style='display:flex; flex-wrap:wrap; gap:10px;'><input name='u' placeholder='Login' class='input-padrao' style='flex:1;' required><input name='e' type='email' placeholder='E-mail' class='input-padrao' style='flex:1;' required><input name='p' type='password' placeholder='Senha' class='input-padrao' style='flex:1;' required><select name='r' class='input-padrao' style='flex:1;'>{opcoes_cargos}</select><button class='btn-acao' style='width:100%;'>SALVAR USUÁRIO</button></form></div>"
    
    modal_acesso = f"""
    <div id='acessoModal' style='display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:1000; align-items:center; justify-content:center;'>
        <div class='card-center' style='position:relative; width:90%; max-width:400px; padding:20px; background:#121214;'>
            <span onclick='fecharModalAcesso()' style='position:absolute; top:10px; right:15px; cursor:pointer; font-size:24px; color:#FFF;'>&times;</span>
            <h3 style='margin-top:0; color:{COR_AMARELO};'>⚙️ ALTERAR CARGO / ACESSO</h3>
            <form action='/alterar_acesso' method='post' style='display:flex; flex-direction:column; gap:10px;'>
                <input type='hidden' name='id' id='acesso_id'>
                <p style='color:#FFF; text-align:left; margin:0;'>Usuário: <b id='acesso_user' style='color:{COR_AMARELO}; text-transform:uppercase;'></b></p>
                <select name='role' id='acesso_role' class='input-padrao' required>
                    {opcoes_cargos}
                </select>
                <button class='btn-acao' style='margin-top:10px;'>CONCEDER ACESSO</button>
            </form>
        </div>
    </div>
    """
    js_modal_acesso = "<script>function abrirModalAcesso(id, user, role) { document.getElementById('acesso_id').value = id; document.getElementById('acesso_user').innerText = user; document.getElementById('acesso_role').value = role; document.getElementById('acessoModal').style.display = 'flex'; } function fecharModalAcesso() { document.getElementById('acessoModal').style.display = 'none'; }</script>"
    return f"<html><head>{CSS}{js_modal_acesso}</head><body>{modal_acesso}<div class='container-center'><div class='card-center' style='max-width:900px;'>{IMG_LOGO_PEQ}<h2>Aprovações e Usuários</h2>{add_form}<div style='max-height:400px; overflow-y:auto; border:1px solid {COR_BORDA};'><table><tr><th>Usuário</th><th>Cargo/Acesso</th><th>Status</th><th>Ações</th></tr>{linhas}</table></div><br><a href='/diretoria' class='btn-acao btn-dark' style='width:250px; margin:auto;'>⬅️ Voltar à Diretoria</a></div></div></body></html>"

@app.post("/toggle_usuario")
async def toggle_usuario(request: Request):
    if request.session.get("role") not in ["admin", "diretoria"]: return RedirectResponse(url="/central")
    f = await request.form()
    try:
        with engine.begin() as conn:
            target = conn.execute(text("SELECT username, status FROM usuarios WHERE id = :id"), {"id": f.get("id")}).fetchone()
            if target and target.username != 'admin':
                novo_status = 'ATIVO' if target.status == 'BLOQUEADO' else 'BLOQUEADO'
                conn.execute(text("UPDATE usuarios SET status = :s WHERE id = :id"), {"s": novo_status, "id": f.get("id")})
    except: pass
    return RedirectResponse(url="/usuarios", status_code=303)

@app.post("/novo_usuario_direto")
async def novo_usuario_direto(request: Request):
    if request.session.get("role") not in ["admin", "diretoria"]: return RedirectResponse(url="/central")
    f = await request.form()
    try:
        with engine.begin() as conn: 
            conn.execute(text("INSERT INTO usuarios (username, email, password, role, status) VALUES (:u, :e, :p, :r, 'ATIVO') ON CONFLICT (username) DO NOTHING"), {"u": f.get("u").lower(), "e": f.get("e").lower(), "p": f.get("p"), "r": f.get("r")})
    except: pass
    return RedirectResponse(url="/usuarios", status_code=303)

@app.post("/alterar_acesso")
async def alterar_acesso(request: Request):
    if request.session.get("role") not in ["admin", "diretoria"]: return RedirectResponse(url="/central")
    f = await request.form()
    try:
        with engine.begin() as conn: 
            conn.execute(text("UPDATE usuarios SET role = :r WHERE id = :id"), {"r": f.get("role"), "id": f.get("id")})
    except: pass
    return RedirectResponse(url="/usuarios", status_code=303)

@app.post("/excluir_usuario")
async def excluir_usuario(request: Request):
    if request.session.get("role") not in ["admin", "diretoria"]: return RedirectResponse(url="/central")
    f = await request.form()
    try:
        with engine.begin() as conn: conn.execute(text("DELETE FROM usuarios WHERE id = :id AND username != 'admin'"), {"id": f.get("id")})
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
async def baixar_conector():
    base_url = "http://localhost:8000" 
    script_content = f"import time\nimport requests\nimport win32print\n\nAPI_URL = '{base_url}'\n\ndef imprimir_ticket(texto):\n    impressora_padrao = win32print.GetDefaultPrinter()\n    try:\n        hPrinter = win32print.OpenPrinter(impressora_padrao)\n        hJob = win32print.StartDocPrinter(hPrinter, 1, ('Ticket Steel Goose', None, 'RAW'))\n        win32print.StartPagePrinter(hPrinter)\n        win32print.WritePrinter(hPrinter, texto.encode('utf-8'))\n        win32print.WritePrinter(hPrinter, b'\\n\\n\\n\\n\\x1B\\x6D')\n        win32print.EndPagePrinter(hPrinter)\n        win32print.EndDocPrinter(hPrinter)\n        win32print.ClosePrinter(hPrinter)\n    except Exception: pass\n\nwhile True:\n    try:\n        resposta = requests.get(f'{{API_URL}}/api/pendentes', timeout=5)\n        if resposta.status_code == 200:\n            dados = resposta.json()\n            for job in dados.get('jobs', []):\n                imprimir_ticket(job['conteudo'])\n                requests.post(f'{{API_URL}}/api/impresso/{{job[\"id\"]}}', timeout=5)\n    except: pass\n    time.sleep(2)"
    return Response(content=script_content, media_type="text/x-python", headers={"Content-Disposition": "attachment; filename=conector_impressao.py"})
