import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração do MySQL (edite conforme seu ambiente)
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),      # Altere para o host do seu MySQL
    'user': os.getenv('DB_USER'),   # Altere para seu usuário
    'password': os.getenv('DB_PASSWORD'), # Altere para sua senha
    'database': os.getenv('DB_NAME')  # Altere para seu banco de dados
}

_conn = None
_cursor = None

def connect_and_init():
    global _conn, _cursor
    if _conn is None or _cursor is None:
        _conn = mysql.connector.connect(**DB_CONFIG)
        _cursor = _conn.cursor()
        _cursor.execute('''
            CREATE TABLE IF NOT EXISTS eventos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nome VARCHAR(255),
                tipo_evento ENUM('entrada','saida'),
                data_hora TIMESTAMP,
                confianca FLOAT,
                camera_id VARCHAR(50)
            )
        ''')
        _conn.commit()

def insert_evento(nome, confianca, tipo_evento, camera_id):
    global _conn, _cursor
    if _conn is None or _cursor is None:
        connect_and_init()
    now = datetime.now()
    _cursor.execute(
        "INSERT INTO eventos (nome, tipo_evento, data_hora, confianca, camera_id) VALUES (%s, %s, %s, %s, %s)",
        (nome, tipo_evento, now, float(confianca), camera_id)
    )
    _conn.commit()

def close_connection():
    global _conn, _cursor
    if _cursor:
        _cursor.close()
    if _conn:
        _conn.close()
    _cursor = None
    _conn = None

def calcular_tempos_permanencia(nome=None):
    """
    Retorna uma lista de tuplas (nome, hora_entrada, hora_saida, tempo_minutos) para cada par entrada/saida.
    Se nome for fornecido, filtra apenas para essa pessoa.
    """
    global _conn, _cursor
    if _conn is None or _cursor is None:
        connect_and_init()
    query = '''
        SELECT 
            entrada.nome,
            entrada.data_hora AS hora_entrada,
            saida.data_hora AS hora_saida,
            TIMESTAMPDIFF(MINUTE, entrada.data_hora, saida.data_hora) AS tempo_minutos
        FROM
            eventos entrada
        JOIN
            eventos saida
            ON entrada.nome = saida.nome
            AND saida.tipo_evento = 'saida'
            AND entrada.tipo_evento = 'entrada'
            AND saida.data_hora > entrada.data_hora
        WHERE
            NOT EXISTS (
                SELECT 1 FROM eventos s2
                WHERE s2.nome = entrada.nome
                AND s2.tipo_evento = 'saida'
                AND s2.data_hora > entrada.data_hora
                AND s2.data_hora < saida.data_hora
            )
    '''
    params = ()
    if nome:
        query += ' AND entrada.nome = %s'
        params = (nome,)
    query += '\nORDER BY entrada.nome, entrada.data_hora;'
    _cursor.execute(query, params)
    return _cursor.fetchall()
