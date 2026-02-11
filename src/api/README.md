# API server for offboarding

A FastAPI-based REST API server for managing project offboarding and archival workflows.

## Quick start

### Prerequisites
- Python 3.8+
- FastAPI and Uvicorn (see [Installation](#installation))

### Installation

1. **Install dependencies** from the project root:
   ```bash
   poetry install
   ```
   This installs the `driveoff` package and all required dependencies including FastAPI.

2. **Set up API keys** (see [API Key Setup](#api-key-setup) below)

3. **Run the server** in development mode:
   ```bash
   poetry run fastapi dev src/api/main.py
   ```
   The server will start on `http://localhost:8000` by default.

## API Key Setup

The API server uses API keys for authentication and access control. Each key is associated with specific HTTP actions (GET, POST, PUT).

### Creating the API keys file

1. **Create the configuration directory** in your home folder:
   ```powershell
   $dir = Join-Path $env:USERPROFILE ".driveoff"
   New-Item -ItemType Directory -Force -Path $dir
   ```

2. **Create `api_keys.json`** in the `.driveoff` directory with your API keys:
   ```json
   {
     "keys": [
       {
         "value": "your-api-key-here",
         "actions": ["GET", "POST", "PUT"]
       }
     ]
   }
   ```

   **For development/PoC**, you can generate a random key using PowerShell:
   ```powershell
   $key = [guid]::NewGuid().ToString()
   $dir = Join-Path $env:USERPROFILE ".driveoff"
   @"
   {
     "keys": [
       {
         "value": "$key",
         "actions": ["GET", "POST", "PUT"]
       }
     ]
   }
   "@ | Out-File -Encoding utf8 -FilePath (Join-Path $dir "api_keys.json")
   Write-Output "API key created: $key"
   ```

   **For production**, generate a secure random key using Python:
   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Then manually add it to your `api_keys.json` file.

3. **Verify** the file is valid JSON and located at:
   ```
   C:\Users\<YourUsername>\.driveoff\api_keys.json
   ```

### Using API keys

Include your API key in requests using either:

- **Query parameter:**
  ```bash
  curl "http://localhost:8000/api/endpoint?api-key=your-api-key-here"
  ```

- **HTTP header:**
  ```bash
  curl -H "x-api-key: your-api-key-here" http://localhost:8000/api/endpoint
  ```

## Running the server

### Development mode (default)
```bash
fastapi dev src/api/main.py
```

The server runs with auto-reload enabled, restarting when code changes are detected.

### Production mode
To run in production mode with production environment variables and settings:
```bash
MODE=production fastapi run src/api/main.py
```

When `MODE=production` is set, ensure your production `api_keys.json` is properly configured with secure keys.

## Project structure

```
src/api/
├── main.py           # FastAPI application entry point
├── security.py       # API key validation and authentication
├── manifests.py      # Manifest-related endpoints
├── cors.py           # CORS configuration
├── fake_resdrive.py  # Mock resource drive responses
└── README.md         # This file
```

## Development tips

- **Auto-reload:** Changes to `.py` files trigger automatic server restart (development mode only)
- **Interactive API docs:** Visit `http://localhost:8000/docs` for Swagger UI
- **Alternative docs:** Visit `http://localhost:8000/redoc` for ReDoc
- **Debug mode:** Check FastAPI logs in the terminal for request/response details

## Troubleshooting

### "API key path is not a valid JSON file" error
- Verify the file exists at `C:\Users\<YourUsername>\.driveoff\api_keys.json`
- Ensure the file contains valid JSON (no trailing commas, proper quotes)
- Check file encoding is UTF-8

### "Invalid or missing API Key" error
- Verify you're including the correct API key in your request
- Check that the key exists in your `api_keys.json` file
- Confirm the request includes the key via query parameter or `x-api-key` header

### Server fails to start
- Ensure FastAPI and dependencies are installed: `poetry install`
- Check that port 8000 is not already in use (change with `--port` flag if needed)
- Review error messages in the terminal output