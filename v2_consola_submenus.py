"""
Laboratorio de Aplicaciones II - 6° G
TP N° 15: Operaciones CRUD con bases de datos en Python
Temática: Sistema de gestión de un pañol de herramientas

El programa se conecta a MySQL con mysql-connector-python y ofrece un menú
por consola organizado en 4 secciones:

  1. VER / BUSCAR              -> consultas (R) de herramientas, personas,
                                  préstamos, historial y categorías
  2. HERRAMIENTAS              -> agregar (C), editar y cambiar estado (U), eliminar (D)
  3. USUARIOS                  -> agregar (C), editar (U), eliminar (D)
  4. PRÉSTAMOS Y DEVOLUCIONES  -> registrar (C), devolver y editar (U), eliminar (D)

Antes de ejecutarlo: correr crear_bd.sql en el servidor y cargar los datos
de conexión en CONFIG_BD (o en las variables de entorno BD_HOST, BD_PORT,
BD_NAME, BD_USER y BD_PASSWORD, así no queda la contraseña escrita en el código).
Si no hay contraseña en el entorno, el programa la pide al iniciar.
"""

# =====================================================================
# 1) IMPORTACIÓN DE LIBRERÍAS
# =====================================================================
import os                        # para leer variables de entorno
from datetime import date, datetime   # fechas (hoy y validación de fechas escritas)
from getpass import getpass      # pedir la contraseña sin mostrarla en pantalla

import mysql.connector           # conector oficial entre Python y MySQL
from mysql.connector import Error, IntegrityError  # excepciones del conector

# =====================================================================
# 2) CONFIGURACIÓN DE LA BASE DE DATOS
# =====================================================================
# Si existe la variable de entorno se usa; si no, se toma el valor por defecto.
# La contraseña NO se escribe en el código: viene del entorno o se pide al iniciar.
CONFIG_BD = {
    "host": os.getenv("BD_HOST", "localhost"),
    "port": int(os.getenv("BD_PORT", "3306")),
    "database": os.getenv("BD_NAME", "panol_herramientas"),
    "user": os.getenv("BD_USER", "root"),
    "password": os.getenv("BD_PASSWORD", "Patricio@360"), #Contraseña de la BD
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


# =====================================================================
# 3) FUNCIONES AUXILIARES (conexión, entrada de datos y consultas)
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

    Abre la conexión, ejecuta, y cierra siempre (finally). Si hay un error
    de base de datos lo muestra y devuelve None.
    """
    conexion = None
    cursor = None
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute(sql, parametros)
        return cursor.fetchall()
    except Error as error:
        print(f"❌ Error de base de datos: {error}")
        return None
    finally:
        cerrar_todo(cursor, conexion)


def pedir_entero(mensaje):
    """Pide un número entero por consola; devuelve None si no es válido."""
    texto = input(mensaje).strip()
    if texto.isdigit():
        return int(texto)
    print("❌ Tenés que ingresar un número entero positivo.")
    return None


def pedir_texto_obligatorio(mensaje):
    """Pide un texto y lo repite hasta que el usuario no lo deje vacío."""
    while True:
        texto = input(mensaje).strip()
        if texto:
            return texto
        print("❌ Este campo no puede estar vacío.")


def pedir_fecha(mensaje, actual):
    """Pide una fecha en formato AAAA-MM-DD.

    - Enter (vacío)  -> devuelve 'actual' (se conserva el valor).
    - Fecha válida   -> devuelve un objeto date.
    - Fecha inválida -> avisa y devuelve False.
    """
    texto = input(mensaje).strip()
    if texto == "":
        return actual
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError:
        print("❌ Fecha inválida. Usá el formato AAAA-MM-DD (por ejemplo 2026-10-27).")
        return False


def texto_o_guion(valor):
    """Para mostrar en tablas: si el valor es NULL (None) muestra un guion."""
    return "-" if valor is None else str(valor)


def recortar(valor, largo):
    """Recorta un texto largo para que no desarme las columnas de la tabla."""
    texto = texto_o_guion(valor)
    return texto if len(texto) <= largo else texto[: largo - 3] + "..."


# =====================================================================
# 4) MENÚS (principal y submenús)
# =====================================================================
def ejecutar_submenu(titulo, opciones):
    """Muestra un submenú y ejecuta la opción elegida hasta que se vuelva atrás.

    'opciones' es una lista de tuplas (texto, función). Así agregar una
    opción nueva es solo sumar una tupla a la lista.
    """
    while True:
        print("\n" + "=" * 46)
        print(f"  {titulo}")
        print("=" * 46)
        for numero, (texto, _) in enumerate(opciones, start=1):
            print(f"{numero}. {texto}")
        print("0. Volver al menú principal")
        print("=" * 46)

        eleccion = input("Seleccione una opción: ").strip()
        if eleccion == "0":
            return
        if eleccion.isdigit() and 1 <= int(eleccion) <= len(opciones):
            opciones[int(eleccion) - 1][1]()          # ejecuta la función elegida
            input("\nPresione Enter para continuar...")
        else:
            print("❌ Opción inválida, intente nuevamente")


def menu_ver_buscar():
    """Sección 1: todas las consultas (solo lectura)."""
    ejecutar_submenu("1. VER / BUSCAR", [
        ("Herramientas (todas, por estado, nombre o categoría)", listar_herramientas),
        ("Personas (todas o buscar por nombre/departamento)", ver_personas),
        ("Préstamos activos", ver_prestamos_activos),
        ("Historial de préstamos (todos, por persona o herramienta)", ver_historial_prestamos),
        ("Categorías", ver_categorias),
    ])


def menu_herramientas():
    """Sección 2: altas, modificaciones y bajas de herramientas."""
    ejecutar_submenu("2. HERRAMIENTAS", [
        ("Agregar nueva herramienta", agregar_herramienta),
        ("Editar nombre, marca, modelo o categoría", editar_herramienta),
        ("Cambiar estado (Disponible / Mantenimiento / Dañado)", actualizar_estado_herramienta),
        ("Eliminar herramienta", eliminar_herramienta),
    ])


def menu_usuarios():
    """Sección 3: altas, modificaciones y bajas de personas."""
    ejecutar_submenu("3. USUARIOS", [
        ("Agregar nueva persona", agregar_persona),
        ("Editar datos de una persona", editar_persona),
        ("Eliminar persona", eliminar_persona),
    ])


def menu_prestamos():
    """Sección 4: préstamos y devoluciones."""
    ejecutar_submenu("4. PRÉSTAMOS Y DEVOLUCIONES", [
        ("Registrar préstamo", registrar_prestamo),
        ("Registrar devolución", registrar_devolucion),
        ("Editar préstamo / devolución", editar_prestamo),
        ("Eliminar préstamo (registro cargado por error)", eliminar_prestamo),
    ])


def mostrar_menu_principal():
    """Muestra las 4 secciones del sistema."""
    print("\n" + "=" * 46)
    print("        SISTEMA DE GESTIÓN DE PAÑOL")
    print("=" * 46)
    print("1. VER / BUSCAR")
    print("2. HERRAMIENTAS")
    print("3. USUARIOS")
    print("4. PRÉSTAMOS Y DEVOLUCIONES")
    print("0. SALIR del sistema")
    print("=" * 46)


# =====================================================================
# 5) READ - LECTURA DE DATOS (SELECT)
# =====================================================================
def imprimir_herramientas(filas):
    """Imprime en formato de tabla las filas de herramientas recibidas."""
    print(f"\n{'ID':<4}{'Nombre':<24}{'Marca':<12}{'Modelo':<13}{'Categoría':<26}{'Estado':<14}")
    print("-" * 93)
    for fila in filas:
        print(
            f"{fila[0]:<4}{texto_o_guion(fila[1]):<24}{texto_o_guion(fila[2]):<12}"
            f"{texto_o_guion(fila[3]):<13}{texto_o_guion(fila[4]):<26}{texto_o_guion(fila[5]):<14}"
        )
    print(f"\nTotal: {len(filas)} herramienta(s)")


def listar_herramientas():
    """Muestra todas las herramientas o las filtra por un criterio."""
    print("\n--- VER / BUSCAR HERRAMIENTAS ---")
    print("1. Ver todas")
    print("2. Filtrar por estado")
    print("3. Buscar por nombre")
    print("4. Filtrar por categoría")
    opcion = input("Seleccione una opción (1-4): ").strip()

    # Consulta base: LEFT JOIN para traer también el nombre de la categoría
    sql = """
        SELECT h.id, h.nombre, h.marca, h.modelo, c.nombre, h.estado
        FROM herramientas h
        LEFT JOIN categorias c ON h.id_categoria = c.id
    """
    parametros = ()  # valores que reemplazan a los %s de la consulta

    # Según la opción, se agrega un WHERE con un parámetro (%s)
    if opcion == "1":
        pass  # sin filtro
    elif opcion == "2":
        estado = ESTADOS.get(input("Estado (1=Disponible, 2=Prestado, 3=Mantenimiento, 4=Dañado): ").strip())
        if estado is None:
            print("❌ Opción de estado inválida")
            return
        sql += " WHERE h.estado = %s"
        parametros = (estado,)
    elif opcion == "3":
        texto = pedir_texto_obligatorio("Texto a buscar en el nombre: ")
        sql += " WHERE h.nombre LIKE %s"
        parametros = (f"%{texto}%",)  # los % van en el valor, no en la consulta
    elif opcion == "4":
        ver_categorias()
        id_categoria = pedir_entero("ID de la categoría: ")
        if id_categoria is None:
            return
        sql += " WHERE h.id_categoria = %s"
        parametros = (id_categoria,)
    else:
        print("❌ Opción inválida")
        return

    sql += " ORDER BY h.id"

    filas = consultar(sql, parametros)
    if filas is None:
        return
    if filas:
        imprimir_herramientas(filas)
    else:
        print("ℹ️  No se encontraron herramientas con ese criterio.")


def listar_herramientas_simple():
    """Lista corta (ID, nombre y estado) para elegir una herramienta."""
    filas = consultar("SELECT id, nombre, estado FROM herramientas ORDER BY id")
    print("\nHerramientas:")
    for fila in filas or []:
        print(f"  {fila[0]}. {fila[1]} ({fila[2]})")


def mostrar_lista_personas():
    """Lista corta de personas (ID, nombre, departamento) para elegir una."""
    personas = consultar("SELECT id, nombre, departamento FROM personas ORDER BY id")
    print("\nPersonas:")
    for p in personas or []:
        print(f"  {p[0]}. {p[1]} ({texto_o_guion(p[2])})")
    return personas


def ver_categorias():
    """Muestra las categorías de herramientas con su cantidad de herramientas."""
    categorias = consultar(
        """
        SELECT c.id, c.nombre, COUNT(h.id)
        FROM categorias c
        LEFT JOIN herramientas h ON h.id_categoria = c.id
        GROUP BY c.id, c.nombre
        ORDER BY c.id
        """
    )
    if categorias is None:
        return
    print("\n--- CATEGORÍAS ---")
    print(f"{'ID':<4}{'Nombre':<28}{'Herramientas':<12}")
    print("-" * 44)
    for c in categorias:
        print(f"{c[0]:<4}{c[1]:<28}{c[2]:<12}")


def ver_personas():
    """Muestra todas las personas o busca por nombre/departamento."""
    print("\n--- VER / BUSCAR PERSONAS ---")
    print("1. Ver todas")
    print("2. Buscar por nombre o departamento")
    opcion = input("Seleccione una opción (1-2): ").strip()

    sql = "SELECT id, nombre, departamento, email FROM personas"
    parametros = ()
    if opcion == "1":
        pass
    elif opcion == "2":
        texto = pedir_texto_obligatorio("Texto a buscar: ")
        sql += " WHERE nombre LIKE %s OR departamento LIKE %s"
        parametros = (f"%{texto}%", f"%{texto}%")
    else:
        print("❌ Opción inválida")
        return
    sql += " ORDER BY id"

    personas = consultar(sql, parametros)
    if personas is None:
        return
    if not personas:
        print("ℹ️  No se encontraron personas con ese criterio.")
        return

    print(f"\n{'ID':<4}{'Nombre':<22}{'Departamento':<16}{'Email':<30}")
    print("-" * 72)
    for p in personas:
        print(f"{p[0]:<4}{texto_o_guion(p[1]):<22}{texto_o_guion(p[2]):<16}{texto_o_guion(p[3]):<30}")
    print(f"\nTotal: {len(personas)} persona(s)")


def imprimir_prestamos(prestamos):
    """Imprime préstamos (activos o devueltos) en formato de tabla."""
    print(f"\n{'ID':<4}{'Herramienta':<24}{'Persona':<20}{'Préstamo':<12}{'Devolución':<12}{'Observaciones':<30}")
    print("-" * 102)
    for p in prestamos:
        devolucion = "Pendiente" if p[4] is None else str(p[4])   # NULL = no devuelto
        print(
            f"{p[0]:<4}{recortar(p[1], 23):<24}{recortar(p[2], 19):<20}"
            f"{str(p[3]):<12}{devolucion:<12}{recortar(p[5], 29):<30}"
        )
    print(f"\nTotal: {len(prestamos)} préstamo(s)")


# Consulta base compartida por el historial, la edición y la eliminación de préstamos
SQL_PRESTAMOS = """
    SELECT p.id, h.nombre, per.nombre, p.fecha_prestamo, p.fecha_devolucion, p.observaciones
    FROM prestamos p
    JOIN herramientas h ON p.id_herramienta = h.id
    JOIN personas per   ON p.id_persona = per.id
"""


def ver_prestamos_activos():
    """Muestra los préstamos que todavía no tienen fecha de devolución."""
    # Un préstamo está activo mientras fecha_devolucion sea NULL
    prestamos = consultar(SQL_PRESTAMOS + " WHERE p.fecha_devolucion IS NULL ORDER BY p.id")
    if prestamos is None:
        return
    print("\n--- PRÉSTAMOS ACTIVOS ---")
    if not prestamos:
        print("✅ No hay préstamos activos.")
        return
    imprimir_prestamos(prestamos)


def ver_historial_prestamos():
    """Muestra todos los préstamos (activos y devueltos), con filtro opcional."""
    print("\n--- HISTORIAL DE PRÉSTAMOS ---")
    print("1. Ver todos")
    print("2. Filtrar por persona")
    print("3. Filtrar por herramienta")
    opcion = input("Seleccione una opción (1-3): ").strip()

    sql = SQL_PRESTAMOS
    parametros = ()
    if opcion == "1":
        pass
    elif opcion == "2":
        mostrar_lista_personas()
        id_persona = pedir_entero("ID de la persona: ")
        if id_persona is None:
            return
        sql += " WHERE p.id_persona = %s"
        parametros = (id_persona,)
    elif opcion == "3":
        listar_herramientas_simple()
        id_herramienta = pedir_entero("ID de la herramienta: ")
        if id_herramienta is None:
            return
        sql += " WHERE p.id_herramienta = %s"
        parametros = (id_herramienta,)
    else:
        print("❌ Opción inválida")
        return
    sql += " ORDER BY p.id"

    prestamos = consultar(sql, parametros)
    if prestamos is None:
        return
    if not prestamos:
        print("ℹ️  No se encontraron préstamos con ese criterio.")
        return
    imprimir_prestamos(prestamos)


# =====================================================================
# 6) HERRAMIENTAS: CREATE / UPDATE / DELETE
# =====================================================================
def agregar_herramienta():
    """Pide los datos al usuario e inserta una nueva herramienta."""
    print("\n--- AGREGAR NUEVA HERRAMIENTA ---")
    nombre = pedir_texto_obligatorio("Nombre de la herramienta: ")
    marca = input("Marca: ").strip() or None     # si queda vacío se guarda NULL
    modelo = input("Modelo: ").strip() or None

    ver_categorias()
    id_categoria = pedir_entero("ID de la categoría: ")
    if id_categoria is None:
        return

    conexion = None
    cursor = None
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()

        # Consulta parametrizada: los %s se reemplazan de forma segura
        sql = """
            INSERT INTO herramientas (nombre, marca, modelo, id_categoria, estado, fecha_adquisicion)
            VALUES (%s, %s, %s, %s, 'Disponible', %s)
        """
        datos = (nombre, marca, modelo, id_categoria, date.today())
        cursor.execute(sql, datos)
        conexion.commit()   # sin commit() los cambios no se guardan en la base
        print(f"✅ Herramienta agregada correctamente (ID {cursor.lastrowid})")
    except IntegrityError:
        # Pasa, por ejemplo, si la categoría ingresada no existe (clave foránea)
        conexion.rollback()
        print("❌ No se pudo agregar: la categoría indicada no existe.")
    except Error as error:
        if conexion is not None:
            conexion.rollback()
        print(f"❌ Error de base de datos: {error}")
    finally:
        cerrar_todo(cursor, conexion)


def editar_herramienta():
    """Modifica nombre, marca, modelo o categoría; con Enter se conserva el valor actual."""
    listar_herramientas_simple()

    print("\n--- EDITAR HERRAMIENTA ---")
    id_herramienta = pedir_entero("ID de la herramienta a editar: ")
    if id_herramienta is None:
        return

    conexion = None
    cursor = None
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()

        # Primero se buscan los datos actuales para mostrarlos
        cursor.execute(
            "SELECT nombre, marca, modelo, id_categoria FROM herramientas WHERE id = %s",
            (id_herramienta,),
        )
        actual = cursor.fetchone()   # una sola fila (o None si no existe)
        if actual is None:
            print("❌ No existe una herramienta con ese ID.")
            return

        ver_categorias()
        print("\n(Presioná Enter para dejar el valor actual)")
        nombre = input(f"Nombre [{texto_o_guion(actual[0])}]: ").strip() or actual[0]
        marca = input(f"Marca [{texto_o_guion(actual[1])}]: ").strip() or actual[1]
        modelo = input(f"Modelo [{texto_o_guion(actual[2])}]: ").strip() or actual[2]
        texto_categoria = input(f"ID de categoría [{texto_o_guion(actual[3])}]: ").strip()
        if texto_categoria == "":
            id_categoria = actual[3]
        elif texto_categoria.isdigit():
            id_categoria = int(texto_categoria)
        else:
            print("❌ La categoría debe ser un número.")
            return

        cursor.execute(
            "UPDATE herramientas SET nombre = %s, marca = %s, modelo = %s, id_categoria = %s WHERE id = %s",
            (nombre, marca, modelo, id_categoria, id_herramienta),
        )
        conexion.commit()
        print("✅ Herramienta actualizada correctamente")
    except IntegrityError:
        conexion.rollback()
        print("❌ No se pudo actualizar: la categoría indicada no existe.")
    except Error as error:
        if conexion is not None:
            conexion.rollback()
        print(f"❌ Error de base de datos: {error}")
    finally:
        cerrar_todo(cursor, conexion)


def actualizar_estado_herramienta():
    """Cambia el estado de una herramienta a partir de su ID.

    Si la herramienta está prestada, el estado se cambia desde la devolución,
    y 'Prestado' solo se asigna al registrar un préstamo.
    """
    listar_herramientas_simple()

    print("\n--- CAMBIAR ESTADO DE HERRAMIENTA ---")
    id_herramienta = pedir_entero("ID de la herramienta a actualizar: ")
    if id_herramienta is None:
        return

    print("\nOpciones de estado:")
    for numero, nombre_estado in ESTADOS_MANUALES.items():
        print(f"  {numero}. {nombre_estado}")
    nuevo_estado = ESTADOS_MANUALES.get(input("Seleccione opción (1-3): ").strip())
    if nuevo_estado is None:
        print("❌ Opción inválida")
        return

    conexion = None
    cursor = None
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()

        # Si tiene un préstamo sin devolver, no se puede cambiar el estado a mano
        cursor.execute(
            "SELECT COUNT(*) FROM prestamos WHERE id_herramienta = %s AND fecha_devolucion IS NULL",
            (id_herramienta,),
        )
        if cursor.fetchone()[0] > 0:
            print("❌ La herramienta está prestada. Registrá primero la devolución.")
            return

        cursor.execute(
            "UPDATE herramientas SET estado = %s WHERE id = %s",
            (nuevo_estado, id_herramienta),
        )
        conexion.commit()
        # rowcount indica cuántas filas se modificaron (0 = el ID no existe)
        if cursor.rowcount == 0:
            print("⚠️  No se modificó nada: el ID no existe o el estado ya era ese.")
        else:
            print(f"✅ Estado actualizado a: {nuevo_estado}")
    except Error as error:
        if conexion is not None:
            conexion.rollback()
        print(f"❌ Error de base de datos: {error}")
    finally:
        cerrar_todo(cursor, conexion)


def eliminar_herramienta():
    """Elimina una herramienta por su ID (con confirmación previa)."""
    listar_herramientas_simple()

    print("\n--- ELIMINAR HERRAMIENTA ---")
    id_herramienta = pedir_entero("ID de la herramienta a eliminar: ")
    if id_herramienta is None:
        return

    conexion = None
    cursor = None
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()

        cursor.execute("SELECT nombre, estado FROM herramientas WHERE id = %s", (id_herramienta,))
        herramienta = cursor.fetchone()
        if herramienta is None:
            print("⚠️  No existe una herramienta con ese ID.")
            return
        if herramienta[1] == "Prestado":
            print("❌ No se puede eliminar: la herramienta está prestada actualmente.")
            return

        if input(f"¿Está seguro de eliminar '{herramienta[0]}'? (s/n): ").strip().lower() != "s":
            print("❌ Eliminación cancelada")
            return

        cursor.execute("DELETE FROM herramientas WHERE id = %s", (id_herramienta,))
        conexion.commit()
        print("✅ Herramienta eliminada correctamente")
    except IntegrityError:
        # La clave foránea impide borrar herramientas que ya tienen préstamos
        conexion.rollback()
        print("❌ No se puede eliminar: la herramienta tiene préstamos registrados.")
        print("   Sugerencia: cambiá su estado a 'Dañado' en lugar de borrarla.")
    except Error as error:
        if conexion is not None:
            conexion.rollback()
        print(f"❌ Error de base de datos: {error}")
    finally:
        cerrar_todo(cursor, conexion)


# =====================================================================
# 7) USUARIOS (PERSONAS): CREATE / UPDATE / DELETE
# =====================================================================
def agregar_persona():
    """Pide los datos al usuario e inserta una nueva persona."""
    print("\n--- AGREGAR NUEVA PERSONA ---")
    nombre = pedir_texto_obligatorio("Nombre completo: ")
    departamento = input("Departamento: ").strip() or None
    email = input("Email: ").strip() or None

    conexion = None
    cursor = None
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        sql = "INSERT INTO personas (nombre, departamento, email) VALUES (%s, %s, %s)"
        cursor.execute(sql, (nombre, departamento, email))
        conexion.commit()
        print(f"✅ Persona agregada correctamente (ID {cursor.lastrowid})")
    except Error as error:
        if conexion is not None:
            conexion.rollback()
        print(f"❌ Error de base de datos: {error}")
    finally:
        cerrar_todo(cursor, conexion)


def editar_persona():
    """Modifica nombre, departamento o email; con Enter se conserva el valor actual."""
    mostrar_lista_personas()

    print("\n--- EDITAR PERSONA ---")
    id_persona = pedir_entero("ID de la persona a editar: ")
    if id_persona is None:
        return

    conexion = None
    cursor = None
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()

        cursor.execute(
            "SELECT nombre, departamento, email FROM personas WHERE id = %s",
            (id_persona,),
        )
        actual = cursor.fetchone()
        if actual is None:
            print("❌ No existe una persona con ese ID.")
            return

        print("(Presioná Enter para dejar el valor actual)")
        nombre = input(f"Nombre [{texto_o_guion(actual[0])}]: ").strip() or actual[0]
        departamento = input(f"Departamento [{texto_o_guion(actual[1])}]: ").strip() or actual[1]
        email = input(f"Email [{texto_o_guion(actual[2])}]: ").strip() or actual[2]

        cursor.execute(
            "UPDATE personas SET nombre = %s, departamento = %s, email = %s WHERE id = %s",
            (nombre, departamento, email, id_persona),
        )
        conexion.commit()
        print("✅ Persona actualizada correctamente")
    except Error as error:
        if conexion is not None:
            conexion.rollback()
        print(f"❌ Error de base de datos: {error}")
    finally:
        cerrar_todo(cursor, conexion)


def eliminar_persona():
    """Elimina una persona por su ID (con confirmación previa)."""
    mostrar_lista_personas()

    print("\n--- ELIMINAR PERSONA ---")
    id_persona = pedir_entero("ID de la persona a eliminar: ")
    if id_persona is None:
        return

    conexion = None
    cursor = None
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()

        cursor.execute("SELECT nombre FROM personas WHERE id = %s", (id_persona,))
        persona = cursor.fetchone()
        if persona is None:
            print("⚠️  No existe una persona con ese ID.")
            return

        # No se puede borrar a alguien que todavía tiene herramientas sin devolver
        cursor.execute(
            "SELECT COUNT(*) FROM prestamos WHERE id_persona = %s AND fecha_devolucion IS NULL",
            (id_persona,),
        )
        if cursor.fetchone()[0] > 0:
            print("❌ No se puede eliminar: la persona tiene herramientas sin devolver.")
            return

        if input(f"¿Está seguro de eliminar a '{persona[0]}'? (s/n): ").strip().lower() != "s":
            print("❌ Eliminación cancelada")
            return

        cursor.execute("DELETE FROM personas WHERE id = %s", (id_persona,))
        conexion.commit()
        print("✅ Persona eliminada correctamente")
    except IntegrityError:
        # La clave foránea impide borrar personas que figuran en el historial
        conexion.rollback()
        print("❌ No se puede eliminar: la persona figura en el historial de préstamos.")
    except Error as error:
        if conexion is not None:
            conexion.rollback()
        print(f"❌ Error de base de datos: {error}")
    finally:
        cerrar_todo(cursor, conexion)


# =====================================================================
# 8) PRÉSTAMOS Y DEVOLUCIONES (varias operaciones en una transacción)
# =====================================================================
def registrar_prestamo():
    """Registra un préstamo y marca la herramienta como 'Prestado'.

    Son DOS operaciones (INSERT en prestamos + UPDATE en herramientas) que
    deben cumplirse juntas: se hace un único commit al final y, si algo
    falla, un rollback deshace todo.
    """
    print("\n--- REGISTRAR PRÉSTAMO ---")

    conexion = None
    cursor = None
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()

        # 1. Mostrar solo las herramientas disponibles
        cursor.execute("SELECT id, nombre FROM herramientas WHERE estado = 'Disponible' ORDER BY id")
        disponibles = cursor.fetchall()
        if not disponibles:
            print("❌ No hay herramientas disponibles")
            return
        print("Herramientas disponibles:")
        for h in disponibles:
            print(f"  {h[0]}. {h[1]}")
        id_herramienta = pedir_entero("ID de la herramienta: ")
        if id_herramienta is None:
            return
        if id_herramienta not in [h[0] for h in disponibles]:
            print("❌ Esa herramienta no existe o no está disponible.")
            return

        # 2. Mostrar personas y validar la elegida
        cursor.execute("SELECT id, nombre, departamento FROM personas ORDER BY id")
        personas = cursor.fetchall()
        print("\nPersonas:")
        for p in personas:
            print(f"  {p[0]}. {p[1]} ({texto_o_guion(p[2])})")
        id_persona = pedir_entero("ID de la persona: ")
        if id_persona is None:
            return
        if id_persona not in [p[0] for p in personas]:
            print("❌ Esa persona no existe.")
            return

        observaciones = input("Observaciones (opcional): ").strip() or None

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
        print("✅ Préstamo registrado correctamente")
    except Error as error:
        if conexion is not None:
            conexion.rollback()   # si algo falló, se deshace todo
        print(f"❌ Error de base de datos: {error}")
    finally:
        cerrar_todo(cursor, conexion)


def registrar_devolucion():
    """Registra la devolución de un préstamo y actualiza el estado de la herramienta."""
    print("\n--- REGISTRAR DEVOLUCIÓN ---")

    conexion = None
    cursor = None
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()

        # 1. Listar préstamos activos
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
            print("✅ No hay préstamos activos")
            return
        print("Préstamos activos:")
        for p in activos:
            print(f"  {p[0]}. {p[1]} - {p[2]}")

        id_prestamo = pedir_entero("ID del préstamo a devolver: ")
        if id_prestamo is None:
            return

        # 2. Buscar el préstamo elegido entre los activos
        elegido = next((p for p in activos if p[0] == id_prestamo), None)
        if elegido is None:
            print("❌ Ese préstamo no existe o ya fue devuelto.")
            return
        id_herramienta = elegido[3]

        # 3. En qué condición vuelve la herramienta (Enter = Disponible)
        print("\n¿En qué estado vuelve la herramienta?")
        for numero, nombre_estado in ESTADOS_MANUALES.items():
            print(f"  {numero}. {nombre_estado}")
        texto_estado = input("Seleccione opción (Enter = Disponible): ").strip() or "1"
        estado_final = ESTADOS_MANUALES.get(texto_estado)
        if estado_final is None:
            print("❌ Opción inválida")
            return
        observacion = input("Observaciones de la devolución (opcional): ").strip() or None

        # 4. Poner fecha de devolución (y sumar la observación a las anteriores)
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
        # 5. Actualizar el estado de la herramienta según cómo volvió
        cursor.execute(
            "UPDATE herramientas SET estado = %s WHERE id = %s",
            (estado_final, id_herramienta),
        )

        conexion.commit()
        print(f"✅ Devolución registrada correctamente (herramienta: {estado_final})")
    except Error as error:
        if conexion is not None:
            conexion.rollback()
        print(f"❌ Error de base de datos: {error}")
    finally:
        cerrar_todo(cursor, conexion)


def editar_prestamo():
    """Corrige un préstamo: persona, fechas y observaciones (Enter = conservar).

    La fecha de devolución solo se edita si el préstamo ya fue devuelto; para
    devolver un préstamo activo se usa 'Registrar devolución'.
    """
    prestamos = consultar(SQL_PRESTAMOS + " ORDER BY p.id")
    if prestamos is None:
        return
    if not prestamos:
        print("ℹ️  No hay préstamos registrados.")
        return
    imprimir_prestamos(prestamos)

    print("\n--- EDITAR PRÉSTAMO / DEVOLUCIÓN ---")
    id_prestamo = pedir_entero("ID del préstamo a editar: ")
    if id_prestamo is None:
        return

    conexion = None
    cursor = None
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()

        # Datos actuales del préstamo
        cursor.execute(
            "SELECT id_persona, fecha_prestamo, fecha_devolucion, observaciones FROM prestamos WHERE id = %s",
            (id_prestamo,),
        )
        actual = cursor.fetchone()
        if actual is None:
            print("❌ No existe un préstamo con ese ID.")
            return
        id_persona, f_prestamo, f_devolucion, observaciones = actual

        mostrar_lista_personas()
        print("\n(Presioná Enter para dejar el valor actual)")

        # Persona: se valida que exista
        texto_persona = input(f"ID de persona [{id_persona}]: ").strip()
        if texto_persona != "":
            if not texto_persona.isdigit():
                print("❌ El ID de la persona debe ser un número.")
                return
            cursor.execute("SELECT id FROM personas WHERE id = %s", (int(texto_persona),))
            if cursor.fetchone() is None:
                print("❌ Esa persona no existe.")
                return
            id_persona = int(texto_persona)

        # Fechas: se validan formato y orden lógico
        nueva_f_prestamo = pedir_fecha(f"Fecha de préstamo [{f_prestamo}] (AAAA-MM-DD): ", f_prestamo)
        if nueva_f_prestamo is False:
            return
        nueva_f_devolucion = f_devolucion
        if f_devolucion is not None:
            nueva_f_devolucion = pedir_fecha(f"Fecha de devolución [{f_devolucion}] (AAAA-MM-DD): ", f_devolucion)
            if nueva_f_devolucion is False:
                return
            if nueva_f_devolucion < nueva_f_prestamo:
                print("❌ La devolución no puede ser anterior al préstamo.")
                return
        else:
            print("ℹ️  Préstamo activo: para devolverlo usá 'Registrar devolución'.")

        # Observaciones: Enter conserva, "-" borra el texto
        texto_obs = input(f"Observaciones [{texto_o_guion(observaciones)}] ('-' para borrar): ").strip()
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
            (id_persona, nueva_f_prestamo, nueva_f_devolucion, observaciones, id_prestamo),
        )
        conexion.commit()
        print("✅ Préstamo actualizado correctamente")
    except Error as error:
        if conexion is not None:
            conexion.rollback()
        print(f"❌ Error de base de datos: {error}")
    finally:
        cerrar_todo(cursor, conexion)


def eliminar_prestamo():
    """Elimina un préstamo cargado por error (con confirmación previa).

    Si el préstamo estaba activo, también deja la herramienta como
    'Disponible'. Son dos operaciones, por eso van en una sola transacción.
    """
    prestamos = consultar(SQL_PRESTAMOS + " ORDER BY p.id")
    if prestamos is None:
        return
    if not prestamos:
        print("ℹ️  No hay préstamos registrados.")
        return
    imprimir_prestamos(prestamos)

    print("\n--- ELIMINAR PRÉSTAMO ---")
    id_prestamo = pedir_entero("ID del préstamo a eliminar: ")
    if id_prestamo is None:
        return

    conexion = None
    cursor = None
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()

        cursor.execute(
            "SELECT id_herramienta, fecha_devolucion FROM prestamos WHERE id = %s",
            (id_prestamo,),
        )
        prestamo = cursor.fetchone()
        if prestamo is None:
            print("⚠️  No existe un préstamo con ese ID.")
            return

        if input("¿Está seguro de eliminar este préstamo? (s/n): ").strip().lower() != "s":
            print("❌ Eliminación cancelada")
            return

        cursor.execute("DELETE FROM prestamos WHERE id = %s", (id_prestamo,))
        # Si todavía no se había devuelto, la herramienta vuelve a estar disponible
        if prestamo[1] is None:
            cursor.execute(
                "UPDATE herramientas SET estado = 'Disponible' WHERE id = %s AND estado = 'Prestado'",
                (prestamo[0],),
            )
        conexion.commit()
        print("✅ Préstamo eliminado correctamente")
    except Error as error:
        if conexion is not None:
            conexion.rollback()
        print(f"❌ Error de base de datos: {error}")
    finally:
        cerrar_todo(cursor, conexion)


# =====================================================================
# 9) PROGRAMA PRINCIPAL
# =====================================================================
def main():
    """Prueba la conexión y ejecuta el menú hasta que el usuario salga."""
    print("🔧 SISTEMA DE GESTIÓN DE PAÑOL")

    # Si la contraseña no vino por variable de entorno, se pide sin mostrarla
    if not CONFIG_BD["password"]:
        CONFIG_BD["password"] = getpass("Contraseña de MySQL (Enter si no tiene): ")

    print("Conectando a la base de datos...")

    # Prueba de conexión inicial: si falla, no tiene sentido mostrar el menú
    try:
        conexion_prueba = conectar_bd()
        print("✅ Conexión exitosa a la base de datos")
        conexion_prueba.close()
    except Error as error:
        print(f"❌ Error: no se pudo conectar a la base de datos ({error})")
        print("Verificá los datos de CONFIG_BD y que el servidor MySQL esté encendido.")
        return

    # Cada sección del menú principal se asocia a su submenú
    secciones = {
        "1": menu_ver_buscar,
        "2": menu_herramientas,
        "3": menu_usuarios,
        "4": menu_prestamos,
    }

    while True:
        mostrar_menu_principal()
        opcion = input("Seleccione una opción: ").strip()

        if opcion == "0":
            print("👋 ¡Hasta luego!")
            break
        seccion = secciones.get(opcion)
        if seccion is None:
            print("❌ Opción inválida, intente nuevamente")
        else:
            seccion()


# Este if hace que main() se ejecute solo al correr el archivo directamente
if __name__ == "__main__":
    main()