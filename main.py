from fastapi import FastAPI, Form, Request, Response, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy import create_engine, text
from starlette.middleware.sessions import SessionMiddleware
from datetime import datetime, date
import os
import shutil
import urllib.parse
import random
import smtplib
from email.mime.text import MIMEText

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="jpms_solucoes_gestao_2026_seguro")

# ==========================================
# CONEXÃO COM O BANCO DE DADOS
# ==========================================
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:GNlZnHiuKAcFnpgXhwILfigqKCNkaHqx@interchange.proxy.rlwy.net:44559/railway")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
UPLOAD_DIR = "comprovantes"
os.makedirs(UPLOAD_DIR, exist_ok=True)

with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL, status TEXT DEFAULT 'ATIVO', email TEXT);
        CREATE TABLE IF NOT EXISTS produtos (id SERIAL PRIMARY KEY, codigo_barras TEXT UNIQUE, nome TEXT NOT NULL, categoria TEXT DEFAULT 'OUTROS', preco DECIMAL(10,2) DEFAULT 0.00, estoque INT DEFAULT 0);
        CREATE TABLE IF NOT EXISTS comandas (id SERIAL PRIMARY KEY, numero_comanda TEXT NOT NULL, total_conta DECIMAL(10,2) DEFAULT 0.00, status TEXT DEFAULT 'ABERTA', forma_pagamento TEXT, data_fechamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP, nfe_solicitada BOOLEAN DEFAULT FALSE, cpf_nota TEXT);
        CREATE TABLE IF NOT EXISTS vendas_itens (id SERIAL PRIMARY KEY, comanda_num TEXT, item_nome TEXT, valor DECIMAL(10,2), data_venda DATE DEFAULT CURRENT_DATE, hora_venda TIME DEFAULT CURRENT_TIME, status TEXT DEFAULT 'ABERTA');
        CREATE TABLE IF NOT EXISTS historico_estoque (id SERIAL PRIMARY KEY, produto_nome TEXT, qtd_adicionada INT, data_entrada DATE DEFAULT CURRENT_DATE, valor_custo DECIMAL(10,2) DEFAULT 0.00, nota_fiscal TEXT);
        CREATE TABLE IF NOT EXISTS caixinha (id SERIAL PRIMARY KEY, username TEXT, mes_ano TEXT, valor DECIMAL(10,2) DEFAULT 50.00, status TEXT DEFAULT 'PENDENTE', comprovante TEXT);
        CREATE TABLE IF NOT EXISTS secretaria_itens (id SERIAL PRIMARY KEY, codigo TEXT UNIQUE, descricao TEXT, preco DECIMAL(10,2), estoque INT);
        CREATE TABLE IF NOT EXISTS pedidos_secretaria (id SERIAL PRIMARY KEY, username TEXT, item_nome TEXT, quantidade INT, valor_total DECIMAL(10,2), status TEXT DEFAULT 'PENDENTE', comprovante TEXT, data_pedido TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS fila_impressao (id SERIAL PRIMARY KEY, conteudo TEXT, status TEXT DEFAULT 'PENDENTE', data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    """))

# Migrações seguras
MIGRACOES = [
    "ALTER TABLE comandas ALTER COLUMN status SET DEFAULT 'ABERTA';",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'ATIVO';",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email TEXT;",
    "ALTER TABLE historico_estoque ADD COLUMN IF NOT EXISTS valor_custo DECIMAL(10,2) DEFAULT 0.00;",
    "ALTER TABLE historico_estoque ADD COLUMN IF NOT EXISTS nota_fiscal TEXT;"
]
for mig in MIGRACOES:
    try:
        with engine.begin() as conn: conn.execute(text(mig))
    except Exception: pass

# Admin Padrão
try:
    with engine.begin() as conn: conn.execute(text("INSERT INTO usuarios (username, password, role, status) VALUES ('admin', '1234', 'admin', 'ATIVO') ON CONFLICT (username) DO NOTHING"))
except: pass

# ==========================================
# CONSTANTES VISUAIS E FUNÇÃO DE ACESSO
# ==========================================
COR_FUNDO, COR_CARD, COR_AMARELO, COR_VERMELHO, COR_TEXTO, COR_BORDA, COR_INPUT = "#121214", "#000000", "#F3BA16", "#C82828", "#E0E0E0", "#222225", "#141416"
IMG_URL = "/logo.png"

def check_access(role_str, allowed_roles):
    if not role_str: return False
    user_roles = [r.strip().lower() for r in role_str.split(",")]
    return any(r in user_roles for r in allowed_roles)

def enviar_email_recuperacao(destinatario, nova_senha):
    remetente = os.getenv("EMAIL_REMETENTE")
    senha_app = os.getenv("EMAIL_SENHA")
    if not remetente or not senha_app:
        print(f"\n[ALERTA] E-mail não configurado. Nova senha para {destinatario}: {nova_senha}\n")
        return
    try:
        msg = MIMEText(f"Salve irmão!\n\nSua nova senha de acesso provisória ao sistema Steel Goose é: {nova_senha}\n\nFaça o login e guarde-a com segurança.\n\nForte abraço,\nDiretoria Steel Goose.")
        msg['Subject'] = 'Recuperação de Senha - Steel Goose'
        msg['From'] = remetente
        msg['To'] = destinatario
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(remetente, senha_app)
        server.sendmail(remetente, destinatario, msg.as_string())
        server.quit()
    except Exception as e: print(f"Erro email: {e}")

CSS = f"""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Steel Goose - Sistema</title>
<style>
    * {{ box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }}
    body {{ margin: 0; background: {COR_FUNDO}; color: {COR_TEXTO}; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}
    h1, h2, h3, h4 {{ color: {COR_AMARELO}; text-transform: uppercase; margin-top: 0; letter-spacing: 1px; }}
    .btn-acao {{ display: block; width: 100%; padding: 15px; margin-bottom: 8px; border: none; border-radius: 5px; font-weight: bold; color: #000; cursor: pointer; text-align: center; text-decoration: none; font-size: 14px; background: {COR_AMARELO}; transition: 0.3s; text-transform: uppercase; }}
    .btn-acao:hover {{ opacity: 0.9; transform: scale(0.98); box-shadow: 0 0 12px rgba(243, 186, 22, 0.4); }}
    .btn-dark {{ background: #1A1A1A; color: {COR_AMARELO}; border: 1px solid {COR_AMARELO}; }}
    .btn-dark:hover {{ background: {COR_AMARELO}; color: #000; }}
    .btn-red {{ background: {COR_VERMELHO}; color: white; border: none; }}
    .btn-green {{ background: #10b981; color: #000; border:none; }}
    .container-center {{ display: flex; align-items: center; justify-content: center; height: 100vh; padding: 20px; overflow-y: auto; }}
    .card-center {{ background: {COR_CARD}; color: {COR_TEXTO}; padding: 30px; border-radius: 15px; width: 100%; max-width: 650px; text-align: center; box-shadow: 0 12px 40px rgba(0,0,0,0.9); margin: auto; border: 1px solid {COR_BORDA}; }}
    .input-padrao {{ width: 100%; padding: 12px; margin: 8px 0; border: 1px solid {COR_BORDA}; border-radius: 5px; font-size: 16px; background: {COR_INPUT}; color: {COR_AMARELO}; font-weight: bold; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 14px; }}
    th, td {{ padding: 10px; border-bottom: 1px solid {COR_BORDA}; text-align: left; vertical-align: middle; }}
    th {{ color: {COR_AMARELO}; text-transform: uppercase; }}
    .logo-peq {{ width: 220px; max-width: 100%; height: auto; margin-bottom: 15px; border-radius: 8px; mix-blend-mode: screen; }}
    .grid-dash {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; width: 100%; margin-bottom: 20px; }} 
    .card-kpi {{ background: {COR_INPUT}; padding: 20px; border-radius: 10px; border-left: 5px solid {COR_AMARELO}; border-top: 1px solid {COR_BORDA}; }} 
    .card-kpi p {{ margin: 10px 0 0; font-size: 28px; font-weight: bold; color: {COR_AMARELO}; }} 
    .chart-container {{ background: {COR_CARD}; padding: 25px; border-radius: 10px; width: 100%; margin-bottom:20px; text-align: left; border: 1px solid {COR_BORDA}; }} 
    .status-pendente {{ color: {COR_VERMELHO}; font-weight: bold; font-size:12px; }}
    .status-analise {{ color: #f59e0b; font-weight: bold; font-size:12px; }}
    .status-pago {{ color: #10b981; font-weight: bold; font-size:12px; }}
    .checkbox-grid label {{ color: #FFF; font-size: 13px; cursor: pointer; display: flex; align-items: center; gap: 5px; }}
    .checkbox-grid input {{ cursor: pointer; transform: scale(1.2); }}
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
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'>{IMG_LOGO_PEQ}<h2>Sistema JPMS - Steel Goose</h2><form action='/login' method='post'><input class='input-padrao' name='user' placeholder='Usuário' required><input class='input-padrao' name='pw' type='password' placeholder='Senha' required><button class='btn-acao' style='padding:15px; font-size:18px; margin-top: 15px;'>ENTRAR NO SISTEMA</button></form><div style='margin-top:15px; margin-bottom:5px;'><a href='/esqueci_senha' style='color:#888; font-size:14px; text-decoration:none;'>Esqueci minha senha</a></div><hr style='border: 0; border-top: 1px dashed {COR_BORDA}; margin: 20px 0;'><a href='/cadastro' class='btn-acao btn-dark' style='text-decoration:none;'>SOLICITAR ACESSO (CADASTRO)</a></div></div></body></html>"

@app.get("/esqueci_senha", response_class=HTMLResponse)
async def esqueci_senha_tela():
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'>{IMG_LOGO_PEQ}<h2>RECUPERAR SENHA</h2><p style='color:#888; font-size:14px;'>Digite o e-mail vinculado à sua conta.</p><form action='/recuperar_senha' method='post' style='text-align:left;'><input class='input-padrao' name='email' type='email' placeholder='Seu e-mail cadastrado' required autocomplete='off'><button class='btn-acao' style='padding:15px; font-size:16px; margin-top: 20px;'>ENVIAR NOVA SENHA</button></form><a href='/' style='color:{COR_AMARELO}; font-size:14px; text-decoration:none;'>⬅️ Voltar ao Login</a></div></div></body></html>"

@app.post("/recuperar_senha")
async def recuperar_senha(email: str = Form(...)):
    email_limpo = email.strip().lower()
    nova_senha = str(random.randint(100000, 999999))
    with engine.begin() as conn:
        user = conn.execute(text("SELECT id FROM usuarios WHERE email = :e"), {"e": email_limpo}).mappings().fetchone()
        if not user:
            return HTMLResponse(f"<script>alert('E-mail não encontrado no sistema!'); window.location.href='/esqueci_senha';</script>")
        conn.execute(text("UPDATE usuarios SET password = :p WHERE id = :id"), {"p": nova_senha, "id": user['id']})
    enviar_email_recuperacao(email_limpo, nova_senha)
    return HTMLResponse("<script>alert('Sua nova senha provisória foi enviada para o seu e-mail (verifique o spam).'); window.location.href='/';</script>")

@app.get("/cadastro", response_class=HTMLResponse)
async def tela_cadastro(): return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'>{IMG_LOGO_PEQ}<h2>CADASTRO DE INTEGRANTE</h2><p style='color:#888; font-size:14px;'>Seu acesso passará por aprovação da Diretoria.</p><form action='/registrar' method='post' style='text-align:left;'><input class='input-padrao' name='u' placeholder='Login' required autocomplete='off'><input class='input-padrao' name='e' type='email' placeholder='E-mail' required autocomplete='off'><input class='input-padrao' name='p' type='password' placeholder='Senha' required><button class='btn-acao' style='padding:15px; font-size:18px; margin-top: 20px;'>ENVIAR SOLICITAÇÃO</button></form><a href='/' style='color:{COR_AMARELO}; font-size:14px; text-decoration:none;'>⬅️ Voltar ao Login</a></div></div></body></html>"

@app.post("/registrar")
async def registrar(u: str = Form(...), e: str = Form(...), p: str = Form(...)):
    try:
        with engine.begin() as conn: conn.execute(text("INSERT INTO usuarios (username, email, password, role, status) VALUES (:u, :e, :p, 'membro', 'BLOQUEADO') ON CONFLICT (username) DO NOTHING"), {"u": u.strip().lower(), "e": e.strip().lower(), "p": p})
        return HTMLResponse("<script>alert('Cadastro realizado com sucesso! Aguarde a aprovação da Diretoria.'); window.location.href='/';</script>")
    except: return HTMLResponse(f"<script>alert('Erro: Usuário já existe.'); window.location.href='/cadastro';</script>")

@app.post("/login")
async def login(request: Request):
    f = await request.form()
    with engine.connect() as conn:
        user = conn.execute(text("SELECT username, role, status FROM usuarios WHERE username = :u AND password = :p"), {"u": f.get("user", "").strip().lower(), "p": f.get("pw", "")}).mappings().fetchone()
        if user:
            if user['status'] == 'BLOQUEADO': return HTMLResponse("<script>alert('Acesso Bloqueado ou Pendente!'); window.location.href='/';</script>")
            request.session["user"], request.session["role"] = user['username'], user['role']
            return RedirectResponse(url="/central", status_code=303)
    return HTMLResponse("<script>alert('Acesso Negado! Verifique credenciais.'); window.location.href='/';</script>")

@app.get("/logout")
async def logout(request: Request): 
    request.session.clear()
    return RedirectResponse("/")

# ==========================================
# HUB CENTRAL E CONTROLE DE EXIBIÇÃO
# ==========================================
@app.get("/central", response_class=HTMLResponse)
async def central(request: Request):
    user, role = request.session.get("user"), request.session.get("role")
    if not user: return RedirectResponse(url="/")
    
    botoes = "<a href='/modulo/steelgoose' class='btn-acao btn-dark' style='padding:25px; font-size:16px;'>🦅 STEEL GOOSE</a>"
    
    if check_access(role, ["admin", "diretoria", "secretario"]):
        botoes += "<a href='/secretaria' class='btn-acao btn-dark' style='padding:25px; font-size:16px;'>🗄️ SECRETARIA</a>"
    else:
        botoes += "<a href='/secretaria/loja' class='btn-acao btn-dark' style='padding:25px; font-size:16px;'>🗄️ SECRETARIA (LOJA)</a>"
        
    if check_access(role, ["admin", "diretoria", "tesoureiro", "membro", "candidato"]):
        botoes += "<a href='/tesouraria' class='btn-acao btn-dark' style='padding:25px; font-size:16px;'>💰 TESOURARIA (CLUBE)</a>"
        
    if check_access(role, ["admin", "diretoria", "rp"]): 
        botoes += "<a href='/modulo/rp' class='btn-acao btn-dark' style='padding:25px; font-size:16px;'>📸 RELAÇÕES PÚBLICAS</a>"
        
    if check_access(role, ["admin", "diretoria"]): 
        botoes += "<a href='/diretoria' class='btn-acao btn-red' style='padding:25px; font-size:16px;'>👔 DIRETORIA</a>"
        
    botoes += "<a href='/modulo/ouvidoria' class='btn-acao btn-dark' style='padding:25px; font-size:16px;'>📢 OUVIDORIA</a>"
    
    if check_access(role, ["admin", "diretoria", "old_goose", "caixa", "tesoureiro"]): 
        botoes += "<a href='/oldgoose' class='btn-acao' style='padding:25px; font-size:16px; grid-column: 1 / -1; box-shadow: 0 0 15px rgba(243, 186, 22, 0.2);'>🦉 OLD GOOSE (BAR)</a>"
        
    botoes_grid = f"<div style='display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:15px; margin-top:20px;'>{botoes}</div>"
    role_display = role.replace(',', ' | ').upper()
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center' style='max-width:850px;'>{IMG_LOGO_PEQ}<p style='color:#888;'>Operador: <b style='color:{COR_AMARELO};'>{user.upper()}</b><br><small style='color:#666;'>Cargos: {role_display}</small></p>{botoes_grid}<br><a href='/logout' style='color:#C82828; font-weight:bold; text-decoration:none;'>[ SAIR DO SISTEMA ]</a></div></div></body></html>"

@app.get("/modulo/{nome}", response_class=HTMLResponse)
async def modulo_em_construcao(request: Request, nome: str):
    if not request.session.get("user"): return RedirectResponse("/")
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'>{IMG_LOGO_PEQ}<h2>Módulo {nome.capitalize()}</h2><p style='color:#888; font-size:18px; margin: 40px 0;'>🚧 Área em Construção 🚧</p><a href='/central' class='btn-acao btn-dark' style='width:250px; margin:auto;'>⬅️ VOLTAR AO MENU</a></div></div></body></html>"

# ==========================================
# MÓDULO SECRETARIA (CONTROLE E LOJA)
# ==========================================
@app.get("/secretaria", response_class=HTMLResponse)
async def menu_secretaria(request: Request):
    user, role = request.session.get("user"), request.session.get("role")
    if not check_access(role, ["admin", "diretoria", "secretario"]): return RedirectResponse("/secretaria/loja")
    
    linhas_itens = ""
    with engine.connect() as conn:
        itens_db = conn.execute(text("SELECT id, codigo, descricao, preco, estoque FROM secretaria_itens ORDER BY descricao")).mappings().fetchall()
        for r in itens_db:
            btn = f"<form action='/secretaria/excluir' method='post' style='margin:0;' onsubmit='return confirm(\"Excluir item?\");'><input type='hidden' name='id' value='{r['id']}'><button class='btn-acao btn-red' style='padding:5px; margin:0;'>🗑️</button></form>"
            linhas_itens += f"<tr><td><b style='color:#FFF;'>{r['descricao']}</b><br><small style='color:#888;'>Cód: {r['codigo']}</small></td><td style='color:{COR_AMARELO};'>R$ {float(r['preco'] or 0):.2f}</td><td style='text-align:center;'>{int(r['estoque'] or 0)} un</td><td>{btn}</td></tr>"
            
    painel_admin = f"<div style='background:{COR_INPUT}; padding:20px; border-radius:10px; margin-bottom:20px; border:1px solid {COR_BORDA};'><h3>➕ ADICIONAR MATERIAL</h3><form action='/secretaria/novo_item' method='post' style='display:flex; flex-wrap:wrap; gap:10px;'><input name='descricao' placeholder='Descrição (Ex: Camisa Oficial)' class='input-padrao' style='flex:2;' required><input name='preco' placeholder='Valor R$' step='0.01' type='number' class='input-padrao' style='width:120px;' required><input name='estoque' type='number' placeholder='Qtd' class='input-padrao' style='width:100px;' required><button class='btn-acao' style='width:100%;'>SALVAR ITEM</button></form></div>"
        
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center' style='max-width:800px;'>{IMG_LOGO_PEQ}<h2>🗄️ SECRETARIA (Controle)</h2>{painel_admin}<div style='max-height:400px; overflow-y:auto; border:1px solid {COR_BORDA};'><table><tr><th>Item</th><th>Preço</th><th style='text-align:center;'>Estoque</th><th>Ações</th></tr>{linhas_itens if linhas_itens else '<tr><td colspan=4 style=text-align:center;color:#777>Nenhum item cadastrado.</td></tr>'}</table></div><br><a href='/central' class='btn-acao btn-dark' style='width:250px; margin:auto;'>⬅️ Voltar ao Menu</a></div></div></body></html>"

@app.get("/secretaria/loja", response_class=HTMLResponse)
async def secretaria_loja(request: Request):
    if not request.session.get("user"): return RedirectResponse("/")
    linhas_itens = ""
    with engine.connect() as conn:
        itens_db = conn.execute(text("SELECT id, codigo, descricao, preco, estoque FROM secretaria_itens ORDER BY descricao")).mappings().fetchall()
        for r in itens_db:
            estoque = int(r['estoque'] or 0)
            btn = f"<form action='/secretaria/solicitar' method='post' style='margin:0;'><input type='hidden' name='id' value='{r['id']}'><button class='btn-acao' style='padding:5px; margin:0; font-size:12px;' {'disabled' if estoque <= 0 else ''}>{'SOLICITAR' if estoque > 0 else 'ESGOTADO'}</button></form>"
            linhas_itens += f"<tr><td><b style='color:#FFF;'>{r['descricao']}</b></td><td style='color:{COR_AMARELO};'>R$ {float(r['preco'] or 0):.2f}</td><td>{btn}</td></tr>"
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center' style='max-width:800px;'>{IMG_LOGO_PEQ}<h2>🛒 SOLICITAÇÃO DE MATERIAIS</h2><p style='color:#888; font-size:14px;'>Ao solicitar, a pendência será lançada na sua Tesouraria.</p><div style='max-height:400px; overflow-y:auto; border:1px solid {COR_BORDA}; margin-top:20px;'><table><tr><th>Item Disponível</th><th>Preço</th><th>Ação</th></tr>{linhas_itens if linhas_itens else '<tr><td colspan=3 style=text-align:center;color:#777>Nenhum item disponível na lojinha.</td></tr>'}</table></div><br><a href='/central' class='btn-acao btn-dark' style='width:250px; margin:auto;'>⬅️ Voltar ao Menu</a></div></div></body></html>"

@app.post("/secretaria/novo_item")
async def sec_novo_item(request: Request, descricao: str = Form(...), preco: float = Form(...), estoque: int = Form(...)):
    if not check_access(request.session.get("role"), ["admin", "diretoria", "secretario"]): return RedirectResponse("/secretaria")
    codigo = "SEC-" + datetime.now().strftime("%Y%m%d%H%M%S")
    with engine.begin() as conn: conn.execute(text("INSERT INTO secretaria_itens (codigo, descricao, preco, estoque) VALUES (:c, :d, :p, :e)"), {"c": codigo, "d": descricao.upper(), "p": preco, "e": estoque})
    return RedirectResponse(url="/secretaria", status_code=303)

@app.post("/secretaria/excluir")
async def sec_excluir(request: Request, id: int = Form(...)):
    if not check_access(request.session.get("role"), ["admin", "diretoria", "secretario"]): return RedirectResponse("/secretaria")
    with engine.begin() as conn: conn.execute(text("DELETE FROM secretaria_itens WHERE id = :id"), {"id": id})
    return RedirectResponse(url="/secretaria", status_code=303)

@app.post("/secretaria/solicitar")
async def sec_solicitar(request: Request, id: int = Form(...)):
    user = request.session.get("user")
    if not user: return RedirectResponse("/")
    with engine.begin() as conn:
        item = conn.execute(text("SELECT descricao, preco, estoque FROM secretaria_itens WHERE id = :id"), {"id": id}).mappings().fetchone()
        if item and item['estoque'] > 0:
            conn.execute(text("INSERT INTO pedidos_secretaria (username, item_nome, quantidade, valor_total, status) VALUES (:u, :n, 1, :v, 'PENDENTE')"), {"u": user, "n": item['descricao'], "v": item['preco']})
            conn.execute(text("UPDATE secretaria_itens SET estoque = estoque - 1 WHERE id = :id"), {"id": id})
    return HTMLResponse("<script>alert('Solicitação enviada com sucesso! Acesse a Tesouraria para realizar o pagamento.'); window.location.href='/tesouraria';</script>")

# ==========================================
# MÓDULO TESOURARIA (CAIXINHAS E PENDÊNCIAS)
# ==========================================
@app.get("/tesouraria", response_class=HTMLResponse)
async def menu_tesouraria(request: Request):
    user, role = request.session.get("user"), request.session.get("role")
    if not user: return RedirectResponse("/")
    
    mes_atual = datetime.now().strftime("%m/%Y")
    with engine.begin() as conn:
        existe_caixinha = conn.execute(text("SELECT id FROM caixinha WHERE username = :u AND mes_ano = :m"), {"u": user, "m": mes_atual}).mappings().fetchone()
        if not existe_caixinha: conn.execute(text("INSERT INTO caixinha (username, mes_ano, valor, status) VALUES (:u, :m, 50.00, 'PENDENTE')"), {"u": user, "m": mes_atual})
        minhas_caixinhas = conn.execute(text("SELECT id, mes_ano, valor, status FROM caixinha WHERE username = :u ORDER BY id DESC"), {"u": user}).mappings().fetchall()
        minhas_pendencias = conn.execute(text("SELECT id, item_nome, valor_total, status, data_pedido FROM pedidos_secretaria WHERE username = :u ORDER BY id DESC"), {"u": user}).mappings().fetchall()
        
    linhas_caixa = ""
    for c in minhas_caixinhas:
        cls_status = "status-pendente" if c['status'] == 'PENDENTE' else "status-analise" if c['status'] == 'EM ANÁLISE' else "status-pago"
        btn = f"<button class='btn-acao' style='padding:5px; font-size:12px; margin:0;' onclick='abrirModalPgto(\"caixinha\", {c['id']}, {float(c['valor'] or 0)})'>PAGAR</button>" if c['status'] == 'PENDENTE' else ""
        linhas_caixa += f"<tr><td><b style='color:#FFF;'>{c['mes_ano']}</b></td><td style='color:{COR_AMARELO};'>R$ {float(c['valor'] or 0):.2f}</td><td class='{cls_status}'>{c['status']}</td><td>{btn}</td></tr>"

    linhas_pend = ""
    for p in minhas_pendencias:
        cls_status = "status-pendente" if p['status'] == 'PENDENTE' else "status-analise" if p['status'] == 'EM ANÁLISE' else "status-pago"
        data_formatada = p['data_pedido'].strftime('%d/%m') if hasattr(p['data_pedido'], 'strftime') else str(p['data_pedido'])
        btn = f"<button class='btn-acao' style='padding:5px; font-size:12px; margin:0;' onclick='abrirModalPgto(\"pedido\", {p['id']}, {float(p['valor_total'] or 0)})'>PAGAR</button>" if p['status'] == 'PENDENTE' else ""
        linhas_pend += f"<tr><td><b style='color:#FFF;'>{p['item_nome']}</b><br><small style='color:#888;'>{data_formatada}</small></td><td style='color:{COR_AMARELO};'>R$ {float(p['valor_total'] or 0):.2f}</td><td class='{cls_status}'>{p['status']}</td><td>{btn}</td></tr>"

    painel_admin = ""
    if check_access(role, ["admin", "diretoria", "tesoureiro"]):
        painel_admin = f"<div style='margin-bottom:20px; display:flex; flex-wrap:wrap; gap:10px;'><a href='/tesouraria/aprovar' class='btn-acao btn-green' style='margin:0;'>✅ APROVAR PAGAMENTOS</a><a href='/tesouraria/relatorio' class='btn-acao btn-dark' style='margin:0;'>📊 RELATÓRIO FINANCEIRO DA FACÇÃO</a></div>"

    modal_pgto = f"""
    <div id='pgtoModal' style='display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index:1000; align-items:center; justify-content:center;'>
        <div class='card-center' style='position:relative; width:90%; max-width:400px; padding:20px; background:#121214; border:1px solid {COR_BORDA};'>
            <span onclick='document.getElementById(\"pgtoModal\").style.display=\"none\"' style='position:absolute; top:10px; right:15px; cursor:pointer; font-size:24px; color:#FFF;'>&times;</span>
            <h3 style='margin-top:0; color:{COR_AMARELO};'>📲 PAGAMENTO PIX</h3>
            <p style='color:#AAA; font-size:14px; margin-bottom:10px;'>Valor a pagar: <b id='modal_valor' style='color:#FFF; font-size:20px;'></b></p>
            <div style='background:#FFF; padding:10px; border-radius:10px; display:inline-block; margin-bottom:15px;'>
                <img src='https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=00020101021126580014br.gov.bcb.pix0136123456780001995204000053039995802BR5913Steel%20Goose6008Brasilia62070503***63041234' width='150'>
            </div>
            <p style='color:#10b981; font-weight:bold; font-size:12px; margin-top:0;'>CHAVE CNPJ: 12.345.678/0001-99</p>
            <hr style='border:0; border-top:1px dashed {COR_BORDA}; margin:15px 0;'>
            <form action='/tesouraria/enviar_comprovante' method='post' enctype='multipart/form-data' style='display:flex; flex-direction:column; gap:10px;'>
                <input type='hidden' name='tipo' id='modal_tipo'>
                <input type='hidden' name='id_ref' id='modal_id'>
                <label style='font-size:12px; color:#aaa; font-weight:bold; text-align:left;'>ANEXAR COMPROVANTE (IMAGEM/PDF):</label>
                <input type='file' name='arquivo' class='input-padrao' required style='background:#000;'>
                <button class='btn-acao' style='margin-top:10px;'>ENVIAR PARA APROVAÇÃO</button>
            </form>
        </div>
    </div>
    <script>function abrirModalPgto(tipo, id, valor) {{ document.getElementById('modal_tipo').value = tipo; document.getElementById('modal_id').value = id; document.getElementById('modal_valor').innerText = 'R$ ' + valor.toFixed(2); document.getElementById('pgtoModal').style.display = 'flex'; }}</script>
    """
    return f"<html><head>{CSS}</head><body>{modal_pgto}<div class='container-center'><div class='card-center' style='max-width:850px;'>{IMG_LOGO_PEQ}<h2>💰 MINHA TESOURARIA</h2>{painel_admin}<div style='text-align:left;'><h3>💵 Caixinha Mensal</h3><div style='max-height:200px; overflow-y:auto; border:1px solid {COR_BORDA}; margin-bottom:20px;'><table><tr><th>Mês</th><th>Valor</th><th>Status</th><th>Ação</th></tr>{linhas_caixa}</table></div><h3>🛒 Pendências (Materiais e Loja)</h3><div style='max-height:200px; overflow-y:auto; border:1px solid {COR_BORDA};'><table><tr><th>Item</th><th>Valor</th><th>Status</th><th>Ação</th></tr>{linhas_pend if linhas_pend else '<tr><td colspan=4 style=text-align:center;color:#777>Nenhuma pendência.</td></tr>'}</table></div></div><br><a href='/central' class='btn-acao btn-dark' style='width:250px; margin:auto;'>⬅️ Voltar ao Menu</a></div></div></body></html>"

@app.post("/tesouraria/enviar_comprovante")
async def enviar_comprovante(tipo: str = Form(...), id_ref: int = Form(...), arquivo: UploadFile = File(...)):
    filename = f"comp_{tipo}_{id_ref}_{datetime.now().strftime('%f')}.jpg"
    with open(os.path.join(UPLOAD_DIR, filename), "wb") as buffer: shutil.copyfileobj(arquivo.file, buffer)
    try:
        with engine.begin() as conn:
            if tipo == "caixinha": conn.execute(text("UPDATE caixinha SET status='EM ANÁLISE', comprovante=:f WHERE id=:id"), {"f": filename, "id": id_ref})
            elif tipo == "pedido": conn.execute(text("UPDATE pedidos_secretaria SET status='EM ANÁLISE', comprovante=:f WHERE id=:id"), {"f": filename, "id": id_ref})
    except: pass
    return HTMLResponse("<script>alert('Comprovante enviado com sucesso! Aguarde a Tesouraria confirmar.'); window.location.href='/tesouraria';</script>")

@app.get("/tesouraria/aprovar", response_class=HTMLResponse)
async def tesouraria_aprovar(request: Request):
    if not check_access(request.session.get("role"), ["admin", "diretoria", "tesoureiro"]): return RedirectResponse("/central")
    linhas = ""
    with engine.connect() as conn:
        cx = conn.execute(text("SELECT id, username, mes_ano as ref, valor, comprovante, 'caixinha' as tipo FROM caixinha WHERE status='EM ANÁLISE'")).mappings().fetchall()
        pd = conn.execute(text("SELECT id, username, item_nome as ref, valor_total as valor, comprovante, 'pedido' as tipo FROM pedidos_secretaria WHERE status='EM ANÁLISE'")).mappings().fetchall()
        for r in cx + pd:
            btn_ap = f"<form action='/tesouraria/processar' method='post' style='margin:0;'><input type='hidden' name='t' value='{r['tipo']}'><input type='hidden' name='i' value='{r['id']}'><input type='hidden' name='st' value='PAGO'><button class='btn-acao btn-green' style='padding:5px; margin:0;'>✔️ APROVAR</button></form>"
            btn_re = f"<form action='/tesouraria/processar' method='post' style='margin:0;'><input type='hidden' name='t' value='{r['tipo']}'><input type='hidden' name='i' value='{r['id']}'><input type='hidden' name='st' value='PENDENTE'><button class='btn-acao btn-red' style='padding:5px; margin:0;'>❌ RECUSAR</button></form>"
            linhas += f"<tr><td><b style='color:#FFF; text-transform:uppercase;'>{r['username']}</b><br><small style='color:#888;'>{r['tipo'].upper()} - {r['ref']}</small></td><td style='color:{COR_AMARELO};'>R$ {float(r['valor'] or 0):.2f}</td><td><a href='/comprovantes/{r['comprovante']}' target='_blank' style='color:#0ea5e9; text-decoration:none; font-weight:bold;'>Ver Anexo 👁️</a></td><td><div style='display:flex;gap:5px;'>{btn_ap}{btn_re}</div></td></tr>"
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center' style='max-width:850px;'>{IMG_LOGO_PEQ}<h2>✅ Aprovar Pagamentos</h2><div style='max-height:400px; overflow-y:auto; border:1px solid {COR_BORDA};'><table><tr><th>Membro / Ref</th><th>Valor</th><th>Comprovante</th><th>Ações</th></tr>{linhas if linhas else '<tr><td colspan=4 style=text-align:center;color:#777>Nenhum pagamento pendente de análise.</td></tr>'}</table></div><br><a href='/tesouraria' class='btn-acao btn-dark' style='width:200px; margin:auto;'>⬅️ Voltar</a></div></div></body></html>"

@app.get("/comprovantes/{filename}")
async def ver_comprovante(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path): return FileResponse(file_path)
    return Response(status_code=404)

@app.post("/tesouraria/processar")
async def tesouraria_processar(request: Request, t: str = Form(...), i: int = Form(...), st: str = Form(...)):
    if not check_access(request.session.get("role"), ["admin", "diretoria", "tesoureiro"]): return RedirectResponse("/central")
    try:
        with engine.begin() as conn:
            if t == "caixinha": conn.execute(text("UPDATE caixinha SET status=:s WHERE id=:id"), {"s": st, "id": i})
            elif t == "pedido": conn.execute(text("UPDATE pedidos_secretaria SET status=:s WHERE id=:id"), {"s": st, "id": i})
    except: pass
    return RedirectResponse("/tesouraria/aprovar", status_code=303)

@app.get("/tesouraria/relatorio", response_class=HTMLResponse)
async def relatorio_geral(request: Request):
    if not check_access(request.session.get("role"), ["admin", "diretoria", "tesoureiro"]): return RedirectResponse("/central")
    with engine.connect() as conn:
        f_bar_val = conn.execute(text("SELECT SUM(total_conta) FROM comandas WHERE status = 'FECHADA'")).scalar() or 0.0
        f_cx_val = conn.execute(text("SELECT SUM(valor) FROM caixinha WHERE status = 'PAGO'")).scalar() or 0.0
        f_sec_val = conn.execute(text("SELECT SUM(valor_total) FROM pedidos_secretaria WHERE status = 'PAGO'")).scalar() or 0.0
        tot_entradas = f_bar_val + f_cx_val + f_sec_val
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center' style='max-width:800px;'>{IMG_LOGO_PEQ}<h2>📊 RELATÓRIO GERAL (FACÇÃO)</h2><div class='grid-dash'><div class='card-kpi' style='border-left-color:#10b981;'><h3>Total de Entradas (Líquido)</h3><p style='color:#10b981;'>R$ {tot_entradas:.2f}</p></div></div><div style='display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px; margin-bottom:20px;'><div style='background:#111; padding:15px; border-radius:8px; border-left:4px solid {COR_AMARELO}; flex:1;'><b>🍺 OLD GOOSE (BAR):</b><br><span style='color:#FFF; font-size:18px;'>R$ {f_bar_val:.2f}</span></div><div style='background:#111; padding:15px; border-radius:8px; border-left:4px solid {COR_AMARELO}; flex:1;'><b>💵 CAIXINHAS PAGAS:</b><br><span style='color:#FFF; font-size:18px;'>R$ {f_cx_val:.2f}</span></div><div style='background:#111; padding:15px; border-radius:8px; border-left:4px solid {COR_AMARELO}; flex:1;'><b>👕 MATERIAIS (SECRETARIA):</b><br><span style='color:#FFF; font-size:18px;'>R$ {f_sec_val:.2f}</span></div></div><br><a href='/tesouraria' class='btn-acao btn-dark' style='width:250px; margin:auto;'>⬅️ Voltar à Tesouraria</a></div></div></body></html>"

# ==========================================
# OLD GOOSE (BAR / PDV / ESTOQUE)
# ==========================================
@app.get("/oldgoose", response_class=HTMLResponse)
async def menu_oldgoose(request: Request):
    role = request.session.get("role")
    if not check_access(role, ["admin", "diretoria", "old_goose", "caixa", "tesoureiro"]): return RedirectResponse("/central")
    botoes = "<a href='/pdv' class='btn-acao' style='font-size: 18px; padding: 20px;'>🛒 PAINEL DE VENDAS (COMANDAS)</a>"
    if check_access(role, ["admin", "diretoria", "old_goose", "tesoureiro"]):
        botoes += "<a href='/estoque' class='btn-acao btn-dark' style='font-size: 18px; padding: 20px;'>📦 GESTÃO DE ESTOQUE E COMPRAS</a>"
        botoes += "<a href='/dashboard' class='btn-acao btn-red' style='font-size: 18px; padding: 20px;'>📊 RELATÓRIOS DO BAR</a>"
    botoes += "<a href='/baixar_conector' class='btn-acao btn-dark' style='padding: 15px;'>🖨️ BAIXAR CONECTOR DE IMPRESSORA</a>"
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'>{IMG_LOGO_PEQ}<h2>🦉 MÓDULO OLD GOOSE (BAR)</h2><div style='display:flex; flex-direction:column; gap:12px; margin-top:20px;'>{botoes}</div><br><a href='/central' style='color:#777; text-decoration:none;'>⬅️ Voltar ao Hub Central</a></div></div></body></html>"

@app.get("/diretoria", response_class=HTMLResponse)
async def menu_diretoria(request: Request):
    role = request.session.get("role")
    if not check_access(role, ["admin", "diretoria"]): return RedirectResponse("/central")
    botoes = "<a href='/usuarios' class='btn-acao' style='font-size: 18px; padding: 20px;'>👥 CONTROLE DE MEMBROS E ACESSOS</a>"
    if check_access(role, ["admin"]): botoes += "<a href='/config_fiscal' class='btn-acao btn-dark' style='padding: 20px;'>⚙️ CONFIGURAÇÕES FISCAIS (NFC-e)</a>"
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'>{IMG_LOGO_PEQ}<h2>👔 MÓDULO DIRETORIA</h2><div style='display:flex; flex-direction:column; gap:12px; margin-top:20px;'>{botoes}</div><br><a href='/central' style='color:#777; text-decoration:none;'>⬅️ Voltar ao Hub Central</a></div></div></body></html>"

@app.get("/pdv", response_class=HTMLResponse)
async def pdv_painel(request: Request):
    if not check_access(request.session.get("role"), ["admin", "diretoria", "old_goose", "caixa", "tesoureiro"]): return RedirectResponse("/central")
    linhas_comandas = ""
    with engine.connect() as conn:
        comandas_abertas = conn.execute(text("SELECT numero_comanda, total_conta FROM comandas WHERE status = 'ABERTA' ORDER BY id DESC")).mappings().fetchall()
        for c in comandas_abertas: 
            linhas_comandas += f"<div class='card-comanda-item' data-nome='{c['numero_comanda']}' style='background:{COR_INPUT}; border:1px solid {COR_BORDA}; border-radius:8px; padding:15px; display:flex; justify-content:space-between; align-items:center;'><div><span style='font-size:18px; font-weight:bold; color:{COR_AMARELO};'>📋 {c['numero_comanda'].upper()}</span><br><small style='color:#888;'>Consumo Parcial</small></div><div style='text-align:right;'><span style='font-size:20px; font-weight:bold; color:#FFF;'>R$ {float(c['total_conta'] or 0):.2f}</span><br><a href='/pdv/comanda/{urllib.parse.quote(c['numero_comanda'])}' class='btn-acao' style='padding:5px 12px; margin:5px 0 0 0; font-size:12px; display:inline-block; width:auto;'>Lançar / Fechar</a></div></div>"
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
    if not check_access(request.session.get("role"), ["admin", "diretoria", "old_goose", "caixa", "tesoureiro"]): return RedirectResponse("/central")
    with engine.connect() as conn:
        comanda = conn.execute(text("SELECT numero_comanda, total_conta FROM comandas WHERE numero_comanda = :c AND status = 'ABERTA' ORDER BY id DESC LIMIT 1"), {"c": numero_comanda}).mappings().fetchone()
        if not comanda: return RedirectResponse("/pdv")
        
        itens_lançados = conn.execute(text("SELECT id, item_nome, valor FROM vendas_itens WHERE comanda_num = :c AND status = 'ABERTA' ORDER BY id DESC"), {"c": numero_comanda}).mappings().fetchall()
        html_itens = "".join([f"<div style='display:flex; justify-content:space-between; padding:10px; border-bottom:1px dashed {COR_BORDA}; color:#FFF; align-items:center;'><span>{it['item_nome']}</span><span>R$ {float(it['valor'] or 0):.2f} <form action='/pdv/remover_item' method='post' style='display:inline; margin-left:15px;'><input type='hidden' name='item_id' value='{it['id']}'><input type='hidden' name='num_comanda' value='{numero_comanda}'><button style='background:none; border:none; color:{COR_VERMELHO}; cursor:pointer; font-size:18px;' title='Estornar Item'>☒</button></form></span></div>" for it in itens_lançados])
        
        produtos_db = conn.execute(text("SELECT id, nome, preco, estoque FROM produtos ORDER BY nome")).mappings().fetchall()
        html_produtos = ""
        for p in produtos_db:
            if p['estoque'] > 0: html_produtos += f"<div class='card-produto' onclick='adicionarItem({p['id']})'><span style='font-weight:bold; color:{COR_AMARELO}; display:block; font-size:15px;'>{p['nome'].upper()}</span><span style='color:#FFF; font-weight:bold; font-size:14px; display:block; margin-top:5px;'>R$ {float(p['preco'] or 0):.2f}</span><span class='badge-estoque'>Estoque: {int(p['estoque'])} un</span></div>"
            else: html_produtos += f"<div class='card-produto' style='border-color:{COR_VERMELHO}; opacity:0.6; cursor:not-allowed;'><span style='font-weight:bold; color:{COR_VERMELHO}; display:block; font-size:15px; text-decoration: line-through;'>{p['nome'].upper()}</span><span style='color:#FFF; font-weight:bold; font-size:14px; display:block; margin-top:5px;'>R$ {float(p['preco'] or 0):.2f}</span><span class='badge-estoque' style='color:{COR_VERMELHO}; font-weight:bold;'>ESGOTADO</span></div>"

    js_inject = f"<script>function adicionarItem(prodId) {{ let form = document.createElement('form'); form.method = 'POST'; form.action = '/pdv/adicionar_item'; form.innerHTML = `<input type='hidden' name='comanda_num' value='{numero_comanda}'><input type='hidden' name='produto_id' value='${{prodId}}'>`; document.body.appendChild(form); form.submit(); }}</script>"
    return f"<html><head>{CSS}{js_inject}</head><body style='background:{COR_FUNDO};'><div style='display:flex; height:100vh; width:100%; overflow:hidden;'><div style='flex:1.3; padding:20px; display:flex; flex-direction:column; background:{COR_CARD}; border-right:2px solid {COR_BORDA}; overflow-y:auto;'><h2>🍺 Itens do Bar</h2><div class='grid-produtos'>{html_produtos}</div></div><div style='flex:1; padding:20px; display:flex; flex-direction:column; justify-content:space-between; background:#080808; overflow-y:auto;'><div><h2 style='color:#FFF; margin-bottom:5px;'>📋 {comanda['numero_comanda'].upper()}</h2><div style='background:#000; border:1px solid {COR_BORDA}; border-radius:8px; padding:10px; margin-top:15px; max-height:220px; overflow-y:auto;'>{html_itens if html_itens else '<p style=\"color:#444; text-align:center;\">Nenhum item lançado ainda.</p>'}</div></div><div style='background:#111; padding:20px; border-radius:8px; margin-top:20px; border:1px solid {COR_BORDA};'><div style='color:#888; font-size:14px;'>TOTAL DA CONTA</div><div style='color:{COR_AMARELO}; font-size:40px; font-weight:bold; margin-bottom:15px;'>R$ {float(comanda['total_conta'] or 0):.2f}</div><form action='/pdv/finalizar_comanda' method='post'><input type='hidden' name='comanda_num' value='{comanda['numero_comanda']}'><select name='pagamento' class='input-padrao' style='font-size:16px; padding:12px; margin-bottom:12px;'><option value='01'>💵 DINHEIRO</option><option value='17'>💠 PIX</option><option value='03'>💳 CRÉDITO</option><option value='04'>💳 DÉBITO</option></select><button class='btn-acao' style='font-size:18px; padding:15px;'>🏁 FECHAR CONTA</button></form><a href='/pdv' class='btn-acao btn-dark' style='margin-top:5px; padding:10px; font-size:12px;'>⬅️ VOLTAR AO PAINEL</a></div></div></div></body></html>"

@app.post("/pdv/adicionar_item")
async def pdv_adicionar_item(comanda_num: str = Form(...), produto_id: int = Form(...)):
    with engine.begin() as conn:
        prod = conn.execute(text("SELECT nome, preco, estoque FROM produtos WHERE id = :id"), {"id": produto_id}).mappings().fetchone()
        if prod and prod['estoque'] > 0:
            conn.execute(text("INSERT INTO vendas_itens (comanda_num, item_nome, valor, status) VALUES (:c, :n, :v, 'ABERTA')"), {"c": comanda_num, "n": prod['nome'], "v": prod['preco']})
            conn.execute(text("UPDATE comandas SET total_conta = total_conta + :v WHERE numero_comanda = :c AND status = 'ABERTA'"), {"v": prod['preco'], "c": comanda_num})
            conn.execute(text("UPDATE produtos SET estoque = estoque - 1 WHERE id = :id"), {"id": produto_id})
    return RedirectResponse(url=f"/pdv/comanda/{urllib.parse.quote(comanda_num)}", status_code=303)

@app.post("/pdv/remover_item")
async def pdv_remover_item(item_id: int = Form(...), num_comanda: str = Form(...)):
    with engine.begin() as conn:
        item = conn.execute(text("SELECT item_nome, valor FROM vendas_itens WHERE id = :id AND status = 'ABERTA'"), {"id": item_id}).mappings().fetchone()
        if item:
            conn.execute(text("UPDATE comandas SET total_conta = GREATEST(total_conta - :v, 0.00) WHERE numero_comanda = :c AND status = 'ABERTA'"), {"v": item['valor'], "c": num_comanda})
            conn.execute(text("UPDATE vendas_itens SET status = 'ESTORNADO' WHERE id = :id"), {"id": item_id})
            conn.execute(text("UPDATE produtos SET estoque = estoque + 1 WHERE nome = :n"), {"n": item['item_nome']})
    return RedirectResponse(url=f"/pdv/comanda/{urllib.parse.quote(num_comanda)}", status_code=303)

@app.post("/pdv/finalizar_comanda")
async def finalizar_comanda(request: Request, comanda_num: str = Form(...), pagamento: str = Form(...)):
    nomes_pag = {"01": "DINHEIRO", "17": "PIX", "03": "C. CREDITO", "04": "C. DEBITO"}
    nome_pagamento = nomes_pag.get(pagamento, "OUTROS")
    usuario = request.session.get("user", "Caixa")
    with engine.begin() as conn:
        comanda = conn.execute(text("SELECT total_conta FROM comandas WHERE numero_comanda = :c AND status = 'ABERTA' ORDER BY id DESC LIMIT 1"), {"c": comanda_num}).mappings().fetchone()
        if not comanda: return RedirectResponse(url="/pdv", status_code=303)
        itens = conn.execute(text("SELECT item_nome, valor FROM vendas_itens WHERE comanda_num = :c AND status = 'ABERTA'"), {"c": comanda_num}).mappings().fetchall()
        
        conn.execute(text("UPDATE comandas SET status = 'FECHADA', forma_pagamento = :p, data_fechamento = CURRENT_TIMESTAMP WHERE numero_comanda = :c AND status = 'ABERTA'"), {"p": nome_pagamento, "c": comanda_num})
        conn.execute(text("UPDATE vendas_itens SET status = 'FECHADA' WHERE comanda_num = :c AND status = 'ABERTA'"), {"c": comanda_num})
        
        txt = f"--------------------------------\n   STEEL GOOSE MOTO GROUP\nPLANALTO-DF\n--------------------------------\nCOMANDA: {comanda_num.upper()}\nOPERADOR: {usuario.upper()}\nDATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n--------------------------------\n"
        for idx, item in enumerate(itens): txt += f"1x {item['item_nome'][:20]:<20} R$ {float(item['valor'] or 0):.2f}\n"
        txt += f"--------------------------------\nTOTAL: R$ {float(comanda['total_conta'] or 0):.2f}\nPAGTO: {nome_pagamento}\n Obrigado pela parceria! 🦅\n--------------------------------\n"
        conn.execute(text("INSERT INTO fila_impressao (conteudo) VALUES (:txt)"), {"txt": txt})
    return HTMLResponse(f"<script>alert('Conta {comanda_num} fechada!'); window.location.href='/pdv';</script>")

@app.get("/estoque", response_class=HTMLResponse)
async def tela_estoque(request: Request):
    if not check_access(request.session.get("role"), ["admin", "diretoria", "old_goose", "tesoureiro"]): return RedirectResponse("/central")
    linhas = ""
    with engine.connect() as conn:
        prods_db = conn.execute(text("SELECT id, nome, categoria, preco, estoque FROM produtos ORDER BY nome")).mappings().fetchall()
        for r in prods_db:
            n_seguro = r['nome'].replace('"', '').replace("'", "")
            acoes = f"<div style='display:flex; gap:5px;'><button type='button' class='btn-acao' style='padding:8px; margin:0; background:#10b981; color:#000;' onclick='abrirModalEntrada({r['id']}, \"{n_seguro}\")' title='Compra c/ NF'>➕</button><button type='button' class='btn-acao btn-dark' style='padding:8px; margin:0;' onclick='abrirModal({r['id']}, \"{n_seguro}\", \"{r['categoria']}\", {float(r['preco'] or 0)})' title='Editar'>✏️</button><form action='/excluir_produto' method='post' style='margin:0;' onsubmit='return confirm(\"Excluir item?\");'><input type='hidden' name='id' value='{r['id']}'><button class='btn-acao btn-red' style='padding:8px; margin:0;'>🗑️</button></form></div>"
            linhas += f"<tr><td style='color:#FFF; font-weight:bold;'>{r['nome'].upper()}</td><td style='color:{COR_AMARELO};'>R$ {float(r['preco'] or 0):.2f}</td><td style='color:#FFF; text-align:center;'>{int(r['estoque'] or 0)} un</td><td>{acoes}</td></tr>"
            
    add_form = f"<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;'><h3>📦 Produtos</h3><a href='/historico_compras' class='btn-acao btn-dark' style='width:auto; margin:0; padding:10px 15px; font-size:12px;'>📜 HISTÓRICO DE COMPRAS</a></div><div style='background:#0A0A0A; padding:20px; border-radius:10px; margin-bottom:20px; border:1px solid {COR_BORDA};'><h3>➕ CADASTRAR PRODUTO NO BAR</h3><form action='/novo_produto' method='post' style='display:flex; flex-wrap:wrap; gap:10px;'><input name='nome' placeholder='Nome da Bebida' class='input-padrao' style='flex:2;' required><select name='cat' class='input-padrao' style='flex:1;'><option value='BEBIDAS'>BEBIDAS</option><option value='ALIMENTOS'>ALIMENTOS</option><option value='OUTROS'>OUTROS</option></select><input name='preco' placeholder='Preço de Venda' step='0.01' type='number' class='input-padrao' style='width:120px;' required><input name='qtd' type='number' placeholder='Qtd Estoque Inicial' class='input-padrao' style='width:150px;' required><button class='btn-acao' style='width:100%;'>SALVAR NO ESTOQUE</button></form></div>"
    modal_edit = f"<div id='editModal' style='display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:1000; align-items:center; justify-content:center;'><div class='card-center' style='position:relative; width:90%; max-width:400px; padding:20px; background:#121214;'><span onclick='document.getElementById(\"editModal\").style.display=\"none\"' style='position:absolute; top:10px; right:15px; cursor:pointer; font-size:24px; color:#FFF;'>&times;</span><h3 style='margin-top:0;'>✏️ EDITAR PRODUTO</h3><form action='/editar_produto' method='post' style='display:flex; flex-direction:column; gap:10px;'><input type='hidden' name='id' id='edit_id'><input name='nome' id='edit_nome' class='input-padrao' required><select name='cat' id='edit_cat' class='input-padrao' required><option value='BEBIDAS'>BEBIDAS</option><option value='ALIMENTOS'>ALIMENTOS</option><option value='OUTROS'>OUTROS</option></select><input name='preco' id='edit_preco' type='number' step='0.01' class='input-padrao' required><button class='btn-acao' style='margin-top:10px;'>SALVAR ALTERAÇÕES</button></form></div></div>"
    
    modal_entrada = f"""
    <div id='entradaModal' style='display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:1000; align-items:center; justify-content:center;'>
        <div class='card-center' style='position:relative; width:90%; max-width:400px; padding:20px; background:#121214; border:1px solid {COR_BORDA};'>
            <span onclick='document.getElementById(\"entradaModal\").style.display=\"none\"' style='position:absolute; top:10px; right:15px; cursor:pointer; font-size:24px; color:#FFF;'>&times;</span>
            <h3 style='margin-top:0; color:#10b981;'>📥 REGISTRAR COMPRA</h3>
            <form action='/att_estoque' method='post' enctype='multipart/form-data' style='display:flex; flex-direction:column; gap:10px;'>
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
                <div>
                    <label style='font-size:12px; color:#aaa; font-weight:bold;'>NOTA FISCAL (OPCIONAL - PDF/IMG):</label>
                    <input type='file' name='nf_arquivo' class='input-padrao' style='background:#000;'>
                </div>
                <button class='btn-acao' style='background:#10b981; margin-top:10px;'>SALVAR ENTRADA E NOTA</button>
            </form>
        </div>
    </div>
    """

    js_modal = "<script>function abrirModal(id, nome, cat, preco) { document.getElementById('edit_id').value = id; document.getElementById('edit_nome').value = nome; document.getElementById('edit_cat').value = cat; document.getElementById('edit_preco').value = preco; document.getElementById('editModal').style.display = 'flex'; } function abrirModalEntrada(id, nome) { document.getElementById('entrada_id').value = id; document.getElementById('entrada_nome').innerText = nome; document.getElementById('entradaModal').style.display = 'flex'; }</script>"
    return f"<html><head>{CSS}{js_modal}</head><body>{modal_edit}{modal_entrada}<div class='container-center'><div class='card-center' style='max-width:800px;'>{IMG_LOGO_PEQ}<h2>📦 Estoque</h2>{add_form}<div style='max-height:400px; overflow-y:auto; border:1px solid {COR_BORDA};'><table><tr><th>Produto</th><th>Preço</th><th>Qtd Atual</th><th>Ações</th></tr>{linhas}</table></div><br><a href='/oldgoose' class='btn-acao btn-dark' style='width:200px; margin:auto;'>⬅️ Voltar ao Old Goose</a></div></div></body></html>"

@app.post("/novo_produto")
async def novo_produto(request: Request):
    if not check_access(request.session.get("role"), ["admin", "diretoria", "old_goose", "tesoureiro"]): return RedirectResponse("/central")
    f = await request.form()
    try:
        with engine.begin() as conn: conn.execute(text("INSERT INTO produtos (codigo_barras, nome, categoria, preco, estoque) VALUES (:cb, :n, :c, :p, :q)"), {"cb": "SG-"+datetime.now().strftime("%f"), "n": f.get("nome").upper(), "c": f.get("cat"), "p": float(f.get("preco").replace(",", ".")), "q": int(f.get("qtd"))})
    except: pass
    return RedirectResponse(url="/estoque", status_code=303)

@app.post("/att_estoque")
async def att_estoque(request: Request):
    if not check_access(request.session.get("role"), ["admin", "diretoria", "old_goose", "tesoureiro"]): return RedirectResponse("/central")
    f = await request.form()
    prod_id = f.get("id")
    qtd = int(f.get("q", "0"))
    custo = float(f.get("custo", "0").replace(",", "."))
    nf_arquivo = f.get("nf_arquivo")
    
    filename = None
    if nf_arquivo and getattr(nf_arquivo, "filename", None):
        ext = nf_arquivo.filename.split(".")[-1]
        filename = f"nf_{prod_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
        with open(os.path.join(UPLOAD_DIR, filename), "wb") as buffer:
            shutil.copyfileobj(nf_arquivo.file, buffer)
            
    try:
        with engine.begin() as conn: 
            prod = conn.execute(text("SELECT nome FROM produtos WHERE id = :id"), {"id": prod_id}).mappings().fetchone()
            if prod:
                conn.execute(text("UPDATE produtos SET estoque = COALESCE(estoque, 0) + :q WHERE id = :id"), {"id": prod_id, "q": qtd})
                conn.execute(text("INSERT INTO historico_estoque (produto_nome, qtd_adicionada, valor_custo, data_entrada, nota_fiscal) VALUES (:n, :q, :c, CURRENT_DATE, :nf)"), {"n": prod['nome'], "q": qtd, "c": custo, "nf": filename})
    except Exception as e: print(e)
    return RedirectResponse(url="/estoque", status_code=303)

@app.get("/historico_compras", response_class=HTMLResponse)
async def historico_compras(request: Request):
    if not check_access(request.session.get("role"), ["admin", "diretoria", "old_goose", "tesoureiro"]): return RedirectResponse("/central")
    linhas = ""
    with engine.connect() as conn:
        hist = conn.execute(text("SELECT produto_nome, qtd_adicionada, valor_custo, data_entrada, nota_fiscal FROM historico_estoque ORDER BY id DESC LIMIT 100")).mappings().fetchall()
        for r in hist:
            qtd = int(r['qtd_adicionada'] or 0)
            custo_total = float(r['valor_custo'] or 0)
            custo_unit = custo_total / qtd if qtd > 0 else 0
            nf_link = f"<a href='/comprovantes/{r['nota_fiscal']}' target='_blank' style='color:#0ea5e9; font-weight:bold; text-decoration:none;'>Ver NF</a>" if r['nota_fiscal'] else "<span style='color:#555;'>-</span>"
            linhas += f"<tr><td style='color:#FFF; font-weight:bold;'>{r['produto_nome']}</td><td style='color:{COR_AMARELO}; text-align:center;'>{qtd}</td><td style='color:#FFF; text-align:right;'>R$ {custo_total:.2f}<br><small style='color:#888;'>R$ {custo_unit:.2f}/un</small></td><td style='color:#888; text-align:center;'>{r['data_entrada']}</td><td style='text-align:center;'>{nf_link}</td></tr>"
            
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center' style='max-width:900px;'>{IMG_LOGO_PEQ}<h2>📜 Histórico de Compras</h2><div style='max-height:500px; overflow-y:auto; border:1px solid {COR_BORDA};'><table><thead style='background:#0A0A0A; position:sticky; top:0;'><tr><th>Produto</th><th style='text-align:center;'>Qtd</th><th style='text-align:right;'>Custo Total</th><th style='text-align:center;'>Data</th><th style='text-align:center;'>Nota Fiscal</th></tr></thead><tbody>{linhas if linhas else '<tr><td colspan=\"5\" style=\"text-align:center; color:#777;\">Nenhum registro encontrado.</td></tr>'}</tbody></table></div><br><a href='/estoque' class='btn-acao btn-dark' style='width:200px; margin:auto;'>⬅️ Voltar ao Estoque</a></div></div></body></html>"

@app.post("/editar_produto")
async def editar_produto(request: Request):
    if not check_access(request.session.get("role"), ["admin", "diretoria", "old_goose", "tesoureiro"]): return RedirectResponse("/central")
    f = await request.form()
    try:
        with engine.begin() as conn: conn.execute(text("UPDATE produtos SET nome = :n, categoria = :c, preco = :p WHERE id = :id"), {"n": f.get("nome").upper(), "c": f.get("cat"), "p": float(f.get("preco").replace(",", ".")), "id": f.get("id")})
    except: pass
    return RedirectResponse(url="/estoque", status_code=303)

@app.post("/excluir_produto")
async def excluir_produto(request: Request):
    if not check_access(request.session.get("role"), ["admin", "diretoria", "old_goose", "tesoureiro"]): return RedirectResponse("/central")
    f = await request.form()
    try:
        with engine.begin() as conn: conn.execute(text("DELETE FROM produtos WHERE id = :id"), {"id": f.get("id")})
    except: pass
    return RedirectResponse(url="/estoque", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, inicio: str = "", fim: str = "", tipo_venda: str = "TODOS"):
    if not check_access(request.session.get("role"), ["admin", "diretoria", "old_goose", "tesoureiro"]): return RedirectResponse("/central")
    
    dt_inicio = inicio if inicio else date.today().strftime("%Y-%m-%d")
    dt_fim = fim if fim else date.today().strftime("%Y-%m-%d")
    
    where_clause = "status = 'FECHADA' AND CAST(data_fechamento AS DATE) BETWEEN CAST(:inicio AS DATE) AND CAST(:fim AS DATE)"
    params = {"inicio": dt_inicio, "fim": dt_fim}
    if tipo_venda and tipo_venda != "TODOS":
        where_clause += " AND forma_pagamento = :tipo"
        params["tipo"] = tipo_venda

    where_estorno = "status = 'ESTORNADO' AND CAST(data_venda AS DATE) BETWEEN CAST(:inicio AS DATE) AND CAST(:fim AS DATE)"
    
    with engine.connect() as conn:
        faturamento_filtrado = conn.execute(text(f"SELECT SUM(total_conta) FROM comandas WHERE {where_clause}"), params).scalar() or 0.0
        
        pag_q = conn.execute(text(f"SELECT forma_pagamento, SUM(total_conta) as total FROM comandas WHERE {where_clause} GROUP BY forma_pagamento"), params).mappings().fetchall()
        totais_pag = {"DINHEIRO": 0.0, "PIX": 0.0, "C. CREDITO": 0.0, "C. DEBITO": 0.0}
        for p in pag_q: 
            if p['forma_pagamento'] in totais_pag: totais_pag[p['forma_pagamento']] = float(p['total'] or 0)

        qtd_estornada = conn.execute(text(f"SELECT COUNT(*) FROM vendas_itens WHERE {where_estorno}"), {"inicio": dt_inicio, "fim": dt_fim}).scalar() or 0
        total_estornado = conn.execute(text(f"SELECT SUM(valor) FROM vendas_itens WHERE {where_estorno}"), {"inicio": dt_inicio, "fim": dt_fim}).scalar() or 0.0
            
        itens_db = conn.execute(text(f"SELECT item_nome, COUNT(*) as qtd, SUM(valor) as t FROM vendas_itens WHERE status = 'FECHADA' AND comanda_num IN (SELECT numero_comanda FROM comandas WHERE {where_clause}) GROUP BY item_nome ORDER BY COUNT(*) DESC"), params).mappings().fetchall()
        linhas_tabela = "".join([f"<tr><td style='color:#FFF; font-weight:bold;'>{it['item_nome']}</td><td style='color:{COR_AMARELO}; text-align:center;'>{it['qtd']}</td><td style='color:#FFF; text-align:right;'>R$ {float(it['t'] or 0):.2f}</td></tr>" for it in itens_db])

    opcoes_select = f"<option value='TODOS' {'selected' if tipo_venda == 'TODOS' else ''}>⚙️ TODOS OS TIPOS</option><option value='DINHEIRO' {'selected' if tipo_venda == 'DINHEIRO' else ''}>💵 DINHEIRO</option><option value='PIX' {'selected' if tipo_venda == 'PIX' else ''}>💠 PIX</option><option value='C. CREDITO' {'selected' if tipo_venda == 'C. CREDITO' else ''}>💳 CARTÃO CRÉDITO</option><option value='C. DEBITO' {'selected' if tipo_venda == 'C. DEBITO' else ''}>💳 CARTÃO DÉBITO</option>"
    
    return f"""<html><head>{CSS}</head><body><div class='container-center'><div class='card-center' style='max-width:850px;'>
        {IMG_LOGO_PEQ}<h2>📊 Relatório do Bar</h2>
        <form method='get' class='filtro-box'><div style='flex:1; min-width:140px;'><label>Data Inicial:</label><br><input type='date' name='inicio' value='{dt_inicio}' class='input-padrao' style='margin:5px 0 0 0; padding:8px;'></div><div style='flex:1; min-width:140px;'><label>Data Final:</label><br><input type='date' name='fim' value='{dt_fim}' class='input-padrao' style='margin:5px 0 0 0; padding:8px;'></div><div style='flex:1; min-width:160px;'><label>Tipo de Venda:</label><br><select name='tipo_venda' class='input-padrao' style='margin:5px 0 0 0; padding:8px;'>{opcoes_select}</select></div><div style='display:flex; align-items:flex-end; min-width:100px;'><button class='btn-acao' style='margin:0; height:41px;'>FILTRAR</button></div></form>
        <div class='grid-dash'><div class='card-kpi'><h3>Faturamento do Período</h3><p>R$ {faturamento_filtrado:.2f}</p></div><div class='card-kpi' style='border-left-color:{COR_VERMELHO};'><h3>Total Estornado (Devolvido)</h3><p style='color:{COR_VERMELHO};'>R$ {total_estornado:.2f} <small style='font-size:14px; color:#888;'>({qtd_estornada} itens)</small></p></div></div>
        <div style='display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px; margin-bottom:20px;'><div style='background:#111; padding:15px; border-radius:8px; border-left:4px solid {COR_AMARELO}; flex:1;'><b>💵 Dinheiro:</b><br><span style='color:#FFF;'>R$ {totais_pag['DINHEIRO']:.2f}</span></div><div style='background:#111; padding:15px; border-radius:8px; border-left:4px solid {COR_AMARELO}; flex:1;'><b>💠 PIX:</b><br><span style='color:#FFF;'>R$ {totais_pag['PIX']:.2f}</span></div><div style='background:#111; padding:15px; border-radius:8px; border-left:4px solid {COR_AMARELO}; flex:1;'><b>💳 Cartões:</b><br><span style='color:#FFF;'>R$ {(totais_pag['C. CREDITO'] + totais_pag['C. DEBITO']):.2f}</span></div></div>
        <div class='chart-container' style='padding: 15px;'><h3 style='border-bottom:2px solid {COR_BORDA}; padding-bottom:5px; margin-top:0;'>📋 LISTA DE ITENS VENDIDOS</h3><div style='max-height:300px; overflow-y:auto;'><table style='margin-top:0;'><thead style='background:#0A0A0A; position:sticky; top:0; box-shadow: 0 2px 4px rgba(0,0,0,0.8);'><tr><th style='color:{COR_AMARELO};'>Produto</th><th style='color:{COR_AMARELO}; text-align:center;'>Qtd</th><th style='color:{COR_AMARELO}; text-align:right;'>Total Arrecadado (R$)</th></tr></thead><tbody>{linhas_tabela if linhas_tabela else "<tr><td colspan='3' style='color:#777; text-align:center;'>Nenhuma venda encontrada no período.</td></tr>"}</tbody></table></div></div>
        <br><a href='/oldgoose' class='btn-acao btn-dark' style='width:250px; margin:auto;'>⬅️ Voltar ao Old Goose</a>
    </div></div></body></html>"""


# ==========================================
# MÓDULO DIRETORIA: CONTROLE DE USUÁRIOS E ACESSOS MULTIPLOS
# ==========================================
@app.get("/usuarios", response_class=HTMLResponse)
async def tela_usuarios(request: Request):
    role_session = request.session.get("role")
    if not check_access(role_session, ["admin", "diretoria"]): return RedirectResponse(url="/central")
    linhas = ""
    with engine.connect() as conn:
        users_db = conn.execute(text("SELECT id, username, email, role, status FROM usuarios ORDER BY status DESC, username")).mappings().fetchall()
        for r in users_db:
            acoes = ""
            if r['username'] != "admin":
                if r['status'] == 'BLOQUEADO': btn_block = f"<form action='/toggle_usuario' method='post' style='margin:0;'><input type='hidden' name='id' value='{r['id']}'><button class='btn-acao' style='background:#10b981; padding:8px; margin:0;' title='Aprovar Acesso'>🔓</button></form>"
                else: btn_block = f"<form action='/toggle_usuario' method='post' style='margin:0;'><input type='hidden' name='id' value='{r['id']}'><button class='btn-acao' style='background:#f59e0b; padding:8px; margin:0;' title='Bloquear'>🔒</button></form>"
                
                btn_reset = f"<form action='/resetar_senha_admin' method='post' style='margin:0;' onsubmit='return confirm(\"Resetar a senha de {r['username'].upper()}?\");'><input type='hidden' name='id' value='{r['id']}'><input type='hidden' name='u' value='{r['username']}'><button class='btn-acao btn-dark' style='padding:8px; margin:0;' title='Gerar Nova Senha'>🔄</button></form>"
                btn_edit_acesso = f"<button type='button' class='btn-acao btn-dark' style='padding:8px; margin:0;' onclick='abrirModalAcesso({r['id']}, \"{r['username']}\", \"{r['role']}\")' title='Alterar Cargo do Membro'>⚙️</button>"
                btn_del = f"<form action='/excluir_usuario' method='post' style='margin:0;' onsubmit='return confirm(\"Excluir membro permanentemente?\");'><input type='hidden' name='id' value='{r['id']}'><button class='btn-acao btn-red' style='padding:8px; margin:0;'>🗑️</button></form>"
                acoes = f"<div style='display:flex; gap:5px;'>{btn_block}{btn_reset}{btn_edit_acesso}{btn_del}</div>"
            
            st_badge = f"<span style='color:#10b981; font-weight:bold;'>ATIVO</span>" if r['status'] == 'ATIVO' else f"<span style='color:{COR_VERMELHO}; font-weight:bold;'>PENDENTE/BLOQ.</span>"
            role_display = (r['role'] or "MEMBRO").replace(',', ', ').upper()
            linhas += f"<tr><td><b style='color:#FFF;'>{r['username'].upper()}</b><br><small style='color:#888;'>{r['email'] or 'S/ Email'}</small></td><td style='color:{COR_AMARELO}; font-weight:bold; font-size:11px;'>{role_display}</td><td>{st_badge}</td><td>{acoes}</td></tr>"
            
    caixas_add = f"""
    <div style='display:grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap:10px; background:#141416; padding:15px; border-radius:8px; border:1px solid {COR_BORDA};'>
        <label class='checkbox-grid'><input type='checkbox' name='roles' value='candidato'> Candidato</label>
        <label class='checkbox-grid'><input type='checkbox' name='roles' value='membro' checked> Membro</label>
        <label class='checkbox-grid'><input type='checkbox' name='roles' value='secretario'> Secretaria</label>
        <label class='checkbox-grid'><input type='checkbox' name='roles' value='tesoureiro'> Tesouraria</label>
        <label class='checkbox-grid'><input type='checkbox' name='roles' value='rp'> Rel. Públicas</label>
        <label class='checkbox-grid'><input type='checkbox' name='roles' value='old_goose'> Old Goose</label>
        <label class='checkbox-grid'><input type='checkbox' name='roles' value='caixa'> Caixa do Bar</label>
        <label class='checkbox-grid'><input type='checkbox' name='roles' value='diretoria'> Diretoria</label>
        <label class='checkbox-grid'><input type='checkbox' name='roles' value='admin'> Admin</label>
    </div>
    """
    
    caixas_edit = f"""
    <div style='display:grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap:10px; background:#000; padding:15px; border-radius:8px; border:1px solid {COR_BORDA}; margin-top:10px;'>
        <label class='checkbox-grid'><input type='checkbox' name='roles' class='edit-role-cb' id='cb_edit_candidato' value='candidato'> Candidato</label>
        <label class='checkbox-grid'><input type='checkbox' name='roles' class='edit-role-cb' id='cb_edit_membro' value='membro'> Membro</label>
        <label class='checkbox-grid'><input type='checkbox' name='roles' class='edit-role-cb' id='cb_edit_secretario' value='secretario'> Secretaria</label>
        <label class='checkbox-grid'><input type='checkbox' name='roles' class='edit-role-cb' id='cb_edit_tesoureiro' value='tesoureiro'> Tesouraria</label>
        <label class='checkbox-grid'><input type='checkbox' name='roles' class='edit-role-cb' id='cb_edit_rp' value='rp'> Rel. Públicas</label>
        <label class='checkbox-grid'><input type='checkbox' name='roles' class='edit-role-cb' id='cb_edit_old_goose' value='old_goose'> Old Goose</label>
        <label class='checkbox-grid'><input type='checkbox' name='roles' class='edit-role-cb' id='cb_edit_caixa' value='caixa'> Caixa do Bar</label>
        <label class='checkbox-grid'><input type='checkbox' name='roles' class='edit-role-cb' id='cb_edit_diretoria' value='diretoria'> Diretoria</label>
        <label class='checkbox-grid'><input type='checkbox' name='roles' class='edit-role-cb' id='cb_edit_admin' value='admin'> Admin</label>
    </div>
    """

    add_form = f"<div style='background:#0A0A0A; padding:20px; border-radius:10px; margin-bottom:20px; border:1px solid {COR_BORDA};'><h3>➕ CRIAR ACESSO MANUAL</h3><form action='/novo_usuario_direto' method='post' style='display:flex; flex-direction:column; gap:10px;'><div style='display:flex; gap:10px; flex-wrap:wrap;'><input name='u' placeholder='Login' class='input-padrao' style='flex:1;' required><input name='e' type='email' placeholder='E-mail' class='input-padrao' style='flex:1;' required><input name='p' type='password' placeholder='Senha' class='input-padrao' style='flex:1;' required></div><label style='font-size:12px; color:#aaa; font-weight:bold;'>PERMISSÕES (Múltiplas escolhas):</label>{caixas_add}<button class='btn-acao' style='width:100%;'>SALVAR USUÁRIO</button></form></div>"
    
    modal_acesso = f"""
    <div id='acessoModal' style='display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:1000; align-items:center; justify-content:center;'>
        <div class='card-center' style='position:relative; width:90%; max-width:500px; padding:20px; background:#121214;'>
            <span onclick='document.getElementById(\"acessoModal\").style.display=\"none\"' style='position:absolute; top:10px; right:15px; cursor:pointer; font-size:24px; color:#FFF;'>&times;</span>
            <h3 style='margin-top:0; color:{COR_AMARELO};'>⚙️ ALTERAR PERMISSÕES</h3>
            <form action='/alterar_acesso' method='post' style='display:flex; flex-direction:column; gap:10px;'>
                <input type='hidden' name='id' id='acesso_id'>
                <p style='color:#FFF; text-align:left; margin:0;'>Usuário: <b id='acesso_user' style='color:{COR_AMARELO}; text-transform:uppercase;'></b></p>
                {caixas_edit}
                <button class='btn-acao' style='margin-top:10px;'>SALVAR ACESSOS</button>
            </form>
        </div>
    </div>
    """
    js_modal_acesso = "<script>function abrirModalAcesso(id, user, roles_str) { document.getElementById('acesso_id').value = id; document.getElementById('acesso_user').innerText = user; let checkboxes = document.querySelectorAll('.edit-role-cb'); checkboxes.forEach(cb => cb.checked = false); if(roles_str) { let roles = roles_str.split(','); roles.forEach(r => { let cb = document.getElementById('cb_edit_' + r.trim()); if(cb) cb.checked = true; }); } document.getElementById('acessoModal').style.display = 'flex'; }</script>"
    return f"<html><head>{CSS}{js_modal_acesso}</head><body>{modal_acesso}<div class='container-center'><div class='card-center' style='max-width:900px;'>{IMG_LOGO_PEQ}<h2>Aprovações e Usuários</h2>{add_form}<div style='max-height:400px; overflow-y:auto; border:1px solid {COR_BORDA};'><table><tr><th>Usuário</th><th>Cargos</th><th>Status</th><th>Ações</th></tr>{linhas}</table></div><br><a href='/central' class='btn-acao btn-dark' style='width:250px; margin:auto;'>⬅️ Voltar à Diretoria</a></div></div></body></html>"

@app.post("/resetar_senha_admin")
async def resetar_senha_admin(request: Request, id: int = Form(...), u: str = Form(...)):
    if not check_access(request.session.get("role"), ["admin", "diretoria"]): return RedirectResponse("/central")
    nova_senha = str(random.randint(100000, 999999))
    try:
        with engine.begin() as conn:
            conn.execute(text("UPDATE usuarios SET password = :p WHERE id = :id"), {"p": nova_senha, "id": id})
        return HTMLResponse(f"<script>alert('Senha do usuário {u.upper()} resetada!\\n\\nA nova senha provisória é: {nova_senha}\\n\\nCopie e envie para ele pelo WhatsApp.'); window.location.href='/usuarios';</script>")
    except: return RedirectResponse("/usuarios", status_code=303)

@app.post("/toggle_usuario")
async def toggle_usuario(request: Request):
    if not check_access(request.session.get("role"), ["admin", "diretoria"]): return RedirectResponse(url="/central")
    f = await request.form()
    try:
        with engine.begin() as conn:
            target = conn.execute(text("SELECT username, status FROM usuarios WHERE id = :id"), {"id": f.get("id")}).mappings().fetchone()
            if target and target['username'] != 'admin':
                novo_status = 'ATIVO' if target['status'] == 'BLOQUEADO' else 'BLOQUEADO'
                conn.execute(text("UPDATE usuarios SET status = :s WHERE id = :id"), {"s": novo_status, "id": f.get("id")})
    except: pass
    return RedirectResponse(url="/usuarios", status_code=303)

@app.post("/novo_usuario_direto")
async def novo_usuario_direto(request: Request):
    if not check_access(request.session.get("role"), ["admin", "diretoria"]): return RedirectResponse(url="/central")
    f = await request.form()
    roles_list = f.getlist("roles")
    roles_str = ",".join(roles_list) if roles_list else "membro"
    try:
        with engine.begin() as conn: 
            conn.execute(text("INSERT INTO usuarios (username, email, password, role, status) VALUES (:u, :e, :p, :r, 'ATIVO') ON CONFLICT (username) DO NOTHING"), {"u": f.get("u").lower(), "e": f.get("e").lower(), "p": f.get("p"), "r": roles_str})
    except: pass
    return RedirectResponse(url="/usuarios", status_code=303)

@app.post("/alterar_acesso")
async def alterar_acesso(request: Request):
    if not check_access(request.session.get("role"), ["admin", "diretoria"]): return RedirectResponse(url="/central")
    f = await request.form()
    roles_list = f.getlist("roles")
    roles_str = ",".join(roles_list) if roles_list else "membro"
    try:
        with engine.begin() as conn: 
            conn.execute(text("UPDATE usuarios SET role = :r WHERE id = :id"), {"r": roles_str, "id": f.get("id")})
    except: pass
    return RedirectResponse(url="/usuarios", status_code=303)

@app.post("/excluir_usuario")
async def excluir_usuario(request: Request):
    if not check_access(request.session.get("role"), ["admin", "diretoria"]): return RedirectResponse(url="/central")
    f = await request.form()
    try:
        with engine.begin() as conn: conn.execute(text("DELETE FROM usuarios WHERE id = :id AND username != 'admin'"), {"id": f.get("id")})
    except: pass
    return RedirectResponse(url="/usuarios", status_code=303)
