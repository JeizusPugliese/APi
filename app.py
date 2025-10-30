from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import uuid
from datetime import datetime, timedelta, timezone
import mysql.connector
from mysql.connector import Error
import jwt as pyjwt


app = Flask(__name__, static_url_path='/static')
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)


SECRET_KEY = os.environ.get("JWT_SECRET", "12345666")
TOKEN_DURATION_HOURS = int(os.environ.get("TOKEN_DURATION_HOURS", 1))

DB_CONFIG = {
    "user": os.environ.get("DB_USER", "u944963489_Greentechiot"),
    "password": os.environ.get("DB_PASSWORD", "Greentechiot2025"),
    "host": os.environ.get("DB_HOST", "srv766.hstgr.io"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "database": os.environ.get("DB_NAME", "u944963489_Greentechiot")
}


# ---------------------------------------------------------------------------
# Utilidades generales
# ---------------------------------------------------------------------------

def get_connection():
    """Obtiene una conexión activa a MySQL o lanza Error."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        if conn.is_connected():
            return conn
        raise Error("No se pudo establecer la conexión con MySQL")
    except Error as exc:
        print("Error de conexión MySQL:", exc)
        raise


def close_resources(cursor=None, conn=None):
    """Cierra cursores y conexiones ignorando excepciones."""
    if cursor:
        try:
            cursor.close()
        except Exception:
            pass
    if conn:
        try:
            conn.close()
        except Exception:
            pass


def json_error(message, status=400):
    """Retorna respuesta JSON de error estándar."""
    return jsonify({"success": False, "message": message}), status


def strip_bearer(token_header):
    if not token_header:
        return None
    if token_header.startswith("Bearer "):
        return token_header.split(" ", 1)[1]
    return token_header


def parse_iso_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        text = value.strip()
    except AttributeError:
        raise ValueError("Formato de fecha inválido")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


# ---------------------------------------------------------------------------
# Gestión de sesiones JWT persistentes
# ---------------------------------------------------------------------------

def store_session(cursor, usuario_id, token, expira_en):
    session_id = str(uuid.uuid4())
    creado_en = datetime.utcnow()
    cursor.execute(
        """
        INSERT INTO sesiones (id, usuario_id, token, creado_en, expira_en, revocado)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (session_id, usuario_id, token, creado_en, expira_en, False),
    )
    return session_id


def find_session(token):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, usuario_id, expira_en, revocado
            FROM sesiones
            WHERE token = %s
            ORDER BY creado_en DESC
            LIMIT 1
            """,
            (token,),
        )
        return cursor.fetchone()
    except Error as exc:
        print("Error al consultar sesión:", exc)
        return None
    finally:
        close_resources(cursor, conn)


def revoke_session(token):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE sesiones SET revocado = 1 WHERE token = %s", (token,))
        conn.commit()
        return cursor.rowcount > 0
    except Error as exc:
        if conn:
            conn.rollback()
        print("Error al revocar sesión:", exc)
        return False
    finally:
        close_resources(cursor, conn)


def token_is_valid(token_header):
    token = strip_bearer(token_header)
    if not token:
        return False
    try:
        pyjwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except pyjwt.ExpiredSignatureError:
        print("Token expirado detectado por JWT.")
        revoke_session(token)
        return False
    except pyjwt.InvalidTokenError:
        print("Token inválido.")
        return False

    session = find_session(token)
    if not session:
        print("Token no registrado en la tabla de sesiones.")
        return False
    if session.get("revocado"):
        print("Token previamente revocado.")
        return False

    expira_en = session.get("expira_en")
    if isinstance(expira_en, datetime) and expira_en <= datetime.utcnow():
        print("Token expirado según la base de datos.")
        revoke_session(token)
        return False

    return True


# ---------------------------------------------------------------------------
# Endpoints generales
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return jsonify({"message": "Bienvenido a la API MySQL de InfoIoT"})


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    correo = data.get("correo")
    password = data.get("password")

    if not correo or not password:
        return json_error("Los campos 'correo' y 'password' son obligatorios.", 400)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, nombre, password, id_rol FROM usuarios WHERE correo = %s",
            (correo,),
        )
        registro = cursor.fetchone()
        if not registro:
            return json_error("Usuario no encontrado.", 404)

        usuario_id, nombre, password_db, id_rol = registro
        if password_db != password:
            return json_error("Contraseña incorrecta.", 401)

        expira_en = datetime.utcnow() + timedelta(hours=TOKEN_DURATION_HOURS)
        token = pyjwt.encode({"id": usuario_id, "exp": expira_en}, SECRET_KEY, algorithm="HS256")

        store_session(cursor, usuario_id, token, expira_en)
        cursor.execute("UPDATE usuarios SET ultimo_acceso = NOW() WHERE id = %s", (usuario_id,))
        cursor.execute("SELECT nombre FROM rol WHERE id = %s", (id_rol,))
        rol = (cursor.fetchone() or (None,))[0]
        conn.commit()

        return jsonify({
            "success": True,
            "token": token,
            "rol": rol,
            "id": usuario_id,
            "nombre": nombre,
        })
    except Error as exc:
        conn.rollback()
        print("Error en login:", exc)
        return json_error("Error al procesar la autenticación.", 500)
    finally:
        close_resources(cursor, conn)


@app.route("/logout", methods=["POST"])
def logout():
    token_header = request.headers.get("Authorization")
    if not token_is_valid(token_header):
        return json_error("Token inválido o expirado.", 401)

    token = strip_bearer(token_header)
    if revoke_session(token):
        return jsonify({"success": True, "message": "Sesión cerrada correctamente."})
    return json_error("No se pudo revocar la sesión.", 500)


@app.route("/verificar_token", methods=["POST"])
def verificar_token_route():
    token_header = request.headers.get("Authorization")
    if token_is_valid(token_header):
        return jsonify({"success": True, "message": "Token válido."})
    return json_error("Token inválido o expirado.", 401)


# ---------------------------------------------------------------------------
# Gestión de usuarios
# ---------------------------------------------------------------------------

@app.route("/crear_usuario", methods=["POST"])
def crear_usuario():
    data = request.get_json(silent=True) or {}
    for field in ("nombre", "apellido", "correo", "password", "celular", "rol"):
        if field not in data or data[field] in (None, ""):
            return json_error(f"El campo '{field}' es obligatorio.", 400)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM usuarios WHERE correo = %s", (data["correo"],))
        if cursor.fetchone():
            return json_error("El correo ya está registrado.", 409)

        cursor.execute(
            """
            INSERT INTO usuarios (nombre, apellido, correo, password, celular, id_rol)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                data["nombre"],
                data["apellido"],
                data["correo"],
                data["password"],
                data["celular"],
                data["rol"],
            ),
        )
        conn.commit()
        return jsonify({"success": True, "message": "Usuario creado exitosamente."}), 201
    except Error as exc:
        conn.rollback()
        print("Error al crear usuario:", exc)
        return json_error("No se pudo crear el usuario.", 500)
    finally:
        close_resources(cursor, conn)


@app.route("/obtener_usuarios", methods=["GET"])
def obtener_usuarios():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, nombre, apellido, correo, celular, id_rol FROM usuarios")
        usuarios = [{
            "id": row[0],
            "nombre": row[1],
            "apellido": row[2],
            "correo": row[3],
            "celular": row[4],
            "rol": row[5],
        } for row in cursor.fetchall()]
        return jsonify({"success": True, "usuarios": usuarios, "count": len(usuarios)})
    except Error as exc:
        print("Error al obtener usuarios:", exc)
        return json_error("No se pudieron obtener los usuarios.", 500)
    finally:
        close_resources(cursor, conn)


@app.route("/obtener_usuario/<correo>", methods=["GET"])
def obtener_usuario(correo):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, nombre, apellido, correo, password, celular, id_rol
            FROM usuarios
            WHERE correo = %s
            """,
            (correo,),
        )
        usuario = cursor.fetchone()
        if not usuario:
            return json_error("Usuario no encontrado.", 404)
        return jsonify({
            "success": True,
            "usuario": {
                "id": usuario[0],
                "nombre": usuario[1],
                "apellido": usuario[2],
                "correo": usuario[3],
                "password": usuario[4],
                "celular": usuario[5],
                "rol": usuario[6],
            },
        })
    except Error as exc:
        print("Error al obtener usuario:", exc)
        return json_error("No se pudo obtener el usuario.", 500)
    finally:
        close_resources(cursor, conn)


@app.route("/actualizar_usuario", methods=["PUT"])
def actualizar_usuario():
    data = request.get_json(silent=True) or {}
    required = ("nombre", "apellido", "correo", "celular")
    if any(not data.get(field) for field in required):
        return json_error("Los campos 'nombre', 'apellido', 'correo' y 'celular' son obligatorios.", 400)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        updates = ["nombre = %s", "apellido = %s", "celular = %s"]
        params = [data["nombre"], data["apellido"], data["celular"]]

        password = data.get("password")
        if password:
            updates.append("password = %s")
            params.append(password)

        params.append(data["correo"])
        cursor.execute(
            f"UPDATE usuarios SET {', '.join(updates)} WHERE correo = %s",
            tuple(params),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return json_error("Usuario no encontrado.", 404)
        return jsonify({"success": True, "message": "Usuario actualizado correctamente."})
    except Error as exc:
        conn.rollback()
        print("Error al actualizar usuario:", exc)
        return json_error("No se pudo actualizar el usuario.", 500)
    finally:
        close_resources(cursor, conn)


@app.route("/eliminar_usuario/<correo>", methods=["DELETE"])
def eliminar_usuario(correo):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM usuarios WHERE correo = %s", (correo,))
        conn.commit()
        if cursor.rowcount == 0:
            return json_error("Usuario no encontrado.", 404)
        return jsonify({"success": True, "message": "Usuario eliminado correctamente."})
    except Error as exc:
        conn.rollback()
        print("Error al eliminar usuario:", exc)
        return json_error("No se pudo eliminar el usuario.", 500)
    finally:
        close_resources(cursor, conn)


@app.route("/obtener_usuarios_admin", methods=["GET"])
def obtener_usuarios_admin():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT u.id, u.nombre, u.apellido, u.correo, u.celular, r.nombre
            FROM usuarios u
            LEFT JOIN rol r ON u.id_rol = r.id
            ORDER BY u.nombre ASC, u.apellido ASC
            """
        )
        usuarios = [{
            "id": row[0],
            "nombre": row[1],
            "apellido": row[2],
            "correo": row[3],
            "celular": row[4],
            "rol": row[5],
        } for row in cursor.fetchall()]
        return jsonify({"success": True, "usuarios": usuarios, "count": len(usuarios)})
    except Error as exc:
        print("Error al obtener usuarios (admin):", exc)
        return json_error("No se pudieron obtener los usuarios.", 500)
    finally:
        close_resources(cursor, conn)


# ---------------------------------------------------------------------------
# Gestión de tipos de sensor y sensores
# ---------------------------------------------------------------------------

def fetch_sensores_con_metricas(conn, where_clause=None, params=()):
    cursor = conn.cursor(dictionary=True)
    try:
        base_query = """
            SELECT s.id,
                   s.nombre_sensor,
                   s.referencia,
                   s.id_tipo_sensor,
                   ts.nombre AS tipo_sensor,
                   s.id_usuario
            FROM sensores s
            INNER JOIN tipo_sensor ts ON s.id_tipo_sensor = ts.id
        """
        if where_clause:
            base_query += f" WHERE {where_clause}"
        base_query += " ORDER BY s.id DESC"

        cursor.execute(base_query, params)
        sensores = cursor.fetchall()
        if not sensores:
            return []

        sensor_ids = [str(sensor["id"]) for sensor in sensores]
        placeholders = ",".join(["%s"] * len(sensor_ids))

        cursor.execute(
            f"""
            SELECT id_sensor, MAX(fecha) AS fecha, valor_de_la_medida
            FROM medidas
            WHERE id_sensor IN ({placeholders})
            GROUP BY id_sensor
            """,
            tuple(sensor_ids),
        )
        ultimas = {row["id_sensor"]: row for row in cursor.fetchall()}

        cursor.execute(
            f"""
            SELECT id_sensor,
                   SUM(
                       CASE
                           WHEN prev_fecha IS NOT NULL
                                AND TIMESTAMPDIFF(MINUTE, prev_fecha, fecha) < 10
                           THEN TIMESTAMPDIFF(MINUTE, prev_fecha, fecha)
                           ELSE 0
                       END
                   ) AS minutos
            FROM (
                SELECT id_sensor,
                       fecha,
                       LAG(fecha) OVER (PARTITION BY id_sensor ORDER BY fecha) AS prev_fecha
                FROM medidas
                WHERE id_sensor IN ({placeholders})
            ) t
            GROUP BY id_sensor
            """,
            tuple(sensor_ids),
        )
        tiempo_encendido = {row["id_sensor"]: int(row["minutos"] or 0) for row in cursor.fetchall()}

        now = datetime.utcnow()
        resultado = []
        for sensor in sensores:
            ultima = ultimas.get(sensor["id"])
            valor = ultima["valor_de_la_medida"] if ultima else None
            fecha = ultima["fecha"] if ultima else None
            estado = "Offline"
            minutos = tiempo_encendido.get(sensor["id"], 0)
            if fecha:
                diff = (now - fecha).total_seconds() / 60
                if diff < 10:
                    estado = "Online"
                    minutos += int(diff)
            resultado.append({
                "id": sensor["id"],
                "nombre_sensor": sensor["nombre_sensor"],
                "referencia": sensor["referencia"],
                "id_tipo_sensor": sensor["id_tipo_sensor"],
                "tipo_sensor": sensor["tipo_sensor"],
                "id_usuario": sensor["id_usuario"],
                "valor": valor,
                "ultimo_dato": fecha.strftime("%Y-%m-%d %H:%M:%S") if fecha else None,
                "estado": estado,
                "tiempo_encendido": minutos,
                "sensor": sensor["nombre_sensor"],
                "fecha": fecha.strftime("%Y-%m-%d %H:%M:%S") if fecha else None,
            })
        return resultado
    finally:
        close_resources(cursor)


@app.route("/tipo_sensor", methods=["GET"])
def get_tipo_sensores():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, nombre, descripcion, unidad FROM tipo_sensor ORDER BY id ASC")
        registros = [{
            "id": row[0],
            "nombre": row[1],
            "descripcion": row[2],
            "unidad": row[3],
        } for row in cursor.fetchall()]
        return jsonify({"success": True, "data": registros})
    except Error as exc:
        print("Error al obtener tipos de sensor:", exc)
        return json_error("No se pudieron obtener los tipos de sensor.", 500)
    finally:
        close_resources(cursor, conn)


@app.route("/add_sensor", methods=["POST"])
def add_sensor():
    data = request.get_json(silent=True) or {}
    required = ("nombre_sensor", "referencia", "id_tipo_sensor", "id_usuario")
    if any(not data.get(field) for field in required):
        return json_error("Los campos 'nombre_sensor', 'referencia', 'id_tipo_sensor' e 'id_usuario' son obligatorios.", 400)

    try:
        id_tipo_sensor = int(data["id_tipo_sensor"])
        id_usuario = int(data["id_usuario"])
    except (TypeError, ValueError):
        return json_error("Los campos 'id_tipo_sensor' e 'id_usuario' deben ser numéricos.", 400)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM tipo_sensor WHERE id = %s", (id_tipo_sensor,))
        if not cursor.fetchone():
            return json_error("El tipo de sensor no existe.", 404)
        cursor.execute("SELECT 1 FROM usuarios WHERE id = %s", (id_usuario,))
        if not cursor.fetchone():
            return json_error("El usuario asignado no existe.", 404)

        cursor.execute(
            """
            INSERT INTO sensores (nombre_sensor, referencia, id_tipo_sensor, id_usuario)
            VALUES (%s, %s, %s, %s)
            """,
            (data["nombre_sensor"], data["referencia"], id_tipo_sensor, id_usuario),
        )
        conn.commit()
        return jsonify({"success": True, "message": "Sensor añadido correctamente."}), 201
    except Error as exc:
        conn.rollback()
        print("Error al añadir sensor:", exc)
        return json_error("No se pudo añadir el sensor.", 500)
    finally:
        close_resources(cursor, conn)


@app.route("/sensores_todos", methods=["GET"])
def obtener_todos_los_sensores():
    conn = get_connection()
    try:
        resultado = fetch_sensores_con_metricas(conn)
        return jsonify(resultado)
    except Error as exc:
        print("Error al obtener sensores:", exc)
        return json_error("No se pudieron obtener los sensores.", 500)
    finally:
        close_resources(conn=conn)


@app.route("/sensores_usuario/<int:id_usuario>", methods=["GET"])
def sensores_usuario(id_usuario):
    conn = get_connection()
    try:
        resultado = fetch_sensores_con_metricas(conn, "s.id_usuario = %s", (id_usuario,))
        return jsonify(resultado)
    except Error as exc:
        print("Error al obtener sensores del usuario:", exc)
        return json_error("No se pudieron obtener los sensores del usuario.", 500)
    finally:
        close_resources(conn=conn)


@app.route("/eliminar_sensor/<int:sensor_id>", methods=["DELETE"])
def eliminar_sensor(sensor_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM sensores WHERE id = %s", (sensor_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return json_error("Sensor no encontrado.", 404)
        return jsonify({"success": True, "message": "Sensor eliminado correctamente."})
    except Error as exc:
        conn.rollback()
        print("Error al eliminar sensor:", exc)
        return json_error("No se pudo eliminar el sensor.", 500)
    finally:
        close_resources(cursor, conn)


@app.route("/toggle_sensor/<int:sensor_id>", methods=["POST"])
def toggle_sensor(sensor_id):
    return jsonify({"success": True, "message": "Acción simulada.", "sensor_id": sensor_id})


@app.route("/calibrar_sensor/<int:sensor_id>", methods=["POST"])
def calibrar_sensor(sensor_id):
    return jsonify({"success": True, "message": "Calibración simulada.", "sensor_id": sensor_id})


# ---------------------------------------------------------------------------
# Tarjetas personalizadas
# ---------------------------------------------------------------------------

@app.route("/add_card", methods=["POST"])
def add_card():
    data = request.get_json(silent=True) or {}
    required = ("user_id", "card_name", "iframe_url")
    if any(not data.get(field) for field in required):
        return json_error("Los campos 'user_id', 'card_name' e 'iframe_url' son obligatorios.", 400)

    try:
        user_id = int(data["user_id"])
    except (TypeError, ValueError):
        return json_error("El campo 'user_id' debe ser numérico.", 400)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM usuarios WHERE id = %s", (user_id,))
        if not cursor.fetchone():
            return json_error("El usuario indicado no existe.", 404)

        cursor.execute(
            """
            INSERT INTO tarjetas (nombre, iframe_url, id_usuario)
            VALUES (%s, %s, %s)
            """,
            (data["card_name"], data["iframe_url"], user_id),
        )
        conn.commit()
        return jsonify({"success": True, "message": "Tarjeta añadida correctamente."}), 201
    except Error as exc:
        conn.rollback()
        print("Error al añadir tarjeta:", exc)
        return json_error("No se pudo añadir la tarjeta.", 500)
    finally:
        close_resources(cursor, conn)


@app.route("/get_tarjetas/<int:user_id>", methods=["GET"])
def get_tarjetas(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT nombre, iframe_url FROM tarjetas WHERE id_usuario = %s", (user_id,))
        tarjetas = [{"nombre": row[0], "iframe_url": row[1]} for row in cursor.fetchall()]
        return jsonify({"success": True, "tarjetas": tarjetas})
    except Error as exc:
        print("Error al obtener tarjetas:", exc)
        return json_error("No se pudieron obtener las tarjetas.", 500)
    finally:
        close_resources(cursor, conn)


# ---------------------------------------------------------------------------
# Medidas e historiales
# ---------------------------------------------------------------------------

def buscar_sensor(cursor, sensor_id=None, referencia=None, nombre=None):
    if sensor_id is not None:
        cursor.execute("SELECT id FROM sensores WHERE id = %s", (sensor_id,))
        resultado = cursor.fetchone()
        if resultado:
            return resultado[0]
    if referencia:
        cursor.execute("SELECT id FROM sensores WHERE referencia = %s", (referencia,))
        resultado = cursor.fetchone()
        if resultado:
            return resultado[0]
    if nombre:
        cursor.execute("SELECT id FROM sensores WHERE nombre_sensor = %s", (nombre,))
        resultado = cursor.fetchone()
        if resultado:
            return resultado[0]
    return None


def buscar_usuario(cursor, usuario_id=None, correo=None, nombre=None):
    if usuario_id is not None:
        cursor.execute("SELECT id FROM usuarios WHERE id = %s", (usuario_id,))
        resultado = cursor.fetchone()
        if resultado:
            return resultado[0]
    if correo:
        cursor.execute("SELECT id FROM usuarios WHERE correo = %s", (correo,))
        resultado = cursor.fetchone()
        if resultado:
            return resultado[0]
    if nombre:
        cursor.execute("SELECT id FROM usuarios WHERE nombre = %s", (nombre,))
        resultado = cursor.fetchone()
        if resultado:
            return resultado[0]
    return None


@app.route("/insertar_medidas", methods=["POST"])
def insertar_medidas():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return json_error("Se requiere un cuerpo JSON válido.", 400)

    raw_valor = data.get("valor_de_la_medida")
    if raw_valor is None:
        return json_error("El campo 'valor_de_la_medida' es obligatorio.", 400)
    try:
        valor = float(raw_valor)
    except (TypeError, ValueError):
        return json_error("El campo 'valor_de_la_medida' debe ser numérico.", 400)

    sensor_id = data.get("id_sensor")
    referencia = data.get("referencia")
    nombre_sensor = data.get("nombre_sensor")

    usuario_id = data.get("id_usuario")
    correo_usuario = data.get("correo")
    nombre_usuario = data.get("nombre_usuario")

    parsed_sensor_id = None
    parsed_usuario_id = None

    if sensor_id is not None:
        try:
            parsed_sensor_id = int(sensor_id)
        except (TypeError, ValueError):
            return json_error("El campo 'id_sensor' debe ser numérico.", 400)

    if usuario_id is not None:
        try:
            parsed_usuario_id = int(usuario_id)
        except (TypeError, ValueError):
            return json_error("El campo 'id_usuario' debe ser numérico.", 400)

    fecha = data.get("fecha")
    if fecha is not None:
        try:
            fecha = parse_iso_datetime(fecha)
        except ValueError as exc:
            return json_error(str(exc), 400)

    if not any([parsed_sensor_id, referencia, nombre_sensor]):
        return json_error("Debe proporcionar 'id_sensor', 'referencia' o 'nombre_sensor' para identificar el sensor.", 400)
    if not any([parsed_usuario_id, correo_usuario, nombre_usuario]):
        return json_error("Debe proporcionar 'id_usuario', 'correo' o 'nombre_usuario' para identificar al usuario.", 400)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        sensor_encontrado = buscar_sensor(cursor, parsed_sensor_id, referencia, nombre_sensor)
        if sensor_encontrado is None:
            return json_error("Sensor no encontrado.", 404)

        usuario_encontrado = buscar_usuario(cursor, parsed_usuario_id, correo_usuario, nombre_usuario)
        if usuario_encontrado is None:
            return json_error("Usuario no encontrado.", 404)

        if fecha:
            cursor.execute(
                """
                INSERT INTO medidas (id_sensor, id_usuarios, valor_de_la_medida, fecha)
                VALUES (%s, %s, %s, %s)
                """,
                (sensor_encontrado, usuario_encontrado, valor, fecha),
            )
        else:
            cursor.execute(
                """
                INSERT INTO medidas (id_sensor, id_usuarios, valor_de_la_medida)
                VALUES (%s, %s, %s)
                """,
                (sensor_encontrado, usuario_encontrado, valor),
            )
        conn.commit()
        return jsonify({"success": True, "message": "Medida registrada correctamente."}), 201
    except Error as exc:
        conn.rollback()
        print("Error al insertar medida:", exc)
        return json_error("No se pudo registrar la medida.", 500)
    finally:
        close_resources(cursor, conn)


@app.route("/ultimo_valor/<int:sensor_id>", methods=["GET"])
def ultimo_valor(sensor_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT valor_de_la_medida
            FROM medidas
            WHERE id_sensor = %s
            ORDER BY fecha DESC
            LIMIT 1
            """,
            (sensor_id,),
        )
        resultado = cursor.fetchone()
        if not resultado:
            return json_error("No hay datos disponibles para el sensor.", 404)
        return jsonify({"success": True, "valor": resultado[0]})
    except Error as exc:
        print("Error al consultar último valor:", exc)
        return json_error("No se pudo obtener el valor.", 500)
    finally:
        close_resources(cursor, conn)


@app.route("/historial", methods=["GET"])
def mostrar_historial():
    sensor_id = request.args.get("sensor", type=int)
    if sensor_id is None:
        return json_error("El parámetro 'sensor' es obligatorio y debe ser numérico.", 400)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT valor_de_la_medida, fecha
            FROM medidas
            WHERE id_sensor = %s
            ORDER BY fecha DESC
            """,
            (sensor_id,),
        )
        historial = [{"valor": row[0], "fecha": row[1].strftime("%Y-%m-%d %H:%M:%S")} for row in cursor.fetchall()]
        return jsonify({"success": True, "historial": historial})
    except Error as exc:
        print("Error al obtener historial:", exc)
        return json_error("No se pudo obtener el historial.", 500)
    finally:
        close_resources(cursor, conn)


# ---------------------------------------------------------------------------
# Reportes
# ---------------------------------------------------------------------------

@app.route("/consultar_reportes", methods=["POST"])
def consultar_reportes():
    data = request.get_json(silent=True) or {}
    nombre_sensor = data.get("nombreSensor")
    fecha_inicio = data.get("fechaInicio")
    fecha_fin = data.get("fechaFin")

    if not nombre_sensor or not fecha_inicio or not fecha_fin:
        return json_error("Los campos 'nombreSensor', 'fechaInicio' y 'fechaFin' son obligatorios.", 400)

    try:
        fecha_inicio_dt = parse_iso_datetime(fecha_inicio)
        fecha_fin_dt = parse_iso_datetime(fecha_fin)
    except ValueError as exc:
        return json_error(str(exc), 400)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT s.nombre_sensor, m.fecha, m.valor_de_la_medida
            FROM medidas m
            INNER JOIN sensores s ON m.id_sensor = s.id
            WHERE s.nombre_sensor = %s
              AND m.fecha BETWEEN %s AND %s
            ORDER BY m.fecha ASC
            """,
            (nombre_sensor, fecha_inicio_dt, fecha_fin_dt),
        )
        reportes = [{
            "nombreSensor": row[0],
            "fecha": row[1].strftime("%Y-%m-%d %H:%M:%S"),
            "valor": row[2],
        } for row in cursor.fetchall()]
        return jsonify({"success": True, "data": reportes})
    except Error as exc:
        print("Error al consultar reportes:", exc)
        return json_error("No se pudieron obtener los reportes.", 500)
    finally:
        close_resources(cursor, conn)


@app.route("/reporte_usuario", methods=["POST"])
def reporte_usuario():
    data = request.get_json(silent=True) or {}
    id_usuario = data.get("id_usuario")
    if id_usuario is None:
        return json_error("El campo 'id_usuario' es obligatorio.", 400)

    try:
        id_usuario = int(id_usuario)
    except (TypeError, ValueError):
        return json_error("El campo 'id_usuario' debe ser numérico.", 400)

    fecha_inicio = data.get("fechaInicio")
    fecha_fin = data.get("fechaFin")
    tipo_reporte = data.get("tipo_reporte")
    sensor_id = data.get("sensor_id")

    if sensor_id not in (None, ""):
        try:
            sensor_id = int(sensor_id)
        except (TypeError, ValueError):
            return json_error("El campo 'sensor_id' debe ser numérico cuando se proporciona.", 400)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, nombre_sensor FROM sensores WHERE id_usuario = %s",
            (id_usuario,),
        )
        sensores = cursor.fetchall()
        if not sensores:
            return jsonify({"success": True, "data": []})

        sensores_ids = [sensor["id"] for sensor in sensores]
        if sensor_id and sensor_id in sensores_ids:
            sensores_ids = [sensor_id]

        filtros = ["m.id_sensor IN (%s)" % ",".join(["%s"] * len(sensores_ids))]
        params = list(sensores_ids)

        if fecha_inicio:
            try:
                fecha_inicio_dt = parse_iso_datetime(fecha_inicio)
            except ValueError as exc:
                return json_error(str(exc), 400)
            filtros.append("m.fecha >= %s")
            params.append(fecha_inicio_dt)

        if fecha_fin:
            try:
                fecha_fin_dt = parse_iso_datetime(fecha_fin)
            except ValueError as exc:
                return json_error(str(exc), 400)
            filtros.append("m.fecha <= %s")
            params.append(fecha_fin_dt)

        where_clause = " AND ".join(filtros)
        cursor.execute(
            f"""
            SELECT m.id_sensor, s.nombre_sensor, m.fecha, m.valor_de_la_medida
            FROM medidas m
            INNER JOIN sensores s ON m.id_sensor = s.id
            WHERE {where_clause}
            ORDER BY m.fecha ASC
            """,
            tuple(params),
        )
        registros = cursor.fetchall()

        if tipo_reporte in ("semanal", "mensual"):
            from collections import defaultdict

            agrupados = defaultdict(list)
            for fila in registros:
                fecha = fila["fecha"]
                if tipo_reporte == "semanal":
                    clave = f"{fecha.year}-S{fecha.isocalendar()[1]}"
                else:
                    clave = f"{fecha.year}-{fecha.month:02d}"
                agrupados[(fila["id_sensor"], clave)].append(fila)

            respuesta = []
            for (sensor, periodo), filas in agrupados.items():
                valores = [f["valor_de_la_medida"] for f in filas]
                promedio = sum(valores) / len(valores) if valores else 0
                respuesta.append({
                    "sensor_id": sensor,
                    "nombre_sensor": filas[0]["nombre_sensor"],
                    "periodo": periodo,
                    "promedio": round(promedio, 2),
                    "medidas": len(valores),
                })
            return jsonify({"success": True, "data": respuesta})

        respuesta = [{
            "sensor_id": fila["id_sensor"],
            "nombre_sensor": fila["nombre_sensor"],
            "fecha": fila["fecha"].strftime("%Y-%m-%d %H:%M:%S"),
            "valor": fila["valor_de_la_medida"],
        } for fila in registros]
        return jsonify({"success": True, "data": respuesta})
    except Error as exc:
        print("Error al generar reporte de usuario:", exc)
        return json_error("No se pudo generar el reporte.", 500)
    finally:
        close_resources(cursor, conn)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)




