from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_mysqldb import MySQL, MySQLdb
from flask_cors import CORS
import os 
import jwt 
from datetime import datetime
import datetime

app = Flask(__name__, static_url_path='/static')
CORS(app)

SECRET_KEY = '12345666'
app.config['MYSQL_HOST'] = 'bwmc0ch6np8udxefdc4p-mysql.services.clever-cloud.com'
app.config['MYSQL_USER'] = 'ub5pgwfmqlphbjdl'
app.config['MYSQL_PASSWORD'] = 'UofpetGdsNMdjfA4reNC'
app.config['MYSQL_DB'] = 'bwmc0ch6np8udxefdc4p'

mysql = MySQL(app)
revoked_tokens = set()

port = int(os.environ.get('PORT', 5000))

@app.route('/')
def home():
    return jsonify({"message": "Bienvenido a la API!"})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    correo = data.get('correo')
    password = data.get('password')

    if not correo or not password:
        return jsonify({"success": False, "message": "Faltan datos"}), 400

    try:
        cursor = mysql.connection.cursor()
        query = "SELECT id, correo, password, id_rol FROM usuarios WHERE correo = %s"
        cursor.execute(query, (correo,))
        user = cursor.fetchone()
        cursor.close()

        if user:
            user_id, correo_db, password_db, id_rol = user

            if password_db == password:
                # Generar el token
                token = jwt.encode({
                    'id': user_id,
                    'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)  # Expira en 1 hora
                }, SECRET_KEY, algorithm='HS256')

                cursor = mysql.connection.cursor()
                query = "SELECT nombre FROM rol WHERE id = %s"
                cursor.execute(query, (id_rol,))
                rol = cursor.fetchone()[0]
                cursor.close()
                return jsonify({"success": True, "token": token, "rol": rol, "id": user_id}), 200
            else:
                return jsonify({"success": False, "message": "Contraseña incorrecta"}), 401
        else:
            return jsonify({"success": False, "message": "Usuario no encontrado"}), 404
    except Exception as e:
        print(f"Error en la consulta: {e}")
        return jsonify({"success": False, "message": "Error en la consulta a la base de datos"}), 500
        

@app.route('/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization')
    print(f"Token recibido: {token}")  # Para depuración
    
    if not token or not verificar_token(token):
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Revocar el token
    if token.startswith("Bearer "):
        token = token.split(" ")[1]
    
    revoked_tokens.add(token)  # Agregar a la lista de revocación

    return jsonify({'message': 'Sesión cerrada con éxito'}), 200

def verificar_token(token):
    try:
        if token.startswith("Bearer "):
            token = token.split(" ")[1]
        
        # Decodificar el token
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        
        # Verificar si el token está en la lista de revocación
        if token in revoked_tokens:
            print("Token revocado")
            return False
        
        print("Token válido:", payload)
        return True
    except jwt.ExpiredSignatureError:
        print("El token ha expirado")
        return False
    except jwt.InvalidTokenError:
        print("Token inválido")
        return False


@app.route('/crear_usuario', methods=['POST'])
def crear_usuario():
    data = request.json
    correo = data['correo']
    
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM usuarios WHERE correo = %s", [correo])
    existing_user = cur.fetchone()
    
    if existing_user:
        return jsonify({'error': 'El correo ya está registrado'}), 409  #
    
    # Insertar nuevo usuario
    nombre = data['nombre']
    apellido = data['apellido']
    password = data['password']
    celular = data['celular']
    rol = data['rol']

    cur.execute("INSERT INTO usuarios (nombre, apellido, correo, password, celular, id_rol) VALUES (%s, %s, %s, %s, %s, %s)", 
                (nombre, apellido, correo, password, celular, rol))
    mysql.connection.commit()
    cur.close()
    
    return jsonify({'message': 'Usuario creado exitosamente'}), 201  


@app.route('/obtener_usuario/<correo>', methods=['GET'])
def obtener_usuario(correo):
    cursor = mysql.connection.cursor()
    query = "SELECT nombre, apellido, correo, password, celular FROM usuarios WHERE correo = %s"
    cursor.execute(query, (correo,))
    usuario = cursor.fetchone()
    cursor.close()

    if usuario:
        return jsonify({"success": True, "usuario": {
            "nombre": usuario[0],
            "apellido": usuario[1],
            "correo": usuario[2],
            "password": usuario[3],  # Asegúrate de manejar la contraseña adecuadamente
            "celular": usuario[4]
        }})
    else:
        return jsonify({"success": False, "message": "Usuario no encontrado"}), 404

@app.route('/actualizar_usuario', methods=['PUT'])
def actualizar_usuario():
    data = request.json
    nombre = data.get('nombre')
    apellido = data.get('apellido')
    correo = data.get('correo')
    password = data.get('password')
    celular = data.get('celular')

    if not all([nombre, apellido, correo, password, celular]):
        return jsonify({"success": False, "message": "Todos los campos son requeridos"}), 400

    try:
        cursor = mysql.connection.cursor()
        query = """
            UPDATE usuarios 
            SET nombre = %s, apellido = %s, password = %s, celular = %s
            WHERE correo = %s
        """
        cursor.execute(query, (nombre, apellido, password, celular, correo))
        mysql.connection.commit()
        cursor.close()
        
        if cursor.rowcount == 0:
            return jsonify({"success": False, "message": "No se encontró el usuario"}), 404
        
        return jsonify({"success": True, "message": "Usuario actualizado"})
    
    except Exception as e:
        mysql.connection.rollback()  # Revertir cambios en caso de error
        print(f"Error al actualizar el usuario: {e}")  # Loguear error para depuración
        return jsonify({"success": False, "message": "Error al actualizar el usuario"}), 500

@app.route('/eliminar_usuario/<correo>', methods=['DELETE'])
def eliminar_usuario(correo):
    cursor = mysql.connection.cursor()
    query = "DELETE FROM usuarios WHERE correo = %s"
    result = cursor.execute(query, (correo,))
    mysql.connection.commit()
    cursor.close()

    if result == 0:  
        return jsonify({"success": False, "message": "Usuario no encontrado"}), 404

    return jsonify({"success": True, "message": "Usuario eliminado"}), 200

@app.route('/tipo_sensor', methods=['GET'])
def get_tipo_sensores():
    try:
        cursor = mysql.connection.cursor()
        query = "SELECT * FROM tipo_sensor"
        cursor.execute(query)
        tipos = cursor.fetchall()
        cursor.close()

        tipo_sensor_list = [{"id": t[0], "nombre": t[1]} for t in tipos]
        return jsonify({"success": True, "data": tipo_sensor_list}), 200
    except Exception as e:
        print(f"Error al obtener tipos de sensores: {e}")
        return jsonify({"success": False, "message": "Error al obtener tipos de sensores"}), 500

@app.route('/ultimo_valor/<int:sensor_id>', methods=['GET'])
def ultimo_valor(sensor_id):
    cursor = mysql.connection.cursor()
    query = "SELECT valor_de_la_medida FROM medidas WHERE id_sensor = %s ORDER BY fecha DESC LIMIT 1"
    cursor.execute(query, (sensor_id,))
    resultado = cursor.fetchone()
    cursor.close()
    
    if resultado:
        return jsonify({'valor': resultado[0]})
    else:
        return jsonify({'valor': 'No hay datos disponibles'}), 404


@app.route('/add_sensor', methods=['POST'])
def add_sensor():
    data = request.json
    nombre_sensor = data.get('nombre_sensor')
    referencia = data.get('referencia')
    id_tipo_sensor = data.get('id_tipo_sensor')

    if not (nombre_sensor and referencia and id_tipo_sensor):
        return jsonify({"success": False, "message": "Faltan datos"}), 400

    try:
        cursor = mysql.connection.cursor()
        query = "INSERT INTO sensores (nombre_sensor, referencia, id_tipo_sensor) VALUES (%s, %s, %s)"
        cursor.execute(query, (nombre_sensor, referencia, id_tipo_sensor))
        mysql.connection.commit()
        cursor.close()

        return jsonify({"success": True, "message": "Sensor añadido con éxito"}), 201
    except Exception as e:
        print(f"Error en la consulta: {e}")
        return jsonify({"success": False, "message": "Error en la consulta a la base de datos"}), 500
    
@app.route('/consultar_reportes', methods=['POST'])
def consultar_reportes():
    data = request.get_json()

    fecha_inicio = data.get('fechaInicio')
    fecha_fin = data.get('fechaFin')
    nombre_sensor = data.get('nombreSensor')

    try:
      
        fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d')

        cur = mysql.connection.cursor()

        
        query = '''
            SELECT s.nombre_sensor, m.fecha, m.valor_de_la_medida
            FROM medidas m
            JOIN sensores s ON m.id_sensor = s.id
            WHERE s.nombre_sensor = %s
            AND m.fecha BETWEEN %s AND %s
        '''
        cur.execute(query, (nombre_sensor, fecha_inicio_dt, fecha_fin_dt))
        resultados = cur.fetchall()

     
        data = []
        for row in resultados:
            data.append({
                'nombreSensor': row[0], 
                'fecha': row[1].strftime('%Y-%m-%d %H:%M:%S'),  
                'valor': row[2]  
            })

        cur.close()

        return jsonify(data), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'No se pudieron obtener los datos'}), 500


@app.route('/sensores_todos', methods=['GET'])
def obtener_todos_los_sensores():
    try:
        cur = mysql.connection.cursor()
        query = """
            SELECT s.nombre_sensor, m.fecha, m.valor_de_la_medida
            FROM medidas m
            JOIN sensores s ON m.id_sensor = s.id
            ORDER BY m.fecha DESC  -- Opcional: ordenar por fecha si lo necesitas
        """
        cur.execute(query)
        resultados = cur.fetchall()

        # Formatear los resultados con los índices correctos
        data = [{'sensor': row[0], 'fecha': row[1].strftime('%Y-%m-%d %H:%M:%S'), 'valor': row[2]} for row in resultados]

        return jsonify(data), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route('/historial')
def mostrar_historial():
    sensor_id = request.args.get('sensor')
    cursor = mysql.connection.cursor()
    query = "SELECT valor_de_la_medida, fecha FROM medidas WHERE id_sensor = %s ORDER BY fecha DESC"
    cursor.execute(query, (sensor_id,))
    historial = cursor.fetchall()
    cursor.close()

    # Definir la zona horaria de Colombia
    colombia_tz = pytz.timezone('America/Bogota')

    # Convertir los resultados a una lista de diccionarios, ajustando la zona horaria
    historial_json = []
    for h in historial:
        valor = h[0]
        fecha_utc = h[1]

        # Asegurarse de que la fecha está en formato datetime y convertirla a la zona horaria de Colombia
        if isinstance(fecha_utc, datetime):
            fecha_colombia = fecha_utc.replace(tzinfo=pytz.utc).astimezone(colombia_tz)
            fecha_formateada = fecha_colombia.strftime('%Y-%m-%d %H:%M:%S')
        else:
            fecha_formateada = fecha_utc  # En caso de que no sea un datetime, dejarlo tal cual

        historial_json.append({'valor': valor, 'fecha': fecha_formateada})

    # Retornar los datos en formato JSON
    return jsonify(historial_json)

@app.route('/add_card', methods=['POST'])
def add_card():
    user_id = request.json.get('user_id')  # Asegúrate de enviar esta ID al hacer la solicitud
    card_name = request.json.get('card_name')
    iframe_url = request.json.get('iframe_url')

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO tarjetas (nombre, iframe_url, id_usuario) VALUES (%s, %s, %s)", 
                       (card_name, iframe_url, user_id))
        mysql.connection.commit()
        cursor.close()

        return jsonify({'message': 'Tarjeta añadida con éxito!'}), 201
    except Exception as e:
        print(f"Error al añadir tarjeta: {e}")
        return jsonify({'message': 'Error al añadir tarjeta'}), 500

@app.route('/get_tarjetas/<int:user_id>', methods=['GET'])
def get_tarjetas(user_id):
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT nombre, iframe_url FROM tarjetas WHERE id_usuario = %s", (user_id,))
        tarjetas = cursor.fetchall()
        cursor.close()

        return jsonify(tarjetas), 200
    except Exception as e:
        print(f"Error en la consulta: {e}")
        return jsonify({"message": "Error en la consulta a la base de datos"}), 500

# ruta para insertar valores de los sensores 

@app.route('/insertar_medidas', methods=['POST'])
def insertar_medidas():
    data = request.json 
    nombre_sensor = data.get('nombre_sensor') 
    nombre_usuario = data.get('nombre_usuario') 
    valor_de_la_medida = data.get('valor_de_la_medida')

    if not nombre_sensor or not nombre_usuario or not valor_de_la_medida:
        return jsonify({"success": False, "message": "Faltan datos"}), 400

    try:
        cursor = mysql.connection.cursor()

        query_sensor = "SELECT id FROM sensores WHERE nombre_sensor = %s"
        cursor.execute(query_sensor, (nombre_sensor,))
        sensor = cursor.fetchone()
        
        if not sensor:
            return jsonify({"success": False, "message": "Sensor no encontrado"}), 404
        id_sensor = sensor[0]

    
        query_usuario = "SELECT id FROM usuarios WHERE nombre = %s"
        cursor.execute(query_usuario, (nombre_usuario,))
        usuario = cursor.fetchone()

        if not usuario:
            return jsonify({"success": False, "message": "Usuario no encontrado"}), 404
        id_usuarios = usuario[0]

        query = "INSERT INTO medidas (id_sensor, id_usuarios, valor_de_la_medida) VALUES (%s, %s, %s)"
        cursor.execute(query, (id_sensor, id_usuarios, valor_de_la_medida))
        mysql.connection.commit()
        cursor.close()

        return jsonify({"success": True, "message": "Medida añadida con éxito"}), 201
    except Exception as e:
        print(f"Error al añadir medida: {e}")
        return jsonify({"success": False, "message": "Error al añadir medida"}), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=port)

