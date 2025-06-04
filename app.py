from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import pandas as pd
import smtplib
from email.message import EmailMessage

app = Flask(__name__)
CORS(app)

EMAIL_USER = 'seu_email@gmail.com'
EMAIL_PASS = 'sua_senha_de_app'
DESTINATARIO = 'destinatario@exemplo.com'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_tipos_piso')
def get_tipos_piso():
    return jsonify(["Paviflex", "Porcelanato", "Cerâmica", "Granilite"])

@app.route('/get_tipos_parede')
def get_tipos_parede():
    return jsonify(["Alvenaria", "Divisória", "Drywall", "Gesso"])

def enviar_email_com_anexo(destinatario, arquivo):
    msg = EmailMessage()
    msg['Subject'] = 'Planilha de Medidas'
    msg['From'] = EMAIL_USER
    msg['To'] = destinatario
    msg.set_content('Segue em anexo a planilha.')

    with open(arquivo, 'rb') as f:
        file_data = f.read()
        file_name = os.path.basename(arquivo)

    msg.add_attachment(file_data, maintype='application', subtype='octet-stream', filename=file_name)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)

@app.route('/salvar_unidade', methods=['POST'])
def salvar_unidade():
    dados = request.get_json()
    medidas = []
    for cat in ['medidas_vidros', 'medidas_sanitarios', 'medidas_internas', 'medidas_externas']:
        for item in dados.get(cat, []):
            medidas.append({ 'categoria': cat, **item })

    df = pd.DataFrame(medidas)
    os.makedirs('arquivos', exist_ok=True)
    file_path = os.path.join('arquivos', f"{dados.get('unidade', 'unidade')}_medidas.xlsx")
    df.to_excel(file_path, index=False)

    try:
        enviar_email_com_anexo(DESTINATARIO, file_path)
        return jsonify({"message": "Unidade salva, planilha gerada e e-mail enviado com sucesso!"})
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return jsonify({"message": "Unidade salva e planilha gerada, mas falhou ao enviar e-mail."})

if __name__ == '__main__':
    app.run(debug=True)
