import os
import json
import smtplib
from email.message import EmailMessage
from flask import Flask, render_template, request, redirect
from openpyxl import Workbook

app = Flask(__name__)

EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
EMAIL_SERVER = os.getenv('EMAIL_SERVER')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_DESTINO = 'comercialservico2025@gmail.com'

ARQUIVO_DADOS = 'localidades.json'

def carregar_dados():
    if os.path.exists(ARQUIVO_DADOS):
        with open(ARQUIVO_DADOS, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def salvar_dados(dados):
    with open(ARQUIVO_DADOS, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/salvar_unidade', methods=['POST'])
def salvar_unidade():
    localidade = request.form['localidade']
    unidade = request.form['unidade']
    data = request.form['data']
    responsavel = request.form.get('responsavel', '')
    qtd_func = request.form.get('qtd_func', '')

    pisos = [k.split('_',1)[1] for k in request.form.keys() if k.startswith('piso_')]
    vidros_altos = request.form.get('vidros_altos', 'Não')
    paredes = [k.split('_',1)[1] for k in request.form.keys() if k.startswith('parede_')]

    estacionamento = 'estacionamento' in request.form
    gramado = 'gramado' in request.form
    curativo = 'curativo' in request.form
    vacina = 'vacina' in request.form

    medidas_json_str = request.form.get('medidas_json', '[]')
    try:
        medidas = json.loads(medidas_json_str)
    except json.JSONDecodeError:
        medidas = []

    localidades = carregar_dados()
    if localidade not in localidades:
        localidades[localidade] = {}
    localidades[localidade][unidade] = {
        'data': data,
        'responsavel': responsavel,
        'qtd_func': qtd_func,
        'piso': pisos,
        'vidros_altos': vidros_altos,
        'paredes': paredes,
        'estacionamento': estacionamento,
        'gramado': gramado,
        'curativo': curativo,
        'vacina': vacina,
        'medidas': medidas
    }
    salvar_dados(localidades)
    return redirect('/')

@app.route('/exportar_excel_e_enviar_email', methods=['POST'])
def exportar_excel_e_enviar_email():
    selected_unit_str = request.form.get('selected_unit_to_export')
    recipient_email = EMAIL_DESTINO

    if not selected_unit_str or " - " not in selected_unit_str:
        return "Selecione uma unidade válida.", 400

    local, unidade = selected_unit_str.split(" - ", 1)
    localidades = carregar_dados()

    if local not in localidades or unidade not in localidades[local]:
        return "Unidade não encontrada.", 404

    info = localidades[local][unidade]
    wb = Workbook()
    ws = wb.active
    ws.title = "Unidade"
    ws.append(["Campo", "Valor"])
    for k, v in info.items():
        ws.append([k, json.dumps(v) if isinstance(v, list) else v])
    filename = f"{local}_{unidade}.xlsx".replace(" ", "_")
    wb.save(filename)

    if not EMAIL_USER or not EMAIL_PASS or not EMAIL_SERVER:
        return "Configurações de e-mail incompletas.", 500

    msg = EmailMessage()
    msg['Subject'] = f"Dados de Cadastro da Unidade: {local} - {unidade}"
    msg['From'] = EMAIL_USER
    msg['To'] = recipient_email
    msg.set_content(f"Segue anexo os dados da unidade {local} - {unidade}.")

    with open(filename, 'rb') as f:
        msg.add_attachment(f.read(), maintype='application', subtype='octet-stream', filename=filename)

    try:
        with smtplib.SMTP(EMAIL_SERVER, EMAIL_PORT) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
    except Exception as e:
        return f"Erro ao enviar e-mail: {e}", 500

    return "Planilha exportada e e-mail enviado com sucesso.", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))