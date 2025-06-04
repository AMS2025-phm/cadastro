from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import pandas as pd

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_tipos_piso')
def get_tipos_piso():
    return jsonify(["Paviflex", "Porcelanato", "Cerâmica", "Granilite"])

@app.route('/get_tipos_parede')
def get_tipos_parede():
    return jsonify(["Alvenaria", "Divisória", "Drywall", "Gesso"])

@app.route('/salvar_unidade', methods=['POST'])
def salvar_unidade():
    dados = request.get_json()
    print('Dados recebidos:', dados)

    medidas = []
    for cat in ['medidas_vidros', 'medidas_sanitarios', 'medidas_internas', 'medidas_externas']:
        for item in dados.get(cat, []):
            medidas.append({ 'categoria': cat, **item })

    df = pd.DataFrame(medidas)
    os.makedirs('arquivos', exist_ok=True)
    file_path = os.path.join('arquivos', f"{dados.get('unidade', 'unidade')}_medidas.xlsx")
    df.to_excel(file_path, index=False)

    print(f"Simulando envio de {file_path} por e-mail...")

    return jsonify({"message": "Unidade salva e planilha gerada com sucesso!"})

if __name__ == '__main__':
    app.run()
