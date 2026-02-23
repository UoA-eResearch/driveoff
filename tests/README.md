## Running tests

This project uses Poetry to manage dependencies and the test dependencies are declared in the project's `pyproject.toml`.

Recommended (Poetry)
- Install Poetry (if not already installed):
	- `pip install poetry`  (or follow Poetry's official installer)
- Install dependencies including test groups:
	- `poetry install --with test --with dev`
- Run the test suite:
	- `poetry run pytest -q`
- Run tests with coverage:
	- `poetry run pytest --cov=src tests`

Running individual tests
- Run a single test file:
	- `poetry run pytest tests/test_submission_api.py -q`
- Run a single test case by nodeid:
	- `poetry run pytest tests/test_submission_api.py::test_some_name -q`

Notes
- pytest is configured via `pyproject.toml` with `pythonpath = "src tests"` so running `pytest` from the repository root should discover tests automatically.
