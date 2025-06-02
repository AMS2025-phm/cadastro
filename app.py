from flask import Flask, render_template, request, redirect, url_for, flash, g

app = Flask(__name__)
app.secret_key = 'super-secret'  # Altere para algo mais seguro
@app.route('/adicionar_unidade', methods=['POST'])

@login_required
def adicionar_unidade():
    localidade_nome = request.form['localidade_nome']
    unidade_nome = request.form['unidade_nome']
    data = request.form['data']
    responsavel = request.form['responsavel']
    
    tipos_piso_selecionados = request.form.getlist('tipo_piso')
    tipos_parede_selecionados = request.form.getlist('tipo_parede')
    possui_estacionamento = request.form.get('possui_estacionamento') == 'sim'
    estacionamento_coberto = request.form.get('estacionamento_coberto') == 'sim' if possui_estacionamento else False
    possui_gramado = request.form.get('possui_gramado') == 'sim'
    possui_sala_vacinacao = request.form.get('possui_sala_vacinacao') == 'sim'
    possui_sala_curativo = request.form.get('possui_sala_curativo') == 'sim'

    observacoes_gerais = request.form.get('observacoes_gerais', '')

    medidas_json_str = request.form.get('medidas_dinamicas_json', '[]')
    try:
        medidas_dinamicas = json.loads(medidas_json_str)
    except json.JSONDecodeError:
        flash('Erro ao processar medidas dinâmicas. Formato inválido.', 'danger')
        return redirect(url_for('index'))

    dados = carregar_dados()
    if localidade_nome not in dados:
        dados[localidade_nome] = []

    for unidade_existente in dados[localidade_nome]:
        if unidade_existente.get('nome') == unidade_nome:
            flash(f'Já existe uma unidade com o nome "{unidade_nome}" na localidade "{localidade_nome}".', 'danger')
            return redirect(url_for('index'))

    nova_unidade = {
        "id": str(datetime.datetime.now().timestamp()),
        "nome": unidade_nome,
        "data": data,
        "responsavel": responsavel,
        "tipos_piso": tipos_piso_selecionados,
                                                                                                        "possui_estacionamento": possui_estacionamento,
        "estacionamento_coberto": estacionamento_coberto,
        "possui_gramado": possui_gramado,
        "possui_sala_vacinacao": possui_sala_vacinacao,
        "possui_sala_curativo": possui_sala_curativo,
        "tipos_parede": tipos_parede_selecionados,
        "observacoes_gerais": observacoes_gerais,
        "medidas": json.dumps(medidas_dinamicas)
    }

    dados[localidade_nome].append(nova_unidade)
    salvar_dados(dados)

    flash(f'Unidade "{unidade_nome}" adicionada com sucesso à localidade "{localidade_nome}"!', 'success')
    return redirect(url_for('index'))
