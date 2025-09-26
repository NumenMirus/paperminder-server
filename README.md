# PaperMinder Server

FastAPI-based websocket service that allows PaperMinder clients to subscribe to personalized message streams.

## Development

Use [uv](https://docs.astral.sh/uv/) or your preferred tool to install dependencies. To install with uv:
```bash
uv sync --extra dev
```

### Run the app locally
```bash
uv run uvicorn src.main:app --reload
```

### Execute the tests
```bash
uv run pytest
```
