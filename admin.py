from flask import Blueprint, render_template, request, redirect, url_for, session
from functools import wraps
import os
from flask import send_file
import pandas as pd
from db_config import get_db_connection

# Crear un Blueprint para el módulo de administración
admin_blueprint = Blueprint('admin', __name__)

# Decorador para requerir inicio de sesión
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login_admin'))
        return f(*args, **kwargs)
    return decorated_function

# Ruta para el inicio de sesión
@admin_blueprint.route('/login', methods=['GET', 'POST'])
def login_admin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Conexión a la base de datos
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Consultar si el usuario existe
        query = "SELECT * FROM administradores WHERE username = %s"
        cursor.execute(query, (username,))
        admin = cursor.fetchone()

        cursor.close()
        connection.close()

        # Validar credenciales
        if admin and admin['password'] == password:  # Asegúrate de usar hash en producción
            session['admin_logged_in'] = True
            session['admin_username'] = admin['username']
            return render_template(
                'admin/login_admin.html',
                success_message="Inicio de sesión exitoso. Redirigiendo al panel de administración..."
            )
        else:
            return render_template(
                'admin/login_admin.html',
                error_message="Usuario o contraseña incorrectos."
            )

    return render_template('admin/login_admin.html')

@admin_blueprint.route('/panel')
@login_required
def panel_admin():
    # Conexión a la base de datos
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    # Obtener el conteo de registros
    cursor.execute("SELECT COUNT(*) FROM diagnosticos")
    num_diagnosticos = cursor.fetchone()['COUNT(*)']

    cursor.execute("SELECT COUNT(*) FROM estudiantes")
    num_estudiantes = cursor.fetchone()['COUNT(*)']

    cursor.execute("SELECT COUNT(*) FROM preguntas")
    num_preguntas = cursor.fetchone()['COUNT(*)']

    cursor.close()
    connection.close()

    # Pasar los conteos a la plantilla
    return render_template('admin/panel_admin.html', 
                           num_diagnosticos=num_diagnosticos,
                           num_estudiantes=num_estudiantes,
                           num_preguntas=num_preguntas)

# Ruta para mostrar el módulo de Diagnósticos
@admin_blueprint.route('/diagnosticos', methods=['GET'])
@login_required
def diagnosticos():
    # Obtener el término de búsqueda desde la URL (nombre o código)
    search_term = request.args.get('search_term', '')  # Parámetro único para buscar por nombre o código

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Consulta con filtrado por nombre o código del estudiante
    query = """
        SELECT d.id_diagnostico, e.id_estudiante, e.nombre, d.puntaje_total, d.nivel_estres, d.nivel_clase, d.recomendaciones, d.fecha_diagnostico
        FROM diagnosticos d
        JOIN estudiantes e ON e.id_estudiante = d.id_estudiante
        WHERE e.nombre LIKE %s OR e.codigo LIKE %s  -- Filtrando por nombre o código
    """
    
    # Filtrando con el valor de búsqueda, permitiendo coincidencias parciales
    cursor.execute(query, ('%' + search_term + '%', '%' + search_term + '%'))  
    diagnosticos = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('admin/diagnosticos.html', diagnosticos=diagnosticos, search_term=search_term)




# Ruta para mostrar el módulo de Estudiantes
@admin_blueprint.route('/estudiantes')
@login_required
def estudiantes():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Aquí puedes agregar la lógica para mostrar los estudiantes
    query = "SELECT id_estudiante, nombre, edad, ciclo, region, seccion, turno, num_celular, codigo FROM estudiantes"
    cursor.execute(query)
    estudiantes = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('admin/estudiantes.html', estudiantes=estudiantes)

# Ruta para mostrar el módulo de Preguntas
@admin_blueprint.route('/preguntas')
@login_required
def preguntas():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Consulta a la base de datos para obtener las preguntas
    query = "SELECT id_pregunta, texto, invertir FROM preguntas"
    cursor.execute(query)
    preguntas = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('admin/preguntas.html', preguntas=preguntas)


# Ruta para exportar las respuestas de un estudiante a Excel
@admin_blueprint.route('/exportar_respuestas/<int:id_estudiante>')
@login_required
def exportar_respuestas(id_estudiante):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Obtener el nombre del estudiante
    cursor.execute("SELECT nombre FROM estudiantes WHERE id_estudiante = %s", (id_estudiante,))
    nombre_estudiante = cursor.fetchone()

    if not nombre_estudiante:
        return "Estudiante no encontrado", 404

    # Obtener las respuestas del estudiante específico con sus textos y el campo 'invertir'
    query = """
        SELECT DISTINCT p.texto AS pregunta, o.opcion AS respuesta, r.respuesta AS valor, p.invertir
        FROM respuestas r
        JOIN preguntas p ON r.id_pregunta = p.id_pregunta
        JOIN opciones o ON r.respuesta = o.valor
        WHERE r.id_estudiante = %s
    """
    cursor.execute(query, (id_estudiante,))
    respuestas = cursor.fetchall()

    # Modificar la respuesta si la pregunta debe ser invertida
    for respuesta in respuestas:
        if respuesta['invertir'] == 1:
            # Invertir la respuesta
            respuesta['valor'] = 4 - int(respuesta['valor'])  # Invertir la respuesta en la escala de 0 a 4

    cursor.close()
    connection.close()

    if respuestas:
        # Crear un DataFrame de las respuestas sin la columna 'invertir'
        df_respuestas = pd.DataFrame(respuestas).drop(columns=['invertir'])

        # Asegurarse de que la columna 'valor' es numérica
        df_respuestas['valor'] = pd.to_numeric(df_respuestas['valor'], errors='coerce')

        # Crear un nombre de archivo seguro con el nombre del estudiante y el id_estudiante
        nombre_archivo = f"respuestas_estudiante_{id_estudiante}_{nombre_estudiante['nombre'].replace(' ', '_')}.xlsx"
        ruta_archivo = os.path.join('./static/exports', nombre_archivo)

        # Guardar el DataFrame como un archivo Excel
        df_respuestas.to_excel(ruta_archivo, index=False)

        # Enviar el archivo Excel al usuario
        return send_file(ruta_archivo, as_attachment=True)

    return "No se encontraron respuestas para este estudiante.", 404





# Ruta para eliminar un diagnóstico
@admin_blueprint.route('/eliminar_diagnostico/<int:id_diagnostico>', methods=['GET', 'POST'])
@login_required
def eliminar_diagnostico(id_diagnostico):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Eliminar las respuestas relacionadas con el diagnóstico
        query_respuestas = "DELETE FROM respuestas WHERE id_estudiante IN (SELECT id_estudiante FROM diagnosticos WHERE id_diagnostico = %s)"
        cursor.execute(query_respuestas, (id_diagnostico,))

        # Eliminar el diagnóstico
        query_diagnostico = "DELETE FROM diagnosticos WHERE id_diagnostico = %s"
        cursor.execute(query_diagnostico, (id_diagnostico,))

        connection.commit()
        return redirect(url_for('admin.diagnosticos'))  # Redirigir a la lista de diagnósticos
    except Exception as e:
        connection.rollback()  # En caso de error, revertir los cambios
        print(f"Error al eliminar el diagnóstico: {e}")
        return "Hubo un error al intentar eliminar el diagnóstico. Intenta nuevamente.", 500
    finally:
        cursor.close()
        connection.close()


# Modificación en la ruta para exportar los diagnósticos a Excel
@admin_blueprint.route('/exportar_diagnosticos', methods=['GET'])
@login_required
def exportar_diagnosticos():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Consulta SQL para obtener los datos del estudiante, las preguntas y las respuestas
    query = """
        SELECT 
            d.id_diagnostico,
            e.sex AS sexo_estudiante,
            e.edad,
            e.region,
            e.zona,
            e.ciclo,
            e.seccion,
            e.turno,
            d.puntaje_total,
            d.nivel_clase,
            p.texto AS pregunta,
            o.opcion AS respuesta
        FROM diagnosticos d
        JOIN estudiantes e ON d.id_estudiante = e.id_estudiante
        JOIN respuestas r ON r.id_estudiante = e.id_estudiante
        JOIN preguntas p ON r.id_pregunta = p.id_pregunta
        JOIN opciones o ON r.respuesta = o.valor
        ORDER BY d.id_estudiante, p.id_pregunta
    """
    cursor.execute(query)
    diagnosticos = cursor.fetchall()

    cursor.close()
    connection.close()

    # Crear un DataFrame con los datos obtenidos
    df_diagnosticos = pd.DataFrame(diagnosticos)

    # Reestructurar el DataFrame para tener una sola fila por estudiante
    df_pivot = df_diagnosticos.pivot_table(
        index=["id_diagnostico", "sexo_estudiante", "edad", "region", "zona", "ciclo", "seccion", "turno", "puntaje_total", "nivel_clase"],
        columns="pregunta",
        values="respuesta",
        aggfunc=lambda x: ' '.join(str(i) for i in x)
    ).reset_index()

    # Guardar el DataFrame como un archivo Excel
    ruta_archivo = './static/exports/diagnosticos_estudiantes.xlsx'
    df_pivot.to_excel(ruta_archivo, index=False)

    # Enviar el archivo Excel al usuario
    return send_file(ruta_archivo, as_attachment=True)



# Ruta para eliminar un estudiante
@admin_blueprint.route('/eliminar_estudiante/<int:id_estudiante>')
@login_required
def eliminar_estudiante(id_estudiante):
    connection = get_db_connection()
    cursor = connection.cursor()

    # Eliminar las respuestas asociadas al estudiante
    cursor.execute("DELETE FROM respuestas WHERE id_estudiante = %s", (id_estudiante,))
    
    # Eliminar el diagnóstico asociado al estudiante
    cursor.execute("DELETE FROM diagnosticos WHERE id_estudiante = %s", (id_estudiante,))
    
    # Eliminar el estudiante
    cursor.execute("DELETE FROM estudiantes WHERE id_estudiante = %s", (id_estudiante,))

    connection.commit()
    cursor.close()
    connection.close()

    return redirect(url_for('admin.estudiantes'))  # Redirige al listado de estudiantes después de eliminar


# Ruta para editar una pregunta
@admin_blueprint.route('/editar_pregunta/<int:id_pregunta>', methods=['GET', 'POST'])
@login_required
def editar_pregunta(id_pregunta):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Obtener la pregunta actual desde la base de datos
    cursor.execute("SELECT * FROM preguntas WHERE id_pregunta = %s", (id_pregunta,))
    pregunta = cursor.fetchone()

    if request.method == 'POST':
        # Obtener los datos del formulario de edición
        texto = request.form['texto']
        invertir = True if request.form.get('invertir') else False  # Convertir a booleano

        # Actualizar la pregunta en la base de datos
        query = """
            UPDATE preguntas
            SET texto = %s, invertir = %s
            WHERE id_pregunta = %s
        """
        cursor.execute(query, (texto, invertir, id_pregunta))
        connection.commit()
        cursor.close()
        connection.close()

        # Redirigir a la página de preguntas después de editar
        return redirect(url_for('admin.preguntas'))

    cursor.close()
    connection.close()

    # Mostrar el formulario con la información de la pregunta actual
    return render_template('admin/editar_pregunta.html', pregunta=pregunta)

# Ruta para eliminar una pregunta
@admin_blueprint.route('/eliminar_pregunta/<int:id_pregunta>', methods=['GET'])
@login_required
def eliminar_pregunta(id_pregunta):
    connection = get_db_connection()
    cursor = connection.cursor()

    # Eliminar todas las respuestas asociadas a la pregunta
    cursor.execute("DELETE FROM respuestas WHERE id_pregunta = %s", (id_pregunta,))
    connection.commit()

    # Eliminar la pregunta de la base de datos
    cursor.execute("DELETE FROM preguntas WHERE id_pregunta = %s", (id_pregunta,))
    connection.commit()

    cursor.close()
    connection.close()

    # Redirigir al módulo de preguntas después de eliminar
    return redirect(url_for('admin.preguntas'))



# Ruta para agregar una nueva pregunta
@admin_blueprint.route('/agregar_pregunta', methods=['GET', 'POST'])
@login_required
def agregar_pregunta():
    if request.method == 'POST':
        texto = request.form['texto']
        invertir = bool(request.form.get('invertir'))  # Si se marca como checkbox, se convierte en un booleano
        
        # Insertar la nueva pregunta en la base de datos
        connection = get_db_connection()
        cursor = connection.cursor()
        query = """
            INSERT INTO preguntas (texto, invertir)
            VALUES (%s, %s)
        """
        cursor.execute(query, (texto, invertir))
        connection.commit()
        cursor.close()
        connection.close()

        return redirect(url_for('admin.preguntas'))  # Redirigir a la lista de preguntas

    return render_template('admin/agregar_pregunta.html')  # El formulario de agregar pregunta



# Ruta para cerrar sesión
@admin_blueprint.route('/logout')
def logout_admin():
    session.clear()
    return redirect(url_for('admin.login_admin'))

