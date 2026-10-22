# API Service Template

## Stack
- Runtime: Python 3.12 / .NET 8 / Node.js 20
- Framework: FastAPI / ASP.NET Core / Express
- Auth: Keycloak OIDC + API key support
- Database: PostgreSQL 16 (if persistent state needed)
- Caching: Redis (if applicable)

## Project Structure
```
service-name/
├── app/
│   ├── api/            # Route handlers (versioned: /v1/)
│   ├── models/         # Data models / DTOs
│   ├── services/       # Business logic
│   ├── middleware/     # Auth, logging, rate limiting
│   ├── config.py       # Settings
│   └── main.py         # App entry
├── tests/
├── pyproject.toml
├── Dockerfile
└── README.md
```

## API Design Rules
- RESTful endpoints with proper HTTP methods
- JSON request/response bodies
- Pagination for list endpoints (limit/offset)
- Consistent error format: `{"detail": "message", "code": "ERROR_CODE"}`
- API versioning via URL prefix (/api/v1/)
- OpenAPI/Swagger documentation auto-generated

## Security Requirements
- Bearer token auth (Keycloak) or API key
- Rate limiting per client
- Input validation (Pydantic models)
- No sensitive data in logs
- HTTPS only in production
