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

# Criação das tabelas do sistema JPMS
with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS produtos (id SERIAL PRIMARY KEY, codigo_barras TEXT UNIQUE, nome TEXT NOT NULL, categoria TEXT DEFAULT 'OUTROS', preco DECIMAL(10,2) DEFAULT 0.00, estoque INT DEFAULT 0);
        CREATE TABLE IF NOT EXISTS comandas (id SERIAL PRIMARY KEY, numero_comanda TEXT NOT NULL, total_conta DECIMAL(10,2) DEFAULT 0.00, status TEXT DEFAULT 'FECHADA', forma_pagamento TEXT, data_fechamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP, nfe_solicitada BOOLEAN DEFAULT FALSE, cpf_nota TEXT);
        CREATE TABLE IF NOT EXISTS vendas_itens (id SERIAL PRIMARY KEY, comanda_num TEXT, item_nome TEXT, valor DECIMAL(10,2), data_venda DATE DEFAULT CURRENT_DATE, hora_venda TIME DEFAULT CURRENT_TIME, status TEXT DEFAULT 'FECHADA');
        CREATE TABLE IF NOT EXISTS fila_impressao (id SERIAL PRIMARY KEY, conteudo TEXT, status TEXT DEFAULT 'PENDENTE', data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS historico_estoque (id SERIAL PRIMARY KEY, produto_nome TEXT, qtd_adicionada INT, data_entrada DATE DEFAULT CURRENT_DATE);
        CREATE TABLE IF NOT EXISTS configuracoes_nfe (id SERIAL PRIMARY KEY, token_focus TEXT, ambiente TEXT DEFAULT 'HOMOLOGACAO', senha_certificado TEXT, nome_arquivo_cert TEXT);
    """))

# Migrações seguras de tabelas existentes
MIGRACOES = [
    "ALTER TABLE produtos ADD COLUMN IF NOT EXISTS codigo_barras TEXT UNIQUE;",
    "ALTER TABLE comandas ADD COLUMN IF NOT EXISTS nfe_solicitada BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE comandas ADD COLUMN IF NOT EXISTS cpf_nota TEXT;",
    "CREATE TABLE IF NOT EXISTS configuracoes_nfe (id SERIAL PRIMARY KEY, token_focus TEXT, ambiente TEXT DEFAULT 'HOMOLOGACAO', senha_certificado TEXT, nome_arquivo_cert TEXT);"
]
for mig in MIGRACOES:
    try:
        with engine.begin() as conn: conn.execute(text(mig))
    except Exception: pass

# Cria o Admin Padrão e uma linha inicial de configuração fiscal se não existirem
try:
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO usuarios (username, password, role) VALUES ('admin', '1234', 'admin') ON CONFLICT (username) DO NOTHING"))
        cfg_exist = conn.execute(text("SELECT id FROM configuracoes_nfe LIMIT 1")).fetchone()
        if not cfg_exist:
            conn.execute(text("INSERT INTO configuracoes_nfe (token_focus, ambiente) VALUES ('', 'HOMOLOGACAO')"))
except Exception: pass

IMG_URL = "/logo.png"
CSS = f"""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>JPMS Soluções de Gestão</title>
<style>
    * {{ box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }}
    body {{ margin: 0; background: #0f172a; color: white; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}
    .btn-acao {{ display: block; width: 100%; padding: 15px; margin-bottom: 8px; border: none; border-radius: 5px; font-weight: bold; color: white; cursor: pointer; text-align: center; text-decoration: none; font-size: 14px; background: #0ea5e9; transition: 0.2s; }}
    .btn-acao:hover {{ opacity: 0.9; transform: scale(0.98); }}
    .container-center {{ display: flex; align-items: center; justify-content: center; height: 100vh; padding: 20px; overflow-y: auto; }}
    .card-center {{ background: white; color: #0f172a; padding: 30px; border-radius: 15px; width: 100%; max-width: 650px; text-align: center; box-shadow: 0 8px 20px rgba(0,0,0,0.4); margin: auto; }}
    .input-padrao {{ width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #cbd5e1; border-radius: 5px; font-size: 16px; box-sizing: border-box; background: #f1f5f9; color: #0f172a; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
    th, td {{ padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: left; vertical-align: middle; }}
    .logo-peq {{ width: 220px; max-width: 100%; height: auto; margin-bottom: 15px; filter: drop-shadow(0px 4px 6px rgba(0,0,0,0.3)); border-radius: 8px; }}
    .grid-dash {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; width: 100%; margin-bottom: 20px; }} 
    .card-kpi {{ background: white; padding: 20px; border-radius: 10px; color: #0f172a; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-left: 5px solid #10b981; }} 
    .card-kpi h3 {{ margin: 0; font-size: 14px; color: #64748b; text-transform: uppercase; }} 
    .card-kpi p {{ margin: 10px 0 0; font-size: 28px; font-weight: bold; color: #0f172a; }} 
    .chart-container {{ background: white; padding: 25px; border-radius: 10px; width: 100%; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom:20px; text-align: left; }} 
    .item-linha {{ display: flex; justify-content: space-between; font-size: 16px; margin-bottom: 10px; border-bottom: 1px dashed #cbd5e1; padding-bottom: 5px; align-items: center; color: #334155; }}
    .filtro-box {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; background: #1e293b; padding: 15px; border-radius: 8px; border: 1px solid #334155; width: 100%; text-align: left; }}
    .filtro-box label {{ font-size: 12px; color: #94a3b8; font-weight: bold; }}
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
"""
IMG_LOGO_PEQ = f"<div style='display:flex; justify-content:center; margin-bottom:15px;'><img src='{IMG_URL}' class='logo-peq'></div>"

@app.get("/logo.png")
async def exibir_logo(): 
    try: return FileResponse("logo.png")
    except: return Response(status_code=404)

@app.get("/", response_class=HTMLResponse)
async def login_page(): 
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'>{IMG_LOGO_PEQ}<h2>JPMS Soluções de Gestão</h2><form action='/login' method='post'><input class='input-padrao' name='user' placeholder='Usuário' required><input class='input-padrao' name='pw' type='password' placeholder='Senha' required><button class='btn-acao' style='padding:15px; font-size:18px;'>ENTRAR</button></form></div></div></body></html>"

@app.post("/login")
async def login(request: Request):
    f = await request.form()
    with engine.connect() as conn:
        user = conn.execute(text("SELECT username, role FROM usuarios WHERE username = :u AND password = :p"), {"u": f.get("user", "").strip().lower(), "p": f.get("pw", "")}).fetchone()
        if user:
            request.session["user"], request.session["role"] = user.username, user.role
            return RedirectResponse(url="/central", status_code=303)
    return HTMLResponse("<script>alert('Usuário ou Senha incorretos!'); window.location.href='/';</script>")

@app.get("/logout")
async def logout(request: Request): 
    request.session.clear()
    return RedirectResponse("/")

@app.get("/central", response_class=HTMLResponse)
async def central(request: Request):
    user, role = request.session.get("user"), request.session.get("role")
    if not user: return RedirectResponse(url="/")
    
    botoes = """
    <a href='/pdv' class='btn-acao' style='background:#10b981; font-size: 20px; padding: 25px;'>🛒 ABRIR CAIXA (PDV)</a>
    <a href='/estoque' class='btn-acao' style='background:#1e293b; font-size: 20px; padding: 25px;'>📦 GESTÃO DE ESTOQUE</a>
    <a href='/dashboard' class='btn-acao' style='background:#0ea5e9;'>📊 RELATÓRIOS E FECHAMENTO</a>
    <a href='/baixar_conector' class='btn-acao' style='background:#f59e0b; color:black;'>🖨️ BAIXAR CONECTOR DE IMPRESSORA</a>
    """
    if role == "admin":
        botoes += """
        <a href='/config_fiscal' class='btn-acao' style='background:#8b5cf6;'>⚙️ CONFIGURAÇÕES FISCAIS (NFC-e)</a>
        <a href='/usuarios' class='btn-acao' style='background:#475569'>👥 GERENCIAR USUÁRIOS</a>
        """
        
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'>{IMG_LOGO_PEQ}<p>Operador: <b>{user.upper()}</b></p><div style='display:flex; flex-direction:column; gap:15px; margin-top:20px;'>{botoes}</div><br><a href='/logout' style='color:gray'>Sair</a></div></div></body></html>"


# ==========================================
# MÓDULO 1: CONFIGURAÇÕES FISCAIS
# ==========================================
@app.get("/config_fiscal", response_class=HTMLResponse)
async def tela_config_fiscal(request: Request):
    if request.session.get("role") != "admin": return RedirectResponse(url="/central")
    with engine.connect() as conn:
        cfg = conn.execute(text("SELECT token_focus, ambiente, nome_arquivo_cert FROM configuracoes_nfe LIMIT 1")).fetchone()
        
    token_atual = cfg.token_focus if cfg and cfg.token_focus else ""
    amb_atual = cfg.ambiente if cfg and cfg.ambiente else "HOMOLOGACAO"
    cert_atual = cfg.nome_arquivo_cert if cfg and cfg.nome_arquivo_cert else "Nenhum arquivo enviado"

    return f"""<html><head>{CSS}</head><body><div class='container-center'><div class='card-center' style='max-width:600px;'>
        {IMG_LOGO_PEQ}
        <h2>⚙️ Configurações de Emissão (Focus NFe)</h2>
        <form action='/salvar_config_fiscal' method='post' enctype='multipart/form-data' style='text-align:left;'>
            <label style='font-weight:bold; font-size:14px;'>Token Focus NFe:</label>
            <input class='input-padrao' name='token_focus' value='{token_atual}' placeholder='Token fornecido pela Focus NFe' required>
            
            <label style='font-weight:bold; font-size:14px;'>Ambiente:</label>
            <select class='input-padrao' name='ambiente'>
                <option value='HOMOLOGACAO' {'selected' if amb_atual == 'HOMOLOGACAO' else ''}>🧪 HOMOLOGAÇÃO (Testes Livres)</option>
                <option value='PRODUCAO' {'selected' if amb_atual == 'PRODUCAO' else ''}>🚀 PRODUÇÃO (Vendas Reais - SEFAZ)</option>
            </select>
            
            <div style='background:#f1f5f9; padding:15px; border-radius:8px; border:1px solid #cbd5e1; margin:15px 0;'>
                <h4 style='margin-top:0; color:#8b5cf6;'>🔑 Certificado Digital A1 (.pfx)</h4>
                <p style='font-size:12px; color:#64748b; margin-top:-5px;'>Arquivo Atual: <b>{cert_atual}</b></p>
                <input type='file' name='arquivo_certificado' accept='.pfx,.p12' style='margin-bottom:10px;'><br>
                <label style='font-size:13px; font-weight:bold;'>Senha do Certificado:</label>
                <input type='password' class='input-padrao' name='senha_certificado' placeholder='Senha do certificado' style='padding:8px; font-size:14px;'>
            </div>
            <button class='btn-acao' style='background:#8b5cf6; font-size:16px;'>💾 SALVAR CREDENCIAIS FISCAIS</button>
        </form>
        <br><a href='/central' style='color:gray'>Voltar ao Painel</a>
    </div></div></body></html>"""

@app.post("/salvar_config_fiscal")
async def salvar_config_fiscal(request: Request, token_focus: str = Form(...), ambiente: str = Form(...), senha_certificado: str = Form(None), arquivo_certificado: UploadFile = File(None)):
    if request.session.get("role") != "admin": return RedirectResponse(url="/central")
    nome_original_cert = None
    if arquivo_certificado and arquivo_certificado.filename:
        nome_original_cert = arquivo_certificado.filename
        file_path = os.path.join(UPLOAD_DIR, nome_original_cert)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(arquivo_certificado.file, buffer)
    try:
        with engine.begin() as conn:
            if nome_original_cert:
                conn.execute(text("UPDATE configuracoes_nfe SET token_focus = :tk, ambiente = :amb, senha_certificado = :senha, nome_arquivo_cert = :nome WHERE id = (SELECT id FROM configuracoes_nfe LIMIT 1)"), {"tk": token_focus.strip(), "amb": ambiente, "senha": senha_certificado, "nome": nome_original_cert})
            else:
                conn.execute(text("UPDATE configuracoes_nfe SET token_focus = :tk, ambiente = :amb WHERE id = (SELECT id FROM configuracoes_nfe LIMIT 1)"), {"tk": token_focus.strip(), "amb": ambiente})
    except Exception: pass
    return HTMLResponse("<script>alert('Configurações Fiscais atualizadas!'); window.location.href='/config_fiscal';</script>")


# ==========================================
# MÓDULO 2: CAIXA EXPRESSO (PDV)
# ==========================================
@app.get("/pdv", response_class=HTMLResponse)
async def pdv_caixa(request: Request):
    if not request.session.get("user"): return RedirectResponse(url="/")
    
    js_pdv = """
    <script>
        let carrinho = [];
        let total = 0.0;

        window.onload = () => document.getElementById('leitor').focus();
        document.addEventListener('click', (e) => {
            if(e.target.tagName !== 'BUTTON' && e.target.tagName !== 'SELECT' && e.target.tagName !== 'INPUT') {
                document.getElementById('leitor').focus();
            }
        });

        async function processarBipe(event) {
            if(event.key === 'Enter') {
                event.preventDefault();
                let input = document.getElementById('leitor');
                let codigo = input.value.trim();
                input.value = ''; 
                if(!codigo) return;

                let res = await fetch('/api/bipar/' + codigo).then(r => r.json());
                
                if(res.status === 'ok') {
                    carrinho.push({id: res.id, nome: res.nome, preco: res.preco});
                    atualizarCarrinho();
                } else if(res.status === 'esgotado') {
                    alert('⚠️ Produto ESGOTADO: ' + res.nome);
                } else {
                    if(confirm('Produto não encontrado! Deseja cadastrar no estoque agora?')) {
                        window.open('/estoque', '_blank');
                    }
                }
            }
        }

        function atualizarCarrinho() {
            let html = '';
            total = 0;
            [...carrinho].reverse().forEach((item, idx) => {
                let idReal = carrinho.length - 1 - idx;
                html += `<div style='display:flex; justify-content:space-between; padding:15px; border-bottom:1px dashed #cbd5e1; font-size:18px; color:#0f172a;'>
                            <span>${item.nome}</span>
                            <span>R$ ${item.preco.toFixed(2)} <b onclick='removerItem(${idReal})' style='color:#ef4444; cursor:pointer; margin-left:15px; font-size:20px;'>☒</b></span>
                         </div>`;
                total += item.preco;
            });
            document.getElementById('lista-itens').innerHTML = html;
            document.getElementById('valor-total').innerText = 'R$ ' + total.toFixed(2);
        }

        function removerItem(idx) { carrinho.splice(idx, 1); atualizarCarrinho(); }

        function finalizarCompra() {
            if(carrinho.length === 0) return alert('O caixa está vazio!');
            
            let form = document.createElement('form');
            form.method = 'POST'; form.action = '/finalizar_pdv';
            
            let i1 = document.createElement('input'); i1.name = 'itens'; i1.value = JSON.stringify(carrinho);
            let i2 = document.createElement('input'); i2.name = 'pagamento'; i2.value = document.getElementById('forma-pag').value;
            let i3 = document.createElement('input'); i3.name = 'nfe'; i3.value = document.getElementById('chk-nfe').checked ? 'true' : 'false';
            let i4 = document.createElement('input'); i4.name = 'cpf_nota'; i4.value = document.getElementById('cpf-nota').value;
            
            form.appendChild(i1); form.appendChild(i2); form.appendChild(i3); form.appendChild(i4);
            document.body.appendChild(form);
            form.submit();
        }
    </script>
    """
    
    return f"""<html><head>{CSS}{js_pdv}</head>
    <body style='background:#e2e8f0;'>
        <div style='display:flex; height:100vh; width:100%;'>
            <div style='flex:2; padding:20px; display:flex; flex-direction:column; border-right:2px solid #cbd5e1; background:white;'>
                <div style='display:flex; align-items:center; gap:20px; margin-bottom:10px;'>
                     {IMG_LOGO_PEQ}
                     <h2 style='color:#0ea5e9; margin:0;'>🛒 Caixa Livre (PDV)</h2>
                </div>
                <div id='lista-itens' style='flex:1; overflow-y:auto; background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; padding:10px;'>
                    <div style='color:#94a3b8; text-align:center; margin-top:20px; font-size:18px;'>Aguardando produtos... Bipe o código de barras.</div>
                </div>
            </div>
            
            <div style='flex:1; padding:20px; display:flex; flex-direction:column; justify-content:space-between; background:#0f172a; min-width:350px;'>
                <div>
                    <h3 style='color:white; margin-top:0;'>Leitor de Código de Barras</h3>
                    <input type='text' id='leitor' onkeypress='processarBipe(event)' style='width:100%; padding:20px; font-size:20px; text-align:center; border:3px solid #10b981; border-radius:8px; background:white; color:black; outline:none;' placeholder='BIPE O CÓDIGO AQUI' autocomplete='off'>
                </div>
                
                <div style='background:#1e293b; padding:20px; border-radius:8px; margin-top:20px;'>
                    <div style='color:#94a3b8; font-size:18px;'>TOTAL DA VENDA</div>
                    <div id='valor-total' style='color:#10b981; font-size:45px; font-weight:bold; margin-bottom:20px;'>R$ 0.00</div>
                    
                    <select id='forma-pag' class='input-padrao' style='font-size:18px; padding:15px; margin-bottom:15px; font-weight:bold;'>
                        <option value='01'>💵 DINHEIRO</option>
                        <option value='17'>💠 PIX</option>
                        <option value='03'>💳 CARTÃO CRÉDITO</option>
                        <option value='04'>💳 CARTÃO DÉBITO</option>
                    </select>

                    <div style='background:#0f172a; padding:15px; border-radius:8px; margin-bottom:15px; border:1px solid #334155;'>
                        <div style='display:flex; align-items:center; justify-content:space-between; margin-bottom:10px;'>
                            <span style='font-weight:bold; color:#10b981; font-size: 16px;'>🧾 Emitir Nota (NFC-e)?</span>
                            <input type='checkbox' id='chk-nfe' onchange='document.getElementById("box-cpf").style.display = this.checked ? "block" : "none"' style='transform: scale(1.5); cursor: pointer;'>
                        </div>
                        <div id='box-cpf' style='display:none;'>
                            <span style='font-size:13px; color:#94a3b8;'>CPF do Cliente:</span>
                            <input type='text' id='cpf-nota' class='input-padrao' placeholder='000.000.000-00' style='margin-top:5px; font-size:16px;' autocomplete='off'>
                        </div>
                    </div>
                    
                    <button class='btn-acao' style='background:#0ea5e9; font-size:22px; padding:20px;' onclick='finalizarCompra()'>FINALIZAR VENDA</button>
                    <a href='/central' class='btn-acao' style='background:#334155; margin-top:10px;'>VOLTAR</a>
                </div>
            </div>
        </div>
    </body></html>"""

@app.post("/finalizar_pdv")
async def finalizar_pdv(request: Request):
    f = await request.form()
    itens = json.loads(f.get("itens", "[]"))
    cod_pagamento = f.get("pagamento")
    
    nomes_pag = {"01": "DINHEIRO", "17": "PIX", "03": "C. CREDITO", "04": "C. DEBITO"}
    nome_pagamento = nomes_pag.get(cod_pagamento, "OUTROS")
    
    nfe_solicitada = f.get("nfe") == "true"
    cpf_nota = f.get("cpf_nota", "").strip()
    usuario = request.session.get("user", "Caixa")
    total = sum(i['preco'] for i in itens)
    cupom_id = "V" + datetime.now().strftime("%Y%m%d%H%M%S")
    
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO comandas (numero_comanda, total_conta, status, forma_pagamento, nfe_solicitada, cpf_nota) VALUES (:c, :t, 'FECHADA', :p, :nfe, :cpf)"), {"c": cupom_id, "t": total, "p": nome_pagamento, "nfe": nfe_solicitada, "cpf": cpf_nota})
            
            txt = f"--------------------------------\n   JPMS SOLUCOES DE GESTAO\nCUPOM: {cupom_id}\nCAIXA: {usuario.upper()}\nDATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n--------------------------------\n"
            for item in itens:
                conn.execute(text("INSERT INTO vendas_itens (comanda_num, item_nome, valor, status) VALUES (:c, :n, :v, 'FECHADA')"), {"c": cupom_id, "n": item['nome'], "v": item['preco']})
                conn.execute(text("UPDATE produtos SET estoque = GREATEST(estoque - 1, 0) WHERE id = :id"), {"id": item['id']})
                txt += f"1x {item['nome'][:20]:<20} R$ {item['preco']:.2f}\n"
                
            txt += f"--------------------------------\nTOTAL: R$ {total:.2f}\nPAGTO: {nome_pagamento}\n--------------------------------\n"
            
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
                                "numero_item": str(idx+1), 
                                "codigo_produto": str(item['id']), 
                                "descricao": item['nome'], 
                                "cfop": "5102", 
                                "unidade_comercial": "UN", 
                                "quantidade_comercial": "1", 
                                "valor_unitario_comercial": str(item['preco']), 
                                "valor_bruto": str(item['preco']), 
                                "icms_origem": "0", 
                                "icms_situacao_tributaria": "102"
                            } for idx, item in enumerate(itens)
                        ],
                        "pagamentos": [{"forma_pagamento": cod_pagamento, "valor_pagamento": str(total)}]
                    }
                    if cpf_nota: payload["cpf_cnpj_destinatario"] = re.sub(r'[^0-9]', '', cpf_nota)
                    try:
                        resp = requests.post(url_api, json=payload, auth=(cfg.token_focus, ""))
                        if resp.status_code in [200, 202]:
                            dados_nfe = resp.json()
                            txt += f"\n✅ COMUNICACAO SEFAZ OK!\nAmbiente: {cfg.ambiente}\nStatus: {dados_nfe.get('status', 'OK')}\n"
                        elif resp.status_code == 401:
                            txt += "\n❌ ERRO API: Token Invalido.\n"
                        else:
                            txt += f"\n⚠️ RETORNO SEFAZ:\n{str(resp.json())[:150]}...\n"
                    except Exception as e: txt += f"\n⚠️ FALHA DE REDE: {e}\n"
                else: txt += "\n⚠️ ERRO: Token nao configurado.\n"
                txt += "--------------------------------\n"

            conn.execute(text("INSERT INTO fila_impressao (conteudo) VALUES (:txt)"), {"txt": txt})
    except Exception as e: print(f"Erro PDV: {e}")
    return RedirectResponse(url="/pdv", status_code=303)


# ==========================================
# MÓDULO 3: ESTOQUE (CÓDIGO DE BARRAS)
# ==========================================
@app.get("/estoque", response_class=HTMLResponse)
async def tela_estoque(request: Request):
    if request.session.get("role") not in ["admin", "gerente"]: return RedirectResponse(url="/central")
    linhas = ""
    with engine.connect() as conn:
        prods_db = conn.execute(text("SELECT id, codigo_barras, nome, categoria, preco, estoque FROM produtos ORDER BY nome")).fetchall()
        for r in prods_db:
            acoes = f"<div style='display:flex; gap:5px;'><form action='/att_estoque' method='post' style='margin:0; display:flex;'><input type='hidden' name='id' value='{r.id}'><input type='number' name='q' class='input-padrao' style='width:60px; padding:5px; margin:0;' placeholder='+Qtd' required><button class='btn-acao' style='background:#10b981; padding:8px; margin:0;'>➕</button></form><form action='/excluir_produto' method='post' style='margin:0;' onsubmit='return confirm(\"Excluir item?\");'><input type='hidden' name='id' value='{r.id}'><button class='btn-acao' style='background:#ef4444; padding:8px; margin:0;'>🗑️</button></form></div>"
            linhas += f"<tr><td style='color:#64748b; font-size:12px;'>{r.codigo_barras or r.id}</td><td style='color:#0f172a; font-weight:bold;'>{r.nome}<br><small style='color:#0ea5e9;'>R$ {float(r.preco or 0):.2f}</small></td><td style='color:#0f172a; font-weight:bold; font-size:18px; text-align:center;'>{int(r.estoque or 0)}</td><td>{acoes}</td></tr>"
            
    add_form = f"""
    <div style='background:#f1f5f9; padding:20px; border-radius:10px; margin-bottom:20px; text-align:left; border:1px solid #cbd5e1;'>
        <h3 style='margin-top:0; color:#0ea5e9;'>➕ CADASTRAR PRODUTO</h3>
        <form action='/novo_produto' method='post' style='display:flex; flex-wrap:wrap; gap:10px;'>
            <input name='codigo_barras' placeholder='Bipe o Código de Barras' class='input-padrao' style='width:100%; border:2px solid #0ea5e9; font-weight:bold;' autocomplete='off'>
            <input name='nome' placeholder='Nome do Produto' class='input-padrao' style='flex:2; min-width:200px;' required>
            <select name='cat' class='input-padrao' style='flex:1; min-width:120px;' required>
                <option value='ALIMENTOS'>ALIMENTOS</option><option value='BEBIDAS'>BEBIDAS</option><option value='LIMPEZA'>LIMPEZA</option><option value='OUTROS'>OUTROS</option>
            </select>
            <input name='preco' placeholder='Preço (Ex: 5.50)' step='0.01' type='number' class='input-padrao' style='width:100px;' required>
            <input name='qtd' type='number' placeholder='Qtd Inicial' class='input-padrao' style='width:100px;' required>
            <button class='btn-acao' style='background:#0ea5e9; width:100%; font-size:18px;'>SALVAR NO SISTEMA</button>
        </form>
    </div>"""
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center' style='max-width:800px;'>{IMG_LOGO_PEQ}<h2>📦 Gestão de Estoque</h2>{add_form}<div style='max-height:400px; overflow-y:auto; border:1px solid #cbd5e1;'><table><tr><th style='color:#0f172a'>Cód. Barras</th><th style='color:#0f172a'>Produto</th><th style='color:#0f172a'>Estoque</th><th style='color:#0f172a'>Ações</th></tr>{linhas}</table></div><br><a href='/central' style='color:gray'>Voltar</a></div></div></body></html>"

@app.post("/novo_produto")
async def novo_produto(request: Request):
    f = await request.form()
    cb = f.get("codigo_barras").strip() if f.get("codigo_barras") else None
    try:
        with engine.begin() as conn: 
            conn.execute(text("INSERT INTO produtos (codigo_barras, nome, categoria, preco, estoque) VALUES (:cb, :n, :c, :p, :q) ON CONFLICT (codigo_barras) DO UPDATE SET estoque = produtos.estoque + :q"), {"cb": cb, "n": f.get("nome"), "c": f.get("cat"), "p": float(f.get("preco").replace(",", ".")), "q": int(f.get("qtd"))})
    except Exception: pass
    return RedirectResponse(url="/estoque", status_code=303)

@app.post("/att_estoque")
async def att_estoque(request: Request):
    f = await request.form()
    try:
        with engine.begin() as conn: conn.execute(text("UPDATE produtos SET estoque = COALESCE(estoque, 0) + :q WHERE id = :id"), {"id": f.get("id"), "q": int(f.get("q", "0"))})
    except: pass
    return RedirectResponse(url="/estoque", status_code=303)

@app.post("/excluir_produto")
async def excluir_produto(request: Request):
    f = await request.form()
    try:
        with engine.begin() as conn: conn.execute(text("DELETE FROM produtos WHERE id = :id"), {"id": f.get("id")})
    except: pass
    return RedirectResponse(url="/estoque", status_code=303)


# ==========================================
# MÓDULO 4: RELATÓRIOS E FECHAMENTO COM FILTROS AVANÇADOS
# ==========================================
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, inicio: str = "", fim: str = "", tipo_venda: str = "TODOS"):
    if request.session.get("role") not in ["admin", "gerente"]: return RedirectResponse(url="/central")
    
    # Se não informar o período, joga o dia atual por padrão
    hoje_str = date.today().strftime("%Y-%m-%d")
    dt_inicio = inicio if inicio else hoje_str
    dt_fim = fim if fim else hoje_str

    # Construção da query SQL dinâmica
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
        
        top_db = conn.execute(text(f"SELECT item_nome, COUNT(*) as qtd FROM vendas_itens WHERE status = 'FECHADA' AND comanda_num IN (SELECT numero_comanda FROM comandas WHERE {where_clause}) GROUP BY item_nome ORDER BY qtd DESC LIMIT 5"), params).fetchall()
        html_top = "".join([f"<div class='item-linha'><span>{i+1}º {r.item_nome}</span><b style='color:#0ea5e9;'>{r.qtd} un</b></div>" for i, r in enumerate(top_db)])

    opcoes_select = f"""
    <option value='TODOS' {'selected' if tipo_venda == 'TODOS' else ''}>⚙️ TODOS OS TIPOS</option>
    <option value='DINHEIRO' {'selected' if tipo_venda == 'DINHEIRO' else ''}>💵 DINHEIRO</option>
    <option value='PIX' {'selected' if tipo_venda == 'PIX' else ''}>💠 PIX</option>
    <option value='C. CREDITO' {'selected' if tipo_venda == 'C. CREDITO' else ''}>💳 CARTÃO CRÉDITO</option>
    <option value='C. DEBITO' {'selected' if tipo_venda == 'C. DEBITO' else ''}>💳 CARTÃO DÉBITO</option>
    """

    return f"""<html><head>{CSS}</head><body><div class='container-center'><div class='card-center' style='max-width:800px;'>
        {IMG_LOGO_PEQ}
        <h2>📊 Relatório de Vendas e Fechamento</h2>
        
        <form method='get' class='filtro-box'>
            <div style='flex:1; min-width:140px;'>
                <label>Data Inicial:</label><br>
                <input type='date' name='inicio' value='{dt_inicio}' class='input-padrao' style='margin:5px 0 0 0; padding:8px;'>
            </div>
            <div style='flex:1; min-width:140px;'>
                <label>Data Final:</label><br>
                <input type='date' name='fim' value='{dt_fim}' class='input-padrao' style='margin:5px 0 0 0; padding:8px;'>
            </div>
            <div style='flex:1; min-width:160px;'>
                <label>Tipo de Venda:</label><br>
                <select name='tipo_venda' class='input-padrao' style='margin:5px 0 0 0; padding:8px; font-weight:bold;'>
                    {opcoes_select}
                </select>
            </div>
            <div style='display:flex; align-items:flex-end; min-width:100px;'>
                <button class='btn-acao' style='background:#10b981; margin:0; padding:10px; height:41px;'>FILTRAR</button>
            </div>
        </form>

        <div class='grid-dash'>
            <div class='card-kpi' style='border-left: 6px solid #10b981;'>
                <h3>Faturamento do Período</h3>
                <p style='color:#10b981; font-size:32px;'>R$ {faturamento_filtrado:.2f}</p>
            </div>
        </div>

        <div style='display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px; margin-bottom:20px;'>
            <div style='background:#f8fafc; padding:15px; border-radius:8px; border-left:4px solid #10b981; flex:1; min-width:130px;'>
                <b>💵 Dinheiro:</b><br><span style='font-size:18px; color:#10b981; font-weight:bold;'>R$ {totais_pag['DINHEIRO']:.2f}</span>
            </div>
            <div style='background:#f8fafc; padding:15px; border-radius:8px; border-left:4px solid #0ea5e9; flex:1; min-width:130px;'>
                <b>💠 PIX:</b><br><span style='font-size:18px; color:#0ea5e9; font-weight:bold;'>R$ {totais_pag['PIX']:.2f}</span>
            </div>
            <div style='background:#f8fafc; padding:15px; border-radius:8px; border-left:4px solid #f59e0b; flex:1; min-width:130px;'>
                <b>💳 Cartões:</b><br><span style='font-size:18px; color:#f59e0b; font-weight:bold;'>R$ {(totais_pag['C. CREDITO'] + totais_pag['C. DEBITO']):.2f}</span>
            </div>
        </div>

        <div class='chart-container'>
            <h3 style='color:#0f172a; margin-top:0; border-bottom:2px solid #e2e8f0; padding-bottom:5px;'>🏆 Produtos Mais Vendidos no Filtro</h3>
            {html_top if html_top else '<p style=\"color:#64748b;\">Nenhuma venda encontrada para este filtro.</p>'}
        </div>
        <br><a href='/central' class='btn-acao' style='background:#334155; width:150px; margin:auto;'>Voltar</a>
    </div></div></body></html>"""


# ==========================================
# MÓDULO 5: USUÁRIOS E IMPRESSORA
# ==========================================
@app.get("/usuarios", response_class=HTMLResponse)
async def tela_usuarios(request: Request):
    if request.session.get("role") != "admin": return RedirectResponse(url="/central")
    linhas = ""
    with engine.connect() as conn:
        users_db = conn.execute(text("SELECT id, username, role FROM usuarios ORDER BY role, username")).fetchall()
        for r in users_db:
            acoes = f"<form action='/excluir_usuario' method='post' style='margin:0;' onsubmit='return confirm(\"Excluir?\");'><input type='hidden' name='id' value='{r.id}'><button class='btn-acao' style='background:#ef4444; padding:8px;'>🗑️</button></form>" if r.username != "admin" else ""
            linhas += f"<tr><td style='color:#0f172a; font-weight:bold;'>{r.username.upper()}</td><td style='color:#0ea5e9;'>{r.role.upper()}</td><td>{acoes}</td></tr>"
    add_form = f"<div style='background:#f1f5f9; padding:20px; border-radius:10px; margin-bottom:20px; text-align:left; border:1px solid #cbd5e1;'><h3 style='margin-top:0; color:#8b5cf6;'>➕ NOVO USUÁRIO</h3><form action='/novo_usuario' method='post' style='display:flex; flex-wrap:wrap; gap:10px;'><input name='u' placeholder='Login' class='input-padrao' style='flex:1;' required><input name='p' type='password' placeholder='Senha' class='input-padrao' style='flex:1;' required><select name='r' class='input-padrao' style='flex:1;'><option value='gerente'>GERENTE</option><option value='caixa'>CAIXA</option></select><button class='btn-acao' style='background:#8b5cf6; width:100%;'>CRIAR ACESSO</button></form></div>"
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'>{IMG_LOGO_PEQ}<h2>Usuários</h2>{add_form}<div style='max-height:400px; overflow-y:auto; border:1px solid #cbd5e1;'><table><tr><th style='color:#0f172a'>Login</th><th style='color:#0f172a'>Cargo</th><th style='color:#0f172a'>Ação</th></tr>{linhas}</table></div><br><a href='/central' style='color:gray'>Voltar</a></div></div></body></html>"

@app.post("/novo_usuario")
async def novo_usuario(request: Request):
    f = await request.form()
    try:
        with engine.begin() as conn: conn.execute(text("INSERT INTO usuarios (username, password, role) VALUES (:u, :p, :r) ON CONFLICT (username) DO NOTHING"), {"u": f.get("u").lower(), "p": f.get("p"), "r": f.get("r")})
    except: pass
    return RedirectResponse(url="/usuarios", status_code=303)

@app.post("/excluir_usuario")
async def excluir_usuario(request: Request):
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
        hJob = win32print.StartDocPrinter(hPrinter, 1, ("Ticket JPMS", None, "RAW"))
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
print("🚀 CONECTOR DE IMPRESSORA JPMS INICIADO")
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
