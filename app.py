# app.py
print("Flask app script started execution.") # Adicionado para depuração de implantação

from flask import Flask, render_template, request, jsonify
import json
import os
import datetime
import openpyxl
import io
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

# Importações para o Banco de Dados
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import joinedload # Para carregar relações de forma eficiente
from sqlalchemy.exc import OperationalError # Importar para tratar erros de conexão ao DB

app = Flask(__name__)

# --- Configurações do Banco de Dados ---
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("ERRO CRÍTICO: Variável de ambiente DATABASE_URL não encontrada. O aplicativo pode não funcionar corretamente.")
    # Para depuração local, você pode definir uma URL padrão aqui, mas REMOVA EM PRODUÇÃO
    # DATABASE_URL = "postgresql://user:password@localhost:5432/mydatabase"

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Desativa o rastreamento de modificações para economizar memória
db = SQLAlchemy(app)

# --- Definição dos Modelos do Banco de Dados ---
class Unidade(db.Model):
    __tablename__ = 'unidades' # Nome da tabela no banco de dados
    id = db.Column(db.Integer, primary_key=True)
    localidade = db.Column(db.String(255), nullable=False)
    nome_unidade = db.Column(db.String(255), nullable=False)
    data = db.Column(db.Date, nullable=False)
    responsavel = db.Column(db.String(255))
    qtd_func = db.Column(db.Integer)
    
    # NOVOS CAMPOS DA UNIDADE
    gramado = db.Column(db.Boolean, default=False)
    estacionamento = db.Column(db.Boolean, default=False)
    estacionamento_coberto = db.Column(db.Boolean, default=False) # Apenas se estacionamento for True
    sala_curativo = db.Column(db.Boolean, default=False)
    sala_vacina = db.Column(db.Boolean, default=False)
    vidros_altos = db.Column(db.Boolean, default=False)
    perigo_limpar_vidros = db.Column(db.Boolean, default=False) # Apenas se vidros_altos for True

    medidas = db.relationship('Medida', backref='unidade', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Unidade {self.localidade} - {self.nome_unidade}>"

class Medida(db.Model):
    __tablename__ = 'medidas' # Nome da tabela no banco de dados
    id = db.Column(db.Integer, primary_key=True)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidades.id'), nullable=False)
    tipo = db.Column(db.String(255))
    largura = db.Column(db.Float)
    altura = db.Column(db.Float)
    area = db.Column(db.Float)
    piso = db.Column(db.String(255))
    parede = db.Column(db.String(255))
    qtde = db.Column(db.Integer)

    def __repr__(self):
        return f"<Medida {self.tipo} para Unidade {self.unidade_id}>"

# Crie as tabelas no banco de dados se elas não existirem
# IMPORTANTE: Em produção, você usaria ferramentas de migração (como Alembic)
# Para este projeto simples, db.create_all() é suficiente, mas execute-o com cautela.
# Pode ser removido após o primeiro deploy bem-sucedido com as tabelas criadas.
with app.app_context():
    try:
        print("Attempting to create database tables (if they don't exist)...")
        db.create_all()
        print("Database tables created successfully or already exist.")
    except OperationalError as e:
        print(f"ERRO DE CONEXÃO COM O BANCO DE DADOS DURANTE db.create_all(): {e}")
        print("Verifique se a DATABASE_URL está correta e se o banco de dados está acessível.")
    except Exception as e:
        print(f"ERRO INESPERADO AO CRIAR TABELAS DO BANCO DE DADOS: {e}")

# --- Listas de opções para os campos do formulário ---
TIPOS_PISO = [
    "Paviflex", "Cerâmica", "Porcelanato", "Granilite",
    "Cimento Queimado", "Epoxi", "Ardósia", "Outros"
]
TIPOS_MEDIDA = ["Vidro", "Sanitário-Vestiário", "Área Interna", "Área Externa"]
TIPOS_PAREDE = ["Alvenaria", "Estuque", "Divisórias"]

# --- Configurações de E-mail (Lidas de variáveis de ambiente do Render) ---
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASS = os.environ.get('EMAIL_PASS')
EMAIL_SERVER = os.environ.get('EMAIL_SERVER')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))

FIXED_RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL')

# --- Funções Auxiliares ---
def gerar_excel(dados_unidades):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Localidades e Medidas"

    # Cabeçalho da planilha - ATUALIZADO COM NOVOS CAMPOS DA UNIDADE
    headers = [
        "Localidade", "Unidade", "Data", "Responsável", "Qtd Funcionário",
        "Gramado", "Estacionamento", "Estacionamento Coberto",
        "Sala Curativo", "Sala Vacina", "Vidros Altos", "Perigo Limpar Vidros",
        "Tipo Medida", "Largura (m)", "Altura (m)", "Área (m²)",
        "Tipo Piso", "Tipo Parede", "Quantidade"
    ]
    sheet.append(headers)

    for unidade_data in dados_unidades:
        localidade = unidade_data.get('localidade', '')
        unidade_nome = unidade_data.get('unidade', '')
        data = unidade_data.get('data', '')
        responsavel = unidade_data.get('responsavel', '')
        qtd_func = unidade_data.get('qtd_func', '')
        
        # NOVOS CAMPOS DA UNIDADE
        gramado = 'Sim' if unidade_data.get('gramado') else 'Não'
        estacionamento = 'Sim' if unidade_data.get('estacionamento') else 'Não'
        estacionamento_coberto = 'Sim' if unidade_data.get('estacionamento_coberto') else 'Não'
        sala_curativo = 'Sim' if unidade_data.get('sala_curativo') else 'Não'
        sala_vacina = 'Sim' if unidade_data.get('sala_vacina') else 'Não'
        vidros_altos = 'Sim' if unidade_data.get('vidros_altos') else 'Não'
        perigo_limpar_vidros = 'Sim' if unidade_data.get('perigo_limpar_vidros') else 'Não'

        medidas = unidade_data.get('medidas', [])

        # Linha base com dados da unidade
        base_row = [
            localidade, unidade_nome, data, responsavel, qtd_func,
            gramado, estacionamento, estacionamento_coberto,
            sala_curativo, sala_vacina, vidros_altos, perigo_limpar_vidros
        ]

        if not medidas: # Adiciona a linha da unidade mesmo que não tenha medidas
            sheet.append(base_row + ["", "", "", "", "", "", ""]) # Campos de medida vazios
        else:
            for medida_data in medidas:
                row = base_row + [
                    medida_data.get('tipo', ''),
                    medida_data.get('largura', ''),
                    medida_data.get('altura', ''),
                    medida_data.get('area', ''),
                    medida_data.get('piso', ''),
                    medida_data.get('parede', ''),
                    medida_data.get('qtde', '')
                ]
                sheet.append(row)

    for column in sheet.columns:
        max_length = 0
        column = [cell for cell in column]
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        sheet.column_dimensions[column[0].column_letter].width = adjusted_width

    excel_file = io.BytesIO()
    workbook.save(excel_file)
    excel_file.seek(0)
    return excel_file.getvalue()

def enviar_email_com_excel(remetente, destinatario, assunto, corpo, excel_content, nome_arquivo):
    msg = MIMEMultipart()
    msg['From'] = remetente
    msg['To'] = destinatario
    msg['Subject'] = assunto

    msg.attach(MIMEText(corpo, 'plain', 'utf-8'))

    part = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    part.set_payload(excel_content)
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f'attachment; filename=\"{nome_arquivo}\"')
    msg.attach(part)

    try:
        with smtplib.SMTP(EMAIL_SERVER, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"Erro de autenticação SMTP: {e}")
        return False
    except smtplib.SMTPConnectError as e:
        print(f"Erro de conexão SMTP: {e}")
        return False
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False

# --- Rotas do Aplicativo ---
@app.route('/')
def index():
    data_hoje = datetime.date.today().isoformat()
    return render_template('index.html', data_hoje=data_hoje)

@app.route('/salvar_unidade', methods=['POST'])
def salvar_unidade():
    dados = request.get_json()
    
    localidade = dados.get('localidade')
    nome_unidade = dados.get('unidade')
    data_str = dados.get('data')
    responsavel = dados.get('responsavel')
    qtd_func = dados.get('qtd_func')

    # NOVOS CAMPOS DA UNIDADE
    gramado = dados.get('gramado', False)
    estacionamento = dados.get('estacionamento', False)
    estacionamento_coberto = dados.get('estacionamento_coberto', False)
    sala_curativo = dados.get('sala_curativo', False)
    sala_vacina = dados.get('sala_vacina', False)
    vidros_altos = dados.get('vidros_altos', False)
    perigo_limpar_vidros = dados.get('perigo_limpar_vidros', False)

    medidas_data = dados.get('medidas')

    if not localidade or not nome_unidade or not data_str:
        return jsonify({"status": "error", "message": "Dados obrigatórios (localidade, unidade, data) faltando."}), 400

    try:
        data_obj = datetime.datetime.strptime(data_str, '%Y-%m-%d').date()
        
        nova_unidade = Unidade(
            localidade=localidade,
            nome_unidade=nome_unidade,
            data=data_obj,
            responsavel=responsavel,
            qtd_func=qtd_func,
            # NOVOS CAMPOS
            gramado=gramado,
            estacionamento=estacionamento,
            estacionamento_coberto=estacionamento_coberto,
            sala_curativo=sala_curativo,
            sala_vacina=sala_vacina,
            vidros_altos=vidros_altos,
            perigo_limpar_vidros=perigo_limpar_vidros
        )
        db.session.add(nova_unidade)
        db.session.commit()

        if medidas_data:
            for medida_dict in medidas_data:
                nova_medida = Medida(
                    unidade_id=nova_unidade.id,
                    tipo=medida_dict.get('tipo'),
                    largura=medida_dict.get('largura'),
                    altura=medida_dict.get('altura'),
                    area=medida_dict.get('area'),
                    piso=medida_dict.get('piso'),
                    parede=medida_dict.get('parede'),
                    qtde=medida_dict.get('qtde')
                )
                db.session.add(nova_medida)
            db.session.commit()

        todas_unidades_db = Unidade.query.options(joinedload(Unidade.medidas)).all()
        
        dados_para_excel = []
        for unidade_db in todas_unidades_db:
            unidade_dict = {
                "localidade": unidade_db.localidade,
                "unidade": unidade_db.nome_unidade,
                "data": unidade_db.data.isoformat() if unidade_db.data else '',
                "responsavel": unidade_db.responsavel,
                "qtd_func": unidade_db.qtd_func,
                # NOVOS CAMPOS
                "gramado": unidade_db.gramado,
                "estacionamento": unidade_db.estacionamento,
                "estacionamento_coberto": unidade_db.estacionamento_coberto,
                "sala_curativo": unidade_db.sala_curativo,
                "sala_vacina": unidade_db.sala_vacina,
                "vidros_altos": unidade_db.vidros_altos,
                "perigo_limpar_vidros": unidade_db.perigo_limpar_vidros,
                "medidas": []
            }
            for medida_db in unidade_db.medidas:
                unidade_dict["medidas"].append({
                    "tipo": medida_db.tipo,
                    "largura": medida_db.largura,
                    "altura": medida_db.altura,
                    "area": medida_db.area,
                    "piso": medida_db.piso,
                    "parede": medida_db.parede,
                    "qtde": medida_db.qtde
                })
            dados_para_excel.append(unidade_dict)

        excel_content = gerar_excel(dados_para_excel)
        nome_arquivo = f"Dados_Unidades_Medidas_{datetime.date.today().isoformat()}.xlsx"

        if not FIXED_RECIPIENT_EMAIL or not EMAIL_USER or not EMAIL_PASS:
             return jsonify({"status": "warning", "message": "Unidade salva, mas e-mail não enviado: Variáveis de ambiente de e-mail não configuradas corretamente."}), 200

        email_enviado = enviar_email_com_excel(
            EMAIL_USER,
            FIXED_RECIPIENT_EMAIL,
            "Dados de Cadastro de Unidades e Medidas",
            "Segue em anexo o arquivo Excel com os dados atualizados de localidades e medidas.",
            excel_content,
            nome_arquivo
        )
        
        if email_enviado:
            return jsonify({"status": "success", "message": "Unidade salva e Excel enviado por e-mail com sucesso!"}), 200
        else:
            return jsonify({"status": "warning", "message": "Unidade salva, mas houve um erro ao enviar o e-mail."}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Erro ao salvar unidade no banco de dados: {e}")
        return jsonify({"status": "error", "message": f"Erro interno ao salvar unidade: {e}"}), 500

@app.route('/get_unidades_salvas', methods=['GET'])
def get_unidades_salvas():
    try:
        unidades_db = db.session.query(Unidade.nome_unidade).distinct().all()
        lista_unidades = [u[0] for u in unidades_db]
        return jsonify(lista_unidades)
    except Exception as e:
        print(f"Erro ao carregar unidades salvas do banco de dados: {e}")
        return jsonify([]), 500

@app.route('/get_tipos_piso', methods=['GET'])
def get_tipos_piso():
    return jsonify(TIPOS_PISO)

@app.route('/get_tipos_medida', methods=['GET'])
def get_tipos_medida():
    return jsonify(TIPOS_MEDIDA)

@app.route('/get_tipos_parede', methods=['GET'])
def get_tipos_parede():
    return jsonify(TIPOS_PAREDE)


if __name__ == '__main__':
    print(f"DATABASE_URL lida do ambiente: {os.environ.get('DATABASE_URL')}")
    app.run(debug=True)