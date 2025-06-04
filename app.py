from flask import Flask, request, jsonify
app = Flask(__name__)

@app.route('/salvar_unidade', methods=['POST'])
def salvar_unidade():
    dados = request.get_json()
    return jsonify({"message": "Unidade salva com sucesso!"})

if __name__ == '__main__':
    app.run(debug=True)
