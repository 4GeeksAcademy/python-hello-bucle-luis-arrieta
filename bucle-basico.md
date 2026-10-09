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

## Qué debes hacer

### API (`api/app.py`)

- [ ] Crear una aplicación FastAPI que almacene los datos de inventario en un fichero `products.csv`.
- [ ] `GET /inventory` — Devolver la lista completa de productos.
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
