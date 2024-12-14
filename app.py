from flask import Flask, render_template, request, redirect, url_for, session
import os
import mysql.connector
from datetime import datetime
from admin import admin_blueprint  # Importamos el módulo admin

app = Flask(__name__)
app.secret_key = 'super_secret_key'  # Cambia esto a algo seguro para la gestión de sesiones

# Registro del Blueprint para el módulo de administración
app.register_blueprint(admin_blueprint, url_prefix='/admin')


# Configuración de la conexión a la base de datos
db_config = {
    'user': 'root',
    'password': '',  # Cambia esto a tu contraseña si es necesario
    'host': 'localhost',  # Cambia a la dirección de tu servidor si es remoto
    'database': 'se_estres'
}

def get_db_connection():
    """Establece una conexión con la base de datos y la retorna"""
    return mysql.connector.connect(**db_config)

def obtener_preguntas():
    """Recupera las preguntas desde la base de datos"""
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT id_pregunta, texto, invertir FROM preguntas")
    preguntas = cursor.fetchall()
    cursor.close()
    connection.close()
    return preguntas

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/registro_usuario')
def registro_usuario():
    return render_template('registro_usuario.html')

@app.route('/guardar_datos', methods=['POST'])
def guardar_datos():
    # Capturar los datos del formulario
    nombre = request.form['nombre'].upper()
    edad = request.form['edad']
    sex = request.form['sex']
    num_celular = request.form['num_celular']
    email = request.form['email']  # Este campo es opcional, por eso usamos get()
    direccion = request.form['direccion']  # Este campo es opcional, por eso usamos get()
    region = request.form['region']
    zona = request.form['zona']
    codigo = request.form['codigo']
    ciclo = request.form['ciclo']
    seccion = request.form['seccion']
    turno = request.form['turno']

    # Imprimir los valores para depuración
    print("Datos recibidos:")
    print(nombre, edad, sex, num_celular, email, direccion, region, zona, codigo, ciclo, seccion, turno)

    # Guardar los datos en la base de datos
    connection = get_db_connection()
    cursor = connection.cursor()
    query = """
        INSERT INTO estudiantes (nombre, edad, sex, num_celular, email, direccion, region, zona, codigo, ciclo, seccion, turno)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(query, (nombre, edad, sex, num_celular, email, direccion, region, zona, codigo, ciclo, seccion, turno))
    connection.commit()
    id_estudiante = cursor.lastrowid  # Obtiene el ID del estudiante recién registrado
    cursor.close()
    connection.close()

    # Guardar el ID del estudiante en la sesión
    session['id_estudiante'] = id_estudiante

    return redirect(url_for('iniciar_test'))



@app.route('/iniciar_test')
def iniciar_test():
    # Redirige a la primera pregunta
    return redirect(url_for('pregunta', num=1))

@app.route('/pregunta/<int:num>', methods=['GET', 'POST'])
def pregunta(num):
    preguntas = obtener_preguntas()
    if num > len(preguntas):
        return redirect(url_for('resultados'))

    if request.method == 'POST':
        respuesta = request.form.get('respuesta')
        id_estudiante = session.get('id_estudiante')

        if id_estudiante and respuesta is not None:
            # Verificar si ya existe una respuesta para esta pregunta y estudiante
            id_pregunta = preguntas[num - 1][0]
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT * FROM respuestas WHERE id_estudiante = %s AND id_pregunta = %s
            """, (id_estudiante, id_pregunta))
            existing_respuesta = cursor.fetchone()

            if existing_respuesta:
                # Si la respuesta ya existe, actualízala
                cursor.execute("""
                    UPDATE respuestas
                    SET respuesta = %s
                    WHERE id_estudiante = %s AND id_pregunta = %s
                """, (int(respuesta), id_estudiante, id_pregunta))
            else:
                # Si no existe, insertar una nueva respuesta
                cursor.execute("""
                    INSERT INTO respuestas (id_estudiante, id_pregunta, respuesta)
                    VALUES (%s, %s, %s)
                """, (id_estudiante, id_pregunta, int(respuesta)))
            connection.commit()
            cursor.close()
            connection.close()

        # Redirige a la siguiente pregunta
        return redirect(url_for('pregunta', num=num + 1))

    return render_template('pregunta.html', num=num, pregunta=preguntas[num - 1][1], total_preguntas=len(preguntas))

@app.route('/resultados')
def resultados():
    id_estudiante = session.get('id_estudiante')
    if not id_estudiante:
        return redirect(url_for('index'))

    # Obtener las respuestas del estudiante
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT p.id_pregunta, p.invertir, r.respuesta
        FROM respuestas r
        JOIN preguntas p ON r.id_pregunta = p.id_pregunta
        WHERE r.id_estudiante = %s
    """, (id_estudiante,))
    respuestas = cursor.fetchall()

# Obtener el nombre del estudiante
    cursor.execute("SELECT nombre FROM estudiantes WHERE id_estudiante = %s", (id_estudiante,))
    nombre_estudiante = cursor.fetchone()[0]  # Obtenemos el nombre del estudiante

    cursor.close()
    connection.close()

    print("Datos de respuestas obtenidas:", respuestas)  # Agregar esta línea para depuración


    # Calcular el puntaje total

    puntaje_total = 0
    for id_pregunta, invertir, respuesta in respuestas:
        if invertir:
            puntaje_total += 4 - respuesta  # Invertir la puntuación
        else:
            puntaje_total += respuesta
    
    # Calcular el porcentaje de progreso basado en puntaje_total
    porcentaje_progreso = round((puntaje_total / 42) * 100, 2)

    # Determinar el nivel de estrés y recomendaciones
    if puntaje_total <= 14:
        nivel_estres = "Casi nunca o nunca está estresado."
        recomendaciones = [
            "Continúe practicando actividades relajantes.",
            "Mantenga hábitos de vida saludables.",
            "Realice ejercicios regularmente para mantener un buen estado físico y mental."
        ]
        nivel_clase = "bajo"
    elif puntaje_total <= 28:
        nivel_estres = "De vez en cuando está estresado."
        recomendaciones = [
            "Practique técnicas de relajación, como la meditación o la respiración profunda.",
            "Intente equilibrar su tiempo entre el trabajo y las actividades recreativas.",
            "Dedique tiempo a sus hobbies y pasatiempos para reducir el estrés."
        ]
        nivel_clase = "moderado"
    elif puntaje_total <= 42:
        nivel_estres = "A menudo está estresado."
        recomendaciones = [
            "Considere establecer una rutina diaria de ejercicios y relajación.",
            "Hable con amigos o familiares sobre sus preocupaciones.",
            "Evalúe la posibilidad de ajustar su carga de trabajo o sus responsabilidades diarias."
        ]
        nivel_clase = "alto"
    else:
        nivel_estres = "Muy a menudo está estresado."
        recomendaciones = [
            "Considere buscar apoyo profesional, como un terapeuta o consejero.",
            "Practique actividades de autocuidado, como el descanso adecuado y una dieta saludable.",
            "Evite el consumo excesivo de estimulantes, como la cafeína o el alcohol."
        ]
        nivel_clase = "muy-alto"

    # Guardar el diagnóstico en la base de datos
    fecha_diagnostico = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    connection = get_db_connection()
    cursor = connection.cursor()
    query = """
        INSERT INTO diagnosticos (id_estudiante, puntaje_total, nivel_estres, nivel_clase, recomendaciones, fecha_diagnostico)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    cursor.execute(query, (id_estudiante, puntaje_total, nivel_estres, nivel_clase, ', '.join(recomendaciones), fecha_diagnostico))
    connection.commit()
    cursor.close()
    connection.close()

    # Pasar los datos al template
    return render_template('resultados.html', nombre_estudiante=nombre_estudiante, puntaje_total=puntaje_total,porcentaje_progreso=porcentaje_progreso, nivel_estres=nivel_estres, recomendaciones=recomendaciones, nivel_clase=nivel_clase)
    
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)



