# Internal Tool Template

## Stack
- Backend: Python 3.12 + FastAPI (or CLI with Click/Typer)
- Frontend (if UI needed): React 18 + Vite
- Auth: Keycloak SSO
- Deployment: Docker container on shared infrastructure

## Project Structure
```
tool-name/
├── app/
│   ├── core/           # Core tool logic
│   ├── api/            # API endpoints (if web-based)
│   ├── cli/            # CLI commands (if CLI-based)
│   ├── config.py       # Configuration
│   └── main.py         # Entry point
├── tests/
├── pyproject.toml
├── Dockerfile
└── README.md
```

## Requirements
- Must be registered in the AI Tool Registry before deployment
- Risk assessment completed (auto-detected from capabilities)
- Training completed by all intended users
- IS review for elevated/high risk tools

## Deployment Path
- T1: Local developer machine only
- T2: Shared VM (IT provisions, IS deploys)
- T3: Dedicated VM with DW access
- T4: Production infrastructure (IS + IT joint)
