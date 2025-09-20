from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import psycopg2
from datetime import datetime, timedelta
import jwt as pyjwt

app = Flask(__name__, static_url_path='/static')
CORS(app, 
     resources={r"/*": {"origins": "*"}}, 
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

SECRET_KEY = '12345666'
port = int(os.environ.get('PORT', 5000))

# 🔑 conexión a PostgreSQL en Azure
def get_connection():
    return psycopg2.connect(
        user="JesusPugliese13",  
        password="Greentech1302",    
        host="greentech.postgres.database.azure.com",
        port=5432,
        database="softcul"           
    )
    

revoked_tokens = set()

@app.route('/')
def home():
    return jsonify({"message": "Bienvenido a la API con PostgreSQL!"})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    correo = data.get('correo')
    password = data.get('password')

    if not correo or not password:
        return jsonify({"success": False, "message": "Faltan datos"}), 400
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = "SELECT id, nombre, correo, password, id_rol FROM usuarios WHERE correo = %s"
        cursor.execute(query, (correo,))
        user = cursor.fetchone()

        if user:
            user_id, nombre, correo_db, password_db, id_rol = user
            if password_db == password:
                token = pyjwt.encode({
                    'id': user_id,
                    'exp': datetime.utcnow() + timedelta(hours=1)
                }, SECRET_KEY, algorithm='HS256')

                cursor.execute("SELECT nombre FROM rol WHERE id = %s", (id_rol,))
                rol = cursor.fetchone()[0]

                cursor.close()
                conn.close()

                return jsonify({
                    "success": True,
                    "token": token,
                    "rol": rol,
                    "id": user_id,
                    "nombre": nombre
                }), 200
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
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        
        # Verificar si el token está en la lista de revocación
        if token in revoked_tokens:
            print("Token revocado")
            return False
        
        print("Token válido:", payload)
        return True
    except pyjwt.ExpiredSignatureError:
        print("El token ha expirado")
        return False
    except pyjwt.InvalidTokenError:
        print("Token inválido")
        return False

@app.route('/verificar_token', methods=['POST'])
def verificar_token_route():
    token = request.headers.get('Authorization')

    if not token:
        return jsonify({'success': False, 'message': 'Token no proporcionado'}), 401

    if verificar_token(token):
        return jsonify({'success': True, 'message': 'Token válido'}), 200
    else:
        return jsonify({'success': False, 'message': 'Token inválido o expirado'}), 401

@app.route('/crear_usuario', methods=['POST'])
def crear_usuario():
    data = request.json
    correo = data['correo']
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE correo = %s", (correo,))
    existing_user = cursor.fetchone()
    
    if existing_user:
        cursor.close()
        conn.close()
        return jsonify({'error': 'El correo ya está registrado'}), 409
    
    # Insertar nuevo usuario
    nombre = data['nombre']
    apellido = data['apellido']
    password = data['password']
    celular = data['celular']
    rol = data['rol']
    cursor.execute("INSERT INTO usuarios (nombre, apellido, correo, password, celular, id_rol) VALUES (%s, %s, %s, %s, %s, %s)", 
                (nombre, apellido, correo, password, celular, rol))
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'message': 'Usuario creado exitosamente'}), 201

@app.route('/obtener_usuarios', methods=['GET'])
def obtener_usuarios():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Incluir todos los campos necesarios: id, nombre, apellido, correo, celular, id_rol
        query = "SELECT id, nombre, apellido, correo, celular, id_rol FROM usuarios"
        cursor.execute(query)
        usuarios = cursor.fetchall()
        
        usuarios_list = []
        for usuario in usuarios:
            usuarios_list.append({
                "id": usuario[0],
                "nombre": usuario[1],
                "apellido": usuario[2],
                "correo": usuario[3],
                "celular": usuario[4],
                "rol": usuario[5]  
            })
            
        return jsonify({
            "success": True,
            "usuarios": usuarios_list,
            "count": len(usuarios_list)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error al obtener usuarios: {str(e)}"
        }), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/obtener_usuario/<correo>', methods=['GET'])
def obtener_usuario(correo):
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT nombre, apellido, correo, password, celular FROM usuarios WHERE correo = %s"
    cursor.execute(query, (correo,))
    usuario = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if usuario:
        return jsonify({"success": True, "usuario": {
            "nombre": usuario[0],
            "apellido": usuario[1],
            "correo": usuario[2],
            "password": usuario[3],
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
    
    if not all([nombre, apellido, correo, celular]):
        return jsonify({"success": False, "message": "Todos los campos son requeridos"}), 400
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            UPDATE usuarios 
            SET nombre = %s, apellido = %s, password = %s, celular = %s
            WHERE correo = %s
        """
        cursor.execute(query, (nombre, apellido, password, celular, correo))
        conn.commit()
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({"success": False, "message": "No se encontró el usuario"}), 404
        
        cursor.close()
        conn.close()
        return jsonify({"success": True, "message": "Usuario actualizado"})
    
    except Exception as e:
        conn.rollback()
        print(f"Error al actualizar el usuario: {e}")
        return jsonify({"success": False, "message": "Error al actualizar el usuario"}), 500

@app.route('/eliminar_usuario/<correo>', methods=['DELETE'])
def eliminar_usuario(correo):
    conn = get_connection()
    cursor = conn.cursor()
    query = "DELETE FROM usuarios WHERE correo = %s"
    cursor.execute(query, (correo,))
    conn.commit()
    rowcount = cursor.rowcount
    cursor.close()
    conn.close()
    
    if rowcount == 0:  
        return jsonify({"success": False, "message": "Usuario no encontrado"}), 404

    return jsonify({"success": True, "message": "Usuario eliminado"}), 200

@app.route('/tipo_sensor', methods=['GET'])
def get_tipo_sensores():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM tipo_sensor"
        cursor.execute(query)
        tipos = cursor.fetchall()
        cursor.close()
        conn.close()
        
        tipo_sensor_list = [{"id": t[0], "nombre": t[1]} for t in tipos]
        return jsonify({"success": True, "data": tipo_sensor_list}), 200
    except Exception as e:
        print(f"Error al obtener tipos de sensores: {e}")
        return jsonify({"success": False, "message": "Error al obtener tipos de sensores"}), 500

@app.route('/ultimo_valor/<int:sensor_id>', methods=['GET'])
def ultimo_valor(sensor_id):
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT valor_de_la_medida FROM medidas WHERE id_sensor = %s ORDER BY fecha DESC LIMIT 1"
    cursor.execute(query, (sensor_id,))
    resultado = cursor.fetchone()
    cursor.close()
    conn.close()
    
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
    id_usuario = data.get('id_usuario')

    if not nombre_sensor or not referencia or not id_tipo_sensor or not id_usuario:
        return jsonify({"message": "Faltan datos"}), 400

    try:
        conn = get_connection()
        cur = conn.cursor()
        query = """
            INSERT INTO sensores (nombre_sensor, referencia, id_tipo_sensor, id_usuario)
            VALUES (%s, %s, %s, %s)
        """
        cur.execute(query, (nombre_sensor, referencia, id_tipo_sensor, id_usuario))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Sensor añadido con éxito!"}), 201
    except Exception as e:
        print(f"Error al añadir sensor: {e}")
        return jsonify({"message": "Error al añadir sensor"}), 500

@app.route('/consultar_reportes', methods=['POST'])
def consultar_reportes():
    data = request.get_json()

    fecha_inicio = data.get('fechaInicio')
    fecha_fin = data.get('fechaFin')
    nombre_sensor = data.get('nombreSensor')
    
    try:
        # Conversión de fechas de string a formato datetime
        fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d')

        conn = get_connection()
        cur = conn.cursor()

        # Consulta a la base de datos para obtener los resultados dentro del rango de fechas
        query = '''
            SELECT s.nombre_sensor, m.fecha, m.valor_de_la_medida
            FROM medidas m
            JOIN sensores s ON m.id_sensor = s.id
            WHERE s.nombre_sensor = %s
            AND m.fecha BETWEEN %s AND %s
        '''
        cur.execute(query, (nombre_sensor, fecha_inicio_dt, fecha_fin_dt))
        resultados = cur.fetchall()

        # Estructura de los resultados en formato JSON
        data = []
        for row in resultados:
            data.append({
                'nombreSensor': row[0],  # Nombre del sensor
                'fecha': row[1].strftime('%Y-%m-%d %H:%M:%S'),  # Formato de la fecha
                'valor': row[2]  # Valor de la medida
            })

        cur.close()
        conn.close()

        return jsonify(data), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'No se pudieron obtener los datos'}), 500

@app.route('/sensores_todos', methods=['GET'])
def obtener_todos_los_sensores():
    try:
        conn = get_connection()
        cur = conn.cursor()
        query = """
            SELECT s.nombre_sensor, m.fecha, m.valor_de_la_medida
            FROM medidas m
            JOIN sensores s ON m.id_sensor = s.id
            ORDER BY m.fecha DESC
        """
        cur.execute(query)
        resultados = cur.fetchall()

        # Formatear los resultados con los índices correctos
        data = [{'sensor': row[0], 'fecha': row[1].strftime('%Y-%m-%d %H:%M:%S'), 'valor': row[2]} for row in resultados]

        cur.close()
        conn.close()
        return jsonify(data), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/historial')
def mostrar_historial():
    sensor_id = request.args.get('sensor')
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT valor_de_la_medida, fecha FROM medidas WHERE id_sensor = %s ORDER BY fecha DESC"
    cursor.execute(query, (sensor_id,))
    historial = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Convertir los resultados a una lista de diccionarios
    historial_json = [{'valor': h[0], 'fecha': h[1]} for h in historial]
    
    # Retornar los datos en formato JSON
    return jsonify(historial_json)

@app.route('/add_card', methods=['POST'])
def add_card():
    user_id = request.json.get('user_id')
    card_name = request.json.get('card_name')
    iframe_url = request.json.get('iframe_url')

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tarjetas (nombre, iframe_url, id_usuario) VALUES (%s, %s, %s)", 
                       (card_name, iframe_url, user_id))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'message': 'Tarjeta añadida con éxito!'}), 201
    except Exception as e:
        print(f"Error al añadir tarjeta: {e}")
        return jsonify({'message': 'Error al añadir tarjeta'}), 500

@app.route('/get_tarjetas/<int:user_id>', methods=['GET'])
def get_tarjetas(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT nombre, iframe_url FROM tarjetas WHERE id_usuario = %s", (user_id,))
        tarjetas = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify(tarjetas), 200
    except Exception as e:
        print(f"Error en la consulta: {e}")
        return jsonify({"message": "Error en la consulta a la base de datos"}), 500

@app.route('/insertar_medidas', methods=['POST'])
def insertar_medidas():
    data = request.json 
    nombre_sensor = data.get('nombre_sensor') 
    nombre_usuario = data.get('nombre_usuario') 
    valor_de_la_medida = data.get('valor_de_la_medida')

    if nombre_sensor is None or nombre_usuario is None or valor_de_la_medida is None:
        return jsonify({"success": False, "message": "Faltan datos"}), 400

    try:
        conn = get_connection()
        cursor = conn.cursor()

        query_sensor = "SELECT id FROM sensores WHERE nombre_sensor = %s"
        cursor.execute(query_sensor, (nombre_sensor,))
        sensor = cursor.fetchone()
        
        if not sensor:
            cursor.close()
            conn.close()
            return jsonify({"success": False, "message": "Sensor no encontrado"}), 404
        id_sensor = sensor[0]

        query_usuario = "SELECT id FROM usuarios WHERE nombre = %s"
        cursor.execute(query_usuario, (nombre_usuario,))
        usuario = cursor.fetchone()

        if not usuario:
            cursor.close()
            conn.close()
            return jsonify({"success": False, "message": "Usuario no encontrado"}), 404
        id_usuarios = usuario[0]

        query = "INSERT INTO medidas (id_sensor, id_usuarios, valor_de_la_medida) VALUES (%s, %s, %s)"
        cursor.execute(query, (id_sensor, id_usuarios, valor_de_la_medida))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True, "message": "Medida añadida con éxito"}), 201
    except Exception as e:
        print(f"Error al añadir medida: {e}")
        return jsonify({"success": False, "message": "Error al añadir medida"}), 500

@app.route('/sensores_usuario/<int:id_usuario>', methods=['GET'])
def sensores_usuario(id_usuario):
    try:
        conn = get_connection()
        cur = conn.cursor()
        query = '''
            SELECT s.id, s.nombre_sensor, s.referencia, s.id_tipo_sensor, ts.nombre as tipo_sensor, s.id_usuario
            FROM sensores s
            JOIN tipo_sensor ts ON s.id_tipo_sensor = ts.id
            WHERE s.id_usuario = %s
            ORDER BY s.id DESC
        '''
        cur.execute(query, (id_usuario,))
        sensores = cur.fetchall()
        data = []
        for row in sensores:
            sensor_id = row[0]
            # Última medida
            cur.execute(
                "SELECT valor_de_la_medida, fecha FROM medidas WHERE id_sensor = %s ORDER BY fecha DESC LIMIT 1",
                (sensor_id,)
            )
            medida = cur.fetchone()
            if medida:
                valor = medida[0]
                fecha_ultima = medida[1]
                from datetime import datetime, timedelta
                ahora = datetime.utcnow()
                # Estado: Online si la última medida es de los últimos 10 minutos
                online = (fecha_ultima and (ahora - fecha_ultima).total_seconds() < 600)
                estado = "Online" if online else "Offline"
                # TIEMPO ENCENDIDO: suma de minutos en los que el sensor estuvo online (todas las medidas con diferencia < 10min)
                cur.execute(
                    "SELECT fecha FROM medidas WHERE id_sensor = %s ORDER BY fecha ASC",
                    (sensor_id,)
                )
                fechas = [f[0] for f in cur.fetchall()]
                tiempo_encendido_min = 0
                if fechas:
                    for i in range(1, len(fechas)):
                        diff = (fechas[i] - fechas[i-1]).total_seconds() / 60
                        if diff < 10:
                            tiempo_encendido_min += diff
                    # Si el sensor está online, suma el tiempo desde la última medida hasta ahora
                    if online:
                        tiempo_encendido_min += (ahora - fechas[-1]).total_seconds() / 60
                    tiempo_encendido_min = int(tiempo_encendido_min)
                else:
                    tiempo_encendido_min = 0
                ultimo_dato = fecha_ultima.strftime('%Y-%m-%d %H:%M:%S')
            else:
                valor = None
                ultimo_dato = None
                estado = "Offline"
                tiempo_encendido_min = 0
            data.append({
                'id': row[0],
                'nombre_sensor': row[1],
                'referencia': row[2],
                'id_tipo_sensor': row[3],
                'tipo_sensor': row[4],
                'id_usuario': row[5],
                'valor': valor,
                'ultimo_dato': ultimo_dato,
                'estado': estado,
                'tiempo_encendido': tiempo_encendido_min
            })
        cur.close()
        conn.close()
        return jsonify(data), 200
    except Exception as e:
        print(f"Error al obtener sensores del usuario: {e}")
        return jsonify({'error': 'No se pudieron obtener los sensores'}), 500

@app.route('/eliminar_sensor/<int:sensor_id>', methods=['DELETE'])
def eliminar_sensor(sensor_id):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM sensores WHERE id = %s", (sensor_id,))
        conn.commit()
        deleted = cur.rowcount
        cur.close()
        conn.close()
        if deleted == 0:
            return jsonify({"success": False, "message": "Sensor no encontrado"}), 404
        return jsonify({"success": True, "message": "Sensor eliminado"}), 200
    except Exception as e:
        print(f"Error al eliminar sensor: {e}")
        return jsonify({"success": False, "message": "Error al eliminar sensor"}), 500

@app.route('/toggle_sensor/<int:sensor_id>', methods=['POST'])
def toggle_sensor(sensor_id):
    # Simulado: no hay campo 'estado' en DB. Responde OK para la UI.
    return jsonify({"success": True, "message": "Cambio de estado simulado", "sensor_id": sensor_id}), 200

@app.route('/calibrar_sensor/<int:sensor_id>', methods=['POST'])
def calibrar_sensor(sensor_id):
    # Simulado: sin cambios en DB. Responde OK para la UI.
    return jsonify({"success": True, "message": "Calibración simulada", "sensor_id": sensor_id}), 200

@app.route('/obtener_usuarios_admin', methods=['GET'])
def obtener_usuarios_admin():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        query = """
            SELECT u.id, u.nombre, u.apellido, u.correo, u.celular, r.nombre as rol
            FROM usuarios u
            LEFT JOIN rol r ON u.id_rol = r.id
            ORDER BY u.nombre ASC, u.apellido ASC
        """
        cursor.execute(query)
        usuarios = cursor.fetchall()
        print("Usuarios obtenidos (raw):", usuarios)  # Depuración

        usuarios_list = []
        for usuario in usuarios:
            usuarios_list.append({
                "id": usuario[0],
                "nombre": usuario[1],
                "apellido": usuario[2],
                "correo": usuario[3],
                "celular": usuario[4],
                "rol": usuario[5]
            })
        print("usuarios_list (dict):", usuarios_list)  # Depuración

        if not usuarios_list:
            print("No hay usuarios en la base de datos o el JOIN no retorna datos.")
        return jsonify({
            "success": True,
            "usuarios": usuarios_list,
            "count": len(usuarios_list)
        })
    except Exception as e:
        print("Error en obtener_usuarios_admin:", e)
        return jsonify({
            "success": False,
            "message": f"Error al obtener usuarios: {str(e)}"
        }), 500
    finally:
        cursor.close()
        conn.close()
    

@app.route('/reporte_usuario', methods=['POST'])
def reporte_usuario():
    data = request.get_json()
    id_usuario = data.get('id_usuario')
    fecha_inicio = data.get('fechaInicio')
    fecha_fin = data.get('fechaFin')
    sensor_id = data.get('sensor_id')  # Puede ser None para todos
    tipo_reporte = data.get('tipo_reporte')  # 'semanal', 'mensual', 'todos'

    if not id_usuario:
        return jsonify({'error': 'Falta id_usuario'}), 400

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Obtener sensores del usuario
        cur.execute(
            "SELECT id, nombre_sensor FROM sensores WHERE id_usuario = %s",
            (id_usuario,)
        )
        sensores = cur.fetchall()
        sensores_dict = {str(s[0]): s[1] for s in sensores}
        if not sensores:
            return jsonify({'error': 'No tiene sensores registrados'}), 404

        # Construir filtro de sensores
        sensores_ids = [str(s[0]) for s in sensores]
        if sensor_id and str(sensor_id) in sensores_ids:
            sensores_ids = [str(sensor_id)]

        # Fechas
        filtros = []
        params = []
        if fecha_inicio:
            filtros.append("m.fecha >= %s")
            params.append(datetime.strptime(fecha_inicio, '%Y-%m-%d'))
        if fecha_fin:
            filtros.append("m.fecha <= %s")
            params.append(datetime.strptime(fecha_fin, '%Y-%m-%d'))

        # Filtro sensores
        filtros.append("m.id_sensor IN %s")
        params.append(tuple(map(int, sensores_ids)))

        where = " AND ".join(filtros)
        query = f"""
            SELECT m.id_sensor, s.nombre_sensor, m.fecha, m.valor_de_la_medida
            FROM medidas m
            JOIN sensores s ON m.id_sensor = s.id
            WHERE {where}
            ORDER BY m.fecha ASC
        """
        cur.execute(query, tuple(params))
        resultados = cur.fetchall()

        # Agrupación por semana/mes si aplica
        from collections import defaultdict
        data = []
        if tipo_reporte in ('semanal', 'mensual'):
            agrupados = defaultdict(list)
            for row in resultados:
                fecha = row[2]
                if tipo_reporte == 'semanal':
                    key = f"{fecha.year}-S{fecha.isocalendar()[1]}"
                else:
                    key = f"{fecha.year}-{fecha.month:02d}"
                agrupados[(row[0], key)].append(row)
            # Promedio por grupo
            for (sensor_id, periodo), rows in agrupados.items():
                valores = [r[3] for r in rows]
                promedio = sum(valores) / len(valores) if valores else 0
                data.append({
                    'sensor_id': sensor_id,
                    'nombre_sensor': sensores_dict.get(str(sensor_id), ''),
                    'periodo': periodo,
                    'promedio': round(promedio, 2),
                    'medidas': len(valores)
                })
        else:
            # Todos los datos crudos
            for row in resultados:
                data.append({
                    'sensor_id': row[0],
                    'nombre_sensor': row[1],
                    'fecha': row[2].strftime('%Y-%m-%d %H:%M:%S'),
                    'valor': row[3]
                })

        cur.close()
        conn.close()
        return jsonify({'success': True, 'data': data}), 200
    except Exception as e:
        print(f"Error en reporte_usuario: {e}")
        return jsonify({'success': False, 'message': 'Error al generar el reporte'}), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=port)
