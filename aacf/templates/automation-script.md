# Automation Script Template

## Stack
- Language: Python 3.12 / PowerShell 7 / Bash
- Scheduling: Admin console scheduled tasks
- Logging: Structured JSON to stdout (captured by scheduler)

## Project Structure
```
script-name/
├── src/
│   ├── main.py         # Entry point
│   ├── config.py       # Configuration from env
│   └── utils.py        # Shared utilities
├── tests/
├── pyproject.toml      # (if Python)
└── README.md
```

## Guidelines
- Single responsibility: one script = one task
- Idempotent: safe to re-run without side effects
- Exit codes: 0 = success, 1 = error, 2 = warning
- Structured output: JSON to stdout for downstream processing
- No hardcoded credentials: use env vars or Keycloak service accounts
- Timeout: define max execution time in scheduler config
- Alerting: emit error events that trigger admin console alerts

## Approval
- T1: Self-service (local only)
- T2+: Requires IS review before scheduling
