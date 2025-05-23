from flask import Flask, render_template, request, redirect, url_for, send_file
import os
import json
import datetime
import openpyxl
from io import BytesIO

app = Flask(__name__)
DATA_FILE = "localidades.json"

def carregar_dados():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_dados(dados):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

@app.route('/')
def index():
    dados = carregar_dados()
    return render_template('index.html', localidades=dados)

@app.route('/adicionar', methods=["POST"])
def adicionar():
    nova_localidade = {
        "nome": request.form['nome'],
        "unidade": request.form['unidade'],
        "responsavel": request.form['responsavel'],
        "data": request.form['data'],
        "tipo_piso": request.form.getlist('tipo_piso'),
        "vidros_altos": request.form.get('vidros_altos', 'Não')
    }
    dados = carregar_dados()
    dados.append(nova_localidade)
    salvar_dados(dados)
    return redirect(url_for('index'))

@app.route('/exportar')
def exportar():
    dados = carregar_dados()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Detalhe"
    ws.append(["Nome", "Unidade", "Responsável", "Data", "Tipos de Piso", "Vidros Altos"])

    for item in dados:
        ws.append([
            item["nome"],
            item["unidade"],
            item["responsavel"],
            item["data"],
            ", ".join(item["tipo_piso"]),
            item["vidros_altos"]
        ])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"localidades_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)