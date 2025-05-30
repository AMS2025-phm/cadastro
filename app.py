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

    medidas = db.Column(db.Text) # This field will store the JSON string of all added measures

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
    # Data for the form in index.html
    tipos_piso = ["Cerâmica", "Porcelanato", "Madeira", "Cimento Queimado", "Vinílico", "Carpete"]
    tipos_parede = ["Alvenaria", "Drywall", "Madeira", "Vidro"]
    tipos_medida = ["Vidros", "Área Interna", "Área Externa", "Vestiário"]

    # Prepare list of existing localities and units for the dropdown
    lista_localidades_unidades = []
    for local in localidades:
        for unidade in local.unidades:
            lista_localidades_unidades.append(f"{local.nome} - {unidade.nome}")

    return render_template(
        'index.html',
        localidades=localidades,
        tipos_piso=tipos_piso,
        tipos_parede=tipos_parede,
        tipos_medida=tipos_medida,
        lista_localidades_unidades=lista_localidades_unidades
    )

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

# This route is simplified to view locality and units, not to add from here anymore
@app.route('/localidade/<int:id>')
@login_required
def ver_localidade(id):
    localidade = Localidade.query.get_or_404(id)
    return render_template('ver_localidade.html', localidade=localidade)


@app.route('/adicionar_unidade', methods=['POST'])
@login_required
def adicionar_unidade():
    try:
        localidade_nome = request.form['localidade_nome']
        unidade_nome = request.form['unidade_nome']
        data = request.form['data']
        responsavel = request.form['responsavel']
        qtd_funcionarios = request.form['qtd_func']
        vidros = request.form.get('vidros_altos', 'Não')

        tipos_piso_selected = [p for p in request.form.keys() if p.startswith('piso_') and request.form[p] == 'on']
        tipos_piso_parsed = [p.replace('piso_', '') for p in tipos_piso_selected]

        paredes_selected = [p for p in request.form.keys() if p.startswith('parede_') and request.form[p] == 'on']
        paredes_parsed = [p.replace('parede_', '') for p in paredes_selected]

        estacionamento = 'Sim' if 'estacionamento' in request.form else 'Não'
        gramado = 'Sim' if 'gramado' in request.form else 'Não'
        sala_curativo = 'Sim' if 'curativo' in request.form else 'Não'
        sala_vacina = 'Sim' if 'vacina' in request.form else 'Não'
        
        # Parse medidas from hidden JSON field
        medidas_json_str = request.form.get('medidas_json', '[]')
        medidas_data = json.loads(medidas_json_str)

        # Extract specific measures for direct columns
        vidros_comprimento = ''
        vidros_largura = ''
        area_interna_comprimento = ''
        area_interna_largura = ''
        area_externa_comprimento = ''
        area_externa_largura = ''
        vestiario_comprimento = ''
        vestiario_largura = ''

        # This part assumes that if multiple "Vidros" or "Área Interna" measures are added,
        # only the last one will be saved to the specific columns.
        # The 'medidas' text field will store the full list.
        for tipo, comp, larg, area in medidas_data:
            if tipo == 'Vidros':
                vidros_comprimento = str(comp)
                vidros_largura = str(larg)
            elif tipo == 'Área Interna':
                area_interna_comprimento = str(comp)
                area_interna_largura = str(larg)
            elif tipo == 'Área Externa':
                area_externa_comprimento = str(comp)
                area_externa_largura = str(larg)
            elif tipo == 'Vestiário':
                vestiario_comprimento = str(comp)
                vestiario_largura = str(larg)

        localidade = Localidade.query.filter_by(nome=localidade_nome).first()
        if not localidade:
            localidade = Localidade(nome=localidade_nome)
            db.session.add(localidade)
            db.session.commit() # Commit to get localidade.id

        unidade = Unidade(
            localidade_id=localidade.id,
            nome=unidade_nome,
            data=data,
            responsavel=responsavel,
            vidros=vidros,
            tipos_piso=json.dumps(tipos_piso_parsed),
            paredes=json.dumps(paredes_parsed),
            estacionamento=estacionamento,
            gramado=gramado,
            sala_curativo=sala_curativo,
            sala_vacina=sala_vacina,
            qtd_funcionarios=qtd_funcionarios,
            vidros_comprimento=vidros_comprimento,
            vidros_largura=vidros_largura,
            area_interna_comprimento=area_interna_comprimento,
            area_interna_largura=area_interna_largura,
            area_externa_comprimento=area_externa_comprimento,
            area_externa_largura=area_externa_largura,
            vestiario_comprimento=vestiario_comprimento,
            vestiario_largura=vestiario_largura,
            medidas=json.dumps(medidas_data) # Store all measures as JSON
        )
        db.session.add(unidade)
        db.session.commit()
        flash('Unidade adicionada com sucesso!')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Erro ao adicionar unidade: {str(e)}')
        print(f"Error adding unit: {e}") # For debugging
        return redirect(url_for('index'))


@app.route('/exportar_e_enviar', methods=['GET'])
@login_required
def exportar_e_enviar():
    localidades = Localidade.query.all()
    wb = openpyxl.Workbook()
    aba_detalhe = wb.active
    aba_detalhe.title = "Detalhe"
    aba_detalhe.append([
        "Localidade", "Unidade", "Data", "Responsável", "Vidros Altos", "Tipos de Piso", "Paredes",
        "Estacionamento", "Gramado", "Sala de Curativo", "Sala de Vacina", "Qtd Funcionários",
        "Vidros (C)", "Vidros (L)", "Área Interna (C)", "Área Interna (L)",
        "Área Externa (C)", "Área Externa (L)", "Vestiário (C)", "Vestiário (L)", "Outras Medidas"
    ])

    for local in localidades:
        for unidade in local.unidades:
            pisos = ", ".join(json.loads(unidade.tipos_piso or "[]"))
            paredes = ", ".join(json.loads(unidade.paredes or "[]"))
            
            # Format the 'medidas' JSON for display in Excel
            all_measures_formatted = []
            if unidade.medidas:
                try:
                    all_measures = json.loads(unidade.medidas)
                    for tipo, comp, larg, area in all_measures:
                        all_measures_formatted.append(f"{tipo}: {comp}m x {larg}m = {area:.2f} m²")
                except json.JSONDecodeError:
                    all_measures_formatted.append("Erro de formato de medida")
            
            aba_detalhe.append([
                local.nome, unidade.nome, unidade.data, unidade.responsavel,
                unidade.vidros, pisos, paredes, unidade.estacionamento,
                unidade.gramado, unidade.sala_curativo, unidade.sala_vacina,
                unidade.qtd_funcionarios,
                unidade.vidros_comprimento, unidade.vidros_largura,
                unidade.area_interna_comprimento, unidade.area_interna_largura,
                unidade.area_externa_comprimento, unidade.area_externa_largura,
                unidade.vestiario_comprimento, unidade.vestiario_largura,
                "; ".join(all_measures_formatted)
            ])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    # Enviar por e-mail
    try:
        msg = EmailMessage()
        msg['Subject'] = 'Planilha de Localidades'
        msg['From'] = os.environ.get('EMAIL_USER')
        # The recipient email is hardcoded as per the original export function.
        # If dynamic email is needed, this function needs to accept it as an argument.
        msg['To'] = "comercialservico2025@gmail.com"
        msg.set_content("Segue em anexo a planilha gerada pelo sistema.")
        msg.add_attachment(buffer.read(), maintype='application', subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename="localidades.xlsx")

        with smtplib.SMTP(os.environ.get('EMAIL_SERVER'), int(os.environ.get('EMAIL_PORT'))) as server:
            server.starttls()
            server.login(os.environ.get('EMAIL_USER'), os.environ.get('EMAIL_PASS'))
            server.send_message(msg)
        flash("Planilha enviada para o e-mail fixo com sucesso.")
    except Exception as e:
        flash(f"Erro ao enviar e-mail: {str(e)}. Verifique as variáveis de ambiente do e-mail.")
        print(f"Error sending email: {e}")

    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create a default admin user if none exists
        if not User.query.filter_by(username='admin').first():
            hashed_password = generate_password_hash('adminpass') # Change this to a strong password in production!
            admin_user = User(username='admin', password=hashed_password)
            db.session.add(admin_user)
            db.session.commit()
            print("Default admin user 'admin' with password 'adminpass' created.")
    app.run(debug=False)