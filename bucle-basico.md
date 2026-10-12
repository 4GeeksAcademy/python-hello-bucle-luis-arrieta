# Bucle Básico de Agente de Inventario con IA

## Auditoría del repositorio y la fuente

- **Cohorte:** Backend development with Coding Agents (ID `1670`).
- **Proyecto en 4Geeks:** AI basic Inventory Agent Loop (tarea `997546`; slug `ai-basic-inventory-agent-loop`).
- **Repositorio auditado:** [python-hello-bucle-luis-arrieta](https://github.com/4GeeksAcademy/python-hello-bucle-luis-arrieta).
- En la auditoría inicial, el repositorio solo contenía el boilerplate básico de Python Hello y los README indicaban cómo empezar con `main.py`. Los avances posteriores se registran en las etapas de este documento.
- Este archivo resume las instrucciones oficiales del README español del proyecto. No modifica ni sustituye el README existente.
- **Fuente oficial del enunciado:** [README.es.md — 4Geeks Academy](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/projects/ai-basic-inventory-agent-loop/README.es.md).

## Objetivo

Construir dos componentes integrados para gestionar el inventario de una tienda de suministros para cafeterías:

1. Una API REST con FastAPI que gestiona productos y persiste el inventario en `products.csv`.
2. Un agente de IA en Python que conversa mediante CLI, utiliza la API como conjunto de tools y registra los eventos en `conversation_log.csv`.

El agente debe implementar manualmente el ciclo **Observar → Pensar → Actuar → Actualizar → Repetir**, sin frameworks de agentes.

## Desarrollo por etapas

Trabajaremos una etapa a la vez. Antes de continuar, se comprobará su resultado, se actualizará este documento y se hará un commit y push con los archivos de esa etapa. Después se esperará la aprobación del usuario. Si falla una comprobación o el push, se resolverá el bloqueo antes de avanzar. No se incluirán cambios ajenos, credenciales ni datos de ejecución en los commits.

| Etapa | Alcance | Criterio de cierre | Estado |
|---|---|---|---|
| 1 | Entorno UV, dependencias y protección de credenciales | Sincronización, imports y exclusiones de Git comprobados | Completada; commit `0649f52` publicado |
| 2 | Persistencia CSV y `GET /inventory` | Pruebas de inventario vacío, lectura e IDs estables | Completada; commit `4679b89` publicado |
| 3 | `POST /inventory` | Pruebas de creación, validación y persistencia | Completada; 50 pruebas superadas; commit `0d64b79` publicado |
| 4 | Actualización de stock y alertas | Pruebas de deltas, errores y umbral configurable | Verificada; 77 pruebas superadas |
| 5 | Definición de tools y conexión HTTP | Pruebas de schemas, rutas, parámetros y errores | Verificada; 17 pruebas superadas |
| 6 | Bucle manual y CLI con Groq | Pruebas con LLM simulado, varias tools y salida limpia | Verificada; 118 pruebas superadas |
| 7 | Registro de conversación | Pruebas del formato CSV y adición entre sesiones | Verificada; 131 pruebas superadas |
| 8 | Integración real y documentación de entrega | Suite completa y flujo real con Groq, incluyendo reinicios | Completada; 131 pruebas y flujo real Groq verificados |

### Etapa 1: entorno seguro y reproducible

- `pyproject.toml` define Python 3.11 o superior y las dependencias de ejecución: FastAPI, Uvicorn, OpenAI y python-dotenv. pytest y httpx se incluyen como dependencias de desarrollo.
- `uv.lock` fija las versiones resueltas. Para preparar el entorno, instalar UV con `python3 -m pip install uv` si no está disponible y ejecutar `uv sync --locked`.
- `.gitignore` excluye `.env` y sus variantes, `.venv`, cachés de Python y pytest, y los dos CSV de ejecución en la raíz. No excluye todos los CSV: los futuros fixtures de pruebas pueden versionarse.
- `.env.example` contiene `GROQ_API_KEY` y `GROQ_MODEL` vacíos, y `API_BASE_URL=http://127.0.0.1:8000`. No contiene secretos. El modelo se elegirá al integrar Groq; todavía no es necesario crear un `.env` real.
- **Comprobaciones realizadas:** sincronización correcta con Python 3.14.2; importación de las seis dependencias; exclusión de credenciales, entorno y datos; confirmación de que `.env.example` y los CSV de pruebas siguen siendo versionables.
- **Límite de esta etapa:** todavía no se ha creado la API, el agente ni la suite de pruebas. No se han hecho llamadas a Groq.

Comprobación de las dependencias:

```bash
uv sync --locked
uv run --locked python -c "import fastapi, uvicorn, openai, dotenv, pytest, httpx"
```

Las etapas siguientes usarán `uv run` para ejecutar Python, pytest y Uvicorn dentro del entorno del proyecto. La integración real de la etapa 8 requerirá una clave y un modelo válidos de Groq; si no están disponibles, se indicará expresamente que esa comprobación queda pendiente.

### Etapa 2: persistencia CSV y consulta

- `api/app.py` expone `GET /inventory`: devuelve HTTP 200 con los productos, o una lista vacía si el CSV no existe, está vacío o solo contiene la cabecera. Consultar el inventario no crea ni modifica el archivo.
- El CSV usa la cabecera `id,name,quantity,unit`. Cada producto tiene un ID entero positivo y único, un nombre y una unidad no vacíos, y una cantidad numérica finita mayor o igual a cero. Se permiten cantidades fraccionarias y productos con el mismo nombre pero distinto ID.
- La ruta de `products.csv` se resuelve desde la raíz del proyecto, independientemente del directorio de trabajo. Los IDs se leen del archivo, sin renumerarlos.
- Un CSV inválido, una codificación incorrecta o un error de lectura devuelve HTTP 500 con un mensaje descriptivo. No se omiten filas inválidas ni se sobrescriben datos para ocultar el error.
- La función de escritura usa el módulo estándar `csv` y reemplaza el archivo mediante un temporal en el mismo directorio. Si el reemplazo falla, conserva el inventario anterior y elimina el temporal. La etapa 3 reutiliza esta función para crear productos.
- **Comprobaciones realizadas:** 23 pruebas con archivos temporales: inventario inexistente o vacío, lectura con IDs estables desde dos clientes independientes, datos inválidos y duplicados, errores de lectura, escritura y lectura de campos con comas, comillas y saltos de línea, conservación del CSV ante un fallo de escritura y ruta independiente del directorio de trabajo. No se han utilizado datos reales.
- **Límite de esta etapa:** todavía no existen `POST`, `PATCH`, alertas ni agente. La prueba de reinicio del servidor real forma parte de la integración final.

Comprobación de esta etapa desde la raíz del proyecto:

```bash
uv run --locked python -m pytest tests/test_inventory.py -q
```

Para consultar manualmente la API:

```bash
uv run --locked uvicorn api.app:app --reload
```

El inventario estará disponible en `http://127.0.0.1:8000/inventory` y la documentación interactiva en `http://127.0.0.1:8000/docs`. En esta etapa, un repositorio sin `products.csv` devuelve `[]`.

### Etapa 3: alta de productos

- `POST /inventory` acepta un objeto JSON con `name`, `quantity` y `unit`, y devuelve HTTP 201 con el producto creado, incluyendo su `id`.
- El nombre y la unidad son textos obligatorios; se eliminan los espacios al principio y al final y se rechazan valores vacíos. La cantidad debe ser un número finito mayor o igual a cero: se permiten fracciones, pero no booleanos ni números enviados como texto. No se admiten campos adicionales ni IDs proporcionados por el cliente. Las entradas inválidas devuelven HTTP 422 sin modificar ni crear el CSV.
- El nuevo ID es uno más que el mayor ID existente; el primer producto recibe el ID 1. No se renumeran los productos anteriores y se permiten nombres repetidos con IDs distintos. El ID se calcula desde el CSV en cada alta, no desde un contador en memoria.
- El ciclo de leer, asignar ID y guardar se protege con un bloqueo dentro del proceso. La API debe ejecutarse con **un solo worker**; este bloqueo no coordina varios procesos o servidores escribiendo en el mismo CSV. Las consultas leen el archivo anterior o el nuevo gracias al reemplazo atómico.
- Si el CSV está dañado o falla el guardado, se devuelve HTTP 500 con un mensaje descriptivo. No se confirma una creación antes de que se guarde el archivo, y los datos anteriores se conservan ante un fallo de reemplazo.
- **Comprobaciones realizadas:** 50 pruebas en total, incluidas las 23 de la etapa anterior. Las nuevas cubren validación, cantidades fraccionarias y cero, altas sobre un archivo vacío, nombres repetidos, IDs no consecutivos, 12 altas concurrentes, lectura y siguiente alta desde un proceso Python nuevo, y errores de lectura o escritura sin pérdida de datos. Todos los CSV utilizados son temporales.
- **Límite de esta etapa:** todavía no existen `PATCH`, alertas ni agente. La comprobación del proceso nuevo usa FastAPI TestClient; el reinicio de Uvicorn se verificará en la integración final.

Comprobación desde la raíz del proyecto:

```bash
uv run --locked python -m pytest tests/test_inventory.py -q
```

### Etapa 4: actualización de stock y alertas

- `PATCH /inventory/{product_id}` acepta `{"delta": número}` y devuelve HTTP 200 con el producto actualizado. Un delta positivo aumenta el stock y uno negativo lo reduce; cero es válido. El stock final debe ser finito y no negativo.
- El delta debe ser un número JSON finito, no un booleano ni texto; no se aceptan campos adicionales. El ID del path debe ser positivo. Una solicitud inválida o un stock final negativo/no finito devuelve HTTP 422 sin modificar el CSV. Un ID inexistente devuelve HTTP 404.
- `GET /inventory/alerts` devuelve los productos cuya cantidad sea **estrictamente menor** que `threshold`, que por defecto es 10. El umbral configurable debe ser finito y no negativo; una cantidad exactamente igual al umbral no genera alerta.
- Ambas escrituras (alta y ajuste de stock) usan el mismo bloqueo durante la lectura, modificación y reemplazo atómico del CSV. Esto evita perder actualizaciones concurrentes dentro del proceso; el servidor sigue requiriendo **un solo worker**, ya que el bloqueo no coordina procesos distintos.
- Los errores de lectura o guardado mantienen la respuesta HTTP 500 descriptiva ya establecida y no descartan los datos anteriores. Consultar alertas no crea ni modifica el archivo.
- **Comprobaciones realizadas:** 77 pruebas en total, incluidas las 50 anteriores. Las nuevas cubren deltas positivos, negativos y cero; ID inexistente; stock negativo y desbordamiento sin modificar datos; payloads inválidos; fallos de guardado; 12 ajustes concurrentes; umbral predeterminado y personalizado, frontera estricta, valores inválidos y CSV corrupto. Todas usan CSV temporales.
- **Límite de esta etapa:** no se han añadido tools, agente ni registro de conversaciones. La concurrencia entre procesos queda fuera de alcance.

Comprobación desde la raíz del proyecto:

```bash
uv run --locked python -m pytest tests/test_inventory.py -q
```

### Etapa 5: tools y conexión HTTP

- `agent.py` define cuatro tools con el formato de funciones de OpenAI-compatible APIs: `list_inventory`, `create_product`, `adjust_stock` y `list_inventory_alerts`. Cada una tiene nombre, descripción y schema JSON tipado, con campos requeridos y propiedades adicionales prohibidas.
- `dispatch_tool(tool_name, arguments)` solo permite las cuatro operaciones declaradas y construye rutas fijas. Convierte el ID y `delta` de `adjust_stock` en path y body; envía el umbral de alertas como query opcional. Argumentos faltantes, desconocidos o un ID inválido se devuelven como un resultado JSON de error.
- La URL se lee de `API_BASE_URL`, con fallback a `http://127.0.0.1:8000`; el cliente HTTP de producción usa timeout de 5 segundos. La función devuelve la respuesta de la API en JSON y convierte errores HTTP, timeout o conexión caída en resultados de error que luego podrán añadirse al historial del LLM.
- **Comprobaciones realizadas:** 17 pruebas aisladas con `httpx.MockTransport`; schemas, mapeo de método/ruta/query/body, argumentos inválidos, valor predeterminado del umbral y errores HTTP/de transporte. No se realizaron llamadas de red ni a un LLM real.
- **Límite al cerrar esta etapa:** todavía no incluía el cliente Groq, el historial, el bucle ni la CLI; se añadieron en la etapa 6.

Comprobación desde la raíz del proyecto:

```bash
uv run --locked python -m pytest tests/test_agent.py -q
```

### Etapa 6: bucle manual y CLI

- `create_llm_client()` configura el SDK de OpenAI con el endpoint compatible de Groq, usando `GROQ_API_KEY` y `GROQ_MODEL` del entorno o `.env`. La clave nunca se imprime. `AGENT_MAX_ITERATIONS` configura el límite de rondas de tools y toma el valor 8 si no se especifica.
- Antes de mostrar el prompt, `agent.py` consulta `GET /inventory`; si la API responde con error, no está disponible o vence el timeout, la CLI termina con un mensaje y código de salida no exitoso.
- `run_agent_turn()` conserva los mensajes de la sesión, envía el historial y las tools al LLM, ejecuta todas las tools solicitadas y devuelve cada resultado con el `tool_call_id` correspondiente antes de pedir la siguiente respuesta. Cuando el modelo responde sin llamadas pendientes, termina el turno y devuelve su texto.
- Las llamadas con JSON inválido reciben un resultado de error asociado a su ID; errores del proveedor y el límite de iteraciones terminan el turno de forma controlada. La CLI acepta mensajes hasta `/exit` y cierra limpiamente ante EOF o Ctrl+C.
- **Comprobaciones realizadas:** 41 pruebas del agente y 118 pruebas en la suite completa. Incluyen un LLM simulado para respuesta final, una tool, llamadas múltiples y el flujo de alta seguido de alertas; historial y `tool_call_id`; límite de rondas, JSON inválido y errores de proveedor/tool/API; configuración Groq; CLI, EOF y salida. No se hicieron llamadas reales a Groq ni a la API desde estas pruebas.
- **Límite de esta etapa:** `GROQ_API_KEY` no estaba establecida en la terminal revisada. La prueba real con un modelo y una API iniciados se mantiene para la etapa 8. El registro CSV de conversaciones queda para la etapa 7.

Configuración y ejecución:

```bash
cp .env.example .env
# Completar GROQ_API_KEY y GROQ_MODEL en .env
uv run --locked python agent.py
```

Opcionalmente, añade `AGENT_MAX_ITERATIONS=8` a `.env` para ajustar el límite. El ciclo está implementado manualmente, sin frameworks de agentes.

### Etapa 7: registro persistente de conversación

- `conversation_log.csv` se crea en la raíz del proyecto al registrar el primer evento. La cabecera única y el orden de columnas son `actor,message,tool_call,timestamp`.
- Cada turno registra el mensaje `user`, la respuesta `agent`, cada llamada de tool como `agent` y cada resultado como `tool`. `tool_call` contiene el nombre de la tool cuando corresponde y queda vacío en otros eventos.
- Los timestamps se generan en UTC con formato ISO 8601 y zona explícita. El módulo estándar `csv` preserva Unicode, comas, comillas y saltos de línea dentro de los campos.
- El archivo se abre en modo de adición; se valida una cabecera existente y nunca se reemplazan las filas previas. Un bloqueo serializa escrituras dentro del proceso. Si la escritura falla, el turno se detiene con un error en vez de continuar silenciosamente sin registro.
- La CLI inyecta el escritor real en el bucle. Las pruebas de `run_agent_turn()` pueden inyectar un escritor en memoria y las pruebas del CSV usan exclusivamente archivos en directorios temporales.
- **Comprobaciones realizadas:** pruebas para cabecera/campos, timestamps UTC, eventos de varias sesiones, escaping de valores, cabecera inválida, errores de escritura y el orden de eventos de una conversación con tool call. También se comprueba que una llamada malformada se registra antes de devolver su error.
- **Límite de esta etapa:** no se registra actividad de varios procesos concurrentes. La interacción real con Groq y la persistencia tras sesiones CLI reales se comprobarán en la etapa 8.

Comprobación desde la raíz del proyecto:

```bash
uv run --locked python -m pytest tests/test_logging.py tests/test_agent.py -q
```

### Etapa 8: integración y entrega

- `README.es.md` y `README.md` describen instalación con UV, configuración local de Groq, arranque de API y agente en terminales separadas, endpoints, pruebas y el requisito de un solo worker.
- **Comprobaciones locales:** `uv sync --locked` terminó correctamente y las 131 pruebas pasaron. Uvicorn arrancó en el puerto documentado; `GET /inventory`, `GET /inventory/alerts` y `GET /openapi.json` respondieron HTTP 200.
- **Integración real:** con `openai/gpt-oss-120b`, dos procesos CLI y un servidor Uvicorn reiniciado entre sesiones, el agente creó un producto y consultó las alertas bajo 10 unidades. Tras el reinicio, el producto persistía; la segunda sesión añadió filas al log sin reemplazar las anteriores.
- **Aislamiento:** productos y log de esta prueba se escribieron en un directorio temporal que se eliminó al terminar. No se crearon ni versionaron CSV de ejecución en el repositorio. La clave se leyó de la configuración local y no se imprimió.
- Para ejecutar la CLI fuera de la prueba, configura `GROQ_MODEL=openai/gpt-oss-120b` en `.env`, además de `GROQ_API_KEY`.

Comprobación local:

```bash
uv sync --locked
uv run --locked python -m pytest -q
```

## Qué debes hacer

### API (`api/app.py`)

- [x] Crear una aplicación FastAPI que almacene los datos de inventario en un fichero `products.csv`.
- [x] `GET /inventory` — Devolver la lista completa de productos.
- [x] `POST /inventory` — Añadir un nuevo producto (`name`, `quantity`, `unit`).
- [x] `PATCH /inventory/{product_id}` — Actualizar el stock de un producto existente (aceptar un valor `delta`: positivo para entradas de stock, negativo para salidas).
- [x] `GET /inventory/alerts` — Devolver todos los productos cuya cantidad esté por debajo de un umbral configurable (por defecto: 10 unidades).
- [x] Hacer que todos los endpoints devuelvan códigos de estado HTTP apropiados y mensajes descriptivos en caso de error.

### Agente (`agent.py`)

- [x] Definir los endpoints de la API como **tools** para el LLM; cada tool debe tener un `name`, una `description` y `parameters` tipados claramente.
- [x] Implementar el **bucle del agente** completo: Observar → Pensar → Actuar → Actualizar → Repetir.
- [x] Mantener el historial de conversación en memoria durante la sesión.
- [x] Cuando el LLM seleccione una tool, llamar al endpoint de la API correspondiente e inyectar el resultado de vuelta en el contexto.
- [x] Terminar el bucle de forma limpia cuando el LLM devuelva una respuesta final sin llamadas a tools pendientes.
- [x] Exponer una interfaz CLI sencilla: leer el input del usuario desde el terminal e imprimir la respuesta del agente.

### Registro de conversación

- [x] Añadir cada evento (mensaje del usuario, respuesta del agente, llamada a tool y resultado de tool) al fichero `conversation_log.csv`.
- [x] Incluir los cuatro campos requeridos en el CSV: `actor`, `message`, `tool_call`, `timestamp`.
- [x] Hacer que el fichero persista entre sesiones (solo adición; nunca sobreescribir).

### General

- [x] Asegurarse de que la API esté en ejecución antes de iniciar el agente. Documentar en el README cómo arrancar ambos procesos.
- [x] **No usar frameworks de agentes** (LangChain, LlamaIndex, AutoGen, etc.). Implementar el bucle manualmente en Python.

## Qué vamos a evaluar

- [x] La FastAPI expone los cuatro endpoints requeridos y devuelve respuestas correctas.
- [x] Los productos persisten en `products.csv` y sobreviven al reinicio del servidor.
- [x] El bucle del agente implementa correctamente el ciclo Observar → Pensar → Actuar → Actualizar → Repetir.
- [x] Las tools están definidas con nombres, descripciones y parámetros tipados que el LLM puede utilizar de forma fiable.
- [x] El agente llama al endpoint de la API correcto cuando el LLM selecciona una tool.
- [x] El resultado del LLM se inyecta de vuelta en el historial de conversación antes de la siguiente iteración.
- [x] `conversation_log.csv` se crea y se completa con los cuatro campos en cada evento.
- [x] El registro es de solo adición entre varias sesiones.
- [x] El agente gestiona una interacción real de varios pasos: alta de producto y consulta de alertas.
- [x] No se utiliza ningún framework de agentes: el bucle está codificado a mano en Python.

> El diseño de interfaz y la presentación visual no se evalúan. Una interfaz de terminal es suficiente.

## Contrato de datos del registro

Cada fila de `conversation_log.csv` debe incluir:

| Campo | Descripción |
|---|---|
| `actor` | `user`, `agent` o `tool` |
| `message` | Texto del mensaje o resultado del evento |
| `tool_call` | Nombre de la tool llamada; vacío si no aplica |
| `timestamp` | Fecha y hora del evento en formato ISO 8601 |

El log es **append-only**: cada sesión añade filas sin borrar las anteriores.

## Puesta en marcha indicada por 4Geeks

Mantener dos terminales abiertas:

```bash
# Terminal 1 — API
uv run --locked uvicorn api.app:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — agente
uv run --locked python agent.py
```

Instalar dependencias con:

```bash
uv add fastapi uvicorn openai python-dotenv
```

Crear `.env` en la raíz para la clave del proveedor LLM (el README oficial usa `GROQ_API_KEY`) y excluirlo de Git desde el inicio. **Nunca subir `.env` ni credenciales al repositorio.**

La entrega debe incluir como mínimo `api/app.py`, `agent.py` y una nota breve en el README que explique cómo arrancar ambos procesos.
