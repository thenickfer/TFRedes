# TFRedes

Boilerplate Python project using a `src/` layout, `pyproject.toml`, and Docker.

## Project Structure

```text
TFRedes/
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── LICENSE
├── README.md
├── pyproject.toml
├── src/
│   └── tfredes/
│       ├── __init__.py
│       ├── __main__.py
│       ├── config.py
│       └── main.py
└── tests/
    ├── __init__.py
    └── test_main.py
```

## Local Development

Using [`uv`](https://docs.astral.sh/uv/):

```bash
uv sync --dev
uv run tfredes
```

Or using standard `venv` + `pip`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m tfredes
```

### Tests & Linting

```bash
uv run pytest
uv run ruff check .
```

## Docker

Build and run the container:

```bash
docker build -t tfredes:latest .
docker run --rm --env-file .env.example tfredes:latest
```
