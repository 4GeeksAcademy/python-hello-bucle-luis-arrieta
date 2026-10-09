# Bucle Básico de Agente de Inventario con IA

## Auditoría del repositorio y la fuente

- **Cohorte:** Backend development with Coding Agents (ID `1670`).
- **Proyecto en 4Geeks:** AI basic Inventory Agent Loop (tarea `997546`; slug `ai-basic-inventory-agent-loop`).
- **Repositorio auditado:** [python-hello-bucle-luis-arrieta](https://github.com/4GeeksAcademy/python-hello-bucle-luis-arrieta).
- El repositorio contiene actualmente el boilerplate básico de Python Hello: los README solo indican cómo empezar con `main.py`. No documentan ni implementan los requisitos de este proyecto.
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
| 2 | Persistencia CSV y `GET /inventory` | Pruebas de inventario vacío, lectura e IDs estables | Verificada; cierre mediante commit y push |
| 3 | `POST /inventory` | Pruebas de creación, validación y persistencia | Pendiente |
| 4 | Actualización de stock y alertas | Pruebas de deltas, errores y umbral configurable | Pendiente |
| 5 | Definición de tools y conexión HTTP | Pruebas de schemas, rutas, parámetros y errores | Pendiente |
| 6 | Bucle manual y CLI con Groq | Pruebas con LLM simulado, varias tools y salida limpia | Pendiente |
| 7 | Registro de conversación | Pruebas del formato CSV y adición entre sesiones | Pendiente |
| 8 | Integración real y documentación de entrega | Suite completa y flujo real con Groq, incluyendo reinicios | Pendiente |

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
- La función de escritura usa el módulo estándar `csv` y reemplaza el archivo mediante un temporal en el mismo directorio. Si el reemplazo falla, conserva el inventario anterior y elimina el temporal. Esta función queda preparada para la etapa 3, sin exponer todavía endpoints de modificación.
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

## Qué debes hacer

### API (`api/app.py`)

- [ ] Crear una aplicación FastAPI que almacene los datos de inventario en un fichero `products.csv`.
- [x] `GET /inventory` — Devolver la lista completa de productos.
- [ ] `POST /inventory` — Añadir un nuevo producto (`name`, `quantity`, `unit`).
- [ ] `PATCH /inventory/{product_id}` — Actualizar el stock de un producto existente (aceptar un valor `delta`: positivo para entradas de stock, negativo para salidas).
- [ ] `GET /inventory/alerts` — Devolver todos los productos cuya cantidad esté por debajo de un umbral configurable (por defecto: 10 unidades).
- [ ] Hacer que todos los endpoints devuelvan códigos de estado HTTP apropiados y mensajes descriptivos en caso de error.

### Agente (`agent.py`)

- [ ] Definir los endpoints de la API como **tools** para el LLM; cada tool debe tener un `name`, una `description` y `parameters` tipados claramente.
- [ ] Implementar el **bucle del agente** completo: Observar → Pensar → Actuar → Actualizar → Repetir.
- [ ] Mantener el historial de conversación en memoria durante la sesión.
- [ ] Cuando el LLM seleccione una tool, llamar al endpoint de la API correspondiente e inyectar el resultado de vuelta en el contexto.
- [ ] Terminar el bucle de forma limpia cuando el LLM devuelva una respuesta final sin llamadas a tools pendientes.
- [ ] Exponer una interfaz CLI sencilla: leer el input del usuario desde el terminal e imprimir la respuesta del agente.

### Registro de conversación

- [ ] Añadir cada evento (mensaje del usuario, respuesta del agente, llamada a tool y resultado de tool) al fichero `conversation_log.csv`.
- [ ] Incluir los cuatro campos requeridos en el CSV: `actor`, `message`, `tool_call`, `timestamp`.
- [ ] Hacer que el fichero persista entre sesiones (solo adición; nunca sobreescribir).

### General

- [ ] Asegurarse de que la API esté en ejecución antes de iniciar el agente. Documentar en el README cómo arrancar ambos procesos.
- [ ] **No usar frameworks de agentes** (LangChain, LlamaIndex, AutoGen, etc.). Implementar el bucle manualmente en Python puro.

## Qué vamos a evaluar

- [ ] La FastAPI expone los cuatro endpoints requeridos y devuelve respuestas correctas.
- [ ] Los productos persisten en `products.csv` y sobreviven al reinicio del servidor.
- [ ] El bucle del agente implementa correctamente el ciclo Observar → Pensar → Actuar → Actualizar → Repetir.
- [ ] Las tools están definidas con nombres, descripciones y parámetros tipados que el LLM puede utilizar de forma fiable.
- [ ] El agente llama al endpoint de la API correcto cuando el LLM selecciona una tool.
- [ ] El resultado del LLM se inyecta de vuelta en el historial de conversación antes de la siguiente iteración.
- [ ] `conversation_log.csv` se crea y se completa con los cuatro campos en cada evento.
- [ ] El registro es de solo adición entre varias sesiones.
- [ ] El agente gestiona al menos una interacción de varios pasos (por ejemplo, añadir un producto y preguntar inmediatamente por las alertas).
- [ ] No se utiliza ningún framework de agentes: el bucle está codificado a mano en Python.

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
uvicorn api.app:app --reload

# Terminal 2 — agente
python agent.py
```

Instalar dependencias con:

```bash
uv add fastapi uvicorn openai python-dotenv
```

Crear `.env` en la raíz para la clave del proveedor LLM (el README oficial usa `GROQ_API_KEY`) y excluirlo de Git desde el inicio. **Nunca subir `.env` ni credenciales al repositorio.**

La entrega debe incluir como mínimo `api/app.py`, `agent.py` y una nota breve en el README que explique cómo arrancar ambos procesos.
