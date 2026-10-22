# Data Pipeline Template

## Stack
- Language: Python 3.12
- Orchestration: Scheduled tasks (cron / admin console scheduler)
- Data: pandas / polars for processing, asyncpg for DB access
- Storage: PostgreSQL data warehouse, file exports to shared drive

## Project Structure
```
pipeline-name/
├── src/
│   ├── extract/        # Data source connectors
│   ├── transform/      # Processing logic
│   ├── load/           # Destination writers
│   ├── utils/          # Shared utilities
│   ├── config.py       # Configuration
│   └── main.py         # Pipeline entry point
├── tests/
├── pyproject.toml
├── Dockerfile
└── README.md
```

## Design Principles
- Idempotent execution (safe to re-run)
- Checkpointing for long-running pipelines
- Structured logging with correlation IDs
- Error handling with retry + dead-letter queue
- Data validation at boundaries (input/output)
- Classification-aware: respect data classification levels

## Data Classification Rules
- PUBLIC: No restrictions on processing
- INTERNAL: Log access, restrict output destinations
- CONFIDENTIAL: Encrypt at rest, audit all access
- STRICTLY_CONFIDENTIAL: Isolated processing, no bulk export
