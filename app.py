from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, g
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
# MUDE ISSO PARA UMA CHAVE SECRETA FORTE E ÚNICA EM PRODUÇÃO!
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'sua_chave_secreta_padrao_muito_segura')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///localidades.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Recomendado para evitar warnings

db = SQLAlchemy(app)

# Filtro para converter JSON para objeto Python no Jinja2
@app.template_filter('from_json')
def from_json_filter(value):
    if value is None:
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return [] # Retorna lista vazia em caso de erro ou valor inválido

# Modelos do Banco de Dados
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Localidade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), unique=True, nullable=False)
    unidades = db.relationship('Unidade', backref='localidade', lazy=True, cascade="all, delete-orphan")

class Unidade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    localidade_id = db.Column(db.Integer, db.ForeignKey('localidade.id'), nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    data = db.Column(db.String(20)) # Formato 'YYYY-MM-DD'
    responsavel = db.Column(db.String(120))
    vidros = db.Column(db.String(10)) # "Sim" ou "Não"
    tipos_piso = db.Column(db.Text) # JSON string of list
    paredes = db.Column(db.Text) # JSON string of list
    estacionamento = db.Column(db.String(10))
    gramado = db.Column(db.String(10))
    sala_curativo = db.Column(db.String(10))
    sala_vacina = db.Column(db.String(10))
    qtd_funcionarios = db.Column(db.String(10)) # Pode ser string para flexibilidade (ex: "5-10")

    # Campos específicos para as primeiras medidas, se existirem
    vidros_comprimento = db.Column(db.String(20), default='')
    vidros_largura = db.Column(db.String(20), default='')
    area_interna_comprimento = db.Column(db.String(20), default='')
    area_interna_largura = db.Column(db.String(20), default='')
    area_externa_comprimento = db.Column(db.String(20), default='')
    area_externa_largura = db.Column(db.String(20), default='')
    vestiario_comprimento = db.Column(db.String(20), default='')
    vestiario_largura = db.Column(db.String(20), default='')

    # Campo para armazenar todas as medidas como JSON
    medidas = db.Column(db.Text, default='[]') # Lista de [tipo, comprimento, largura, area]

# Funções de Autenticação
@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    	# Verifica se precisa redirecionar para login
        if request.endpoint not in ['login', 'register', 'static']:
            return redirect(url_for('login'))
	else:
        g.user = User.query.get(user_id)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Você precisa estar logado para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

#@app.before_request
#def verificar_login_e_redirecionar():
#    # Permite acesso às rotas de login, registro e arquivos estáticos sem estar logado
#    if not session.get('user_id') and \
#       request.endpoint not in ['login', 'register', 'static']:
#        # 'static' é o endpoint para arquivos estáticos (CSS, JS, etc.)
#        return redirect(url_for('login'))

# Rotas da Aplicação

@app.route('/')
@login_required
def index():
    localidades = Localidade.query.order_by(Localidade.nome).all()
    tipos_piso = ["Cerâmica", "Porcelanato", "Madeira", "Cimento Queimado", "Vinílico", "Carpete", "Outro"]
    tipos_parede = ["Alvenaria", "Drywall", "Madeira", "Vidro", "Outro"]
    tipos_medida = ["Vidros", "Área Interna", "Área Externa", "Vestiário", "Outro"]

    return render_template(
        'index.html',
        localidades=localidades,
        tipos_piso=tipos_piso,
        tipos_parede=tipos_parede,
        tipos_medida=tipos_medida
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user: # Se o usuário já estiver logado, redireciona para a página inicial
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Login bem-sucedido!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Nome de usuário ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if g.user: # Se o usuário já estiver logado, redireciona para a página inicial
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if not username or not password or not confirm_password:
            flash('Todos os campos são obrigatórios.', 'danger')
            return render_template('register.html')

        if password != confirm_password:
            flash('As senhas não coincidem.', 'danger')
            return render_template('register.html')

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Nome de usuário já existe. Escolha outro.', 'danger')
            return render_template('register.html')

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registro bem-sucedido! Faça login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login'))

@app.route('/nova_localidade', methods=['GET', 'POST'])
@login_required
def nova_localidade():
    if request.method == 'POST':
        nome = request.form['nome'].strip()
        if not nome:
            flash('O nome da localidade não pode ser vazio.', 'danger')
            return render_template('nova_localidade.html')

        existing_localidade = Localidade.query.filter_by(nome=nome).first()
        if existing_localidade:
            flash(f'A localidade "{nome}" já existe.', 'warning')
            return render_template('nova_localidade.html')

        localidade = Localidade(nome=nome)
        db.session.add(localidade)
        db.session.commit()
        flash(f'Localidade "{nome}" adicionada com sucesso!', 'success')
        return redirect(url_for('index'))
    return render_template('nova_localidade.html')

@app.route('/localidade/<int:id>')
@login_required
def ver_localidade(id):
    localidade = Localidade.query.get_or_404(id)
    return render_template('ver_localidade.html', localidade=localidade)

@app.route('/excluir_localidade/<int:id>', methods=['POST'])
@login_required
def excluir_localidade(id):
    localidade = Localidade.query.get_or_404(id)
    db.session.delete(localidade)
    db.session.commit()
    flash(f'Localidade "{localidade.nome}" e todas as suas unidades foram excluídas.', 'success')
    return redirect(url_for('index'))

@app.route('/adicionar_unidade', methods=['POST'])
@login_required
def adicionar_unidade():
    try:
        localidade_nome = request.form['localidade_nome'].strip()
        unidade_nome = request.form['unidade_nome'].strip()
        data = request.form['data']
        responsavel = request.form['responsavel'].strip()
        qtd_funcionarios = request.form['qtd_func'].strip()
        vidros = request.form.get('vidros_altos', 'Não')

        tipos_piso_selected = [p.replace('piso_', '') for p in request.form.keys() if p.startswith('piso_') and request.form[p] == 'on']
        paredes_selected = [p.replace('parede_', '') for p in request.form.keys() if p.startswith('parede_') and request.form[p] == 'on']

        estacionamento = 'Sim' if 'estacionamento' in request.form else 'Não'
        gramado = 'Sim' if 'gramado' in request.form else 'Não'
        sala_curativo = 'Sim' if 'curativo' in request.form else 'Não'
        sala_vacina = 'Sim' if 'vacina' in request.form else 'Não'
        
        # Validar dados essenciais
        if not localidade_nome or not unidade_nome or not data:
            flash('Nome da Localidade, Nome da Unidade e Data são campos obrigatórios.', 'danger')
            return redirect(url_for('index'))

        # Encontra ou cria a localidade
        localidade = Localidade.query.filter_by(nome=localidade_nome).first()
        if not localidade:
            localidade = Localidade(nome=localidade_nome)
            db.session.add(localidade)
            db.session.commit() # Commit para obter o ID da nova localidade

        # Processar medidas do JSON
        medidas_json_str = request.form.get('medidas_json', '[]')
        medidas_data = json.loads(medidas_json_str)

        # Extrair medidas específicas para as colunas diretas (se houver)
        vidros_comprimento = ''
        vidros_largura = ''
        area_interna_comprimento = ''
        area_interna_largura = ''
        area_externa_comprimento = ''
        area_externa_largura = ''
        vestiario_comprimento = ''
        vestiario_largura = ''

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

        unidade = Unidade(
            localidade_id=localidade.id,
            nome=unidade_nome,
            data=data,
            responsavel=responsavel,
            vidros=vidros,
            tipos_piso=json.dumps(tipos_piso_selected),
            paredes=json.dumps(paredes_selected),
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
            medidas=json.dumps(medidas_data) # Armazena todas as medidas como JSON
        )
        db.session.add(unidade)
        db.session.commit()
        flash(f'Unidade "{unidade_nome}" adicionada com sucesso à localidade "{localidade_nome}"!', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Erro ao adicionar unidade: {str(e)}', 'danger')
        print(f"Error adding unit: {e}") # Para depuração no console
        return redirect(url_for('index'))

@app.route('/exportar_e_enviar', methods=['POST'])
@login_required
def exportar_e_enviar():
    localidades = Localidade.query.all()
    if not localidades:
        flash('Não há dados para exportar.', 'info')
        return redirect(url_for('index'))

    wb = openpyxl.Workbook()
    aba_detalhe = wb.active
    aba_detalhe.title = "Detalhe Localidades"
    aba_detalhe.append([
        "Localidade", "Unidade", "Data", "Responsável", "Vidros Altos", "Tipos de Piso", "Paredes",
        "Estacionamento", "Gramado", "Sala de Curativo", "Sala de Vacina", "Qtd Funcionários",
        "Vidros (C)", "Vidros (L)", "Área Interna (C)", "Área Interna (L)",
        "Área Externa (C)", "Área Externa (L)", "Vestiário (C)", "Vestiário (L)", "Outras Medidas Detalhadas"
    ])

    for local in localidades:
        for unidade in local.unidades:
            pisos = ", ".join(json.loads(unidade.tipos_piso or "[]"))
            paredes = ", ".join(json.loads(unidade.paredes or "[]"))
            
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
        sender_email = os.environ.get('EMAIL_USER')
        sender_password = os.environ.get('EMAIL_PASS')
        smtp_server = os.environ.get('EMAIL_SERVER')
        smtp_port = int(os.environ.get('EMAIL_PORT', 587)) # Default para 587 se não definida

        if not all([sender_email, sender_password, smtp_server]):
            flash('Configurações de e-mail incompletas. Verifique as variáveis de ambiente.', 'danger')
            return redirect(url_for('index'))

        msg = EmailMessage()
        msg['Subject'] = 'Planilha de Localidades Cadastradas'
        msg['From'] = sender_email
        msg['To'] = "comercialservico2025@gmail.com" # E-mail do destinatário fixo
        msg.set_content("Segue em anexo a planilha com os dados de localidades e unidades cadastradas no sistema.")
        msg.add_attachment(buffer.read(), maintype='application', subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename="localidades_e_unidades.xlsx")

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls() # Usar TLS para segurança
            server.login(sender_email, sender_password)
            server.send_message(msg)
        flash("Planilha enviada para o e-mail fixo com sucesso!", 'success')
    except Exception as e:
        flash(f"Erro ao enviar e-mail: {str(e)}. Verifique as variáveis de ambiente do e-mail e a conexão.", 'danger')
        print(f"Erro ao enviar e-mail: {e}")

    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Cria um usuário admin padrão se não existir
        if not User.query.filter_by(username='admin').first():
            # Mude 'senha_segura_admin' para uma senha forte em produção!
            hashed_password = generate_password_hash('senha_segura_admin')
            admin_user = User(username='admin', password=hashed_password)
            db.session.add(admin_user)
            db.session.commit()
            print("Usuário 'admin' com senha 'senha_segura_admin' criado (mude em produção!).")
    app.run(debug=True) # Mude debug para False em produção