from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy import create_engine, text
from starlette.middleware.sessions import SessionMiddleware
from datetime import datetime, date
import json
import urllib.parse
import os

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="jpms_solucoes_gestao_2026_seguro")

# Conexão com o Banco de Dados do Railway
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:GNlZnHiuKAcFnpgXhwILfigqKCNkaHqx@interchange.proxy.rlwy.net:44559/railway")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Criação das tabelas simplificadas para Mercearia
with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS produtos (id SERIAL PRIMARY KEY, codigo_barras TEXT UNIQUE, nome TEXT NOT NULL, categoria TEXT DEFAULT 'OUTROS', preco DECIMAL(10,2) DEFAULT 0.00, estoque INT DEFAULT 0);
        CREATE TABLE IF NOT EXISTS comandas (id SERIAL PRIMARY KEY, numero_comanda TEXT NOT NULL, total_conta DECIMAL(10,2) DEFAULT 0.00, status TEXT DEFAULT 'FECHADA', forma_pagamento TEXT, data_fechamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS vendas_itens (id SERIAL PRIMARY KEY, comanda_num TEXT, item_nome TEXT, valor DECIMAL(10,2), data_venda DATE DEFAULT CURRENT_DATE, hora_venda TIME DEFAULT CURRENT_TIME, status TEXT DEFAULT 'FECHADA');
        CREATE TABLE IF NOT EXISTS fila_impressao (id SERIAL PRIMARY KEY, conteudo TEXT, status TEXT DEFAULT 'PENDENTE', data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS historico_estoque (id SERIAL PRIMARY KEY, produto_nome TEXT, qtd_adicionada INT, data_entrada DATE DEFAULT CURRENT_DATE);
    """))

# Migração segura para adicionar as colunas novas (Código de Barras e Nota Fiscal) sem quebrar o banco atual
MIGRACOES = [
    "ALTER TABLE produtos ADD COLUMN IF NOT EXISTS codigo_barras TEXT UNIQUE;",
    "ALTER TABLE comandas ADD COLUMN IF NOT EXISTS nfe_solicitada BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE comandas ADD COLUMN IF NOT EXISTS cpf_nota TEXT;"
]
for mig in MIGRACOES:
    try:
        with engine.begin() as conn: conn.execute(text(mig))
    except Exception: pass

# Cria o Admin Padrão
try:
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO usuarios (username, password, role) VALUES ('admin', '1234', 'admin') ON CONFLICT (username) DO NOTHING"))
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
    .logo-central {{ width: 280px; max-width: 100%; height: auto; margin-bottom: 20px; filter: drop-shadow(0px 4px 6px rgba(0,0,0,0.5)); border-radius: 10px; }}
    .logo-peq {{ width: 180px; max-width: 100%; height: auto; margin-bottom: 10px; filter: drop-shadow(0px 2px 4px rgba(0,0,0,0.5)); border-radius: 8px; }}
    .grid-dash {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 15px; width: 100%; margin-bottom: 20px; }} 
    .card-kpi {{ background: white; padding: 15px; border-radius: 10px; color: #0f172a; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-left: 5px solid #0ea5e9; }} 
    .card-kpi h3 {{ margin: 0; font-size: 13px; color: #64748b; text-transform: uppercase; }} 
    .card-kpi p {{ margin: 10px 0 0; font-size: 20px; font-weight: bold; color: #0f172a; }} 
    .chart-container {{ background: white; padding: 15px; border-radius: 10px; width: 100%; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom:20px; }} 
    .item-linha {{ display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 8px; border-bottom: 1px dashed #cbd5e1; padding-bottom: 5px; align-items: center; color: #334155; }}
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
"""
IMG_LOGO_PEQ = f"<div style='display:flex; justify-content:center; margin-bottom:15px;'><img src='{IMG_URL}' class='logo-peq' onerror=\"this.style.display='none'\"></div>"

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
    <a href='/dashboard' class='btn-acao' style='background:#0ea5e9;'>📊 RELATÓRIOS E FINANCEIRO</a>
    <a href='/baixar_conector' class='btn-acao' style='background:#f59e0b; color:black;'>🖨️ BAIXAR CONECTOR DE IMPRESSORA</a>
    """
    if role == "admin":
        botoes += "<a href='/usuarios' class='btn-acao' style='background:#475569'>👥 GERENCIAR USUÁRIOS</a>"
        
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'>{IMG_LOGO_PEQ}<p>Operador: <b>{user.upper()}</b></p><div style='display:flex; flex-direction:column; gap:15px; margin-top:20px;'>{botoes}</div><br><a href='/logout' style='color:gray'>Sair</a></div></div></body></html>"


# ==========================================
# MÓDULO 1: CAIXA EXPRESSO (PDV) - ATUALIZADO COM NFE
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
            // Mantém o input do leitor focado, a menos que o usuário clique em um botão, select ou no input de CPF
            if(e.target.tagName !== 'BUTTON' && e.target.tagName !== 'SELECT' && e.target.tagName !== 'INPUT') {
                document.getElementById('leitor').focus();
            }
        });

        async function processarBipe(event) {
            if(event.key === 'Enter') {
                event.preventDefault(); // Evita recarregar a página
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
                <h2 style='color:#0ea5e9; margin-top:0;'>🛒 Caixa Livre (PDV)</h2>
                <div id='lista-itens' style='flex:1; overflow-y:auto; background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; padding:10px;'>
                    <div style='color:#94a3b8; text-align:center; margin-top:20px; font-size:18px;'>Aguardando produtos... Bipe o código de barras.</div>
                </div>
            </div>
            
            <div style='flex:1; padding:20px; display:flex; flex-direction:column; justify-content:space-between; background:#0f172a; min-width:350px;'>
                <div>
                    {IMG_LOGO_PEQ}
                    <input type='text' id='leitor' onkeypress='processarBipe(event)' style='width:100%; padding:20px; font-size:20px; text-align:center; border:3px solid #10b981; border-radius:8px; background:white; color:black; outline:none;' placeholder='BIPE O CÓDIGO AQUI' autocomplete='off'>
                </div>
                
                <div style='background:#1e293b; padding:20px; border-radius:8px; margin-top:20px;'>
                    <div style='color:#94a3b8; font-size:18px;'>TOTAL DA VENDA</div>
                    <div id='valor-total' style='color:#10b981; font-size:45px; font-weight:bold; margin-bottom:20px;'>R$ 0.00</div>
                    
                    <select id='forma-pag' class='input-padrao' style='font-size:18px; padding:15px; margin-bottom:15px; font-weight:bold;'>
                        <option value='DINHEIRO'>💵 DINHEIRO</option>
                        <option value='PIX'>💠 PIX</option>
                        <option value='C. CREDITO'>💳 CARTÃO CRÉDITO</option>
                        <option value='C. DEBITO'>💳 CARTÃO DÉBITO</option>
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

@app.get("/api/bipar/{codigo}")
async def bipar_produto(codigo: str):
    with engine.connect() as conn:
        prod = conn.execute(text("SELECT id, nome, preco, estoque FROM produtos WHERE codigo_barras = :c OR id::text = :c OR nome ILIKE :c LIMIT 1"), {"c": codigo.strip()}).fetchone()
        if prod:
            if prod.estoque <= 0: return {"status": "esgotado", "nome": prod.nome}
            return {"status": "ok", "id": prod.id, "nome": prod.nome, "preco": float(prod.preco)}
        return {"status": "erro", "msg": "Produto não encontrado"}

@app.post("/finalizar_pdv")
async def finalizar_pdv(request: Request):
    f = await request.form()
    itens = json.loads(f.get("itens", "[]"))
    pagamento = f.get("pagamento")
    
    nfe_solicitada = f.get("nfe") == "true"
    cpf_nota = f.get("cpf_nota", "").strip()
    
    usuario = request.session.get("user", "Caixa")
    total = sum(i['preco'] for i in itens)
    cupom_id = "V" + datetime.now().strftime("%Y%m%d%H%M%S")
    
    try:
        with engine.begin() as conn:
            # Insere a comanda fechada
            conn.execute(text("INSERT INTO comandas (numero_comanda, total_conta, status, forma_pagamento, nfe_solicitada, cpf_nota) VALUES (:c, :t, 'FECHADA', :p, :nfe, :cpf)"), {"c": cupom_id, "t": total, "p": pagamento, "nfe": nfe_solicitada, "cpf": cpf_nota})
            
            txt = f"--------------------------------\n   JPMS SOLUCOES DE GESTAO\nCUPOM: {cupom_id}\nCAIXA: {usuario.upper()}\nDATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n--------------------------------\n"
            
            for item in itens:
                conn.execute(text("INSERT INTO vendas_itens (comanda_num, item_nome, valor, status) VALUES (:c, :n, :v, 'FECHADA')"), {"c": cupom_id, "n": item['nome'], "v": item['preco']})
                conn.execute(text("UPDATE produtos SET estoque = GREATEST(estoque - 1, 0) WHERE id = :id"), {"id": item['id']})
                txt += f"1x {item['nome'][:20]:<20} R$ {item['preco']:.2f}\n"
                
            txt += f"--------------------------------\nTOTAL: R$ {total:.2f}\nPAGTO: {pagamento}\n--------------------------------\n"
            
            if nfe_solicitada:
                txt += "EMISSAO DE NFC-e SOLICITADA\n"
                if cpf_nota:
                    txt += f"CPF/CNPJ: {cpf_nota}\n"
                txt += "--------------------------------\n"

            conn.execute(text("INSERT INTO fila_impressao (conteudo) VALUES (:txt)"), {"txt": txt})
    except Exception as e: print(f"Erro PDV: {e}")
    
    return RedirectResponse(url="/pdv", status_code=303)


# ==========================================
# MÓDULO 2: ESTOQUE (COM CÓDIGO DE BARRAS)
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
    
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center' style='max-width:800px;'><h2>📦 Gestão de Estoque</h2>{add_form}<div style='max-height:400px; overflow-y:auto; border:1px solid #cbd5e1;'><table><tr><th style='color:#0f172a'>Cód. Barras</th><th style='color:#0f172a'>Produto</th><th style='color:#0f172a'>Estoque</th><th style='color:#0f172a'>Ações</th></tr>{linhas}</table></div><br><a href='/central' style='color:gray'>Voltar</a></div></div></body></html>"

@app.post("/novo_produto")
async def novo_produto(request: Request):
    f = await request.form()
    cb = f.get("codigo_barras").strip() if f.get("codigo_barras") else None
    try:
        with engine.begin() as conn: 
            conn.execute(text("INSERT INTO produtos (codigo_barras, nome, categoria, preco, estoque) VALUES (:cb, :n, :c, :p, :q) ON CONFLICT (codigo_barras) DO UPDATE SET estoque = produtos.estoque + :q"), {"cb": cb, "n": f.get("nome"), "c": f.get("cat"), "p": float(f.get("preco").replace(",", ".")), "q": int(f.get("qtd"))})
            conn.execute(text("INSERT INTO historico_estoque (produto_nome, qtd_adicionada) VALUES (:n, :q)"), {"n": f.get("nome"), "q": int(f.get("qtd"))})
    except Exception as e: print(e)
    return RedirectResponse(url="/estoque", status_code=303)

@app.post("/att_estoque")
async def att_estoque(request: Request):
    f = await request.form()
    try:
        with engine.begin() as conn: 
            conn.execute(text("UPDATE produtos SET estoque = COALESCE(estoque, 0) + :q WHERE id = :id"), {"id": f.get("id"), "q": int(f.get("q", "0"))})
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
# MÓDULO 3: RELATÓRIOS SIMPLIFICADOS
# ==========================================
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if request.session.get("role") not in ["admin", "gerente"]: return RedirectResponse(url="/central")
    hoje = date.today().strftime("%Y-%m-%d")
    
    with engine.connect() as conn:
        kpi = conn.execute(text(f"SELECT SUM(total_conta) as total FROM comandas WHERE status = 'FECHADA' AND CAST(data_fechamento AS DATE) = CAST('{hoje}' AS DATE)")).fetchone()
        faturamento_hoje = float(kpi.total or 0)
        
        pag_q = conn.execute(text(f"SELECT forma_pagamento, SUM(total_conta) as total FROM comandas WHERE status = 'FECHADA' AND CAST(data_fechamento AS DATE) = CAST('{hoje}' AS DATE) GROUP BY forma_pagamento")).fetchall()
        totais_pag = {"DINHEIRO": 0.0, "PIX": 0.0, "C. CREDITO": 0.0, "C. DEBITO": 0.0}
        for p in pag_q: totais_pag[p.forma_pagamento] = float(p.total or 0)
        
        top_db = conn.execute(text(f"SELECT item_nome, COUNT(*) as qtd FROM vendas_itens WHERE status = 'FECHADA' AND CAST(data_venda AS DATE) = CAST('{hoje}' AS DATE) GROUP BY item_nome ORDER BY qtd DESC LIMIT 5")).fetchall()
        html_top = "".join([f"<div class='item-linha'><span>{i+1}º {r.item_nome}</span><b style='color:#0ea5e9;'>{r.qtd} un</b></div>" for i, r in enumerate(top_db)])

    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'><h2>📊 Resumo do Dia ({date.today().strftime('%d/%m/%Y')})</h2><div class='grid-dash'><div class='card-kpi'><h3>Faturamento Hoje</h3><p style='color:#10b981; font-size:28px;'>R$ {faturamento_hoje:.2f}</p></div></div><div style='display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px; margin-bottom:20px;'><div style='background:#f8fafc; padding:15px; border-radius:8px; border-left:4px solid #10b981; flex:1;'><b>💵 Dinheiro:</b><br><span style='font-size:20px; color:#10b981;'>R$ {totais_pag['DINHEIRO']:.2f}</span></div><div style='background:#f8fafc; padding:15px; border-radius:8px; border-left:4px solid #0ea5e9; flex:1;'><b>💠 PIX:</b><br><span style='font-size:20px; color:#0ea5e9;'>R$ {totais_pag['PIX']:.2f}</span></div><div style='background:#f8fafc; padding:15px; border-radius:8px; border-left:4px solid #f59e0b; flex:1;'><b>💳 Cartões:</b><br><span style='font-size:20px; color:#f59e0b;'>R$ {(totais_pag['C. CREDITO'] + totais_pag['C. DEBITO']):.2f}</span></div></div><div class='chart-container'><h3 style='color:#0f172a; margin-top:0; border-bottom:2px solid #e2e8f0; padding-bottom:5px;'>🏆 Top 5 Mais Vendidos Hoje</h3>{html_top if html_top else '<p style=\"color:#64748b;\">Nenhuma venda hoje.</p>'}</div><br><a href='/central' class='btn-acao' style='background:#334155;'>Voltar</a></div></div></body></html>"


# ==========================================
# MÓDULO 4: USUÁRIOS E IMPRESSORA
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
    return f"<html><head>{CSS}</head><body><div class='container-center'><div class='card-center'><h2>Usuários</h2>{add_form}<div style='max-height:400px; overflow-y:auto; border:1px solid #cbd5e1;'><table><tr><th style='color:#0f172a'>Login</th><th style='color:#0f172a'>Cargo</th><th style='color:#0f172a'>Ação</th></tr>{linhas}</table></div><br><a href='/central' style='color:gray'>Voltar</a></div></div></body></html>"

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
