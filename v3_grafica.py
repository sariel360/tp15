"""
Laboratorio de Aplicaciones II - 6° G
TP N° 15: Operaciones CRUD con bases de datos en Python
Temática: Sistema de gestión de un pañol de herramientas

Versión con INTERFAZ GRÁFICA (customtkinter). Reemplaza al menú por consola:
las consultas SQL, las transacciones y las reglas de negocio son las mismas;
solo cambió la forma de pedir y mostrar los datos (formularios y tablas en
lugar de input() y print()).

Pantallas (barra lateral):
  Inicio        -> resumen del pañol y préstamos activos
  Herramientas  -> ver/buscar (R), agregar (C), editar y cambiar estado (U), eliminar (D)
  Personas      -> ver/buscar (R), agregar (C), editar (U), eliminar (D)
  Préstamos     -> ver activos/historial (R), registrar (C), devolver y editar (U), eliminar (D)
  Categorías    -> consulta (R)

Antes de ejecutarlo:
  1) pip install customtkinter mysql-connector-python
  2) correr crear_bd.sql en el servidor
  3) cargar los datos de conexión en CONFIG_BD (o en las variables de entorno
     BD_HOST, BD_PORT, BD_NAME, BD_USER y BD_PASSWORD).
Si no hay contraseña, el programa la pide al iniciar.
"""

# =====================================================================
# 1) IMPORTACIÓN DE LIBRERÍAS
# =====================================================================
import os                                   # para leer variables de entorno
from datetime import date, datetime         # fechas (hoy y validación de fechas escritas)
from tkinter import ttk, messagebox, simpledialog   # tabla, avisos y pedido de contraseña

import customtkinter as ctk                 # interfaz gráfica moderna sobre tkinter
import mysql.connector                      # conector oficial entre Python y MySQL
from mysql.connector import Error, IntegrityError   # excepciones del conector

# =====================================================================
# 2) CONFIGURACIÓN DE LA BASE DE DATOS
# =====================================================================
# Si existe la variable de entorno se usa; si no, se toma el valor por defecto.
CONFIG_BD = {
    "host": os.getenv("BD_HOST", "localhost"),
    "port": int(os.getenv("BD_PORT", "3306")),
    "database": os.getenv("BD_NAME", "panol_herramientas"),
    "user": os.getenv("BD_USER", "root"),
    "password": os.getenv("BD_PASSWORD", "Patricio@360"),  # Contraseña de la BD
    "charset": "utf8mb4",   # para que las tildes y la ñ se vean bien
}

# Estados posibles de una herramienta (coinciden con el ENUM de la tabla)
ESTADOS = {
    "1": "Disponible",
    "2": "Prestado",
    "3": "Mantenimiento",
    "4": "Dañado",
}

# Estados que se pueden elegir a mano. "Prestado" no está: se asigna solo
# al registrar un préstamo, así el estado y la tabla prestamos no se desfasan.
ESTADOS_MANUALES = {
    "1": "Disponible",
    "2": "Mantenimiento",
    "3": "Dañado",
}

# Último mensaje de error de base de datos (lo muestra la interfaz)
ULTIMO_ERROR = ""

# =====================================================================
# 3) FUNCIONES AUXILIARES DE BASE DE DATOS
# =====================================================================
def conectar_bd():
    """Abre y devuelve una conexión a MySQL (si falla, lanza un Error)."""
    return mysql.connector.connect(**CONFIG_BD)


def cerrar_todo(cursor, conexion):
    """Cierra el cursor y la conexión si existen y están abiertos.

    Se llama siempre desde el bloque 'finally', así los recursos se liberan
    aunque haya ocurrido un error en el medio.
    """
    if cursor is not None:
        cursor.close()
    if conexion is not None and conexion.is_connected():
        conexion.close()


def consultar(sql, parametros=()):
    """Ejecuta un SELECT parametrizado y devuelve todas las filas.

    Si hay un error de base de datos guarda el mensaje en ULTIMO_ERROR
    (la interfaz lo muestra) y devuelve None.
    """
    global ULTIMO_ERROR
    conexion = None
    cursor = None
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute(sql, parametros)
        return cursor.fetchall()
    except Error as error:
        ULTIMO_ERROR = str(error)
        return None
    finally:
        cerrar_todo(cursor, conexion)


def ejecutar_operacion(operacion):
    """Abre la conexión, ejecuta 'operacion(cursor, conexion)' y cierra todo.

    'operacion' devuelve una tupla (ok, mensaje). Si ocurre un error de base
    de datos se hace rollback y se devuelve (False, mensaje de error).
    """
    conexion = None
    cursor = None
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        return operacion(cursor, conexion)
    except Error as error:
        if conexion is not None:
            conexion.rollback()
        return False, f"Error de base de datos: {error}"
    finally:
        cerrar_todo(cursor, conexion)


def texto_o_guion(valor):
    """Para mostrar en tablas: si el valor es NULL (None) muestra un guion."""
    return "-" if valor is None else str(valor)


def validar_fecha(texto, actual):
    """Interpreta una fecha escrita como AAAA-MM-DD.

    - Texto vacío    -> devuelve 'actual' (se conserva el valor).
    - Fecha válida   -> devuelve un objeto date.
    - Fecha inválida -> devuelve False.
    """
    texto = texto.strip()
    if texto == "":
        return actual
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError:
        return False


def id_de(opcion):
    """Extrae el ID de una opción de lista desplegable con formato '3 - Nombre'."""
    parte = opcion.split(" - ")[0].strip()
    return int(parte) if parte.isdigit() else None


# =====================================================================
# 4) READ - CONSULTAS (SELECT)
# =====================================================================
# Consulta base de herramientas: LEFT JOIN para traer también la categoría
SQL_HERRAMIENTAS = """
    SELECT h.id, h.nombre, h.marca, h.modelo, c.nombre, h.estado
    FROM herramientas h
    LEFT JOIN categorias c ON h.id_categoria = c.id
"""

# Consulta base compartida por el historial, la edición y la eliminación de préstamos
SQL_PRESTAMOS = """
    SELECT p.id, h.nombre, per.nombre, p.fecha_prestamo, p.fecha_devolucion, p.observaciones
    FROM prestamos p
    JOIN herramientas h ON p.id_herramienta = h.id
    JOIN personas per   ON p.id_persona = per.id
"""


def buscar_herramientas(texto="", estado="", id_categoria=None):
    """Herramientas con filtros opcionales (nombre, estado y categoría)."""
    sql = SQL_HERRAMIENTAS
    condiciones = []
    parametros = []
    if estado:
        condiciones.append("h.estado = %s")
        parametros.append(estado)
    if texto:
        condiciones.append("h.nombre LIKE %s")
        parametros.append(f"%{texto}%")      # los % van en el valor, no en la consulta
    if id_categoria:
        condiciones.append("h.id_categoria = %s")
        parametros.append(id_categoria)
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY h.id"
    return consultar(sql, tuple(parametros))


def buscar_personas(texto=""):
    """Personas; si hay texto, busca por nombre o departamento."""
    sql = "SELECT id, nombre, departamento, email FROM personas"
    parametros = ()
    if texto:
        sql += " WHERE nombre LIKE %s OR departamento LIKE %s"
        parametros = (f"%{texto}%", f"%{texto}%")
    sql += " ORDER BY id"
    return consultar(sql, parametros)


def obtener_categorias():
    """Categorías con su cantidad de herramientas."""
    return consultar(
        """
        SELECT c.id, c.nombre, COUNT(h.id)
        FROM categorias c
        LEFT JOIN herramientas h ON h.id_categoria = c.id
        GROUP BY c.id, c.nombre
        ORDER BY c.id
        """
    )


def obtener_prestamos(solo_activos=False, id_persona=None, id_herramienta=None):
    """Préstamos (activos o historial completo) con filtros opcionales."""
    sql = SQL_PRESTAMOS
    condiciones = []
    parametros = []
    if solo_activos:
        # Un préstamo está activo mientras fecha_devolucion sea NULL
        condiciones.append("p.fecha_devolucion IS NULL")
    if id_persona:
        condiciones.append("p.id_persona = %s")
        parametros.append(id_persona)
    if id_herramienta:
        condiciones.append("p.id_herramienta = %s")
        parametros.append(id_herramienta)
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY p.id"
    return consultar(sql, tuple(parametros))


# =====================================================================
# 5) HERRAMIENTAS: CREATE / UPDATE / DELETE
# =====================================================================
def agregar_herramienta(nombre, marca, modelo, id_categoria):
    """Inserta una nueva herramienta (estado inicial 'Disponible')."""
    nombre = nombre.strip()
    if not nombre:
        return False, "El nombre no puede estar vacío."
    marca = marca.strip() or None       # si queda vacío se guarda NULL
    modelo = modelo.strip() or None

    def operacion(cursor, conexion):
        try:
            # Consulta parametrizada: los %s se reemplazan de forma segura
            cursor.execute(
                """
                INSERT INTO herramientas (nombre, marca, modelo, id_categoria, estado, fecha_adquisicion)
                VALUES (%s, %s, %s, %s, 'Disponible', %s)
                """,
                (nombre, marca, modelo, id_categoria, date.today()),
            )
            conexion.commit()   # sin commit() los cambios no se guardan en la base
            return True, f"Herramienta agregada correctamente (ID {cursor.lastrowid})"
        except IntegrityError:
            # Pasa, por ejemplo, si la categoría ingresada no existe (clave foránea)
            conexion.rollback()
            return False, "No se pudo agregar: la categoría indicada no existe."

    return ejecutar_operacion(operacion)


def editar_herramienta(id_herramienta, nombre, marca, modelo, id_categoria):
    """Modifica nombre, marca, modelo o categoría; un campo vacío conserva el valor actual."""
    def operacion(cursor, conexion):
        cursor.execute(
            "SELECT nombre, marca, modelo, id_categoria FROM herramientas WHERE id = %s",
            (id_herramienta,),
        )
        actual = cursor.fetchone()
        if actual is None:
            return False, "No existe una herramienta con ese ID."

        nuevo_nombre = nombre.strip() or actual[0]
        nueva_marca = marca.strip() or actual[1]
        nuevo_modelo = modelo.strip() or actual[2]
        nueva_categoria = id_categoria if id_categoria is not None else actual[3]
        try:
            cursor.execute(
                "UPDATE herramientas SET nombre = %s, marca = %s, modelo = %s, id_categoria = %s WHERE id = %s",
                (nuevo_nombre, nueva_marca, nuevo_modelo, nueva_categoria, id_herramienta),
            )
            conexion.commit()
            return True, "Herramienta actualizada correctamente"
        except IntegrityError:
            conexion.rollback()
            return False, "No se pudo actualizar: la categoría indicada no existe."

    return ejecutar_operacion(operacion)


def actualizar_estado_herramienta(id_herramienta, nuevo_estado):
    """Cambia el estado de una herramienta.

    Si la herramienta está prestada, el estado se cambia desde la devolución,
    y 'Prestado' solo se asigna al registrar un préstamo.
    """
    if nuevo_estado not in ESTADOS_MANUALES.values():
        return False, "Opción de estado inválida."

    def operacion(cursor, conexion):
        # Si tiene un préstamo sin devolver, no se puede cambiar el estado a mano
        cursor.execute(
            "SELECT COUNT(*) FROM prestamos WHERE id_herramienta = %s AND fecha_devolucion IS NULL",
            (id_herramienta,),
        )
        if cursor.fetchone()[0] > 0:
            return False, "La herramienta está prestada. Registrá primero la devolución."

        cursor.execute(
            "UPDATE herramientas SET estado = %s WHERE id = %s",
            (nuevo_estado, id_herramienta),
        )
        conexion.commit()
        # rowcount indica cuántas filas se modificaron (0 = el ID no existe)
        if cursor.rowcount == 0:
            return False, "No se modificó nada: el ID no existe o el estado ya era ese."
        return True, f"Estado actualizado a: {nuevo_estado}"

    return ejecutar_operacion(operacion)


def eliminar_herramienta(id_herramienta, confirmar):
    """Elimina una herramienta. 'confirmar(texto)' pide la confirmación al usuario."""
    def operacion(cursor, conexion):
        cursor.execute("SELECT nombre, estado FROM herramientas WHERE id = %s", (id_herramienta,))
        herramienta = cursor.fetchone()
        if herramienta is None:
            return False, "No existe una herramienta con ese ID."
        if herramienta[1] == "Prestado":
            return False, "No se puede eliminar: la herramienta está prestada actualmente."

        if not confirmar(f"¿Está seguro de eliminar '{herramienta[0]}'?"):
            return False, "Eliminación cancelada"
        try:
            cursor.execute("DELETE FROM herramientas WHERE id = %s", (id_herramienta,))
            conexion.commit()
            return True, "Herramienta eliminada correctamente"
        except IntegrityError:
            # La clave foránea impide borrar herramientas que ya tienen préstamos
            conexion.rollback()
            return False, ("No se puede eliminar: la herramienta tiene préstamos registrados.\n"
                           "Sugerencia: cambiá su estado a 'Dañado' en lugar de borrarla.")

    return ejecutar_operacion(operacion)


# =====================================================================
# 6) PERSONAS: CREATE / UPDATE / DELETE
# =====================================================================
def agregar_persona(nombre, departamento, email):
    """Inserta una nueva persona."""
    nombre = nombre.strip()
    if not nombre:
        return False, "El nombre no puede estar vacío."
    departamento = departamento.strip() or None
    email = email.strip() or None

    def operacion(cursor, conexion):
        cursor.execute(
            "INSERT INTO personas (nombre, departamento, email) VALUES (%s, %s, %s)",
            (nombre, departamento, email),
        )
        conexion.commit()
        return True, f"Persona agregada correctamente (ID {cursor.lastrowid})"

    return ejecutar_operacion(operacion)


def editar_persona(id_persona, nombre, departamento, email):
    """Modifica nombre, departamento o email; un campo vacío conserva el valor actual."""
    def operacion(cursor, conexion):
        cursor.execute(
            "SELECT nombre, departamento, email FROM personas WHERE id = %s",
            (id_persona,),
        )
        actual = cursor.fetchone()
        if actual is None:
            return False, "No existe una persona con ese ID."

        cursor.execute(
            "UPDATE personas SET nombre = %s, departamento = %s, email = %s WHERE id = %s",
            (nombre.strip() or actual[0],
             departamento.strip() or actual[1],
             email.strip() or actual[2],
             id_persona),
        )
        conexion.commit()
        return True, "Persona actualizada correctamente"

    return ejecutar_operacion(operacion)


def eliminar_persona(id_persona, confirmar):
    """Elimina una persona. 'confirmar(texto)' pide la confirmación al usuario."""
    def operacion(cursor, conexion):
        cursor.execute("SELECT nombre FROM personas WHERE id = %s", (id_persona,))
        persona = cursor.fetchone()
        if persona is None:
            return False, "No existe una persona con ese ID."

        # No se puede borrar a alguien que todavía tiene herramientas sin devolver
        cursor.execute(
            "SELECT COUNT(*) FROM prestamos WHERE id_persona = %s AND fecha_devolucion IS NULL",
            (id_persona,),
        )
        if cursor.fetchone()[0] > 0:
            return False, "No se puede eliminar: la persona tiene herramientas sin devolver."

        if not confirmar(f"¿Está seguro de eliminar a '{persona[0]}'?"):
            return False, "Eliminación cancelada"
        try:
            cursor.execute("DELETE FROM personas WHERE id = %s", (id_persona,))
            conexion.commit()
            return True, "Persona eliminada correctamente"
        except IntegrityError:
            # La clave foránea impide borrar personas que figuran en el historial
            conexion.rollback()
            return False, "No se puede eliminar: la persona figura en el historial de préstamos."

    return ejecutar_operacion(operacion)


# =====================================================================
# 7) PRÉSTAMOS Y DEVOLUCIONES (varias operaciones en una transacción)
# =====================================================================
def registrar_prestamo(id_herramienta, id_persona, observaciones):
    """Registra un préstamo y marca la herramienta como 'Prestado'.

    Son DOS operaciones (INSERT en prestamos + UPDATE en herramientas) que
    deben cumplirse juntas: se hace un único commit al final y, si algo
    falla, un rollback deshace todo.
    """
    observaciones = observaciones.strip() or None

    def operacion(cursor, conexion):
        # 1. Validar que la herramienta exista y esté disponible
        cursor.execute("SELECT id, nombre FROM herramientas WHERE estado = 'Disponible' ORDER BY id")
        disponibles = cursor.fetchall()
        if not disponibles:
            return False, "No hay herramientas disponibles"
        if id_herramienta not in [h[0] for h in disponibles]:
            return False, "Esa herramienta no existe o no está disponible."

        # 2. Validar que la persona exista
        cursor.execute("SELECT id, nombre, departamento FROM personas ORDER BY id")
        personas = cursor.fetchall()
        if id_persona not in [p[0] for p in personas]:
            return False, "Esa persona no existe."

        # 3. Insertar el préstamo con la fecha de hoy
        cursor.execute(
            """
            INSERT INTO prestamos (id_herramienta, id_persona, fecha_prestamo, observaciones)
            VALUES (%s, %s, %s, %s)
            """,
            (id_herramienta, id_persona, date.today(), observaciones),
        )

        # 4. Cambiar el estado de la herramienta
        cursor.execute(
            "UPDATE herramientas SET estado = 'Prestado' WHERE id = %s",
            (id_herramienta,),
        )

        conexion.commit()   # se guardan las dos operaciones juntas
        return True, "Préstamo registrado correctamente"

    return ejecutar_operacion(operacion)


def registrar_devolucion(id_prestamo, estado_final, observacion):
    """Registra la devolución de un préstamo y actualiza el estado de la herramienta."""
    observacion = observacion.strip() or None
    if estado_final not in ESTADOS_MANUALES.values():
        return False, "Opción de estado inválida."

    def operacion(cursor, conexion):
        # 1. Buscar el préstamo elegido entre los activos
        cursor.execute(
            """
            SELECT p.id, h.nombre, per.nombre, p.id_herramienta
            FROM prestamos p
            JOIN herramientas h ON p.id_herramienta = h.id
            JOIN personas per   ON p.id_persona = per.id
            WHERE p.fecha_devolucion IS NULL
            ORDER BY p.id
            """
        )
        activos = cursor.fetchall()
        if not activos:
            return False, "No hay préstamos activos"
        elegido = next((p for p in activos if p[0] == id_prestamo), None)
        if elegido is None:
            return False, "Ese préstamo no existe o ya fue devuelto."
        id_herramienta = elegido[3]

        # 2. Poner fecha de devolución (y sumar la observación a las anteriores)
        cursor.execute(
            """
            UPDATE prestamos
            SET fecha_devolucion = %s,
                observaciones = CASE WHEN %s IS NULL THEN observaciones
                                     ELSE CONCAT_WS(' | ', observaciones, %s) END
            WHERE id = %s
            """,
            (date.today(), observacion, observacion, id_prestamo),
        )
        # 3. Actualizar el estado de la herramienta según cómo volvió
        cursor.execute(
            "UPDATE herramientas SET estado = %s WHERE id = %s",
            (estado_final, id_herramienta),
        )

        conexion.commit()
        return True, f"Devolución registrada correctamente (herramienta: {estado_final})"

    return ejecutar_operacion(operacion)


def editar_prestamo(id_prestamo, id_persona, texto_f_prestamo, texto_f_devolucion, texto_obs):
    """Corrige un préstamo: persona, fechas y observaciones (vacío = conservar).

    La fecha de devolución solo se edita si el préstamo ya fue devuelto; para
    devolver un préstamo activo se usa 'Registrar devolución'.
    """
    def operacion(cursor, conexion):
        # Datos actuales del préstamo
        cursor.execute(
            "SELECT id_persona, fecha_prestamo, fecha_devolucion, observaciones FROM prestamos WHERE id = %s",
            (id_prestamo,),
        )
        actual = cursor.fetchone()
        if actual is None:
            return False, "No existe un préstamo con ese ID."
        persona_actual, f_prestamo, f_devolucion, observaciones = actual

        # Persona: se valida que exista
        nueva_persona = persona_actual
        if id_persona is not None:
            cursor.execute("SELECT id FROM personas WHERE id = %s", (id_persona,))
            if cursor.fetchone() is None:
                return False, "Esa persona no existe."
            nueva_persona = id_persona

        # Fechas: se validan formato y orden lógico
        nueva_f_prestamo = validar_fecha(texto_f_prestamo, f_prestamo)
        if nueva_f_prestamo is False:
            return False, "Fecha de préstamo inválida. Usá el formato AAAA-MM-DD (por ejemplo 2026-10-27)."
        nueva_f_devolucion = f_devolucion
        if f_devolucion is not None:
            nueva_f_devolucion = validar_fecha(texto_f_devolucion, f_devolucion)
            if nueva_f_devolucion is False:
                return False, "Fecha de devolución inválida. Usá el formato AAAA-MM-DD (por ejemplo 2026-10-27)."
            if nueva_f_devolucion < nueva_f_prestamo:
                return False, "La devolución no puede ser anterior al préstamo."

        # Observaciones: vacío conserva, "-" borra el texto
        texto_obs = texto_obs.strip()
        if texto_obs == "-":
            observaciones = None
        elif texto_obs != "":
            observaciones = texto_obs

        cursor.execute(
            """
            UPDATE prestamos
            SET id_persona = %s, fecha_prestamo = %s, fecha_devolucion = %s, observaciones = %s
            WHERE id = %s
            """,
            (nueva_persona, nueva_f_prestamo, nueva_f_devolucion, observaciones, id_prestamo),
        )
        conexion.commit()
        return True, "Préstamo actualizado correctamente"

    return ejecutar_operacion(operacion)


def eliminar_prestamo(id_prestamo, confirmar):
    """Elimina un préstamo cargado por error (con confirmación previa).

    Si el préstamo estaba activo, también deja la herramienta como
    'Disponible'. Son dos operaciones, por eso van en una sola transacción.
    """
    def operacion(cursor, conexion):
        cursor.execute(
            "SELECT id_herramienta, fecha_devolucion FROM prestamos WHERE id = %s",
            (id_prestamo,),
        )
        prestamo = cursor.fetchone()
        if prestamo is None:
            return False, "No existe un préstamo con ese ID."

        if not confirmar("¿Está seguro de eliminar este préstamo?"):
            return False, "Eliminación cancelada"

        cursor.execute("DELETE FROM prestamos WHERE id = %s", (id_prestamo,))
        # Si todavía no se había devuelto, la herramienta vuelve a estar disponible
        if prestamo[1] is None:
            cursor.execute(
                "UPDATE herramientas SET estado = 'Disponible' WHERE id = %s AND estado = 'Prestado'",
                (prestamo[0],),
            )
        conexion.commit()
        return True, "Préstamo eliminado correctamente"

    return ejecutar_operacion(operacion)


# =====================================================================
# 8) ESTILO VISUAL
# =====================================================================
# Paleta inspirada en un taller: acero oscuro en la barra lateral, papel gris
# frío para trabajar y amarillo de herramienta como único color de acento.
FONDO = "#E6EAED"
PANEL = "#FFFFFF"
LATERAL = "#1F2B36"
LATERAL_HOVER = "#2C3B49"
ACENTO = "#F2B705"
ACENTO_HOVER = "#D9A300"
TEXTO = "#1B232B"
TEXTO_SUAVE = "#5F6B76"
BORDE = "#CBD3D9"
ENCABEZADO_TABLA = "#DDE3E8"
FILA_PAR = "#F5F7F8"
PELIGRO = "#B3261E"
PELIGRO_HOVER = "#8F1D17"

# Color del texto de la columna Estado en las tablas
COLORES_ESTADO = {
    "Disponible": "#1B7F4B",
    "Prestado": "#B26A00",
    "Mantenimiento": "#1D5FA8",
    "Dañado": "#B3261E",
}

FUENTE_TITULO = "Bahnschrift"   # tipografía industrial de Windows (si no está, se usa la del sistema)
FUENTE_TEXTO = "Segoe UI"


def configurar_estilo_tabla():
    """Aplica el estilo de las tablas (ttk.Treeview) para que combinen con la interfaz."""
    estilo = ttk.Style()
    estilo.theme_use("clam")
    estilo.configure("Panol.Treeview", background=PANEL, fieldbackground=PANEL,
                     foreground=TEXTO, rowheight=32, borderwidth=0,
                     font=(FUENTE_TEXTO, 11))
    estilo.configure("Panol.Treeview.Heading", background=ENCABEZADO_TABLA, foreground=TEXTO,
                     font=(FUENTE_TEXTO, 11, "bold"), relief="flat", padding=(8, 8))
    estilo.map("Panol.Treeview", background=[("selected", "#FBE08A")],
               foreground=[("selected", TEXTO)])
    estilo.map("Panol.Treeview.Heading", background=[("active", "#CFD7DD")])


def boton(master, texto, comando, estilo="neutro", ancho=110):
    """Crea un botón con uno de tres estilos: primario (amarillo), neutro o peligro."""
    colores = {
        "primario": (ACENTO, ACENTO_HOVER, TEXTO, None),
        "neutro": (PANEL, "#EEF1F3", TEXTO, BORDE),
        "peligro": (PANEL, "#FBE9E7", PELIGRO, PELIGRO),
    }
    fondo, hover, texto_color, borde = colores[estilo]
    return ctk.CTkButton(master, text=texto, command=comando, width=ancho, height=36,
                         corner_radius=6, fg_color=fondo, hover_color=hover,
                         text_color=texto_color, border_width=0 if borde is None else 1,
                         border_color=borde or fondo,
                         font=ctk.CTkFont(family=FUENTE_TEXTO, size=13, weight="bold"))


def desplegable(master, valores, ancho=200, comando=None):
    """Lista desplegable de solo selección."""
    combo = ctk.CTkComboBox(master, values=valores, width=ancho, height=36, state="readonly",
                            corner_radius=6, fg_color=PANEL, border_color=BORDE,
                            button_color=BORDE, button_hover_color="#B5BFC7",
                            text_color=TEXTO, dropdown_fg_color=PANEL,
                            dropdown_text_color=TEXTO, dropdown_hover_color="#FBE08A",
                            command=comando)
    if valores:
        combo.set(valores[0])
    return combo


def campo_texto(master, ancho=240, pista=""):
    """Campo de texto de una línea."""
    return ctk.CTkEntry(master, width=ancho, height=36, corner_radius=6, fg_color=PANEL,
                        border_color=BORDE, text_color=TEXTO, placeholder_text=pista,
                        placeholder_text_color="#8A95A0")


def encabezado(master, titulo, subtitulo):
    """Título y bajada de cada pantalla."""
    ctk.CTkLabel(master, text=titulo, anchor="w", text_color=TEXTO,
                 font=ctk.CTkFont(family=FUENTE_TITULO, size=28, weight="bold")).pack(fill="x")
    ctk.CTkLabel(master, text=subtitulo, anchor="w", text_color=TEXTO_SUAVE,
                 font=ctk.CTkFont(family=FUENTE_TEXTO, size=13)).pack(fill="x", pady=(0, 14))


def pedir_confirmacion(texto):
    """Reemplaza al 'conforme (s/n)' de la consola por un cuadro de confirmación."""
    return messagebox.askyesno("Confirmar", texto, icon="warning")


def mostrar_error_bd():
    """Muestra el último error de base de datos."""
    messagebox.showerror("Error de base de datos", ULTIMO_ERROR or "Ocurrió un error inesperado.")


# =====================================================================
# 9) COMPONENTES REUTILIZABLES: TABLA Y FORMULARIO
# =====================================================================
class Tabla(ctk.CTkFrame):
    """Tabla con barra de desplazamiento; devuelve la fila seleccionada."""

    def __init__(self, master, columnas, anchos):
        super().__init__(master, fg_color=PANEL, corner_radius=8, border_width=1, border_color=BORDE)
        self.arbol = ttk.Treeview(self, columns=columnas, show="headings",
                                  style="Panol.Treeview", selectmode="browse")
        for columna, ancho in zip(columnas, anchos):
            self.arbol.heading(columna, text=columna, anchor="w")
            self.arbol.column(columna, width=ancho, minwidth=50, anchor="w")
        barra = ctk.CTkScrollbar(self, command=self.arbol.yview, fg_color=PANEL)
        self.arbol.configure(yscrollcommand=barra.set)
        self.arbol.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=2)
        barra.pack(side="right", fill="y", padx=(0, 2), pady=2)
        for estado, color in COLORES_ESTADO.items():
            self.arbol.tag_configure(estado, foreground=color)
        self.arbol.tag_configure("par", background=FILA_PAR)
        self.arbol.tag_configure("pendiente", foreground="#B26A00")

    def cargar(self, filas, etiqueta=None):
        """Reemplaza el contenido. 'etiqueta(fila)' devuelve el tag de color de la fila."""
        self.arbol.delete(*self.arbol.get_children())
        for posicion, fila in enumerate(filas):
            etiquetas = ["par"] if posicion % 2 else []
            if etiqueta is not None and etiqueta(fila):
                etiquetas.append(etiqueta(fila))
            self.arbol.insert("", "end", values=[texto_o_guion(v) for v in fila], tags=etiquetas)

    def seleccionada(self):
        """Devuelve los valores de la fila seleccionada o None."""
        seleccion = self.arbol.selection()
        if not seleccion:
            messagebox.showinfo("Seleccioná una fila", "Elegí una fila de la tabla para continuar.")
            return None
        return self.arbol.item(seleccion[0])["values"]


class Formulario(ctk.CTkToplevel):
    """Ventana emergente con campos. 'al_guardar(valores)' devuelve (ok, mensaje).

    Tipos de campo: 'texto', 'combo' (lista desplegable) y 'solo_lectura'.
    Si al_guardar devuelve ok la ventana se cierra; si no, se muestra el motivo
    y la ventana queda abierta para corregir.
    """

    def __init__(self, master, titulo, campos, al_guardar, texto_boton="Guardar", ayuda=""):
        super().__init__(master)
        self.al_guardar = al_guardar
        self.widgets = {}
        self.title(titulo)
        self.configure(fg_color=FONDO)
        self.resizable(False, False)

        ctk.CTkLabel(self, text=titulo, anchor="w", text_color=TEXTO,
                     font=ctk.CTkFont(family=FUENTE_TITULO, size=22, weight="bold")
                     ).pack(fill="x", padx=26, pady=(22, 2))
        if ayuda:
            ctk.CTkLabel(self, text=ayuda, anchor="w", justify="left", text_color=TEXTO_SUAVE,
                         wraplength=380, font=ctk.CTkFont(family=FUENTE_TEXTO, size=12)
                         ).pack(fill="x", padx=26)

        marco = ctk.CTkFrame(self, fg_color="transparent")
        marco.pack(fill="x", padx=26, pady=(8, 4))
        for campo in campos:
            ctk.CTkLabel(marco, text=campo["etiqueta"], anchor="w", text_color=TEXTO,
                         font=ctk.CTkFont(family=FUENTE_TEXTO, size=12, weight="bold")
                         ).pack(fill="x", pady=(10, 2))
            tipo = campo.get("tipo", "texto")
            if tipo == "combo":
                widget = desplegable(marco, campo["opciones"], ancho=380)
                if campo.get("valor") in campo["opciones"]:
                    widget.set(campo["valor"])
            else:
                widget = campo_texto(marco, ancho=380, pista=campo.get("pista", ""))
                if campo.get("valor"):
                    widget.insert(0, campo["valor"])
                if tipo == "solo_lectura":
                    widget.configure(state="disabled", fg_color="#EEF1F3")
            widget.pack(fill="x")
            self.widgets[campo["clave"]] = widget

        botones = ctk.CTkFrame(self, fg_color="transparent")
        botones.pack(fill="x", padx=26, pady=(20, 22))
        boton(botones, texto_boton, self.guardar, "primario", 140).pack(side="right")
        boton(botones, "Cancelar", self.destroy, "neutro", 110).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda evento: self.guardar())
        self.bind("<Escape>", lambda evento: self.destroy())

        # Centrar sobre la ventana principal y bloquear la ventana de atrás
        ventana = master.winfo_toplevel()
        self.update_idletasks()
        x = ventana.winfo_rootx() + (ventana.winfo_width() - self.winfo_reqwidth()) // 2
        y = ventana.winfo_rooty() + (ventana.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.transient(ventana)
        self.after(150, self._tomar_foco)

    def _tomar_foco(self):
        """grab_set se llama con un pequeño retraso porque en Windows falla si la ventana aún no se dibujó."""
        self.grab_set()
        self.focus_force()

    def guardar(self):
        valores = {clave: widget.get() for clave, widget in self.widgets.items()}
        ok, mensaje = self.al_guardar(valores)
        if ok:
            self.destroy()
        else:
            messagebox.showerror("No se pudo guardar", mensaje, parent=self)


# =====================================================================
# 10) PANTALLAS
# =====================================================================
class Pagina(ctk.CTkFrame):
    """Base de todas las pantallas."""

    def __init__(self, app):
        super().__init__(app.contenido, fg_color="transparent")
        self.app = app

    def al_mostrar(self):
        self.recargar()

    def recargar(self):
        pass

    def terminar(self, resultado):
        """Procesa el (ok, mensaje) de una operación: avisa y refresca la tabla."""
        ok, mensaje = resultado
        if ok:
            self.app.notificar(mensaje)
            self.recargar()
        return ok, mensaje

    def barra_herramientas(self):
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", pady=(0, 10))
        return barra


class PaginaInicio(Pagina):
    """Resumen general del pañol."""

    def __init__(self, app):
        super().__init__(app)
        encabezado(self, "Inicio", "Estado actual del pañol")

        resumen = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=8, border_width=1, border_color=BORDE)
        resumen.pack(fill="x", pady=(0, 16))
        self.cifras = {}
        for columna, (clave, texto) in enumerate([
            ("total", "Herramientas"),
            ("disponibles", "Disponibles"),
            ("prestadas", "Prestadas ahora"),
            ("fuera", "En mantenimiento o dañadas"),
        ]):
            resumen.grid_columnconfigure(columna, weight=1, uniform="cifras")
            caja = ctk.CTkFrame(resumen, fg_color="transparent")
            caja.grid(row=0, column=columna, sticky="nsew", pady=16)
            cifra = ctk.CTkLabel(caja, text="-", text_color=TEXTO,
                                 font=ctk.CTkFont(family=FUENTE_TITULO, size=34, weight="bold"))
            cifra.pack()
            ctk.CTkLabel(caja, text=texto, text_color=TEXTO_SUAVE,
                         font=ctk.CTkFont(family=FUENTE_TEXTO, size=12)).pack()
            self.cifras[clave] = cifra
            if columna:
                ctk.CTkFrame(resumen, width=1, fg_color=BORDE).grid(row=0, column=columna,
                                                                    sticky="nsw", pady=14)

        ctk.CTkLabel(self, text="Préstamos activos", anchor="w", text_color=TEXTO,
                     font=ctk.CTkFont(family=FUENTE_TITULO, size=18, weight="bold")
                     ).pack(fill="x", pady=(0, 8))
        self.tabla = Tabla(self, ("ID", "Herramienta", "Persona", "Préstamo", "Observaciones"),
                           (50, 230, 200, 110, 380))
        self.tabla.pack(fill="both", expand=True)

    def recargar(self):
        conteo = consultar("SELECT estado, COUNT(*) FROM herramientas GROUP BY estado")
        activos = obtener_prestamos(solo_activos=True)
        if conteo is None or activos is None:
            mostrar_error_bd()
            return
        por_estado = dict(conteo)
        self.cifras["total"].configure(text=str(sum(por_estado.values())))
        self.cifras["disponibles"].configure(text=str(por_estado.get("Disponible", 0)))
        self.cifras["prestadas"].configure(text=str(len(activos)))
        self.cifras["fuera"].configure(
            text=str(por_estado.get("Mantenimiento", 0) + por_estado.get("Dañado", 0)))
        # Se omite la columna de devolución (siempre pendiente en los activos)
        self.tabla.cargar([(p[0], p[1], p[2], p[3], p[5]) for p in activos])


class PaginaHerramientas(Pagina):
    """Ver/buscar, agregar, editar, cambiar estado y eliminar herramientas."""

    def __init__(self, app):
        super().__init__(app)
        encabezado(self, "Herramientas", "Inventario del pañol: buscá, filtrá y administrá cada herramienta")
        self.categorias = []

        barra = self.barra_herramientas()
        self.buscar = campo_texto(barra, 230, "Buscar por nombre")
        self.buscar.pack(side="left")
        self.buscar.bind("<KeyRelease>", lambda evento: app.diferir(self.recargar))
        self.filtro_estado = desplegable(barra, ["Todos los estados"] + list(ESTADOS.values()),
                                         170, lambda valor: self.recargar())
        self.filtro_estado.pack(side="left", padx=(8, 0))
        self.filtro_categoria = desplegable(barra, ["Todas las categorías"], 210,
                                            lambda valor: self.recargar())
        self.filtro_categoria.pack(side="left", padx=(8, 0))

        boton(barra, "Eliminar", self.eliminar, "peligro", 90).pack(side="right")
        boton(barra, "Cambiar estado", self.cambiar_estado, "neutro", 130).pack(side="right", padx=(0, 8))
        boton(barra, "Editar", self.editar, "neutro", 90).pack(side="right", padx=(0, 8))
        boton(barra, "Agregar herramienta", self.agregar, "primario", 170).pack(side="right", padx=(0, 8))

        self.tabla = Tabla(self, ("ID", "Nombre", "Marca", "Modelo", "Categoría", "Estado"),
                           (50, 240, 130, 140, 200, 130))
        self.tabla.pack(fill="both", expand=True)
        self.total = ctk.CTkLabel(self, text="", anchor="w", text_color=TEXTO_SUAVE)
        self.total.pack(fill="x", pady=(6, 0))

    def al_mostrar(self):
        # Se refresca la lista de categorías del filtro (conservando la elegida)
        filas = consultar("SELECT id, nombre FROM categorias ORDER BY id")
        if filas is not None:
            self.categorias = [f"{f[0]} - {f[1]}" for f in filas]
            elegida = self.filtro_categoria.get()
            self.filtro_categoria.configure(values=["Todas las categorías"] + self.categorias)
            self.filtro_categoria.set(elegida if elegida in self.categorias else "Todas las categorías")
        self.recargar()

    def recargar(self):
        estado = self.filtro_estado.get()
        filas = buscar_herramientas(
            self.buscar.get().strip(),
            estado if estado in ESTADOS.values() else "",
            id_de(self.filtro_categoria.get()),
        )
        if filas is None:
            mostrar_error_bd()
            return
        self.tabla.cargar(filas, etiqueta=lambda fila: fila[5])
        self.total.configure(text=f"Total: {len(filas)} herramienta(s)")

    def agregar(self):
        categorias = consultar("SELECT id, nombre FROM categorias ORDER BY id")
        if categorias is None:
            mostrar_error_bd()
            return
        if not categorias:
            messagebox.showwarning("Sin categorías", "Primero tiene que existir al menos una categoría.")
            return
        opciones = [f"{c[0]} - {c[1]}" for c in categorias]
        Formulario(self, "Agregar herramienta", [
            {"clave": "nombre", "etiqueta": "Nombre"},
            {"clave": "marca", "etiqueta": "Marca (opcional)"},
            {"clave": "modelo", "etiqueta": "Modelo (opcional)"},
            {"clave": "categoria", "etiqueta": "Categoría", "tipo": "combo", "opciones": opciones},
        ], lambda v: self.terminar(agregar_herramienta(
            v["nombre"], v["marca"], v["modelo"], id_de(v["categoria"]))),
            texto_boton="Agregar", ayuda="La herramienta se crea como Disponible, con la fecha de hoy.")

    def editar(self):
        fila = self.tabla.seleccionada()
        if fila is None:
            return
        id_herramienta = int(fila[0])
        datos = consultar("SELECT nombre, marca, modelo, id_categoria FROM herramientas WHERE id = %s",
                          (id_herramienta,))
        categorias = consultar("SELECT id, nombre FROM categorias ORDER BY id")
        if datos is None or categorias is None:
            mostrar_error_bd()
            return
        if not datos:
            messagebox.showerror("No existe", "No existe una herramienta con ese ID.")
            return
        nombre, marca, modelo, id_categoria = datos[0]
        opciones = [f"{c[0]} - {c[1]}" for c in categorias]
        actual = next((o for o in opciones if id_de(o) == id_categoria), None)
        if actual is None:                      # herramienta sin categoría: se conserva
            opciones.insert(0, "(sin categoría)")
            actual = opciones[0]
        Formulario(self, f"Editar herramienta #{id_herramienta}", [
            {"clave": "nombre", "etiqueta": "Nombre", "valor": nombre},
            {"clave": "marca", "etiqueta": "Marca", "valor": marca or ""},
            {"clave": "modelo", "etiqueta": "Modelo", "valor": modelo or ""},
            {"clave": "categoria", "etiqueta": "Categoría", "tipo": "combo",
             "opciones": opciones, "valor": actual},
        ], lambda v: self.terminar(editar_herramienta(
            id_herramienta, v["nombre"], v["marca"], v["modelo"], id_de(v["categoria"]))),
            ayuda="Si dejás un campo vacío se conserva el valor actual.")

    def cambiar_estado(self):
        fila = self.tabla.seleccionada()
        if fila is None:
            return
        id_herramienta = int(fila[0])
        opciones = list(ESTADOS_MANUALES.values())
        Formulario(self, "Cambiar estado", [
            {"clave": "herramienta", "etiqueta": "Herramienta", "tipo": "solo_lectura", "valor": str(fila[1])},
            {"clave": "estado", "etiqueta": "Nuevo estado", "tipo": "combo",
             "opciones": opciones, "valor": str(fila[5])},
        ], lambda v: self.terminar(actualizar_estado_herramienta(id_herramienta, v["estado"])),
            ayuda="'Prestado' se asigna solo al registrar un préstamo.")

    def eliminar(self):
        fila = self.tabla.seleccionada()
        if fila is None:
            return
        resultado = eliminar_herramienta(int(fila[0]), pedir_confirmacion)
        if resultado[0]:
            self.terminar(resultado)
        elif resultado[1] == "Eliminación cancelada":
            self.app.notificar(resultado[1], ok=False)
        else:
            messagebox.showerror("No se pudo eliminar", resultado[1])


class PaginaPersonas(Pagina):
    """Ver/buscar, agregar, editar y eliminar personas."""

    def __init__(self, app):
        super().__init__(app)
        encabezado(self, "Personas", "Quiénes pueden retirar herramientas del pañol")

        barra = self.barra_herramientas()
        self.buscar = campo_texto(barra, 300, "Buscar por nombre o departamento")
        self.buscar.pack(side="left")
        self.buscar.bind("<KeyRelease>", lambda evento: app.diferir(self.recargar))
        boton(barra, "Eliminar", self.eliminar, "peligro", 90).pack(side="right")
        boton(barra, "Editar", self.editar, "neutro", 90).pack(side="right", padx=(0, 8))
        boton(barra, "Agregar persona", self.agregar, "primario", 150).pack(side="right", padx=(0, 8))

        self.tabla = Tabla(self, ("ID", "Nombre", "Departamento", "Email"), (50, 250, 200, 320))
        self.tabla.pack(fill="both", expand=True)
        self.total = ctk.CTkLabel(self, text="", anchor="w", text_color=TEXTO_SUAVE)
        self.total.pack(fill="x", pady=(6, 0))

    def recargar(self):
        personas = buscar_personas(self.buscar.get().strip())
        if personas is None:
            mostrar_error_bd()
            return
        self.tabla.cargar(personas)
        self.total.configure(text=f"Total: {len(personas)} persona(s)")

    def agregar(self):
        Formulario(self, "Agregar persona", [
            {"clave": "nombre", "etiqueta": "Nombre completo"},
            {"clave": "departamento", "etiqueta": "Departamento (opcional)"},
            {"clave": "email", "etiqueta": "Email (opcional)"},
        ], lambda v: self.terminar(agregar_persona(v["nombre"], v["departamento"], v["email"])),
            texto_boton="Agregar")

    def editar(self):
        fila = self.tabla.seleccionada()
        if fila is None:
            return
        id_persona = int(fila[0])
        datos = consultar("SELECT nombre, departamento, email FROM personas WHERE id = %s", (id_persona,))
        if datos is None:
            mostrar_error_bd()
            return
        if not datos:
            messagebox.showerror("No existe", "No existe una persona con ese ID.")
            return
        nombre, departamento, email = datos[0]
        Formulario(self, f"Editar persona #{id_persona}", [
            {"clave": "nombre", "etiqueta": "Nombre", "valor": nombre},
            {"clave": "departamento", "etiqueta": "Departamento", "valor": departamento or ""},
            {"clave": "email", "etiqueta": "Email", "valor": email or ""},
        ], lambda v: self.terminar(editar_persona(
            id_persona, v["nombre"], v["departamento"], v["email"])),
            ayuda="Si dejás un campo vacío se conserva el valor actual.")

    def eliminar(self):
        fila = self.tabla.seleccionada()
        if fila is None:
            return
        resultado = eliminar_persona(int(fila[0]), pedir_confirmacion)
        if resultado[0]:
            self.terminar(resultado)
        elif resultado[1] == "Eliminación cancelada":
            self.app.notificar(resultado[1], ok=False)
        else:
            messagebox.showerror("No se pudo eliminar", resultado[1])


class PaginaPrestamos(Pagina):
    """Préstamos activos e historial; registrar, devolver, editar y eliminar."""

    def __init__(self, app):
        super().__init__(app)
        encabezado(self, "Préstamos y devoluciones", "Quién tiene qué, desde cuándo y en qué condición volvió")

        barra = self.barra_herramientas()
        self.modo = ctk.CTkSegmentedButton(
            barra, values=["Activos", "Historial"], command=lambda valor: self.recargar(),
            fg_color=BORDE, selected_color=ACENTO, selected_hover_color=ACENTO_HOVER,
            unselected_color=BORDE, unselected_hover_color="#B5BFC7", text_color=TEXTO,
            height=36, font=ctk.CTkFont(family=FUENTE_TEXTO, size=13, weight="bold"))
        self.modo.set("Activos")
        self.modo.pack(side="left")
        self.filtro_persona = desplegable(barra, ["Todas las personas"], 200, lambda valor: self.recargar())
        self.filtro_persona.pack(side="left", padx=(8, 0))
        self.filtro_herramienta = desplegable(barra, ["Todas las herramientas"], 210,
                                              lambda valor: self.recargar())
        self.filtro_herramienta.pack(side="left", padx=(8, 0))

        acciones = self.barra_herramientas()
        boton(acciones, "Registrar préstamo", self.registrar, "primario", 170).pack(side="left")
        boton(acciones, "Registrar devolución", self.devolver, "neutro", 180).pack(side="left", padx=(8, 0))
        boton(acciones, "Editar", self.editar, "neutro", 90).pack(side="left", padx=(8, 0))
        boton(acciones, "Eliminar", self.eliminar, "peligro", 90).pack(side="left", padx=(8, 0))

        self.tabla = Tabla(self, ("ID", "Herramienta", "Persona", "Préstamo", "Devolución", "Observaciones"),
                           (50, 200, 170, 100, 100, 300))
        self.tabla.pack(fill="both", expand=True)
        self.total = ctk.CTkLabel(self, text="", anchor="w", text_color=TEXTO_SUAVE)
        self.total.pack(fill="x", pady=(6, 0))

    def al_mostrar(self):
        # Se refrescan las listas de los filtros (conservando lo elegido)
        personas = consultar("SELECT id, nombre FROM personas ORDER BY id")
        herramientas = consultar("SELECT id, nombre FROM herramientas ORDER BY id")
        if personas is not None and herramientas is not None:
            self._actualizar_filtro(self.filtro_persona, "Todas las personas",
                                    [f"{p[0]} - {p[1]}" for p in personas])
            self._actualizar_filtro(self.filtro_herramienta, "Todas las herramientas",
                                    [f"{h[0]} - {h[1]}" for h in herramientas])
        self.recargar()

    @staticmethod
    def _actualizar_filtro(combo, texto_todos, opciones):
        elegida = combo.get()
        combo.configure(values=[texto_todos] + opciones)
        combo.set(elegida if elegida in opciones else texto_todos)

    def recargar(self):
        prestamos = obtener_prestamos(
            solo_activos=self.modo.get() == "Activos",
            id_persona=id_de(self.filtro_persona.get()),
            id_herramienta=id_de(self.filtro_herramienta.get()),
        )
        if prestamos is None:
            mostrar_error_bd()
            return
        # fecha_devolucion NULL = todavía no se devolvió
        filas = [(p[0], p[1], p[2], p[3], "Pendiente" if p[4] is None else p[4], p[5]) for p in prestamos]
        self.tabla.cargar(filas, etiqueta=lambda fila: "pendiente" if fila[4] == "Pendiente" else None)
        self.total.configure(text=f"Total: {len(filas)} préstamo(s)")

    def registrar(self):
        herramientas = consultar("SELECT id, nombre FROM herramientas WHERE estado = 'Disponible' ORDER BY id")
        personas = consultar("SELECT id, nombre, departamento FROM personas ORDER BY id")
        if herramientas is None or personas is None:
            mostrar_error_bd()
            return
        if not herramientas:
            messagebox.showwarning("Sin herramientas", "No hay herramientas disponibles.")
            return
        if not personas:
            messagebox.showwarning("Sin personas", "Primero tenés que cargar al menos una persona.")
            return
        Formulario(self, "Registrar préstamo", [
            {"clave": "herramienta", "etiqueta": "Herramienta disponible", "tipo": "combo",
             "opciones": [f"{h[0]} - {h[1]}" for h in herramientas]},
            {"clave": "persona", "etiqueta": "Persona", "tipo": "combo",
             "opciones": [f"{p[0]} - {p[1]} ({texto_o_guion(p[2])})" for p in personas]},
            {"clave": "observaciones", "etiqueta": "Observaciones (opcional)"},
        ], lambda v: self.terminar(registrar_prestamo(
            id_de(v["herramienta"]), id_de(v["persona"]), v["observaciones"])),
            texto_boton="Registrar", ayuda="El préstamo se registra con la fecha de hoy.")

    def devolver(self):
        activos = consultar(
            """
            SELECT p.id, h.nombre, per.nombre
            FROM prestamos p
            JOIN herramientas h ON p.id_herramienta = h.id
            JOIN personas per   ON p.id_persona = per.id
            WHERE p.fecha_devolucion IS NULL
            ORDER BY p.id
            """
        )
        if activos is None:
            mostrar_error_bd()
            return
        if not activos:
            messagebox.showinfo("Sin préstamos activos", "No hay préstamos activos.")
            return
        opciones = [f"{a[0]} - {a[1]} - {a[2]}" for a in activos]
        # Si hay una fila activa seleccionada, ya viene elegida
        seleccion = self.tabla.arbol.selection()
        elegido = None
        if seleccion:
            id_sel = int(self.tabla.arbol.item(seleccion[0])["values"][0])
            elegido = next((o for o in opciones if id_de(o) == id_sel), None)
        Formulario(self, "Registrar devolución", [
            {"clave": "prestamo", "etiqueta": "Préstamo a devolver", "tipo": "combo",
             "opciones": opciones, "valor": elegido},
            {"clave": "estado", "etiqueta": "¿En qué estado vuelve la herramienta?", "tipo": "combo",
             "opciones": list(ESTADOS_MANUALES.values()), "valor": "Disponible"},
            {"clave": "observacion", "etiqueta": "Observaciones de la devolución (opcional)"},
        ], lambda v: self.terminar(registrar_devolucion(
            id_de(v["prestamo"]), v["estado"], v["observacion"])),
            texto_boton="Devolver", ayuda="La devolución se registra con la fecha de hoy.")

    def editar(self):
        fila = self.tabla.seleccionada()
        if fila is None:
            return
        id_prestamo = int(fila[0])
        datos = consultar(
            "SELECT id_persona, fecha_prestamo, fecha_devolucion, observaciones FROM prestamos WHERE id = %s",
            (id_prestamo,),
        )
        personas = consultar("SELECT id, nombre, departamento FROM personas ORDER BY id")
        if datos is None or personas is None:
            mostrar_error_bd()
            return
        if not datos:
            messagebox.showerror("No existe", "No existe un préstamo con ese ID.")
            return
        id_persona, f_prestamo, f_devolucion, observaciones = datos[0]
        opciones = [f"{p[0]} - {p[1]} ({texto_o_guion(p[2])})" for p in personas]
        persona_actual = next((o for o in opciones if id_de(o) == id_persona), None)

        if f_devolucion is not None:
            campo_devolucion = {"clave": "f_devolucion", "etiqueta": "Fecha de devolución (AAAA-MM-DD)",
                                "valor": str(f_devolucion)}
        else:
            campo_devolucion = {"clave": "f_devolucion", "etiqueta": "Fecha de devolución",
                                "tipo": "solo_lectura", "valor": "Pendiente: usá 'Registrar devolución'"}
        Formulario(self, f"Editar préstamo #{id_prestamo}", [
            {"clave": "persona", "etiqueta": "Persona", "tipo": "combo",
             "opciones": opciones, "valor": persona_actual},
            {"clave": "f_prestamo", "etiqueta": "Fecha de préstamo (AAAA-MM-DD)", "valor": str(f_prestamo)},
            campo_devolucion,
            {"clave": "observaciones", "etiqueta": "Observaciones", "valor": observaciones or ""},
        ], lambda v: self.terminar(editar_prestamo(
            id_prestamo, id_de(v["persona"]), v["f_prestamo"], v["f_devolucion"], v["observaciones"])),
            ayuda="Un campo vacío conserva el valor actual. En observaciones, escribí '-' para borrar el texto.")

    def eliminar(self):
        fila = self.tabla.seleccionada()
        if fila is None:
            return
        resultado = eliminar_prestamo(int(fila[0]), pedir_confirmacion)
        if resultado[0]:
            self.terminar(resultado)
        elif resultado[1] == "Eliminación cancelada":
            self.app.notificar(resultado[1], ok=False)
        else:
            messagebox.showerror("No se pudo eliminar", resultado[1])


class PaginaCategorias(Pagina):
    """Consulta de categorías con su cantidad de herramientas."""

    def __init__(self, app):
        super().__init__(app)
        encabezado(self, "Categorías", "Cómo se agrupan las herramientas del pañol")
        self.tabla = Tabla(self, ("ID", "Nombre", "Herramientas"), (60, 360, 140))
        self.tabla.pack(fill="both", expand=True)

    def recargar(self):
        categorias = obtener_categorias()
        if categorias is None:
            mostrar_error_bd()
            return
        self.tabla.cargar(categorias)


# =====================================================================
# 11) VENTANA PRINCIPAL
# =====================================================================
class App(ctk.CTk):
    """Ventana principal: barra lateral, contenido y aviso inferior."""

    def __init__(self):
        super().__init__()
        self.title("Sistema de Gestión de Pañol")
        self.geometry("1200x740")
        self.minsize(1020, 640)
        self.configure(fg_color=FONDO)
        configurar_estilo_tabla()

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ----- Barra lateral -----
        lateral = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color=LATERAL)
        lateral.grid(row=0, column=0, rowspan=2, sticky="nsew")
        lateral.grid_propagate(False)
        ctk.CTkLabel(lateral, text="PAÑOL", anchor="w", text_color=ACENTO,
                     font=ctk.CTkFont(family=FUENTE_TITULO, size=30, weight="bold")
                     ).pack(fill="x", padx=24, pady=(28, 0))
        ctk.CTkLabel(lateral, text="Gestión de herramientas", anchor="w", text_color="#9AA8B5",
                     font=ctk.CTkFont(family=FUENTE_TEXTO, size=12)
                     ).pack(fill="x", padx=24, pady=(0, 28))

        self.botones_menu = {}
        for clave, texto in [("inicio", "Inicio"), ("herramientas", "Herramientas"),
                             ("personas", "Personas"), ("prestamos", "Préstamos"),
                             ("categorias", "Categorías")]:
            boton_menu = ctk.CTkButton(
                lateral, text=texto, anchor="w", height=42, corner_radius=6,
                fg_color="transparent", hover_color=LATERAL_HOVER, text_color="#E6ECF1",
                font=ctk.CTkFont(family=FUENTE_TEXTO, size=14, weight="bold"),
                command=lambda c=clave: self.mostrar(c))
            boton_menu.pack(fill="x", padx=14, pady=2)
            self.botones_menu[clave] = boton_menu
        ctk.CTkButton(lateral, text="Salir", anchor="w", height=42, corner_radius=6,
                      fg_color="transparent", hover_color="#5A2A27", text_color="#F3B8B3",
                      font=ctk.CTkFont(family=FUENTE_TEXTO, size=14, weight="bold"),
                      command=self.destroy).pack(side="bottom", fill="x", padx=14, pady=18)

        # ----- Contenido y aviso inferior -----
        self.contenido = ctk.CTkFrame(self, fg_color="transparent")
        self.contenido.grid(row=0, column=1, sticky="nsew", padx=28, pady=(24, 6))
        self.aviso = ctk.CTkLabel(self, text="", anchor="w", height=36, corner_radius=6,
                                  font=ctk.CTkFont(family=FUENTE_TEXTO, size=13, weight="bold"))
        self.aviso.grid(row=1, column=1, sticky="ew", padx=28, pady=(0, 16))

        self.paginas = {}
        self.actual = None
        self._temporizador_aviso = None
        self._temporizador_busqueda = None
        self.after(100, self.iniciar)

    def iniciar(self):
        """Pide la contraseña si falta, prueba la conexión y recién ahí arma las pantallas."""
        if not CONFIG_BD["password"]:
            clave = simpledialog.askstring("Conexión a MySQL", "Contraseña de MySQL (vacío si no tiene):",
                                           show="*", parent=self)
            CONFIG_BD["password"] = clave or ""

        # Prueba de conexión inicial: si falla, no tiene sentido mostrar el programa
        try:
            conectar_bd().close()
        except Error as error:
            messagebox.showerror(
                "No se pudo conectar",
                f"No se pudo conectar a la base de datos.\n\n{error}\n\n"
                "Verificá los datos de CONFIG_BD y que el servidor MySQL esté encendido.")
            self.destroy()
            return

        self.paginas = {
            "inicio": PaginaInicio(self),
            "herramientas": PaginaHerramientas(self),
            "personas": PaginaPersonas(self),
            "prestamos": PaginaPrestamos(self),
            "categorias": PaginaCategorias(self),
        }
        self.mostrar("inicio")
        self.notificar("Conexión exitosa a la base de datos")

    def mostrar(self, clave):
        """Cambia de pantalla y resalta el botón del menú activo."""
        if self.actual is not None:
            self.actual.pack_forget()
        self.actual = self.paginas[clave]
        self.actual.pack(fill="both", expand=True)
        self.actual.al_mostrar()
        for nombre, boton_menu in self.botones_menu.items():
            activo = nombre == clave
            boton_menu.configure(fg_color=ACENTO if activo else "transparent",
                                 hover_color=ACENTO_HOVER if activo else LATERAL_HOVER,
                                 text_color=TEXTO if activo else "#E6ECF1")

    def notificar(self, mensaje, ok=True):
        """Muestra un aviso breve abajo (verde si salió bien, gris si se canceló)."""
        if self._temporizador_aviso is not None:
            self.after_cancel(self._temporizador_aviso)
        self.aviso.configure(text=f"   {mensaje}", fg_color="#D5EBDD" if ok else "#DDE3E8",
                             text_color="#14532D" if ok else TEXTO)
        self._temporizador_aviso = self.after(4000, lambda: self.aviso.configure(text="", fg_color="transparent"))

    def diferir(self, funcion):
        """Espera un instante tras la última tecla antes de buscar (evita una consulta por letra)."""
        if self._temporizador_busqueda is not None:
            self.after_cancel(self._temporizador_busqueda)
        self._temporizador_busqueda = self.after(300, funcion)


# =====================================================================
# 12) PROGRAMA PRINCIPAL
# =====================================================================
def main():
    """Crea la ventana y deja la interfaz funcionando hasta que se cierre."""
    ctk.set_appearance_mode("light")
    App().mainloop()


# Este if hace que main() se ejecute solo al correr el archivo directamente
if __name__ == "__main__":
    main()