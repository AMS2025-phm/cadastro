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

# --- Configurações de Segurança e Sessão ---
# A SECRET_KEY é CRUCIAL para a segurança das sessões Flask.
# No ambiente de produção (Render), SEMPRE defina esta chave como uma Variável de Ambiente.
# Exemplo no Render: Key: SECRET_KEY, Value: sua_string_longa_e_aleatoria_aqui
# Você pode gerar uma no terminal Python com: import os; print(os.urandom(24).hex())
# Se não for definida no ambiente, usa um valor padrão APENAS para desenvolvimento local.
app.secret_key = os.environ.get('SECRET_KEY', 'uma_chave_secreta_padrao_muito_fraca_para_dev_nao_usar_em_prod')

# --- Usuários Fixos (Lista Fixa) ---
# Dicionário de usuários e senhas permitidos para autenticação.
# Essas credenciais estão HARDCODED no código.
# ALTERE ESTES VALORES para as suas credenciais desejadas.
USERS = {
    "admin": "admin123",        # Usuário de exemplo: "admin" com senha "admin123"
    "gerente": "senha_gerente", # Usuário de exemplo: "gerente" com senha "senha_gerente"
    "operador": "senha_operador" # Usuário de exemplo: "operador" com senha "senha_operador"
}

# Nome do arquivo onde os dados das localidades são armazenados.
# Este arquivo será salvo no sistema de arquivos do contêiner do Render.
# Dados salvos aqui podem persistir entre reinícios de container, mas NÃO são garantidos
# em caso de recriação completa do contêiner ou em planos gratuitos sem disco persistente dedicado.
ARQUIVO_DADOS = "localidades.json"

# Listas de opções para os campos do formulário (configuração estática).
TIPOS_PISO = [
    "Paviflex", "Cerâmica", "Porcelanato", "Granilite",
    "Cimento Queimado", "Epoxi", "Ardósia", "Outros"
]
TIPOS_MEDIDA = ["Vidro", "Sanitário-Vestiário", "Área Interna", "Área Externa"]
TIPOS_PAREDE = ["Alvenaria", "Estuque", "Divisórias"]

# --- Configurações de E-mail ---
# Lidas de variáveis de ambiente do Render para segurança e flexibilidade.
# Configure estas variáveis no Dashboard do Render para o seu serviço:
# EMAIL_USER, EMAIL_PASS, EMAIL_SERVER, EMAIL_PORT
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASS = os.environ.get('EMAIL_PASS')
EMAIL_SERVER = os.environ.get('EMAIL_SERVER')
# EMAIL_PORT é opcional; se não definida, usa 587 como padrão.
# Garante que a porta seja um inteiro.
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))

def carregar_dados():
    """Carrega os dados existentes do arquivo JSON."""
    if not os.path.exists(ARQUIVO_DADOS):
        return {}
    try:
        with open(ARQUIVO_DADOS, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Erro ao carregar {ARQUIVO_DADOS}: {e}. Retornando dicionário vazio.")
        # Pode ser útil logar a stack trace completa para depuração
        # import traceback
        # traceback.print_exc()
        return {}
    except Exception as e:
        print(f"Erro inesperado ao carregar {ARQUIVO_DADOS}: {e}.")
        return {}

def salvar_dados(dados):
    """Salva os dados no arquivo JSON."""
    try:
        with open(ARQUIVO_DADOS, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Erro ao salvar {ARQUIVO_DADOS}: {e}")

# --- Funções de Autenticação e Sessão ---

@app.before_request
def load_logged_in_user():
    """
    Carrega o usuário logado antes de cada requisição, se houver um 'user_id' na sessão.
    Isso permite que o usuário permaneça logado e o seu nome de usuário seja acessível via `g.user.username`.
    """
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        # Verifica se o user_id (username) existe na nossa lista fixa de USERS.
        g.user = {"username": user_id} if user_id in USERS else None

def login_required(view):
    """
    Decorador para rotas que exigem que o usuário esteja autenticado.
    Se o usuário não estiver logado, redireciona para a página de login.
    """
    @wraps(view) # Importante para preservar metadados da função original
    def wrapped_view(**kwargs):
        if g.user is None:
            flash('Você precisa estar logado para acessar esta página.', 'danger')
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

# --- Rotas de Autenticação ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Rota para o formulário de login e processamento da autenticação.
    Se o usuário já estiver logado, redireciona para a página inicial.
    """
    if g.user: # Se já estiver logado, redireciona para a página principal
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        error = None
        if username not in USERS:
            error = 'Nome de usuário incorreto.'
        elif USERS[username] != password: # Comparação direta de senha (não ideal para produção real)
            error = 'Senha incorreta.'

        if error is None:
            session.clear() # Limpa qualquer sessão anterior para evitar conflitos
            session['user_id'] = username # Armazena o username na sessão
            flash(f'Bem-vindo, {username}!', 'success')
            return redirect(url_for('index'))
        else:
            flash(error, 'danger') # Exibe mensagem de erro
            
    return render_template('login.html')

@app.route('/logout')
@login_required # Garante que apenas usuários logados podem fazer logout (melhoria de UX)
def logout():
    """Rota para logout de usuários."""
    flash('Você foi desconectado.', 'success')
    session.clear() # Limpa a sessão
    return redirect(url_for('login'))

# --- Rotas Principais da Aplicação (Protegidas por @login_required) ---

@app.route('/')
@login_required
def index():
    """
    Página inicial da aplicação. Exibe formulário de cadastro de unidades
    e lista de localidades existentes.
    """
    dados = carregar_dados()
    localidades = list(dados.keys()) # Obtém apenas os nomes das localidades
    
    # Prepara as listas de localidades para o select2 (frontend JavaScript)
    localidades_para_select = [{"id": loc, "text": loc} for loc in sorted(localidades)]

    return render_template(
        'index.html',
        tipos_piso=TIPOS_PISO,
        tipos_medida=TIPOS_MEDIDA,
        tipos_parede=TIPOS_PAREDE,
        localidades=localidades,
        localidades_json=json.dumps(localidades_para_select) # Passa como JSON para o JS
    )

@app.route('/nova_localidade', methods=['GET', 'POST'])
@login_required
def nova_localidade():
    """Permite adicionar uma nova localidade ao sistema."""
    if request.method == 'POST':
        nome_localidade = request.form['nome'].strip()
        if not nome_localidade:
            flash('O nome da localidade não pode ser vazio.', 'danger')
            return redirect(url_for('nova_localidade'))

        dados = carregar_dados()
        if nome_localidade in dados:
            flash(f'A localidade "{nome_localidade}" já existe.', 'danger')
        else:
            dados[nome_localidade] = [] # Cria uma nova localidade vazia
            salvar_dados(dados)
            flash(f'Localidade "{nome_localidade}" adicionada com sucesso!', 'success')
            return redirect(url_for('index')) # Redireciona para a página principal após adicionar

    return render_template('nova_localidade.html')


@app.route('/adicionar_unidade', methods=['POST'])
@login_required
def adicionar_unidade():
    """Rota para adicionar uma nova unidade a uma localidade existente."""
    localidade_nome = request.form['localidade_nome']
    unidade_nome = request.form['unidade_nome']
    data = request.form['data']
    responsavel = request.form['responsavel']
    tipo_piso = request.form['tipo_piso']
    
    # Campos de Comprimento/Largura (para tratamento de vírgulas e conversão para float)
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

    tipo_parede = request.form['tipo_parede']
    observacoes_gerais = request.form['observacoes_gerais']

    # Recupera as medidas dinâmicas do campo oculto (JSON string)
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

    # Verifica se a unidade já existe dentro da localidade (opcional)
    for unidade in dados[localidade_nome]:
        if unidade['nome'] == unidade_nome:
            flash(f'Já existe uma unidade com o nome "{unidade_nome}" na localidade "{localidade_nome}".', 'danger')
            return redirect(url_for('index'))

    nova_unidade = {
        "id": str(datetime.datetime.now().timestamp()), # ID único baseado no timestamp
        "nome": unidade_nome,
        "data": data,
        "responsavel": responsavel,
        "tipo_piso": tipo_piso,
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
        "tipo_parede": tipo_parede,
        "observacoes_gerais": observacoes_gerais,
        "medidas": json.dumps(medidas_dinamicas) # Armazena as medidas dinâmicas como string JSON
    }

    dados[localidade_nome].append(nova_unidade)
    salvar_dados(dados)
    flash(f'Unidade "{unidade_nome}" adicionada com sucesso à localidade "{localidade_nome}"!', 'success')

    # Após salvar, tenta enviar o e-mail
    try:
        # Chama a função de envio de e-mail. Ela já imprime mensagens no console/logs.
        enviar_excel_por_email(localidade_nome, nova_unidade, dados)
    except Exception as e:
        flash(f'Unidade salva, mas houve um erro ao enviar o e-mail: {e}', 'warning')
        print(f"Erro ao enviar e-mail na rota adicionar_unidade: {e}") # Loga o erro para depuração no Render

    return redirect(url_for('index'))


@app.route('/ver_localidade/<nome_localidade>')
@login_required
def ver_localidade(nome_localidade):
    """Exibe as unidades cadastradas para uma localidade específica."""
    dados = carregar_dados()
    localidade_info = {
        "nome": nome_localidade,
        "unidades": dados.get(nome_localidade, [])
    }
    return render_template('ver_localidade.html', localidade=localidade_info)

@app.route('/salvar_unidade/<nome_localidade>/<id_unidade>', methods=['POST'])
@login_required
def salvar_unidade(nome_localidade, id_unidade):
    """
    Atualiza os dados de uma unidade específica.
    Recebe os dados do formulário de edição via AJAX.
    """
    dados = carregar_dados()
    localidade_unidades = dados.get(nome_localidade, [])

    for i, unidade in enumerate(localidade_unidades):
        if unidade.get('id') == id_unidade:
            try:
                # Atualiza os campos com os dados do formulário
                unidade['nome'] = request.form.get('nome')
                unidade['data'] = request.form.get('data')
                unidade['responsavel'] = request.form.get('responsavel')
                unidade['tipo_piso'] = request.form.get('tipo_piso')
                
                # Tratamento de vírgulas para campos numéricos
                unidade['area_interna_comprimento'] = request.form.get('area_interna_comprimento', '').replace(',', '.')
                unidade['area_interna_largura'] = request.form.get('area_interna_largura', '').replace(',', '.')
                unidade['area_externa_comprimento'] = request.form.get('area_externa_comprimento', '').replace(',', '.')
                unidade['area_externa_largura'] = request.form.get('area_externa_largura', '').replace(',', '.')
                unidade['vestiario_comprimento'] = request.form.get('vestiario_comprimento', '').replace(',', '.')
                unidade['vestiario_largura'] = request.form.get('vestiario_largura', '').replace(',', '.')

                unidade['tem_vidros'] = request.form.get('tem_vidros') == 'True' # Campo checkbox
                unidade['vidros_tipo'] = request.form.get('vidros_tipo', '')
                unidade['vidros_quantidade'] = request.form.get('vidros_quantidade', '')
                unidade['vidros_observacao'] = request.form.get('vidros_observacao', '')
                unidade['tipo_parede'] = request.form.get('tipo_parede')
                unidade['observacoes_gerais'] = request.form.get('observacoes_gerais')
                
                # As medidas dinâmicas vêm como string JSON
                medidas_json_str = request.form.get('medidas_dinamicas_json', '[]')
                unidade['medidas'] = medidas_json_str

                salvar_dados(dados)
                flash('Unidade atualizada com sucesso!', 'success')
                return jsonify({"status": "success", "message": "Unidade atualizada com sucesso!"}), 200

            except Exception as e:
                flash(f'Erro ao atualizar unidade: {e}', 'danger')
                print(f"Erro ao atualizar unidade: {e}")
                return jsonify({"status": "error", "message": f"Erro ao atualizar unidade: {e}"}), 500
    
    flash('Unidade não encontrada.', 'danger')
    return jsonify({"status": "error", "message": "Unidade não encontrada."}), 404

@app.route('/excluir_unidade/<nome_localidade>/<id_unidade>', methods=['POST'])
@login_required
def excluir_unidade(nome_localidade, id_unidade):
    """
    Exclui uma unidade específica de uma localidade.
    """
    dados = carregar_dados()
    
    if nome_localidade not in dados:
        flash(f'Localidade "{nome_localidade}" não encontrada.', 'danger')
        return jsonify({"status": "error", "message": "Localidade não encontrada."}), 404

    unidades_atuais = dados[nome_localidade]
    
    # Cria uma nova lista de unidades excluindo a que corresponde ao id_unidade
    unidades_atualizadas = [u for u in unidades_atuais if u.get('id') != id_unidade]
    
    if len(unidades_atuais) == len(unidades_atualizadas):
        # A unidade não foi encontrada se as listas tiverem o mesmo tamanho
        flash(f'Unidade com ID "{id_unidade}" não encontrada na localidade "{nome_localidade}".', 'danger')
        return jsonify({"status": "error", "message": "Unidade não encontrada."}), 404
    
    dados[nome_localidade] = unidades_atualizadas
    salvar_dados(dados)
    flash('Unidade excluída com sucesso!', 'success')
    return jsonify({"status": "success", "message": "Unidade excluída com sucesso!"}), 200


@app.route('/download_excel/<nome_localidade>')
@login_required
def download_excel(nome_localidade):
    """
    Gera e permite o download de um arquivo Excel para uma localidade.
    """
    dados = carregar_dados()
    localidade = dados.get(nome_localidade)

    if not localidade:
        flash(f'Localidade "{nome_localidade}" não encontrada.', 'danger')
        return redirect(url_for('index'))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Unidades de {nome_localidade}"

    # Cabeçalho do Excel
    headers = [
        "Localidade", "Nome da Unidade", "Data", "Responsável", "Tipo de Piso",
        "Área Interna (C)", "Área Interna (L)", "Área Externa (C)", "Área Externa (L)",
        "Vestiário (C)", "Vestiário (L)",
        "Tem Vidros", "Tipo de Vidro", "Quantidade de Vidros", "Observação Vidros",
        "Tipo de Parede", "Observações Gerais", "Medidas Detalhadas"
    ]
    ws.append(headers)

    # Preenche as linhas com os dados das unidades
    for unidade in localidade:
        medidas_detalhadas = ""
        try:
            medidas_json = json.loads(unidade.get('medidas', '[]'))
            medidas_detalhadas = "; ".join([f"{tipo}: {c}x{l}={a}m²" for tipo, c, l, a in medidas_json])
        except json.JSONDecodeError:
            medidas_detalhadas = "Erro ao carregar medidas."
        
        row = [
            nome_localidade,
            unidade.get('nome'),
            unidade.get('data'),
            unidade.get('responsavel'),
            unidade.get('tipo_piso'),
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
            unidade.get('tipo_parede'),
            unidade.get('observacoes_gerais'),
            medidas_detalhadas
        ]
        ws.append(row)

    # Salva o arquivo Excel em memória
    excel_file_in_memory = io.BytesIO()
    wb.save(excel_file_in_memory)
    excel_file_in_memory.seek(0)

    # Para download no navegador
    from flask import send_file
    return send_file(
        excel_file_in_memory,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'cadastro_{nome_localidade}.xlsx'
    )

def enviar_excel_por_email(local, info_unidade_adicionada, dados_completos):
    """
    Gera um arquivo Excel da localidade e envia por e-mail.
    Esta função imprime logs e não retorna jsonify, pois é chamada dentro de uma rota que já tem um retorno.
    Parâmetros:
        local (str): O nome da localidade.
        info_unidade_adicionada (dict): As informações da unidade recém-adicionada.
        dados_completos (dict): Todos os dados do aplicativo (necessário para gerar o Excel completo).
    """
    # Verifica se as configurações de e-mail estão presentes.
    if not EMAIL_USER or not EMAIL_PASS or not EMAIL_SERVER:
        print("Configurações de e-mail ausentes (EMAIL_USER, EMAIL_PASS, EMAIL_SERVER). Não será possível enviar o e-mail.")
        return # Sai da função

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Unidades de {local}"

    # Cabeçalho do Excel
    headers = [
        "Localidade", "Nome da Unidade", "Data", "Responsável", "Tipo de Piso",
        "Área Interna (C)", "Área Interna (L)", "Área Externa (C)", "Área Externa (L)",
        "Vestiário (C)", "Vestiário (L)",
        "Tem Vidros", "Tipo de Vidro", "Quantidade de Vidros", "Observação Vidros",
        "Tipo de Parede", "Observações Gerais", "Medidas Detalhadas"
    ]
    ws.append(headers)

    # Preenche as linhas com os dados de TODAS as unidades da localidade (dados_completos.get(local, []))
    for unidade in dados_completos.get(local, []):
        medidas_detalhadas = ""
        try:
            medidas_json = json.loads(unidade.get('medidas', '[]'))
            medidas_detalhadas = "; ".join([f"{tipo}: {c}x{l}={a}m²" for tipo, c, l, a in medidas_json])
        except json.JSONDecodeError:
            medidas_detalhadas = "Erro ao carregar medidas."
        
        row = [
            local,
            unidade.get('nome'),
            unidade.get('data'),
            unidade.get('responsavel'),
            unidade.get('tipo_piso'),
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
            unidade.get('tipo_parede'),
            unidade.get('observacoes_gerais'),
            medidas_detalhadas
        ]
        ws.append(row)

    # Salva o arquivo Excel em memória
    excel_file_in_memory = io.BytesIO()
    wb.save(excel_file_in_memory)
    excel_file_in_memory.seek(0) # Volta ao início do arquivo em memória para leitura

    # Configuração do e-mail
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_USER # Pode ser um destinatário fixo ou configurável via variável de ambiente
    msg['Subject'] = f"Nova Unidade Cadastrada: {info_unidade_adicionada.get('nome', 'N/A')} em {local}"

    # Gera um nome de arquivo único para o anexo
    nome_arquivo = f"cadastro_{local.replace(' ', '_')}_{info_unidade_adicionada.get('nome', 'unidade').replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"

    # Corpo do e-mail
    body = f"""
    Uma nova unidade foi cadastrada no sistema.

    Detalhes da Unidade Recém-Adicionada:
    Localidade: {local}
    Nome da Unidade: {info_unidade_adicionada.get('nome', 'Não informado')}
    Data: {info_unidade_adicionada.get('data', 'Não informada')}
    Responsável: {info_unidade_adicionada.get('responsavel', 'Não informado')}

    O arquivo Excel com todos os dados atualizados da localidade "{local}" está anexado.

    Atenciosamente,
    Seu Sistema de Cadastro
    """
    
    msg.attach(MIMEText(body, 'plain', 'utf-8')) # Anexa o corpo do e-mail como texto puro

    # Anexando o arquivo Excel
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(excel_file_in_memory.read())
    encoders.encode_base64(part) # Codifica o anexo em base64
    part.add_header('Content-Disposition', f'attachment; filename=\"{nome_arquivo}\"')
    msg.attach(part)

    try:
        # Tenta enviar o e-mail via SMTP
        # O Render geralmente suporta a porta 587 com STARTTLS.
        with smtplib.SMTP(EMAIL_SERVER, EMAIL_PORT) as server:
            server.starttls()  # Inicia TLS para comunicação segura
            server.login(EMAIL_USER, EMAIL_PASS) # Autentica com o servidor SMTP
            server.send_message(msg) # Envia a mensagem completa
        
        print(f"E-mail enviado com sucesso para {EMAIL_USER} sobre {local} - {info_unidade_adicionada.get('nome', 'N/A')}")

    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}") # Loga o erro para depuração no Render
        # Não está retornando jsonify aqui, pois a rota adicionar_unidade já cuida do redirecionamento/flash.

# Esta parte só é executada quando o script é rodado diretamente (e.g., python app.py)
# Não será executada quando o gunicorn iniciar a aplicação no Render.
if __name__ == '__main__':
    # Para desenvolvimento local, você pode definir DEBUG=True.
    # Em produção (Render), o modo debug deve ser DESATIVADO por segurança.
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1', port=int(os.environ.get('PORT', 5000)))