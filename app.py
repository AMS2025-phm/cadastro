from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, g
import json
import os
import datetime
import openpyxl
import io
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from functools import wraps # Importar wraps para o decorador

app = Flask(__name__)

# Adicionar filtro from_json para Jinja2
@app.template_filter('from_json')
def from_json_filter(value):
    import json
    if isinstance(value, list): # Se já for uma lista, retorna ela mesma
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return [] # Retorna lista vazia em caso de erro no parsing
    return []


# --- Configurações de Segurança e Sessão ---
app.secret_key = os.environ.get('SECRET_KEY', 'uma_chave_secreta_padrao_muito_fraca_para_dev_nao_usar_em_prod')

# --- Usuários Fixos (Lista Fixa) ---
USERS = {
    "admin": "admin123",
    "gerente": "senha_gerente",
    "operador": "senha_operador"
}

ARQUIVO_DADOS = "localidades.json"

TIPOS_PISO = [
    "Paviflex", "Cerâmica", "Porcelanato", "Granilite",
    "Cimento Queimado", "Epoxi", "Ardósia", "Outros"
]
TIPOS_MEDIDA = ["Vidro", "Sanitário-Vestiário", "Área Interna", "Área Externa"] # Mantido como no original
TIPOS_PAREDE = ["Alvenaria", "Estuque", "Divisórias", "Outros"] # Adicionado "Outros" como exemplo

# --- Configurações de E-mail ---
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASS = os.environ.get('EMAIL_PASS')
EMAIL_SERVER = os.environ.get('EMAIL_SERVER')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_RECIPIENT = "comercialservico2025@gmail.com" # Destinatário fixo conforme solicitado

def carregar_dados():
    if not os.path.exists(ARQUIVO_DADOS):
        return {}
    try:
        with open(ARQUIVO_DADOS, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Erro ao carregar {ARQUIVO_DADOS}: {e}. Retornando dicionário vazio.")
        return {}
    except Exception as e:
        print(f"Erro inesperado ao carregar {ARQUIVO_DADOS}: {e}.")
        return {}

def salvar_dados(dados):
    try:
        with open(ARQUIVO_DADOS, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)
        print(f"Dados salvos com sucesso em {ARQUIVO_DADOS}") # Log para Render
    except Exception as e:
        print(f"Erro crítico ao salvar {ARQUIVO_DADOS}: {e}") # Log para Render
        # Considerar lançar uma exceção aqui ou retornar False para indicar falha
        # flash(f"Erro crítico ao tentar salvar os dados no servidor: {e}", "danger") # Isso não funcionaria aqui diretamente

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = {"username": user_id} if user_id in USERS else None

def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash('Você precisa estar logado para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        error = None
        if username not in USERS:
            error = 'Nome de usuário incorreto.'
        elif USERS[username] != password:
            error = 'Senha incorreta.'
        if error is None:
            session.clear()
            session['user_id'] = username
            flash(f'Bem-vindo, {username}!', 'success')
            return redirect(url_for('index'))
        else:
            flash(error, 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    flash('Você foi desconectado.', 'success')
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    dados = carregar_dados()
    localidades = list(dados.keys())
    localidades_para_select = [{"id": loc, "text": loc} for loc in sorted(localidades)]
    return render_template(
        'index.html',
        tipos_piso=TIPOS_PISO,
        tipos_medida=TIPOS_MEDIDA, # Mantido para Medidas Dinâmicas
        tipos_parede=TIPOS_PAREDE,
        localidades=localidades,
        localidades_json=json.dumps(localidades_para_select)
    )

@app.route('/nova_localidade', methods=['GET', 'POST'])
@login_required
def nova_localidade():
    if request.method == 'POST':
        nome_localidade = request.form['nome'].strip()
        if not nome_localidade:
            flash('O nome da localidade não pode ser vazio.', 'danger')
            return redirect(url_for('nova_localidade'))
        dados = carregar_dados()
        if nome_localidade in dados:
            flash(f'A localidade "{nome_localidade}" já existe.', 'danger')
        else:
            dados[nome_localidade] = []
            salvar_dados(dados) # Chamar salvar_dados aqui
            flash(f'Localidade "{nome_localidade}" adicionada com sucesso!', 'success')
            return redirect(url_for('index'))
    return render_template('nova_localidade.html')

@app.route('/adicionar_unidade', methods=['POST'])
@login_required
def adicionar_unidade():
    localidade_nome = request.form['localidade_nome']
    unidade_nome = request.form['unidade_nome']
    data = request.form['data']
    responsavel = request.form['responsavel']
    
    tipos_piso_selecionados = request.form.getlist('tipo_piso') # Ponto 1: Múltiplos pisos
    tipos_parede_selecionados = request.form.getlist('tipo_parede') # Ponto 3: Múltiplas paredes

    area_interna_comprimento = request.form.get('area_interna_comprimento', '').replace(',', '.')
    area_interna_largura = request.form.get('area_interna_largura', '').replace(',', '.')
    area_externa_comprimento = request.form.get('area_externa_comprimento', '').replace(',', '.')
    area_externa_largura = request.form.get('area_externa_largura', '').replace(',', '.')
    vestiario_comprimento = request.form.get('vestiario_comprimento', '').replace(',', '.')
    vestiario_largura = request.form.get('vestiario_largura', '').replace(',', '.')

    tem_vidros = request.form.get('tem_vidros') == 'sim'
    vidros_tipo = request.form.get('vidros_tipo', '') if tem_vidros else ''
    vidros_quantidade = request.form.get('vidros_quantidade', '') if tem_vidros else ''
    vidros_observacao = request.form.get('vidros_observacao', '') if tem_vidros else ''
    
    # Ponto 2: Vidro Alto e Perigo
    possui_vidro_alto = request.form.get('possui_vidro_alto') == 'sim' if tem_vidros else False
    vidro_alto_perigoso = request.form.get('vidro_alto_perigoso') == 'sim' if possui_vidro_alto else False

    observacoes_gerais = request.form['observacoes_gerais']
    medidas_json_str = request.form.get('medidas_dinamicas_json', '[]')
    try:
        medidas_dinamicas = json.loads(medidas_json_str)
    except json.JSONDecodeError:
        flash('Erro ao processar medidas dinâmicas. Formato inválido.', 'danger')
        return redirect(url_for('index'))

    dados = carregar_dados()
    if localidade_nome not in dados:
        flash(f'Localidade "{localidade_nome}" não encontrada.', 'danger')
        return redirect(url_for('index'))

    for unidade_existente in dados[localidade_nome]:
        if unidade_existente.get('nome') == unidade_nome: # Adicionado .get para segurança
            flash(f'Já existe uma unidade com o nome "{unidade_nome}" na localidade "{localidade_nome}".', 'danger')
            return redirect(url_for('index'))

    nova_unidade = {
        "id": str(datetime.datetime.now().timestamp()),
        "nome": unidade_nome,
        "data": data,
        "responsavel": responsavel,
        "tipos_piso": tipos_piso_selecionados, # Ponto 1
        "area_interna_comprimento": area_interna_comprimento,
        "area_interna_largura": area_interna_largura,
        "area_externa_comprimento": area_externa_comprimento,
        "area_externa_largura": area_externa_largura,
        "vestiario_comprimento": vestiario_comprimento,
        "vestiario_largura": vestiario_largura,
        "tem_vidros": tem_vidros,
        "vidros_tipo": vidros_tipo,
        "vidros_quantidade": vidros_quantidade,
        "vidros_observacao": vidros_observacao,
        "possui_vidro_alto": possui_vidro_alto, # Ponto 2
        "vidro_alto_perigoso": vidro_alto_perigoso, # Ponto 2
        "tipos_parede": tipos_parede_selecionados, # Ponto 3
        "observacoes_gerais": observacoes_gerais,
        "medidas": json.dumps(medidas_dinamicas)
    }

    dados[localidade_nome].append(nova_unidade)
    
    print(f"Tentando salvar dados para {localidade_nome}...") # Log
    salvar_dados(dados) # A função salvar_dados já imprime seu próprio log

    flash(f'Unidade "{unidade_nome}" adicionada com sucesso à localidade "{localidade_nome}"!', 'success')
    
    # Após salvar, tenta enviar o e-mail
    print(f"Tentando enviar email para {EMAIL_RECIPIENT}...") # Log
    try:
        enviar_excel_por_email(localidade_nome, nova_unidade, dados)
    except Exception as e:
        flash(f'Unidade salva, mas houve um erro ao enviar o e-mail: {e}', 'warning')
        print(f"Erro ao enviar e-mail na rota adicionar_unidade: {e}")

    return redirect(url_for('index'))


@app.route('/ver_localidade/<nome_localidade>')
@login_required
def ver_localidade(nome_localidade):
    dados = carregar_dados()
    unidades = dados.get(nome_localidade, [])
    
    # Passar TIPOS_PISO, TIPOS_PAREDE, TIPOS_MEDIDA para o template do modal de edição
    localidade_info = {
        "nome": nome_localidade,
        "unidades": unidades
    }
    return render_template(
        'ver_localidade.html', 
        localidade=localidade_info,
        tipos_piso_json=json.dumps(TIPOS_PISO), # Passa como JSON para JS
        tipos_parede_json=json.dumps(TIPOS_PAREDE), # Passa como JSON para JS
        tipos_medida_json=json.dumps(TIPOS_MEDIDA) # Passa como JSON para JS
        # As listas em si também são passadas para o Jinja, se necessário para preencher selects no HTML diretamente
        ,tipos_piso=TIPOS_PISO 
        ,tipos_parede=TIPOS_PAREDE
        ,tipos_medida=TIPOS_MEDIDA
    )


@app.route('/salvar_unidade/<nome_localidade>/<id_unidade>', methods=['POST'])
@login_required
def salvar_unidade(nome_localidade, id_unidade):
    dados = carregar_dados()
    localidade_unidades = dados.get(nome_localidade, [])
    unidade_encontrada = False

    for i, unidade in enumerate(localidade_unidades):
        if unidade.get('id') == id_unidade:
            unidade_encontrada = True
            try:
                unidade['nome'] = request.form.get('nome')
                unidade['data'] = request.form.get('data')
                unidade['responsavel'] = request.form.get('responsavel')
                
                unidade['tipos_piso'] = request.form.getlist('tipos_piso') # Ponto 1
                
                unidade['area_interna_comprimento'] = request.form.get('area_interna_comprimento', '').replace(',', '.')
                unidade['area_interna_largura'] = request.form.get('area_interna_largura', '').replace(',', '.')
                unidade['area_externa_comprimento'] = request.form.get('area_externa_comprimento', '').replace(',', '.')
                unidade['area_externa_largura'] = request.form.get('area_externa_largura', '').replace(',', '.')
                unidade['vestiario_comprimento'] = request.form.get('vestiario_comprimento', '').replace(',', '.')
                unidade['vestiario_largura'] = request.form.get('vestiario_largura', '').replace(',', '.')

                unidade['tem_vidros'] = request.form.get('tem_vidros') == 'True' # Veio do form como string 'True'/'False'
                unidade['vidros_tipo'] = request.form.get('vidros_tipo', '')
                unidade['vidros_quantidade'] = request.form.get('vidros_quantidade', '')
                unidade['vidros_observacao'] = request.form.get('vidros_observacao', '')

                # Ponto 2: Vidro Alto e Perigo na edição
                unidade['possui_vidro_alto'] = request.form.get('possui_vidro_alto') == 'True' if unidade['tem_vidros'] else False
                unidade['vidro_alto_perigoso'] = request.form.get('vidro_alto_perigoso') == 'True' if unidade['possui_vidro_alto'] else False
                
                unidade['tipos_parede'] = request.form.getlist('tipos_parede') # Ponto 3
                unidade['observacoes_gerais'] = request.form.get('observacoes_gerais')
                
                medidas_json_str = request.form.get('medidas_dinamicas_json', '[]')
                unidade['medidas'] = medidas_json_str # Já é string JSON

                dados[nome_localidade][i] = unidade # Atualiza a unidade na lista
                salvar_dados(dados)
                flash('Unidade atualizada com sucesso!', 'success')
                return jsonify({"status": "success", "message": "Unidade atualizada com sucesso!"}), 200

            except Exception as e:
                print(f"Erro ao atualizar unidade {id_unidade}: {e}")
                flash(f'Erro ao atualizar unidade: {e}', 'danger')
                return jsonify({"status": "error", "message": f"Erro ao atualizar unidade: {e}"}), 500
    
    if not unidade_encontrada:
        flash('Unidade não encontrada.', 'danger')
        return jsonify({"status": "error", "message": "Unidade não encontrada."}), 404


@app.route('/excluir_unidade/<nome_localidade>/<id_unidade>', methods=['POST'])
@login_required
def excluir_unidade(nome_localidade, id_unidade):
    dados = carregar_dados()
    if nome_localidade not in dados:
        flash(f'Localidade "{nome_localidade}" não encontrada.', 'danger')
        return jsonify({"status": "error", "message": "Localidade não encontrada."}), 404

    unidades_atuais = dados[nome_localidade]
    unidades_atualizadas = [u for u in unidades_atuais if u.get('id') != id_unidade]
    
    if len(unidades_atuais) == len(unidades_atualizadas):
        flash(f'Unidade com ID "{id_unidade}" não encontrada na localidade "{nome_localidade}".', 'danger')
        return jsonify({"status": "error", "message": "Unidade não encontrada."}), 404
    
    dados[nome_localidade] = unidades_atualizadas
    salvar_dados(dados)
    flash('Unidade excluída com sucesso!', 'success')
    return jsonify({"status": "success", "message": "Unidade excluída com sucesso!"}), 200


@app.route('/download_excel/<nome_localidade>')
@login_required
def download_excel(nome_localidade):
    dados = carregar_dados()
    unidades_localidade = dados.get(nome_localidade) # Renomeado para clareza

    if not unidades_localidade:
        flash(f'Localidade "{nome_localidade}" não encontrada ou sem unidades.', 'danger')
        return redirect(url_for('index'))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Unidades de {nome_localidade}"

    headers = [
        "Localidade", "Nome da Unidade", "Data", "Responsável", 
        "Tipos de Piso", # Modificado
        "Área Interna (C)", "Área Interna (L)", "Área Externa (C)", "Área Externa (L)",
        "Vestiário (C)", "Vestiário (L)",
        "Tem Vidros", "Tipo de Vidro", "Quantidade de Vidros", "Observação Vidros",
        "Possui Vidro Alto", "Vidro Alto é Perigoso", # Adicionado Ponto 2
        "Tipos de Parede", # Modificado
        "Observações Gerais", "Medidas Detalhadas"
    ]
    ws.append(headers)

    for unidade in unidades_localidade:
        medidas_detalhadas_str = ""
        try:
            # 'medidas' já é uma string JSON, precisa ser carregada
            medidas_lista = json.loads(unidade.get('medidas', '[]'))
            medidas_detalhadas_str = "; ".join([f"{tipo}: {c}x{l}={a}m²" for tipo, c, l, a in medidas_lista])
        except json.JSONDecodeError:
            medidas_detalhadas_str = "Erro ao carregar medidas."
        
        row = [
            nome_localidade,
            unidade.get('nome'),
            unidade.get('data'),
            unidade.get('responsavel'),
            ", ".join(unidade.get('tipos_piso', [])), # Ponto 1
            unidade.get('area_interna_comprimento'),
            unidade.get('area_interna_largura'),
            unidade.get('area_externa_comprimento'),
            unidade.get('area_externa_largura'),
            unidade.get('vestiario_comprimento'),
            unidade.get('vestiario_largura'),
            "Sim" if unidade.get('tem_vidros') else "Não",
            unidade.get('vidros_tipo'),
            unidade.get('vidros_quantidade'),
            unidade.get('vidros_observacao'),
            "Sim" if unidade.get('possui_vidro_alto') else "Não", # Ponto 2
            "Sim" if unidade.get('vidro_alto_perigoso') else "Não", # Ponto 2
            ", ".join(unidade.get('tipos_parede', [])), # Ponto 3
            unidade.get('observacoes_gerais'),
            medidas_detalhadas_str
        ]
        ws.append(row)

    excel_file_in_memory = io.BytesIO()
    wb.save(excel_file_in_memory)
    excel_file_in_memory.seek(0)

    from flask import send_file
    return send_file(
        excel_file_in_memory,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'cadastro_{nome_localidade}.xlsx'
    )

def enviar_excel_por_email(local, info_unidade_adicionada, dados_completos):
    if not EMAIL_USER or not EMAIL_PASS or not EMAIL_SERVER:
        print("Configurações de e-mail ausentes (EMAIL_USER, EMAIL_PASS, EMAIL_SERVER). Não será possível enviar o e-mail.")
        # flash("Configurações de e-mail do servidor incompletas. E-mail não enviado.", "warning") # Isso não funciona bem aqui
        return

    print(f"Iniciando geração de Excel para e-mail - Local: {local}")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Unidades de {local}"

    headers = [
        "Localidade", "Nome da Unidade", "Data", "Responsável", 
        "Tipos de Piso", # Modificado
        "Área Interna (C)", "Área Interna (L)", "Área Externa (C)", "Área Externa (L)",
        "Vestiário (C)", "Vestiário (L)",
        "Tem Vidros", "Tipo de Vidro", "Quantidade de Vidros", "Observação Vidros",
        "Possui Vidro Alto", "Vidro Alto é Perigoso", # Adicionado Ponto 2
        "Tipos de Parede", # Modificado
        "Observações Gerais", "Medidas Detalhadas"
    ]
    ws.append(headers)

    unidades_da_localidade = dados_completos.get(local, [])
    if not unidades_da_localidade:
        print(f"Nenhuma unidade encontrada para a localidade {local} ao gerar e-mail.")
        # Não envia e-mail se não há unidades, ou envia um e-mail de aviso? Por ora, não envia.
        return

    for unidade in unidades_da_localidade:
        medidas_detalhadas_str = ""
        try:
            medidas_lista = json.loads(unidade.get('medidas', '[]')) # 'medidas' é string JSON
            medidas_detalhadas_str = "; ".join([f"{tipo}: {c}x{l}={a}m²" for tipo, c, l, a in medidas_lista])
        except json.JSONDecodeError:
            medidas_detalhadas_str = "Erro ao carregar medidas."
        
        row = [
            local,
            unidade.get('nome'),
            unidade.get('data'),
            unidade.get('responsavel'),
            ", ".join(unidade.get('tipos_piso', [])), # Ponto 1
            unidade.get('area_interna_comprimento'),
            unidade.get('area_interna_largura'),
            unidade.get('area_externa_comprimento'),
            unidade.get('area_externa_largura'),
            unidade.get('vestiario_comprimento'),
            unidade.get('vestiario_largura'),
            "Sim" if unidade.get('tem_vidros') else "Não",
            unidade.get('vidros_tipo'),
            unidade.get('vidros_quantidade'),
            unidade.get('vidros_observacao'),
            "Sim" if unidade.get('possui_vidro_alto') else "Não", # Ponto 2
            "Sim" if unidade.get('vidro_alto_perigoso') else "Não", # Ponto 2
            ", ".join(unidade.get('tipos_parede', [])), # Ponto 3
            unidade.get('observacoes_gerais'),
            medidas_detalhadas_str
        ]
        ws.append(row)

    excel_file_in_memory = io.BytesIO()
    wb.save(excel_file_in_memory)
    excel_file_in_memory.seek(0)

    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_RECIPIENT # Ponto 5: Destinatário alterado
    msg['Subject'] = f"Nova Unidade Cadastrada: {info_unidade_adicionada.get('nome', 'N/A')} em {local}"

    nome_arquivo = f"cadastro_{local.replace(' ', '_')}_{info_unidade_adicionada.get('nome', 'unidade').replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    
    body = f"""
    Uma nova unidade foi cadastrada no sistema.

    Detalhes da Unidade Recém-Adicionada:
    Localidade: {local}
    Nome da Unidade: {info_unidade_adicionada.get('nome', 'Não informado')}
    Data: {info_unidade_adicionada.get('data', 'Não informada')}
    Responsável: {info_unidade_adicionada.get('responsavel', 'Não informado')}

    O arquivo Excel com todos os dados atualizados da localidade "{local}" está anexado.

    Atenciosamente,
    Sistema de Cadastro de Unidades
    """
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    part = MIMEBase('application', 'octet-stream')
    part.set_payload(excel_file_in_memory.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f'attachment; filename=\"{nome_arquivo}\"')
    msg.attach(part)

    try:
        print(f"Tentando conexão SMTP com {EMAIL_SERVER}:{EMAIL_PORT}...")
        with smtplib.SMTP(EMAIL_SERVER, EMAIL_PORT) as server:
            print("Conexão SMTP estabelecida. Tentando STARTTLS...")
            server.starttls()
            print("STARTTLS bem-sucedido. Tentando login...")
            server.login(EMAIL_USER, EMAIL_PASS)
            print(f"Login SMTP bem-sucedido. Enviando mensagem para {EMAIL_RECIPIENT}...")
            server.send_message(msg)
            print(f"E-mail enviado com sucesso para {EMAIL_RECIPIENT} sobre {local} - {info_unidade_adicionada.get('nome', 'N/A')}")
    except Exception as e:
        print(f"Falha crítica ao enviar e-mail: {e}")
        # Re-lançar a exceção pode ser útil para que a rota que chamou saiba da falha.
        # Ou lidar com isso de outra forma, mas o flash message será na rota 'adicionar_unidade'.
        raise e # Para que a rota adicionar_unidade capture e mostre o flash message


if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1', port=int(os.environ.get('PORT', 5000)))