## Installation

To get started with the server, you first need to install `uv`.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then, sync the dependencies, and activate the virtual environment:

```bash
uv sync
source .venv/bin/activate
```

## Run (FastAPI)

From this `server/` directory (where `main.py` lives), run the API with Uvicorn via `uv run`:

```bash
uv run uvicorn main:app --reload
```

If you've activated the venv (`source .venv/bin/activate`), you can also run:

```bash
uvicorn main:app --reload
```

If you want it accessible on your LAN:

```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
