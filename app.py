
import os
import json
import datetime
import smtplib
from email.message import EmailMessage
from flask import Flask, render_template, request, redirect, url_for, flash
from openpyxl import Workbook

app = Flask(__name__)
app.secret_key = 'super-secret'

EMAIL_USUARIO = os.getenv('EMAIL_USUARIO')
EMAIL_SENHA = os.getenv('EMAIL_SENHA')
EMAIL_DESTINO = 'comercialservico2025@gmail.com'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/adicionar_unidade', methods=['POST'])
def adicionar_unidade():
    localidade_nome = request.form['localidade_nome']
    unidade_nome = request.form['unidade_nome']
    data = request.form['data']
    responsavel = request.form['responsavel']
    
    tipos_piso_selecionados = request.form.getlist('tipo_piso')
    tipos_parede_selecionados = request.form.getlist('tipo_parede')
    possui_estacionamento = request.form.get('possui_estacionamento') == 'sim'
    estacionamento_coberto = request.form.get('estacionamento_coberto') == 'sim' if possui_estacionamento else False
    possui_sala_vacinacao = request.form.get('possui_sala_vacinacao') == 'sim'
    possui_sala_curativo = request.form.get('possui_sala_curativo') == 'sim'

    observacoes_gerais = request.form.get('observacoes_gerais', '')
    medidas_json_str = request.form.get('medidas_dinamicas_json', '[]')
    try:
        medidas_dinamicas = json.loads(medidas_json_str)
    except json.JSONDecodeError:
        medidas_dinamicas = []

    nova_unidade = {
        "id": str(datetime.datetime.now().timestamp()),
        "nome": unidade_nome,
        "data": data,
        "responsavel": responsavel,
        "tipos_piso": tipos_piso_selecionados,
        "tipos_parede": tipos_parede_selecionados,
        "possui_estacionamento": possui_estacionamento,
        "estacionamento_coberto": estacionamento_coberto,
        "possui_sala_vacinacao": possui_sala_vacinacao,
        "possui_sala_curativo": possui_sala_curativo,
        "observacoes_gerais": observacoes_gerais,
        "medidas": json.dumps(medidas_dinamicas)
    }

    salvar_dados(localidade_nome, nova_unidade)
    planilha_path = gerar_planilha(nova_unidade)
    enviar_email_com_anexo(planilha_path)

    flash('Unidade adicionada e e-mail enviado com sucesso!', 'success')
    return redirect(url_for('index'))

def salvar_dados(localidade, unidade):
    dados = {}
    if os.path.exists('dados.json'):
        with open('dados.json', 'r') as f:
            dados = json.load(f)
    if localidade not in dados:
        dados[localidade] = []
    dados[localidade].append(unidade)
    with open('dados.json', 'w') as f:
        json.dump(dados, f, indent=4)

def gerar_planilha(unidade):
    wb = Workbook()
    ws = wb.active
    ws.title = "Unidade"
    ws.append(["Campo", "Valor"])
    for k, v in unidade.items():
        ws.append([k, json.dumps(v) if isinstance(v, list) else v])
    arquivo = f"{unidade['nome']}.xlsx"
    wb.save(arquivo)
    return arquivo

def enviar_email_com_anexo(arquivo):
    msg = EmailMessage()
    msg['Subject'] = 'Nova unidade cadastrada'
    msg['From'] = EMAIL_USUARIO
    msg['To'] = EMAIL_DESTINO
    msg.set_content('Segue em anexo a planilha da nova unidade.')

    with open(arquivo, 'rb') as f:
        file_data = f.read()
        msg.add_attachment(file_data, maintype='application', subtype='octet-stream', filename=arquivo)

    with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
        smtp.starttls()
        smtp.login(EMAIL_USUARIO, EMAIL_SENHA)
        smtp.send_message(msg)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
