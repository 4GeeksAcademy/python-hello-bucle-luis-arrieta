# Agente de inventario para cafeterías

API FastAPI con persistencia CSV y un agente CLI que consulta y modifica el inventario mediante tools.

## Requisitos

- Python 3.11 o posterior.
- [uv](https://docs.astral.sh/uv/).
- Una clave de API de Groq y un modelo disponible en tu cuenta.

## Instalación y configuración

Desde la raíz del proyecto:

```bash
uv sync --locked
cp .env.example .env
```

Edita `.env` y configura `GROQ_API_KEY` y `GROQ_MODEL=openai/gpt-oss-120b` (modelo verificado con este agente; comprueba que siga disponible en tu cuenta). `API_BASE_URL` usa `http://127.0.0.1:8000` por defecto. Para limitar las rondas de tools, puedes añadir `AGENT_MAX_ITERATIONS=8`.

No subas `.env` ni credenciales al repositorio. El archivo está excluido de Git.

## Ejecución

Abre dos terminales desde la raíz del proyecto.

Terminal 1, API:

```bash
uv run --locked uvicorn api.app:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2, agente:

```bash
uv run --locked python agent.py
```

El agente comprueba que la API responde antes de iniciar la conversación. Escribe `/exit` para cerrar la CLI. Los eventos se añaden a `conversation_log.csv`; los productos se guardan en `products.csv`.

## API y pruebas

- `GET /inventory`: lista productos.
- `POST /inventory`: crea un producto.
- `PATCH /inventory/{product_id}`: ajusta el stock con `delta`.
- `GET /inventory/alerts?threshold=10`: consulta productos bajo el umbral.
- Documentación interactiva: `http://127.0.0.1:8000/docs`.

Ejecuta las pruebas con:

```bash
uv run --locked python -m pytest -q
```

La API CSV debe ejecutarse con un solo worker; su bloqueo de escritura no coordina varios procesos.

## Créditos de la plantilla

Este proyecto comenzó con la plantilla Python Hello de 4Geeks, creada como parte de los [recursos de Python de 4Geeks](https://4geeks.com/es/technology/python) por [Alejandro Sanchez](https://twitter.com/alesanchezr) y [otros contribuidores](https://github.com/4GeeksAcademy/python-hello/graphs/contributors).
