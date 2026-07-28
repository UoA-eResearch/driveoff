## Running tests

This project uses `uv` to manage Python dependencies and the test dependencies are declared in the project's `pyproject.toml`.

Recommended (uv)
- Install uv (if not already installed):
	- `pip install uv`  (or follow uv's official installer)
- Install dependencies including the dev and test groups:
	- `uv sync --group dev --group test`
- Run the test suite:
	- `uv run pytest -q`
- Run tests with coverage:
	- `uv run pytest --cov=src tests`

Running individual tests
- Run a single test file:
	- `uv run pytest tests/test_submission_api.py -q`
- Run a single test case by nodeid:
	- `uv run pytest tests/test_submission_api.py::test_some_name -q`

Notes
- pytest is configured via `pyproject.toml` with `pythonpath = "src tests"` so running `pytest` from the repository root should discover tests automatically.
