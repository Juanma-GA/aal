# Web Application Template

## Stack
- Frontend: React 18 + TypeScript + Vite 6
- Styling: Tailwind CSS 4 + shadcn/ui
- State: Zustand
- Backend: FastAPI + SQLAlchemy 2.0 async
- Database: PostgreSQL 16
- Auth: Keycloak OIDC

## Project Structure
```
project-name/
├── frontend/
│   ├── src/
│   │   ├── components/     # Reusable UI components
│   │   ├── pages/          # Page-level components
│   │   ├── services/       # API client layer
│   │   ├── stores/         # Zustand stores
│   │   ├── hooks/          # Custom React hooks
│   │   └── types/          # TypeScript types
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.ts
├── backend/
│   ├── app/
│   │   ├── api/            # Route handlers
│   │   ├── db/             # Models + session
│   │   ├── services/       # Business logic
│   │   ├── auth/           # OIDC integration
│   │   ├── config.py       # Settings
│   │   └── main.py         # FastAPI app
│   ├── pyproject.toml
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## Security Checklist
- [ ] OIDC authentication configured
- [ ] CORS restricted to known origins
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (React default escaping)
- [ ] CSRF protection
- [ ] Rate limiting on sensitive endpoints
- [ ] Secrets in environment variables, not code
