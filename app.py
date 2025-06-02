@app.route('/adicionar_unidade', methods=['POST'])
@login_required
def adicionar_unidade():
    localidade_nome = request.form['localidade_nome']
    unidade_nome = request.form['unidade_nome']
    data = request.form['data']
    responsavel = request.form['responsavel']
    
    tipos_piso_selecionados = request.form.getlist('tipo_piso')
    tipos_parede_selecionados = request.form.getlist('tipo_parede')

    area_interna_comprimento = request.form.get('area_interna_comprimento', '').replace(',', '.')
    area_interna_largura = request.form.get('area_interna_largura', '').replace(',', '.')
    area_externa_comprimento = request.form.get('area_externa_comprimento', '').replace(',', '.')
    area_externa_largura = request.form.get('area_externa_largura', '').replace(',', '.')
    vestiario_comprimento = request.form.get('vestiario_comprimento', '').replace(',', '.')
    vestiario_largura = request.form.get('vestiario_largura', '').replace(',', '.')

    tem_vidros = request.form.get('tem_vidros') == 'sim'
    possui_vidro_alto = request.form.get('possui_vidro_alto') == 'sim' if tem_vidros else False
    vidro_alto_perigoso = request.form.get('vidro_alto_perigoso') == 'sim' if possui_vidro_alto else False

    vidros_tipo = request.form.get('vidros_tipo', '') if tem_vidros else ''
    vidros_quantidade = request.form.get('vidros_quantidade', '') if tem_vidros else ''
    vidros_observacao = request.form.get('vidros_observacao', '') if tem_vidros else ''

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
        "area_interna_comprimento": area_interna_comprimento,
        "area_interna_largura": area_interna_largura,
        "area_externa_comprimento": area_externa_comprimento,
        "area_externa_largura": area_externa_largura,
        "vestiario_comprimento": vestiario_comprimento,
        "vestiario_largura": vestiario_largura,
        "tem_vidros": tem_vidros,
        "possui_vidro_alto": possui_vidro_alto,
        "vidros_tipo": vidros_tipo,
        "vidros_quantidade": vidros_quantidade,
        "vidros_observacao": vidros_observacao,
        "vidro_alto_perigoso": vidro_alto_perigoso,
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
