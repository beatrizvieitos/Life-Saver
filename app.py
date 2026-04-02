# app.py – Aplicação Flask com autenticação, gestão de tarefas, listas de compras/medicamentos e partilha de tarefas/listas com amigos (com permissão de edição).

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import requests
import os
import json
import re
from dotenv import load_dotenv
from google import genai
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer


load_dotenv()   # Carrega as variáveis do ficheiro .env
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
client = genai.Client(api_key=GEMINI_API_KEY)

app = Flask(__name__)
app.secret_key = '549-937-952'
CORS(app)

app.config.update(
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=7)
)

# Configuração do envio de E-mails (Exemplo com Gmail)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME') # O teu email (ex: no .env)
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD') # Palavra-passe de aplicação (ex: no .env)

mail = Mail(app)

# Serializer para gerar tokens seguros baseados na tua secret_key
s = URLSafeTimedSerializer(app.secret_key)

# Configuração da base de dados
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'carolbea',
    'database': 'gestortarefas'
}

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

class User(UserMixin):
    # Adicionamos os novos campos com valores por defeito vazios ('')
    def __init__(self, id, username, nome='', apelido='', email='', localidade=''):
        self.id = id
        self.username = username
        self.nome = nome
        self.apelido = apelido
        self.email = email
        self.localidade = localidade

@login_manager.user_loader
def load_user(user_id):
    try:
        conn = mysql.connector.connect(**db_config)
        # O dictionary=True é importante para podermos usar user_db['nome']
        cursor = conn.cursor(dictionary=True) 
        
        # O SELECT * garante que trazemos todas as colunas da tabela utilizadores
        cursor.execute("SELECT * FROM utilizadores WHERE id = %s", (user_id,))
        user_db = cursor.fetchone()
        
        if user_db:
            # Criamos o utilizador com TODOS os dados que vieram da BD
            return User(
                id=user_db['id'],
                username=user_db['username'],
                nome=user_db.get('nome', ''),
                apelido=user_db.get('apelido', ''),
                email=user_db.get('email', ''),
                localidade=user_db.get('localidade', '')
            )
        return None
    except Exception as e:
        print(f"Erro ao carregar utilizador: {e}")
        return None
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

# --------------------------------------------------------------
# Função auxiliar para verificar se uma tabela existe
# --------------------------------------------------------------
def table_exists(table_name):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES LIKE %s", (table_name,))
        result = cursor.fetchone()
        return result is not None
    except Exception:
        return False
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

# --------------------------------------------------------------
# Rotas principais
# --------------------------------------------------------------
@app.route('/')
@app.route('/index.html')
@login_required
def index():
    return render_template('index.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

# --------------------------------------------------------------
# API de autenticação
# --------------------------------------------------------------
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    campos_obrigatorios = ['username', 'email', 'password', 'nome', 'apelido', 'localidade']
    for campo in campos_obrigatorios:
        if campo not in data or not data[campo]:
            return jsonify({'erro': f'O campo {campo} é obrigatório.'}), 400

    hashed_password = generate_password_hash(data['password'])

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        sql = """INSERT INTO utilizadores 
                 (username, email, password, nome, apelido, localidade) 
                 VALUES (%s, %s, %s, %s, %s, %s)"""
        valores = (data['username'], data['email'], hashed_password,
                   data['nome'], data['apelido'], data['localidade'])
        cursor.execute(sql, valores)
        conn.commit()
        return jsonify({'mensagem': 'Registado com sucesso!'}), 201
    except mysql.connector.IntegrityError:
        return jsonify({'erro': 'Este username ou e-mail já está em uso.'}), 409
    except mysql.connector.Error as err:
        return jsonify({'erro': f'Erro na base de dados: {err}'}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, password FROM utilizadores WHERE username=%s", (data['username'],))
        user = cursor.fetchone()
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

    if user and check_password_hash(user['password'], data['password']):
        login_user(User(id=user['id'], username=data['username']))
        return jsonify({'mensagem': 'Login efetuado com sucesso!'})

    return jsonify({'erro': 'Username ou palavra-passe incorretos.'}), 401

@app.route('/api/logout')
@login_required
def logout():
    logout_user()
    return jsonify({'mensagem': 'Logout efetuado.'})

@app.after_request
def add_security_headers(response):
    if request.endpoint and request.endpoint != 'static' and response.mimetype == 'text/html':
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

# --------------------------------------------------------------
# API de Tarefas (com suporte a partilha)
# --------------------------------------------------------------
@app.route('/api/tarefas', methods=['GET', 'POST'])
@login_required
def api_tarefas():
    if request.method == 'GET':
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)

            # Tarefas próprias
            cursor.execute("""
                SELECT id, nome_tarefa as tarefa, categoria, prioridade, estado, data_adicao,
                       1 as is_owner, NULL as owner_username, NULL as owner_nome, NULL as owner_apelido
                FROM tarefas
                WHERE user_id = %s
            """, (current_user.id,))
            own_tasks = cursor.fetchall()

            # Tarefas partilhadas – só se a tabela existir
            shared_tasks = []
            if table_exists('shared_tasks'):
                try:
                    cursor.execute("""
                        SELECT t.id, t.nome_tarefa as tarefa, t.categoria, t.prioridade, t.estado, t.data_adicao,
                               0 as is_owner,
                               u.username as owner_username,
                               u.nome as owner_nome,
                               u.apelido as owner_apelido
                        FROM shared_tasks st
                        JOIN tarefas t ON st.task_id = t.id
                        JOIN utilizadores u ON st.owner_id = u.id
                        WHERE st.shared_with_id = %s
                    """, (current_user.id,))
                    shared_tasks = cursor.fetchall()
                except mysql.connector.Error:
                    pass

            all_tasks = own_tasks + shared_tasks

            # Formatar datas
            for task in all_tasks:
                if task.get('data_adicao'):
                    task['data'] = task['data_adicao'].strftime("%d-%m-%Y")
                else:
                    task['data'] = ""
                if 'data_adicao' in task:
                    del task['data_adicao']

            return jsonify(all_tasks)

        except mysql.connector.Error as err:
            print("Erro ao carregar tarefas:", err)
            return jsonify([]), 200
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals() and conn.is_connected(): conn.close()

    elif request.method == 'POST':
        data = request.json
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            sql = "INSERT INTO tarefas (nome_tarefa, categoria, prioridade, estado, user_id) VALUES (%s, %s, %s, 'pendente', %s)"
            valores = (data['nome'], data['categoria'], data['prioridade'], current_user.id)
            cursor.execute(sql, valores)
            conn.commit()
            return jsonify({'mensagem': 'Tarefa adicionada com sucesso! ✅'}), 201
        except mysql.connector.Error as err:
            return jsonify({'erro': str(err)}), 500
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals() and conn.is_connected(): conn.close()

# --------------------------------------------------------------
# Alternar estado e apagar tarefas
# --------------------------------------------------------------
@app.route('/api/tarefas/<int:id_tarefa>/alternar', methods=['PUT'])
@login_required
def api_alternar_tarefa(id_tarefa):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id, estado FROM tarefas WHERE id = %s AND user_id = %s", (id_tarefa, current_user.id))
        tarefa = cursor.fetchone()
        if not tarefa:
            return jsonify({'erro': 'Tarefa não encontrada ou não tens permissão'}), 403

        estado_atual = tarefa['estado'].lower()
        novo_estado = 'pendente' if estado_atual == 'feito' else 'feito'
        cursor.execute("UPDATE tarefas SET estado = %s WHERE id = %s", (novo_estado, id_tarefa))
        conn.commit()
        return jsonify({'mensagem': 'Estado atualizado', 'novo_estado': novo_estado})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500
    finally:
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/tarefas/<int:id_tarefa>', methods=['DELETE'])
@login_required
def api_remover_tarefa(id_tarefa):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tarefas WHERE id = %s AND user_id = %s", (id_tarefa, current_user.id))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({'erro': 'Tarefa não encontrada ou não tens permissão'}), 403
        return jsonify({'mensagem': 'Tarefa apagada com sucesso!'})
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

# --------------------------------------------------------------
# API de Amigos e Partilha de Tarefas
# --------------------------------------------------------------
@app.route('/api/friends/request', methods=['POST'])
@login_required
def api_send_friend_request():
    data = request.json
    identifier = data.get('email')
    if not identifier:
        return jsonify({'erro': 'Username ou e-mail necessário'}), 400

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        if '@' in identifier:
            cursor.execute("SELECT id FROM utilizadores WHERE email = %s", (identifier,))
        else:
            cursor.execute("SELECT id FROM utilizadores WHERE username = %s", (identifier,))

        friend = cursor.fetchone()
        if not friend:
            return jsonify({'erro': 'Utilizador não encontrado'}), 404

        if friend['id'] == current_user.id:
            return jsonify({'erro': 'Não podes adicionar-te a ti mesmo'}), 400

        cursor.execute("""
            SELECT id, status FROM friendships 
            WHERE (user_id = %s AND friend_id = %s) OR (user_id = %s AND friend_id = %s)
        """, (current_user.id, friend['id'], friend['id'], current_user.id))
        existing = cursor.fetchone()
        if existing:
            if existing['status'] == 'accepted':
                return jsonify({'erro': 'Já são amigos'}), 400
            elif existing['status'] == 'pending':
                return jsonify({'erro': 'Pedido pendente'}), 400

        cursor.execute("INSERT INTO friendships (user_id, friend_id, status) VALUES (%s, %s, 'pending')",
                       (current_user.id, friend['id']))
        conn.commit()
        return jsonify({'mensagem': 'Pedido enviado com sucesso!'})

    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/friends', methods=['GET'])
@login_required
def api_list_friends():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        # Amigos aceites
        cursor.execute("""
            SELECT u.id, u.username, u.email, u.nome, u.apelido, f.status
            FROM friendships f
            JOIN utilizadores u ON (u.id = f.user_id OR u.id = f.friend_id)
            WHERE (f.user_id = %s OR f.friend_id = %s) AND f.status = 'accepted'
              AND u.id != %s
        """, (current_user.id, current_user.id, current_user.id))
        friends = cursor.fetchall()
        # Pedidos recebidos
        cursor.execute("""
            SELECT f.id as request_id, u.id as user_id, u.username, u.email, u.nome, u.apelido
            FROM friendships f
            JOIN utilizadores u ON f.user_id = u.id
            WHERE f.friend_id = %s AND f.status = 'pending'
        """, (current_user.id,))
        pending = cursor.fetchall()
        # Pedidos enviados
        cursor.execute("""
            SELECT f.id as request_id, u.id as user_id, u.username, u.email, u.nome, u.apelido
            FROM friendships f
            JOIN utilizadores u ON f.friend_id = u.id
            WHERE f.user_id = %s AND f.status = 'pending'
        """, (current_user.id,))
        sent = cursor.fetchall()
        return jsonify({'friends': friends, 'pending': pending, 'sent': sent})
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/friends/accept/<int:request_id>', methods=['PUT'])
@login_required
def api_accept_friend(request_id):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("UPDATE friendships SET status = 'accepted' WHERE id = %s AND friend_id = %s AND status = 'pending'",
                       (request_id, current_user.id))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({'erro': 'Pedido não encontrado ou não pode ser aceite'}), 404
        return jsonify({'mensagem': 'Amigo adicionado!'})
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/friends/decline/<int:request_id>', methods=['DELETE'])
@login_required
def api_decline_friend(request_id):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM friendships WHERE id = %s AND friend_id = %s AND status = 'pending'",
                       (request_id, current_user.id))
        conn.commit()
        return jsonify({'mensagem': 'Pedido recusado'})
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/friends/remove/<int:friend_id>', methods=['DELETE'])
@login_required
def api_remove_friend(friend_id):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM friendships 
            WHERE (user_id = %s AND friend_id = %s AND status = 'accepted')
               OR (user_id = %s AND friend_id = %s AND status = 'accepted')
        """, (current_user.id, friend_id, friend_id, current_user.id))
        conn.commit()
        return jsonify({'mensagem': 'Amigo removido'})
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/friends/list', methods=['GET'])
@login_required
def api_friends_list():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT u.id, u.nome, u.apelido, u.username
            FROM friendships f
            JOIN utilizadores u ON (u.id = f.user_id OR u.id = f.friend_id)
            WHERE (f.user_id = %s OR f.friend_id = %s) AND f.status = 'accepted'
              AND u.id != %s
        """, (current_user.id, current_user.id, current_user.id))
        friends = cursor.fetchall()
        return jsonify(friends)
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/tarefas/<int:task_id>/share', methods=['POST'])
@login_required
def api_share_task(task_id):
    data = request.json
    friend_id = data.get('friend_id')
    if not friend_id:
        return jsonify({'erro': 'ID do amigo necessário'}), 400
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM tarefas WHERE id = %s AND user_id = %s", (task_id, current_user.id))
        if not cursor.fetchone():
            return jsonify({'erro': 'Não tens permissão para partilhar esta tarefa'}), 403
        cursor.execute("""
            SELECT id FROM friendships 
            WHERE ((user_id = %s AND friend_id = %s) OR (user_id = %s AND friend_id = %s))
              AND status = 'accepted'
        """, (current_user.id, friend_id, friend_id, current_user.id))
        if not cursor.fetchone():
            return jsonify({'erro': 'Não és amigo deste utilizador'}), 403
        cursor.execute("""
            INSERT INTO shared_tasks (task_id, owner_id, shared_with_id) 
            VALUES (%s, %s, %s)
        """, (task_id, current_user.id, friend_id))
        conn.commit()
        return jsonify({'mensagem': 'Tarefa partilhada!'})
    except mysql.connector.Error as err:
        if err.errno == 1062:
            return jsonify({'erro': 'Tarefa já partilhada com este amigo'}), 409
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/tarefas/<int:task_id>/share/<int:friend_id>', methods=['DELETE'])
@login_required
def api_unshare_task(task_id, friend_id):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM shared_tasks 
            WHERE task_id = %s AND owner_id = %s AND shared_with_id = %s
        """, (task_id, current_user.id, friend_id))
        conn.commit()
        return jsonify({'mensagem': 'Partilha removida'})
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/tarefas/<int:task_id>/shares', methods=['GET'])
@login_required
def api_task_shares(task_id):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT st.shared_with_id, u.username, u.email
            FROM shared_tasks st
            JOIN utilizadores u ON st.shared_with_id = u.id
            WHERE st.task_id = %s AND st.owner_id = %s
        """, (task_id, current_user.id))
        shares = cursor.fetchall()
        return jsonify(shares)
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

# --------------------------------------------------------------
# Rotas para Notas
# --------------------------------------------------------------
@app.route('/notas')
@login_required
def notas_page():
    return render_template('notas.html')

@app.route('/api/notas', methods=['GET', 'POST'])
@login_required
def api_notas():
    if request.method == 'GET':
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM notas WHERE user_id = %s ORDER BY data_criacao DESC", (current_user.id,))
            notas = cursor.fetchall()
            return jsonify(notas)
        except mysql.connector.Error as err:
            return jsonify({'erro': str(err)}), 500
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals() and conn.is_connected(): conn.close()
    elif request.method == 'POST':
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            sql = "INSERT INTO notas (user_id, titulo, conteudo) VALUES (%s, '', '')"
            cursor.execute(sql, (current_user.id,))
            conn.commit()
            return jsonify({'mensagem': 'Nota criada com sucesso!', 'id': cursor.lastrowid}), 201
        except mysql.connector.Error as err:
            return jsonify({'erro': str(err)}), 500
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/notas/<int:id_nota>', methods=['PUT', 'DELETE'])
@login_required
def api_nota_individual(id_nota):
    if request.method == 'PUT':
        data = request.json
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            sql = "UPDATE notas SET titulo = %s, conteudo = %s WHERE id = %s AND user_id = %s"
            cursor.execute(sql, (data['titulo'], data['conteudo'], id_nota, current_user.id))
            conn.commit()
            return jsonify({'mensagem': 'Nota atualizada!'})
        except mysql.connector.Error as err:
            return jsonify({'erro': str(err)}), 500
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals() and conn.is_connected(): conn.close()
    elif request.method == 'DELETE':
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM notas WHERE id = %s AND user_id = %s", (id_nota, current_user.id))
            conn.commit()
            return jsonify({'mensagem': 'Nota apagada!'})
        except mysql.connector.Error as err:
            return jsonify({'erro': str(err)}), 500
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals() and conn.is_connected(): conn.close()

# --------------------------------------------------------------
# Rotas para Lista de Compras (com suporte a partilha e permissões)
# --------------------------------------------------------------
@app.route('/listas')
@login_required
def listas_page():
    return render_template('listas.html')

@app.route('/api/compras', methods=['GET', 'POST'])
@login_required
def api_gerir_compras():
    if request.method == 'GET':
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)

            # Compras próprias – o utilizador é o dono
            cursor.execute("""
                SELECT c.*, 1 as is_owner, NULL as owner_name, NULL as can_edit
                FROM compras c
                WHERE c.utilizador_id = %s
            """, (current_user.id,))
            own_items = cursor.fetchall()

            # Compras partilhadas (de outros utilizadores)
            shared_items = []
            if table_exists('shared_shopping_lists'):
                try:
                    cursor.execute("""
                        SELECT c.*, 0 as is_owner,
                               CONCAT(u.nome, ' ', u.apelido) as owner_name,
                               s.can_edit
                        FROM shared_shopping_lists s
                        JOIN compras c ON c.utilizador_id = s.owner_id
                        JOIN utilizadores u ON s.owner_id = u.id
                        WHERE s.shared_with_id = %s
                    """, (current_user.id,))
                    shared_items = cursor.fetchall()
                except mysql.connector.Error:
                    pass

            all_items = own_items + shared_items

            # Converter preços para float
            for item in all_items:
                item['preco_unidade'] = float(item['preco_unidade'])

            return jsonify(all_items)
        except mysql.connector.Error as err:
            return jsonify({'erro': str(err)}), 500
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals() and conn.is_connected(): conn.close()

    elif request.method == 'POST':
        dados = request.json
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO compras (utilizador_id, produto, supermercado, quantidade, preco_unidade) VALUES (%s, %s, %s, %s, %s)",
                (current_user.id, dados['produto'], dados.get('supermercado', ''), dados['quantidade'], dados['preco_unidade'])
            )
            if dados.get('supermercado'):
                cursor.execute("""
                    INSERT INTO catalogo_precos (produto, supermercado, preco) 
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE preco = %s
                """, (dados['produto'], dados['supermercado'], dados['preco_unidade'], dados['preco_unidade']))
            conn.commit()
            return jsonify({'mensagem': 'Produto adicionado!'}), 201
        except mysql.connector.Error as err:
            return jsonify({'erro': str(err)}), 500
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/compras/<int:id_compra>/alternar', methods=['PUT'])
@login_required
def api_alternar_compra(id_compra):
    """
    Alterna o estado 'comprado' de um item da lista de compras.
    Permite edição ao dono ou a utilizadores com partilha ativa e can_edit=1.
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Obtém o dono do item
        cursor.execute("SELECT utilizador_id FROM compras WHERE id = %s", (id_compra,))
        item = cursor.fetchone()
        if not item:
            return jsonify({'erro': 'Item não encontrado'}), 404

        dono_id = item['utilizador_id']
        user_id = int(current_user.id)  # Converte para inteiro

        # Caso 1: o utilizador é o dono
        if dono_id == user_id:
            cursor.execute("UPDATE compras SET comprado = NOT comprado WHERE id = %s", (id_compra,))
            conn.commit()
            return jsonify({'mensagem': 'Estado atualizado!'})

        # Caso 2: verifica permissão de edição partilhada
        cursor.execute("""
            SELECT can_edit FROM shared_shopping_lists
            WHERE owner_id = %s AND shared_with_id = %s
        """, (dono_id, user_id))
        share = cursor.fetchone()

        if not share or share.get('can_edit') != 1:
            return jsonify({'erro': 'Não tens permissão para editar este item'}), 403

        # Tem permissão – atualiza
        cursor.execute("UPDATE compras SET comprado = NOT comprado WHERE id = %s", (id_compra,))
        conn.commit()
        return jsonify({'mensagem': 'Estado atualizado!'})

    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/compras/<int:id_compra>', methods=['DELETE'])
@login_required
def api_remover_compra(id_compra):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        # Só permite apagar se o item pertencer ao utilizador atual ou se tiver permissão de edição
        cursor.execute("SELECT utilizador_id FROM compras WHERE id = %s", (id_compra,))
        result = cursor.fetchone()
        if not result:
            return jsonify({'erro': 'Item não encontrado'}), 404
        if result[0] != current_user.id:
            cursor.execute("""
                SELECT can_edit FROM shared_shopping_lists
                WHERE owner_id = %s AND shared_with_id = %s
            """, (result[0], current_user.id))
            share = cursor.fetchone()
            if not share or not share[0]:
                return jsonify({'erro': 'Não tens permissão para eliminar este item'}), 403
        cursor.execute("DELETE FROM compras WHERE id = %s", (id_compra,))
        conn.commit()
        return jsonify({'mensagem': 'Produto removido!'})
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

# --------------------------------------------------------------
# Rotas para Catálogo de Preços (auto‑fill)
# --------------------------------------------------------------
@app.route('/api/preco_estimado', methods=['GET'])
@login_required
def api_obter_preco():
    produto = request.args.get('produto')
    supermercado = request.args.get('supermercado')
    if not produto or not supermercado:
        return jsonify({'preco': None})
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT preco FROM catalogo_precos WHERE LOWER(produto) = LOWER(%s) AND LOWER(supermercado) = LOWER(%s)", (produto, supermercado))
        resultado = cursor.fetchone()
        if resultado:
            return jsonify({'preco': float(resultado['preco'])})
        return jsonify({'preco': None})
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/produto_mais_barato', methods=['GET'])
@login_required
def api_produto_mais_barato():
    produto = request.args.get('produto')
    if not produto:
        return jsonify({'erro': 'Produto não especificado'}), 400
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT supermercado, MIN(preco) as preco_minimo
            FROM catalogo_precos
            WHERE LOWER(produto) = LOWER(%s)
            GROUP BY supermercado
            ORDER BY preco_minimo ASC
            LIMIT 1
        """, (produto,))
        resultado = cursor.fetchone()
        if resultado:
            return jsonify({
                'supermercado': resultado['supermercado'],
                'preco': float(resultado['preco_minimo'])
            })
        else:
            return jsonify({'mensagem': 'Não há informação de preços para este produto.'}), 404
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

# --------------------------------------------------------------
# Rotas para Lista de Medicamentos (com suporte a partilha e permissões)
# --------------------------------------------------------------
@app.route('/medicamentos')
@login_required
def medicamentos_page():
    return render_template('medicamentos.html')

@app.route('/api/membros', methods=['GET', 'POST'])
@login_required
def api_membros():
    if request.method == 'GET':
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, nome FROM membros_familia WHERE user_id = %s ORDER BY nome", (current_user.id,))
            membros = cursor.fetchall()
            return jsonify(membros)
        except mysql.connector.Error as err:
            return jsonify({'erro': str(err)}), 500
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals() and conn.is_connected(): conn.close()
    elif request.method == 'POST':
        data = request.json
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO membros_familia (user_id, nome) VALUES (%s, %s)", (current_user.id, data['nome']))
            conn.commit()
            return jsonify({'id': cursor.lastrowid, 'nome': data['nome']}), 201
        except mysql.connector.IntegrityError:
            return jsonify({'erro': 'Já existe um membro com este nome.'}), 409
        except mysql.connector.Error as err:
            return jsonify({'erro': str(err)}), 500
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/membros/<int:id_membro>', methods=['DELETE'])
@login_required
def api_remover_membro(id_membro):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM membros_familia WHERE id = %s AND user_id = %s", (id_membro, current_user.id))
        conn.commit()
        return jsonify({'mensagem': 'Membro removido!'})
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/medicamentos', methods=['GET', 'POST'])
@login_required
def api_medicamentos():
    if request.method == 'GET':
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)

            # Medicamentos próprios
            cursor.execute("""
                SELECT m.id, m.nome, m.tipo, m.comprado, m.membro_id,
                       f.nome as membro_nome, 1 as is_owner, NULL as owner_name, NULL as can_edit
                FROM medicamentos m
                LEFT JOIN membros_familia f ON m.membro_id = f.id
                WHERE m.user_id = %s
                ORDER BY m.tipo DESC, f.nome, m.nome
            """, (current_user.id,))
            own_meds = cursor.fetchall()

            # Medicamentos partilhados (de outros utilizadores)
            shared_meds = []
            if table_exists('shared_medication_lists'):
                try:
                    cursor.execute("""
                        SELECT m.id, m.nome, m.tipo, m.comprado, m.membro_id,
                               f.nome as membro_nome, 0 as is_owner,
                               CONCAT(u.nome, ' ', u.apelido) as owner_name,
                               s.can_edit
                        FROM shared_medication_lists s
                        JOIN medicamentos m ON m.user_id = s.owner_id
                        LEFT JOIN membros_familia f ON m.membro_id = f.id
                        JOIN utilizadores u ON s.owner_id = u.id
                        WHERE s.shared_with_id = %s
                        ORDER BY m.tipo DESC, f.nome, m.nome
                    """, (current_user.id,))
                    shared_meds = cursor.fetchall()
                except mysql.connector.Error:
                    pass

            all_meds = own_meds + shared_meds
            return jsonify(all_meds)
        except mysql.connector.Error as err:
            return jsonify({'erro': str(err)}), 500
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals() and conn.is_connected(): conn.close()

    elif request.method == 'POST':
        data = request.json
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            membro_id = data.get('membro_id') if data.get('tipo') == 'habitual' else None
            cursor.execute("""
                INSERT INTO medicamentos (user_id, nome, tipo, membro_id, comprado)
                VALUES (%s, %s, %s, %s, %s)
            """, (current_user.id, data['nome'], data['tipo'], membro_id, False))
            conn.commit()
            return jsonify({'id': cursor.lastrowid, 'mensagem': 'Medicamento adicionado!'}), 201
        except mysql.connector.Error as err:
            return jsonify({'erro': str(err)}), 500
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals() and conn.is_connected(): conn.close()



@app.route('/api/medicamentos/<int:id_medicamento>/alternar', methods=['PUT'])
@login_required
def api_alternar_medicamento(id_medicamento):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM medicamentos WHERE id = %s", (id_medicamento,))
        result = cursor.fetchone()
        if not result:
            return jsonify({'erro': 'Medicamento não encontrado'}), 404
        
        user_id = int(current_user.id)  # 🔹 Conversão para inteiro
        if result[0] != user_id:
            cursor.execute("""
                SELECT can_edit FROM shared_medication_lists
                WHERE owner_id = %s AND shared_with_id = %s
            """, (result[0], user_id))
            share = cursor.fetchone()
            if not share or not share[0]:
                return jsonify({'erro': 'Não tens permissão para alterar este medicamento'}), 403
        cursor.execute("UPDATE medicamentos SET comprado = NOT comprado WHERE id = %s", (id_medicamento,))
        conn.commit()
        return jsonify({'mensagem': 'Estado alterado!'})
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

# --------------------------------------------------------------
# Rotas para partilha de listas (compras e medicamentos) com permissões
# --------------------------------------------------------------
# Partilha da lista de compras
@app.route('/api/shopping/share', methods=['POST'])
@login_required
def api_share_shopping_list():
    data = request.json
    friend_id = data.get('friend_id')
    can_edit = data.get('can_edit', False)
    if not friend_id:
        return jsonify({'erro': 'ID do amigo necessário'}), 400
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        # Verificar se são amigos
        cursor.execute("""
            SELECT id FROM friendships 
            WHERE ((user_id = %s AND friend_id = %s) OR (user_id = %s AND friend_id = %s))
              AND status = 'accepted'
        """, (current_user.id, friend_id, friend_id, current_user.id))
        if not cursor.fetchone():
            return jsonify({'erro': 'Não és amigo deste utilizador'}), 403
        # Inserir ou atualizar partilha com permissão
        cursor.execute("""
            INSERT INTO shared_shopping_lists (owner_id, shared_with_id, can_edit)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE can_edit = %s
        """, (current_user.id, friend_id, can_edit, can_edit))
        conn.commit()
        return jsonify({'mensagem': 'Lista de compras partilhada e atualizada!'})
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/shopping/unshare/<int:friend_id>', methods=['DELETE'])
@login_required
def api_unshare_shopping_list(friend_id):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM shared_shopping_lists 
            WHERE owner_id = %s AND shared_with_id = %s
        """, (current_user.id, friend_id))
        conn.commit()
        return jsonify({'mensagem': 'Partilha removida'})
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/shopping/shares', methods=['GET'])
@login_required
def api_shopping_shares():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT u.id, u.username, u.nome, u.apelido, s.can_edit
            FROM shared_shopping_lists s
            JOIN utilizadores u ON s.shared_with_id = u.id
            WHERE s.owner_id = %s
        """, (current_user.id,))
        shares = cursor.fetchall()
        return jsonify(shares)
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

# Partilha da lista de medicamentos
@app.route('/api/medications/share', methods=['POST'])
@login_required
def api_share_medication_list():
    data = request.json
    friend_id = data.get('friend_id')
    can_edit = data.get('can_edit', False)
    if not friend_id:
        return jsonify({'erro': 'ID do amigo necessário'}), 400
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id FROM friendships 
            WHERE ((user_id = %s AND friend_id = %s) OR (user_id = %s AND friend_id = %s))
              AND status = 'accepted'
        """, (current_user.id, friend_id, friend_id, current_user.id))
        if not cursor.fetchone():
            return jsonify({'erro': 'Não és amigo deste utilizador'}), 403
        cursor.execute("""
            INSERT INTO shared_medication_lists (owner_id, shared_with_id, can_edit)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE can_edit = %s
        """, (current_user.id, friend_id, can_edit, can_edit))
        conn.commit()
        return jsonify({'mensagem': 'Lista de medicamentos partilhada e atualizada!'})
    except mysql.connector.Error as err:
        if err.errno == 1062:
            return jsonify({'erro': 'Lista já partilhada com este amigo'}), 409
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/medications/unshare/<int:friend_id>', methods=['DELETE'])
@login_required
def api_unshare_medication_list(friend_id):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM shared_medication_lists 
            WHERE owner_id = %s AND shared_with_id = %s
        """, (current_user.id, friend_id))
        conn.commit()
        return jsonify({'mensagem': 'Partilha removida'})
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/medications/shares', methods=['GET'])
@login_required
def api_medications_shares():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT u.id, u.username, u.nome, u.apelido, s.can_edit
            FROM shared_medication_lists s
            JOIN utilizadores u ON s.shared_with_id = u.id
            WHERE s.owner_id = %s
        """, (current_user.id,))
        shares = cursor.fetchall()
        return jsonify(shares)
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

# --------------------------------------------------------------
# Rotas para estatísticas
# --------------------------------------------------------------
@app.route('/api/tarefas/ultimo_mes')
@login_required
def api_tarefas_ultimo_mes():
    from datetime import datetime, timedelta
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT DATE(data_adicao) as data, COUNT(*) as total
            FROM tarefas
            WHERE user_id = %s AND data_adicao >= CURDATE() - INTERVAL 30 DAY
            GROUP BY DATE(data_adicao)
        """, (current_user.id,))
        resultados = cursor.fetchall()
        contagem = {str(row['data']): row['total'] for row in resultados}
        hoje = datetime.now().date()
        ultimos_dias = []
        for i in range(29, -1, -1):
            dia = hoje - timedelta(days=i)
            dia_str = dia.strftime('%Y-%m-%d')
            ultimos_dias.append({
                'data': dia_str,
                'total': contagem.get(dia_str, 0)
            })
        return jsonify(ultimos_dias)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/tarefas/estado')
@login_required
def api_tarefas_estado():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN estado = 'feito' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN estado = 'pendente' THEN 1 ELSE 0 END) as pendentes
            FROM tarefas
            WHERE user_id = %s
        """, (current_user.id,))
        resultado = cursor.fetchone()
        return jsonify({
            'concluidas': resultado['concluidas'] or 0,
            'pendentes': resultado['pendentes'] or 0
        })
    except Exception as e:
        return jsonify({'erro': str(e)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()



@app.route('/estatisticas')
@login_required
def estatisticas_page():
    return render_template('estatisticas.html')

# -------------------------------------------------------------------------------------------------------
# Rotas para limpar a lista de compras (apaga apenas os itens do próprio utilizador, não os partilhados)
# -------------------------------------------------------------------------------------------------------

@app.route('/api/compras/limpar', methods=['DELETE'])
@login_required
def api_limpar_compras():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        # Apaga apenas os itens do próprio utilizador (não apaga os que lhe foram partilhados)
        cursor.execute("DELETE FROM compras WHERE utilizador_id = %s", (current_user.id,))
        conn.commit()
        return jsonify({'mensagem': 'Carrinho limpo com sucesso!'}), 200
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

# ----------------------------------------------------------------------------------
# Rotas para obtenção de preços de produtos (com cache, Groq e Gemini como fallback)
# ----------------------------------------------------------------------------------

@app.route('/api/compras/preco-produto', methods=['POST'])
def preco_produto_groq():
    dados = request.json
    produto = dados.get('produto')
    
    if not produto:
        return jsonify({"sucesso": False, "erro": "Produto não especificado"}), 400

    # Tentar Cache da Base de Dados
    def get_cached_precos(prod_nome):
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT supermercado, preco FROM catalogo_precos WHERE LOWER(produto) = LOWER(%s)",
                (prod_nome,)
            )
            rows = cursor.fetchall()
            if rows:
                return {row['supermercado']: float(row['preco']) for row in rows}
        except Exception as e:
            print(f"Erro ao ler cache: {e}")
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals() and conn.is_connected(): conn.close()
        return None

    cached = get_cached_precos(produto)
    if cached:
        print(f"[CACHE] Preços encontrados para {produto}")
        return jsonify({"sucesso": True, "precos": cached, "origem": "base_dados"})

    # Tentar Groq
    precos = None
    try:
        print(f"[IA] A pedir à Groq para: {produto}...")
        prompt = f"""
        Procura o preço atual, realista e médio em euros (€) do produto "{produto}" nos supermercados portugueses no ano de 2026.
        Considera a inflação recente. NÃO inventes preços absurdamente baixos nem uses valores de anos passados.
        Queremos o valor de uma marca branca normal ou o produto mais comum.
        Supermercados: Continente, Pingo Doce, Lidl, Auchan, Mercadona, Aldi.
        Devolve APENAS um JSON puro (sem texto antes ou depois): {{"Continente": 1.25, "Pingo Doce": 1.19, "Lidl": 1.20, "Auchan": 1.22, "Mercadona": 1.20, "Aldi": 1.19}}
        """
        response = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            },
            timeout=8
        )
        
        if response.status_code == 200:
            conteudo = response.json()["choices"][0]["message"]["content"]
            precos = json.loads(conteudo)
            save_to_cache(produto, precos)
            return jsonify({"sucesso": True, "precos": precos, "origem": "groq"})
        
        elif response.status_code == 429:
            print("Groq atingiu o limite (429). A tentar Gemini...")
    except Exception as e:
        print(f"Erro na Groq: {e}")

    # Tentar Gemini (Fallback Final)
    try:
        print(f"[IA] A pedir ao Gemini para: {produto}...")
        response = client.models.generate_content(
            model="models/gemini-2.0-flash",
            contents=f"""
                Procura o preço atual, realista e médio em euros (€) do produto "{produto}" nos supermercados portugueses no ano de 2026.
                Considera a inflação recente. NÃO inventes preços absurdamente baixos nem uses valores de anos passados.
                Queremos o valor de uma marca branca normal ou o produto mais comum.
                Supermercados: Continente, Pingo Doce, Lidl, Auchan, Mercadona, Aldi.
                Devolve APENAS um JSON puro (sem texto antes ou depois): {{"Continente": 1.25, "Pingo Doce": 1.19, "Lidl": 1.20, "Auchan": 1.22, "Mercadona": 1.20, "Aldi": 1.19}}
                """
        )
        text = response.text
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            precos = json.loads(json_match.group())
            save_to_cache(produto, precos)
            return jsonify({"sucesso": True, "precos": precos, "origem": "gemini"})
    except Exception as e:
        print(f"Erro no Gemini: {e}")

    return jsonify({"sucesso": False, "erro": "Limite de todas as APIs excedido. Tenta mais tarde."}), 429

# Função auxiliar para guardar no cache
def save_to_cache(produto, precos):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        for sup, preco in precos.items():
            cursor.execute("""
                INSERT INTO catalogo_precos (produto, supermercado, preco)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE preco = %s
            """, (produto, sup, preco, preco))
        conn.commit()
    except Exception as e:
        print(f"Erro ao salvar cache: {e}")
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

        # ==============================================================
# NOVO MÓDULO: GESTÃO DE RECEITAS E INTEGRAÇÃO DE COMPRAS
# ==============================================================

@app.route('/receitas')
@login_required
def receitas_page():
    return render_template('receitas.html')

@app.route('/api/receitas/gerar', methods=['POST'])
@login_required
def api_gerar_receita():
    """Pede à IA (Groq com fallback para Gemini) para criar uma receita e listar ingredientes."""
    dados = request.json
    prato = dados.get('prato')
    
    if not prato:
        return jsonify({"erro": "Nome do prato não fornecido."}), 400

    prompt = f"""
    És um chef profissional português. Cria a melhor receita clássica para "{prato}".
    Devolve APENAS um objeto JSON estrito com esta estrutura, sem qualquer texto adicional ou formatação markdown:
    {{
        "nome": "Nome completo do prato",
        "instrucoes": "Passo 1: ... Passo 2: ... (tudo numa string com \\n para quebras de linha)",
        "ingredientes": [
            {{"produto": "Nome do Ingrediente", "quantidade": "Quantidade exata (ex: 500g, 2 unidades)"}}
        ]
    }}
    Usa ingredientes comuns em supermercados portugueses.
    """

    receita_json = None

    # 1. Tentar Groq
    try:
        response = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "response_format": {"type": "json_object"}
            },
            timeout=10
        )
        if response.status_code == 200:
            conteudo = response.json()["choices"][0]["message"]["content"]
            receita_json = json.loads(conteudo)
    except Exception as e:
        print(f"Erro ao gerar receita na Groq: {e}")

    # 2. Tentar Gemini (Fallback)
    if not receita_json:
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            text = response.text
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                receita_json = json.loads(json_match.group())
        except Exception as e:
            print(f"Erro ao gerar receita no Gemini: {e}")

    if receita_json:
        return jsonify({"sucesso": True, "receita": receita_json})
    else:
        return jsonify({"erro": "Não foi possível gerar a receita. Tenta novamente."}), 500

@app.route('/api/receitas/guardar', methods=['POST'])
@login_required
def api_guardar_receita():
    """Guarda a receita gerada na base de dados do utilizador."""
    dados = request.json
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # Inserir Receita
        cursor.execute(
            "INSERT INTO receitas_guardadas (user_id, nome, instrucoes) VALUES (%s, %s, %s)",
            (current_user.id, dados['nome'], dados['instrucoes'])
        )
        receita_id = cursor.lastrowid
        
        # Inserir Ingredientes
        for ing in dados['ingredientes']:
            cursor.execute(
                "INSERT INTO ingredientes_receita (receita_id, produto, quantidade) VALUES (%s, %s, %s)",
                (receita_id, ing['produto'], ing['quantidade'])
            )
        conn.commit()
        return jsonify({'mensagem': 'Receita guardada com sucesso!'}), 201
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/receitas/listar', methods=['GET'])
@login_required
def api_listar_receitas():
    """Devolve todas as receitas guardadas pelo utilizador."""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, nome, instrucoes FROM receitas_guardadas WHERE user_id = %s ORDER BY data_criacao DESC", (current_user.id,))
        receitas = cursor.fetchall()
        
        for receita in receitas:
            cursor.execute("SELECT produto, quantidade FROM ingredientes_receita WHERE receita_id = %s", (receita['id'],))
            receita['ingredientes'] = cursor.fetchall()
            
        return jsonify(receitas)
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/receitas/comprar', methods=['POST'])
@login_required
def api_adicionar_compras_receita():
    """Adiciona a lista de ingredientes à lista principal de Compras do utilizador."""
    ingredientes = request.json.get('ingredientes', [])
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        for ing in ingredientes:
            # Assume quantidade como 1 para simplificar, com a descrição do ingrediente a conter o peso
            produto_descritivo = f"{ing['produto']} ({ing['quantidade']})"
            cursor.execute(
                "INSERT INTO compras (utilizador_id, produto, supermercado, quantidade, preco_unidade) VALUES (%s, %s, %s, %s, %s)",
                (current_user.id, produto_descritivo, 'Todos', 1, 0.0)
            )
        conn.commit()
        return jsonify({'mensagem': 'Ingredientes adicionados à tua Lista de Compras!'})
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/receitas/<int:receita_id>', methods=['DELETE'])
@login_required
def api_apagar_receita(receita_id):
    """Apaga uma receita guardada pelo utilizador atual."""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # Garante que a receita pertence a este utilizador antes de apagar
        cursor.execute(
            "DELETE FROM receitas_guardadas WHERE id = %s AND user_id = %s",
            (receita_id, current_user.id)
        )
        conn.commit()
        
        if cursor.rowcount > 0:
            return jsonify({'mensagem': 'Receita apagada com sucesso!'}), 200
        else:
            return jsonify({'erro': 'Não foi possível apagar a receita.'}), 403
            
    except mysql.connector.Error as err:
        return jsonify({'erro': str(err)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

# --------------------------------------------------------------
# Recuperação de Conta
# --------------------------------------------------------------

@app.route('/api/esqueci_username', methods=['POST'])
def esqueci_username():
    data = request.json
    email = data.get('email')
    
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT username FROM utilizadores WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if user:
            msg = Message('Recuperação de Nome de Utilizador', 
                          sender=app.config['MAIL_USERNAME'], 
                          recipients=[email])
            msg.body = f"Olá!\n\nO teu nome de utilizador é: {user['username']}\n\nCumprimentos,\nEquipa Life Saver"
            mail.send(msg)
            
        # Retornamos sucesso mesmo que não exista para não revelar e-mails registados (boa prática de segurança)
        return jsonify({'mensagem': 'Se o e-mail existir no nosso sistema, receberás o teu nome de utilizador em breve.'}), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/api/esqueci_password', methods=['POST'])
def esqueci_password():
    data = request.json
    email = data.get('email')
    
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM utilizadores WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if user:
            # Gera um token válido por 1 hora (3600 segundos)
            token = s.dumps(email, salt='recuperacao-password')
            link = request.url_root + f'reset_password/{token}'
            
            msg = Message('Redefinição de Palavra-passe', 
                          sender=app.config['MAIL_USERNAME'], 
                          recipients=[email])
            msg.body = f"Olá!\n\nClica no link abaixo para redefinir a tua palavra-passe. O link é válido por 1 hora.\n{link}\n\nSe não pediste isto, ignora este e-mail."
            mail.send(msg)
            
        return jsonify({'mensagem': 'Se o e-mail existir, receberás um link de recuperação.'}), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        # Verifica o token (expira em 3600 segundos = 1 hora)
        email = s.loads(token, salt='recuperacao-password', max_age=3600)
    except Exception:
        return "O link de recuperação é inválido ou expirou.", 400

    if request.method == 'GET':
        # Retorna uma página HTML simples para definir a nova password
        return '''
        <form method="POST">
            <h2>Redefinir Palavra-passe</h2>
            <input type="password" name="password" placeholder="Nova Palavra-passe" required>
            <button type="submit">Atualizar</button>
        </form>
        '''
    elif request.method == 'POST':
        nova_password = request.form.get('password')
        hashed_password = generate_password_hash(nova_password)
        
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute("UPDATE utilizadores SET password = %s WHERE email = %s", (hashed_password, email))
            conn.commit()
            return "Palavra-passe atualizada com sucesso! Já podes fazer <a href='/login'>login</a>."
        except Exception as e:
            return "Erro ao atualizar a base de dados.", 500
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals() and conn.is_connected(): conn.close()

# --- Rota para renderizar a página de Perfil ---
@app.route('/perfil')
@login_required
def perfil():
    # O objeto 'current_user' já contém os dados do utilizador logado
    return render_template('perfil.html', user=current_user)

@app.route('/api/user/update', methods=['POST'])
@login_required
def update_user():
    data = request.json
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        query = """
            UPDATE utilizadores 
            SET nome = %s, apelido = %s, email = %s, localidade = %s 
            WHERE id = %s
        """
        cursor.execute(query, (data['nome'], data['apelido'], data['email'], data['localidade'], current_user.id))
        conn.commit()
        
        return jsonify({'mensagem': 'Dados atualizados com sucesso!'}), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()



@app.route('/api/user/change_password', methods=['POST'])
@login_required
def change_password():
    data = request.json
    antiga = data.get('antiga')
    nova = data.get('nova')
    confirmacao = data.get('confirmacao')

    if nova != confirmacao:
        return jsonify({'erro': 'As novas palavras-passe não coincidem.'}), 400
    
    if len(nova) < 6:
        return jsonify({'erro': 'A nova palavra-passe deve ter pelo menos 6 caracteres.'}), 400

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # Verificar se a password antiga está correta
        cursor.execute("SELECT password FROM utilizadores WHERE id = %s", (current_user.id,))
        user = cursor.fetchone()

        if not user or not check_password_hash(user['password'], antiga):
            return jsonify({'erro': 'A palavra-passe antiga está incorreta.'}), 400

        # Atualizar para a nova hash
        nova_hash = generate_password_hash(nova)
        cursor.execute("UPDATE utilizadores SET password = %s WHERE id = %s", (nova_hash, current_user.id))
        conn.commit()

        return jsonify({'mensagem': 'Palavra-passe alterada com sucesso!'}), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals() and conn.is_connected(): conn.close()

# --------------------------------------------------------------
# Executar a aplicação
# --------------------------------------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)