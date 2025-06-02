from flask import Flask, render_template, request, jsonify
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

app = Flask(__name__)

# Nome do arquivo onde os dados são armazenados
ARQUIVO_DADOS = "localidades.json"

# Listas de opções para os campos do formulário
TIPOS_PISO = [
    "Paviflex", "Cerâmica", "Porcelanato", "Granilite",
    "Cimento Queimado", "Epoxi", "Ardósia", "Outros"
]
TIPOS_MEDIDA = ["Vidro", "Sanitário-Vestiário", "Área Interna", "Área Externa"]
TIPOS_PAREDE = ["Alvenaria", "Estuque", "Divisórias"]

# --- Configurações de E-mail (Lidas de variáveis de ambiente do Render) ---
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASS = os.environ.get('EMAIL_PASS')
EMAIL_SERVER = os.environ.get('EMAIL_SERVER')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587)) # Padrão 587, converte para int

def carregar_dados():
    """Carrega os dados existentes do arquivo JSON."""
    if os.path.exists(ARQUIVO_DADOS):
        with open(ARQUIVO_DADOS, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_dados(dados):
    """Salva os dados no arquivo JSON."""
    with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

@app.route('/')
def index():
    """Renderiza a página principal com o formulário e a lista de unidades."""
    localidades = carregar_dados()
    
    # Prepara uma lista plana de "Localidade - Unidade" para exibir no dropdown
    lista_localidades_unidades = []
    for local, unidades in sorted(localidades.items()):
        for unidade_nome in sorted(unidades.keys()):
            lista_localidades_unidades.append(f"{local} - {unidade_nome}")
    
    data_hoje = datetime.date.today().isoformat() # Data atual para preencher o campo de data

    return render_template(
        'index.html',
        tipos_piso=TIPOS_PISO,
        tipos_medida=TIPOS_MEDIDA,
        tipos_parede=TIPOS_PAREDE,
        data_hoje=data_hoje,
        lista_localidades_unidades=lista_localidades_unidades
    )

@app.route('/salvar_unidade', methods=['POST'])
def salvar_unidade():
    """Salva os dados de uma unidade submetidos via formulário."""
    localidade = request.form['localidade'].strip()
    unidade = request.form['unidade'].strip()

    if not localidade or not unidade:
        return jsonify({"status": "error", "message": "Localidade e Unidade são campos obrigatórios."}), 400

    data = request.form.get('data', '')
    responsavel = request.form.get('responsavel', '')
    qtd_func = request.form.get('qtd_func', '')

    piso_selecionado = []
    for tipo_piso in TIPOS_PISO:
        if request.form.get(f'piso_{tipo_piso}'):
            piso_selecionado.append(tipo_piso)

    vidros_altos = request.form.get('vidros_altos', 'Não')

    paredes_selecionadas = []
    for tipo_parede in TIPOS_PAREDE:
        if request.form.get(f'parede_{tipo_parede}'):
            paredes_selecionadas.append(tipo_parede)

    # Verifica se os checkboxes "Outras Informações" foram marcados
    estacionamento = 'estacionamento' in request.form
    gramado = 'gramado' in request.form
    curativo = 'curativo' in request.form
    vacina = 'vacina' in request.form

    medidas_json_str = request.form.get('medidas_json', '[]')
    try:
        medidas = json.loads(medidas_json_str)
    except json.JSONDecodeError:
        medidas = [] # Retorna lista vazia se houver erro no JSON

    localidades = carregar_dados()
    if localidade not in localidades:
        localidades[localidade] = {}
    
    localidades[localidade][unidade] = {
        "data": data,
        "responsavel": responsavel,
        "qtd_func": qtd_func,
        "piso": piso_selecionado,
        "vidros_altos": vidros_altos,
        "paredes": paredes_selecionadas,
        "estacionamento": estacionamento,
        "gramado": gramado,
        "curativo": curativo,
        "vacina": vacina,
        "medidas": medidas
    }
    salvar_dados(localidades)
    return jsonify({"status": "success", "message": "Unidade salva com sucesso!"})

@app.route('/carregar_unidade', methods=['POST'])
def carregar_unidade():
    """Carrega os dados de uma unidade específica para edição."""
    data = request.get_json()
    local_unidade = data.get('local_unidade')
    
    if not local_unidade or " - " not in local_unidade:
        return jsonify({"status": "error", "message": "Formato de unidade inválido."}), 400

    local, unidade = local_unidade.split(" - ", 1)
    localidades = carregar_dados()

    if local in localidades and unidade in localidades[local]:
        return jsonify({"status": "success", "data": localidades[local][unidade]}), 200
    else:
        return jsonify({"status": "error", "message": "Unidade não encontrada."}), 404

@app.route('/exportar_excel_e_enviar_email', methods=['POST'])
def exportar_excel_e_enviar_email():
    """Gera uma planilha Excel com os dados de uma unidade e a envia por e-mail."""
    selected_unit_str = request.form.get('selected_unit_to_export')
    recipient_email = request.form.get('recipient_email_to_send')

    if not selected_unit_str or " - " not in selected_unit_str:
        return jsonify({"status": "error", "message": "Selecione uma unidade válida para exportar."}), 400
    
    if not recipient_email:
        return jsonify({"status": "error", "message": "Endereço de e-mail do destinatário é obrigatório."}), 400

    local, unidade = selected_unit_str.split(" - ", 1)
    localidades = carregar_dados()

    if local not in localidades or unidade not in localidades[local]:
        return jsonify({"status": "error", "message": "Unidade não encontrada para exportação."}), 404

    info = localidades[local][unidade]

    wb = openpyxl.Workbook()
    
    # --- CORREÇÃO DA ABA "DETALHE" ---
    # Pega a aba padrão (geralmente 'Sheet') e a renomeia para "Detalhe"
    # Isso garante que estamos sempre trabalhando na mesma aba.
    ws_detalhe = wb.active
    ws_detalhe.title = "Detalhe" 

    # Adicionando o cabeçalho na aba "Detalhe"
    ws_detalhe.append(["Localidade", "Unidade", "Data", "Responsável", "Tipo de Piso", 
                       "Vidros Altos", "Paredes", "Estacionamento", "Gramado", 
                       "Sala de Curativo", "Sala de Vacina", "Qtd Funcionários"])
    
    # Adicionando os dados na aba "Detalhe"
    ws_detalhe.append([
        local, 
        unidade, 
        info.get("data", ""), 
        info.get("responsavel", ""),
        ", ".join(info.get("piso", [])), 
        info.get("vidros_altos", ""),
        ", ".join(info.get("paredes", [])),
        "Sim" if info.get("estacionamento") else "Não",
        "Sim" if info.get("gramado") else "Não",
        "Sim" if info.get("curativo") else "Não",
        "Sim" if info.get("vacina") else "Não",
        info.get("qtd_func", "")
    ])

    # Cria as outras abas para medidas (se houverem)
    abas = {
        "Vidro": wb.create_sheet("Vidros"),
        "Área Interna": wb.create_sheet("Área Interna"),
        "Sanitário-Vestiário": wb.create_sheet("Sanitário-Vestiário"),
        "Área Externa": wb.create_sheet("Área Externa")
    }
    # Adiciona cabeçalhos para as abas de medidas
    for ws in abas.values():
        ws.append(["Localidade", "Unidade", "Comprimento (m)", "Largura (m)", "Área (m²)"])

    # Popula as abas de medidas
    for medida in info.get("medidas", []):
        tipo, comp, larg, area = medida
        if tipo in abas:
            abas[tipo].append([local, unidade, comp, larg, round(area, 2)])

    # Remove sheets vazias (que só têm o cabeçalho e não foram usadas)
    for sheet_name, sheet_obj in list(abas.items()):
        if sheet_obj.max_row == 1: # Se só tem o cabeçalho
            wb.remove(sheet_obj)
            
    # Remove a sheet padrão se ela ainda existir e estiver vazia (redundante após a correção, mas seguro)
    if "Sheet" in wb.sheetnames:
        default_sheet = wb["Sheet"]
        if default_sheet.max_row == 0 or (default_sheet.max_row == 1 and all(cell.value is None for cell in default_sheet[1])):
            wb.remove(default_sheet)

    # Garante que a aba Detalhe é a aba ativa ao abrir o Excel
    if "Detalhe" in wb.sheetnames:
        wb.active = wb["Detalhe"]

    # Salva o workbook em um buffer de memória
    excel_file_in_memory = io.BytesIO()
    wb.save(excel_file_in_memory)
    excel_file_in_memory.seek(0) # Volta ao início do arquivo para leitura

    # Trata caracteres especiais para o nome do arquivo Excel
    nome_arquivo = f"{local}_{unidade}.xlsx".replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_").replace("*", "_").replace("?", "_").replace("\"", "_").replace("<", "_").replace(">", "_").replace("|", "_")
    
    # --- Parte do Envio de E-mail ---
    if not EMAIL_USER or not EMAIL_PASS or not EMAIL_SERVER:
        return jsonify({"status": "error", "message": "Configurações de e-mail incompletas no servidor. Verifique EMAIL_USER, EMAIL_PASS, EMAIL_SERVER no Render."}), 500

    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = recipient_email
    msg['Subject'] = f"Dados de Cadastro da Unidade: {local} - {unidade}"

    # Corpo do e-mail em texto simples
    body = f"""
    Prezado(a),

    Segue em anexo a planilha Excel com os dados de cadastro da unidade {local} - {unidade}.

    Data: {info.get('data', 'Não informada')}
    Responsável: {info.get('responsavel', 'Não informado')}

    Atenciosamente,
    Seu Sistema de Cadastro
    """
    
    # Anexando o corpo do e-mail usando MIMEText (correção anterior)
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    # Anexando o arquivo Excel
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(excel_file_in_memory.read())
    encoders.encode_base64(part) # Codifica o anexo em base64
    part.add_header('Content-Disposition', f'attachment; filename="{nome_arquivo}"')
    msg.attach(part)

    try:
        # Tenta enviar o e-mail via SMTP
        with smtplib.SMTP(EMAIL_SERVER, EMAIL_PORT) as server:
            server.starttls()  # Inicia TLS para comunicação segura
            server.login(EMAIL_USER, EMAIL_PASS) # Autentica com o servidor SMTP
            server.send_message(msg) # Envia a mensagem completa
        
        return jsonify({"status": "success", "message": "Unidade salva e Excel enviado por e-mail com sucesso!"}), 200

    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}") # Loga o erro para depuração
        return jsonify({"status": "error", "message": f"Erro ao enviar Excel por e-mail: {str(e)}. Verifique as configurações de e-mail e permissões (app password)."}), 500

if __name__ == '__main__':
    # Roda a aplicação Flask em modo de depuração se executado diretamente
    app.run(debug=True)