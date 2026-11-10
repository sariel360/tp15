# Informe – TP N° 15: Operaciones CRUD con bases de datos en Python

**Materia:** Laboratorio de Aplicaciones II – 6° G
**Proyecto:** Sistema de gestión de un pañol de herramientas
**Archivos entregados:** `crear_bd.sql`, `v3_grafica.py`, `informe.md`

---

## 1. ¿Qué temática elegí y por qué?

Elegí un **sistema de gestión de un pañol de herramientas**. Un pañol es el lugar de un taller o una fábrica donde se guardan las herramientas y de donde las retiran las personas para trabajar. Me pareció un tema ideal porque es un problema real que todavía se resuelve muchas veces con cuadernos o planillas: hay que saber qué herramientas hay, en qué estado están, quién tiene cada una y cuándo la devolvió.

Además, el tema permite aplicar de forma natural todo lo visto en clase: varias tablas relacionadas, claves foráneas y operaciones que deben hacerse "juntas" (por ejemplo, prestar una herramienta implica registrar el préstamo **y** cambiar su estado).

## 2. ¿Cómo diseñé la base de datos y qué campos incluí?

La base se llama `panol_herramientas` y se crea con `crear_bd.sql` (usa `utf8mb4` para que se vean bien las tildes y la ñ). Tiene **4 tablas**, todas con clave primaria autoincremental:

| Tabla | Campos | Función |
|---|---|---|
| `categorias` | id, nombre, descripcion | Agrupa las herramientas (manuales, eléctricas, medición, sujeción). |
| `herramientas` | id, nombre, marca, modelo, id_categoria (FK), estado, fecha_adquisicion | **Tabla principal del CRUD.** `estado` es un `ENUM`: Disponible, Prestado, Mantenimiento, Dañado. |
| `personas` | id, nombre, departamento, email | Empleados que pueden pedir herramientas. |
| `prestamos` | id, id_herramienta (FK), id_persona (FK), fecha_prestamo, fecha_devolucion, observaciones | Relaciona herramientas con personas. Si `fecha_devolucion` es `NULL`, el préstamo sigue activo. |

Decisiones de diseño que quiero destacar:

- Separé **categorías** en otra tabla para no repetir el texto de la categoría en cada herramienta (normalización).
- Usé **claves foráneas** para que la base no permita préstamos de herramientas o personas inexistentes.
- Usé `NULL` en `fecha_devolucion` para distinguir préstamos activos de los ya devueltos, sin necesitar un campo extra.
- El script incluye datos de prueba: 4 categorías, 6 herramientas, 3 personas y 2 préstamos (más de los 5 registros pedidos).

## 3. ¿Cómo está armado el programa?

El programa es una aplicación con **interfaz gráfica** hecha con `customtkinter`, que usa `mysql-connector-python` para hablar con MySQL. Primero hice una versión por consola con menú, y después la pasé a ventanas, manteniendo la misma lógica de consultas y transacciones. Tiene una barra lateral con cinco pantallas:

- **Inicio:** resumen del pañol y préstamos activos.
- **Herramientas:** ver y buscar (por nombre, estado o categoría), agregar, editar, cambiar estado y eliminar.
- **Personas:** ver y buscar, agregar, editar y eliminar.
- **Préstamos:** ver activos o historial, registrar, devolver, editar y eliminar.
- **Categorías:** consulta.

Cómo cubre los cuatro requisitos CRUD y las demás pautas del enunciado:

- **Create:** `INSERT` desde formularios (`agregar_herramienta`, `agregar_persona`, `registrar_prestamo`).
- **Read:** `SELECT` con filtros y `JOIN` entre tablas (`buscar_herramientas`, `buscar_personas`, `obtener_prestamos`).
- **Update:** `UPDATE` a partir del ID de la fila seleccionada (`editar_herramienta`, `editar_persona`, `editar_prestamo`, `registrar_devolucion`, `actualizar_estado_herramienta`).
- **Delete:** `DELETE` con confirmación previa (`eliminar_herramienta`, `eliminar_persona`, `eliminar_prestamo`).
- **Consultas parametrizadas:** todas usan `%s` y pasan los valores aparte, por ejemplo `cursor.execute("UPDATE herramientas SET estado = %s WHERE id = %s", (estado, id))`.
- **Excepciones y cierre de recursos:** las operaciones pasan por funciones auxiliares (`consultar` y `ejecutar_operacion`) que capturan `mysql.connector.Error`, hacen `rollback` si algo falla y cierran cursor y conexión siempre en un bloque `finally`.
- **Comentarios:** el código está comentado paso a paso.

También agregué reglas para que los datos no queden inconsistentes: no se puede eliminar una herramienta prestada, no se puede eliminar una persona con herramientas sin devolver, y "Prestado" no se puede elegir a mano (solo se asigna al registrar un préstamo).

## 4. ¿El programa funcionó correctamente? ¿Qué dificultades encontré?

El programa permite realizar correctamente las cuatro operaciones CRUD sobre las tablas, y las validaciones (campos vacíos, fechas con formato incorrecto, herramientas no disponibles, claves foráneas inexistentes) devuelven mensajes claros en vez de cerrar el programa.

Las dificultades más importantes no fueron del código sino del entorno de trabajo:

1. **El servidor MySQL no estaba corriendo.** Al ejecutar el programa por primera vez apareció el error `Can't connect to MySQL server (2003)`. Aprendí que instalar MySQL no alcanza: hay que terminar de configurarlo con *MySQL Configurator* (tipo de servidor, puerto 3306, contraseña de `root`, servicio de Windows) y asegurarse de que el servicio esté iniciado.
2. **El MySQL Command Line Client se cerraba apenas lo abría.** Lo resolví abriéndolo desde PowerShell, así podía ver el mensaje de error y no se cerraba la ventana.
3. **`pip` no se reconocía en PowerShell.** Es un problema de PATH. La solución fue usar `py -m pip install ...` en vez de `pip install ...`.
4. **Carga del script SQL.** Tuve que usar el comando `source` con barras normales (`/`) y el `;` final para cargar `crear_bd.sql` desde el cliente.
5. **Manejo de la contraseña.** Entendí que no conviene dejar la contraseña escrita en el código. Por eso el programa la toma de la variable de entorno `BD_PASSWORD` y, si no la encuentra, la pide al iniciar.
6. **Lógica de campos opcionales al editar.** En la versión por consola, dejar un campo vacío significaba "conservar el valor actual". Al pasar a la interfaz gráfica mantuve esa lógica y los formularios se abren ya completados con los valores actuales.

## 5. ¿Qué aprendí sobre la conexión entre Python y MySQL?

- Que Python no "es" la base de datos: es un **cliente** que se conecta a un servidor MySQL que tiene que estar encendido y configurado (host, puerto, usuario, contraseña y nombre de la base).
- El flujo de trabajo siempre es el mismo: **conectar → crear cursor → ejecutar → (commit) → cerrar**. Si se corta en el medio, los recursos tienen que cerrarse igual; para eso sirve `finally`.
- Los errores se capturan con `mysql.connector.Error` y sus subclases, como `IntegrityError` para violaciones de claves foráneas, y conviene mostrarlos de forma entendible.
- Las tablas relacionadas se consultan con `JOIN`, y las claves foráneas protegen la integridad de los datos desde la propia base.
- Separar la **lógica de datos** de la **interfaz** me permitió cambiar de consola a ventanas sin tocar las consultas.

## 6. Reflexión: consultas parametrizadas y transacciones (commit)

**Consultas parametrizadas.** En vez de armar el SQL pegando texto (`"... WHERE nombre = '" + nombre + "'"`), uso marcadores `%s` y paso los valores por separado. El conector los escapa, y así lo que escribe el usuario siempre se trata como **dato** y nunca como **código SQL**. Esto evita la inyección SQL: sin parametrizar, alguien podría escribir en un campo algo como `'; DROP TABLE herramientas; --` y borrar información. Además, el código queda más prolijo y se evitan errores con comillas o caracteres especiales.

**Transacciones y `commit`.** Los cambios que hace un `INSERT`, `UPDATE` o `DELETE` no quedan guardados definitivamente hasta ejecutar `commit()`. Esto es fundamental cuando hay **operaciones que van juntas**. Por ejemplo, al registrar un préstamo se hace un `INSERT` en `prestamos` y un `UPDATE` del estado en `herramientas`: si el primero se hiciera y el segundo fallara, la base quedaría inconsistente (un préstamo activo con la herramienta marcada como "Disponible"). Por eso hago **un solo `commit` al final** y, si ocurre cualquier error, un `rollback` que deshace todo. Lo mismo pasa con devolver y eliminar préstamos. Entendí que el `commit` y el `rollback` son lo que garantiza que los datos queden siempre en un estado coherente.

---

## 7. Declaración de uso de IA (transparencia)

Utilicé asistentes de IA como apoyo, dentro de los usos permitidos por el enunciado (planificar la estructura del código, depurar errores, consultar buenas prácticas y redactar documentación). A continuación detallo en qué me ayudaron:

| # | Consulta | Asistente | Para qué lo usé |
|---|---|---|---|
| 1 | Verificar mi TP contra el enunciado y agregar funciones para editar/eliminar personas y editar préstamos/devoluciones, ordenando el programa en 4 secciones (Ver/Buscar, Herramientas, Usuarios, Préstamos y devoluciones) | Claude | Revisión de requisitos, ampliación de funciones y reorganización del menú. Lo probó contra una base MariaDB cargada con mi `crear_bd.sql`. Me avisó además que faltaba el informe y que la contraseña estaba escrita en el código. |
| 2 | "Quiero abrir MySQL Command Line Client y se me cierra apenas intento abrirlo" | Claude | Depurar el entorno: iniciar el servicio, abrir el cliente desde PowerShell y cargar `crear_bd.sql` con `source`. |
| 3 | Pasos para cargar la base, poner la contraseña en `CONFIG_BD` y ejecutar el programa | Claude | Guía para dejar el programa funcionando en mi PC y qué significa cada error (2003, Access denied, Unknown database). |
| 4 | Pantalla de *Sample Databases* del instalador de MySQL | Claude | Saber que no hacía falta instalar las bases de ejemplo (Sakila y World). |
| 5 | "¿Cómo configuro esto?" (MySQL Configurator + error 2003) | Claude | Configuración paso a paso del servidor: puerto, contraseña de `root`, servicio de Windows. |
| 6 | Error "pip no se reconoce" al instalar `mysql-connector-python` | Claude | Solución usando `py -m pip install` y verificación de Python/PATH. |
| 7 | Mismo problema de `pip` al instalar `customtkinter` | Otro asistente de IA | Alternativa con `py -m pip` y `ensurepip`. |
| 8 | Agregar una interfaz gráfica al código de la base de datos, consultando antes cualquier cambio que afectara la lógica | Claude | Pasar la versión por consola a `customtkinter` (decidí usar esa librería, mantener la lógica "campo vacío = conservar el valor" y reemplazar la consola en el mismo archivo). Resultado: `v3_grafica.py`. |
| 9 |ayuda para redactar el informe, incluyendo el detalle de los chats anteriores | Claude | Redacción y estructura del presente informe a partir del enunciado, mi código final y el historial de mis chats. |

**Qué hice yo y qué hizo la IA.** El tema, el diseño de la base y la decisión de cómo debía comportarse el programa (menú ordenado en cuatro secciones, interfaz gráfica, reglas de edición) fueron decisiones mías; la IA colaboró escribiendo y corrigiendo código, y explicando errores. Revisé el código final, lo ejecuté en mi computadora con un servidor MySQL local y las explicaciones de este informe corresponden a lo que entendí del funcionamiento del programa.
