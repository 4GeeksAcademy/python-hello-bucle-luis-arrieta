# Coffee Shop Inventory Agent

A FastAPI inventory API with CSV persistence and a CLI agent that reads and updates stock through tools.

## Requirements

- Python 3.11 or later.
- [uv](https://docs.astral.sh/uv/).
- A Groq API key and a model available to your account.

## Install and configure

From the project root:

```bash
uv sync --locked
cp .env.example .env
```

Set `GROQ_API_KEY` and `GROQ_MODEL=openai/gpt-oss-120b` in `.env` (model verified with this agent; check that it remains available to your account). `API_BASE_URL` defaults to `http://127.0.0.1:8000`. Optionally set `AGENT_MAX_ITERATIONS=8` to limit tool rounds.

Never commit `.env` or credentials. Git ignores the local environment file.

## Run

Open two terminals in the project root.

Terminal 1, API:

```bash
uv run --locked uvicorn api.app:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2, agent:

```bash
uv run --locked python agent.py
```

The agent checks that the API responds before starting the conversation. Enter `/exit` to leave the CLI. Events append to `conversation_log.csv`; products persist in `products.csv`.

## API and tests

- `GET /inventory`: list products.
- `POST /inventory`: create a product.
- `PATCH /inventory/{product_id}`: adjust stock with `delta`.
- `GET /inventory/alerts?threshold=10`: list products below the threshold.
- Interactive API docs: `http://127.0.0.1:8000/docs`.

Run tests with:

```bash
uv run --locked python -m pytest -q
```

Run the CSV-backed API with one worker; its write lock does not coordinate multiple processes.

## Template credits

This project started from the 4Geeks Python Hello template, created as part of [4Geeks Python Resources](https://4geeks.com/technology/python) by [Alejandro Sanchez](https://twitter.com/alesanchezr) and [other contributors](https://github.com/4GeeksAcademy/python-hello/graphs/contributors).
