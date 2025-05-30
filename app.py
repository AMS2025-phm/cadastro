from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask import g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
import json
import io
import datetime
import openpyxl
import smtplib
from email.message import EmailMessage

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///localidades.db'
db = SQLAlchemy(app)

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = User.query.get(user_id)

# Modelos
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Localidade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120))
    unidades = db.relationship('Unidade', backref='localidade', lazy=True)

class Unidade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    localidade_id = db.Column(db.Integer, db.ForeignKey('localidade.id'), nullable=False)
    nome = db.Column(db.String(120))
    data = db.Column(db.String(20))
    responsavel = db.Column(db.String(120))
    vidros = db.Column(db.String(10))
    tipos_piso = db.Column(db.String(300))
    paredes = db.Column(db.String(300))
    estacionamento = db.Column(db.String(10))
    gramado = db.Column(db.String(10))
    sala_curativo = db.Column(db.String(10))
    sala_vacina = db.Column(db.String(10))
    qtd_funcionarios = db.Column(db.String(10))

    vidros_comprimento = db.Column(db.String(20))
    vidros_largura = db.Column(db.String(20))
    area_interna_comprimento = db.Column(db.String(20))
    area_interna_largura = db.Column(db.String(20))
    area_externa_comprimento = db.Column(db.String(20))
    area_externa_largura = db.Column(db.String(20))
    vestiario_comprimento = db.Column(db.String(20))
    vestiario_largura = db.Column(db.String(20))

    medidas = db.Column(db.Text)

# Login requerido
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def verificar_login():
    if not session.get('user_id') and (request.endpoint is None or (request.endpoint not in ['login', 'static'] and not request.endpoint.startswith('static'))):
        return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    localidades = Localidade.query.all()
    return render_template('index.html', localidades=localidades)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            return redirect(url_for('index'))
        flash('Login inválido.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/nova_localidade', methods=['GET', 'POST'])
@login_required
def nova_localidade():
    if request.method == 'POST':
        nome = request.form['nome']
        localidade = Localidade(nome=nome)
        db.session.add(localidade)
        db.session.commit()
        flash('Localidade adicionada.')
        return redirect(url_for('index'))
    return render_template('nova_localidade.html')

@app.route('/localidade/<int:id>', methods=['GET', 'POST'])
@login_required
def ver_localidade(id):
    localidade = Localidade.query.get_or_404(id)
    if request.method == 'POST':
        unidade = Unidade(
            localidade_id=id,
            nome=request.form['nome'],
            data=request.form['data'],
            responsavel=request.form['responsavel'],
            vidros=request.form.get('vidros', 'Não'),
            tipos_piso=json.dumps(request.form.getlist('tipos_piso')),
            paredes=json.dumps(request.form.getlist('paredes')),
            estacionamento=request.form.get('estacionamento', 'Não'),
            gramado=request.form.get('gramado', 'Não'),
            sala_curativo=request.form.get('sala_curativo', 'Não'),
            sala_vacina=request.form.get('sala_vacina', 'Não'),
            qtd_funcionarios=request.form['qtd_funcionarios'],
            vidros_comprimento=request.form.get('vidros_comprimento'),
            vidros_largura=request.form.get('vidros_largura'),
            area_interna_comprimento=request.form.get('area_interna_comprimento'),
            area_interna_largura=request.form.get('area_interna_largura'),
            area_externa_comprimento=request.form.get('area_externa_comprimento'),
            area_externa_largura=request.form.get('area_externa_largura'),
            vestiario_comprimento=request.form.get('vestiario_comprimento'),
            vestiario_largura=request.form.get('vestiario_largura'),
            medidas=request.form['medidas']
        )
        db.session.add(unidade)
        db.session.commit()
        flash('Unidade adicionada.')
    return render_template('ver_localidade.html', localidade=localidade)

@app.route('/exportar_e_enviar')
@login_required
def exportar_e_enviar():
    localidades = Localidade.query.all()
    wb = openpyxl.Workbook()
    aba_detalhe = wb.active
    aba_detalhe.title = "Detalhe"
    aba_detalhe.append([
        "Localidade", "Unidade", "Data", "Responsável", "Vidros Altos", "Tipos de Piso", "Paredes",
        "Estacionamento", "Gramado", "Sala de Curativo", "Sala de Vacina", "Qtd Funcionários", "Medidas",
        "Vidros (C)", "Vidros (L)", "Área Interna (C)", "Área Interna (L)",
        "Área Externa (C)", "Área Externa (L)", "Vestiário (C)", "Vestiário (L)"
    ])

    for local in localidades:
        for unidade in local.unidades:
            pisos = ", ".join(json.loads(unidade.tipos_piso or "[]"))
            paredes = ", ".join(json.loads(unidade.paredes or "[]"))
            aba_detalhe.append([
                local.nome, unidade.nome, unidade.data, unidade.responsavel,
                unidade.vidros, pisos, paredes, unidade.estacionamento,
                unidade.gramado, unidade.sala_curativo, unidade.sala_vacina,
                unidade.qtd_funcionarios, unidade.medidas,
                unidade.vidros_comprimento, unidade.vidros_largura,
                unidade.area_interna_comprimento, unidade.area_interna_largura,
                unidade.area_externa_comprimento, unidade.area_externa_largura,
                unidade.vestiario_comprimento, unidade.vestiario_largura
            ])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    # Enviar por e-mail
    msg = EmailMessage()
    msg['Subject'] = 'Planilha de Localidades'
    msg['From'] = os.environ.get('EMAIL_USER')
    msg['To'] = "comercialservico2025@gmail.com"
    msg.set_content("Segue em anexo a planilha gerada pelo sistema.")
    msg.add_attachment(buffer.read(), maintype='application', subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename="localidades.xlsx")

    with smtplib.SMTP(os.environ.get('EMAIL_SERVER'), int(os.environ.get('EMAIL_PORT'))) as server:
        server.starttls()
        server.login(os.environ.get('EMAIL_USER'), os.environ.get('EMAIL_PASS'))
        server.send_message(msg)

    flash("Planilha enviada para o e-mail fixo com sucesso.")
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=False)
