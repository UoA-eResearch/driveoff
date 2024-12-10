# API server for offboarding

## Setting a mode
By default, the API server runs in development mode. To change to production mode and use production env variables (e.g. API keys, etc), set `MODE=production`. e.g.:

```
MODE=production fastapi run src/api/main.py
```