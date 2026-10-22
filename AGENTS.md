# AGENTS.md — AAL (Análisis de Apoyo Logístico)

Entrada para cualquier agente de código (Claude Code, Cursor, Copilot, Codex…), según el estándar
[`AGENTS.md`](https://agents.md). Los ficheros propios de cada herramienta (`CLAUDE.md`, …) apuntan
aquí y solo añaden lo específico de esa herramienta.

## ⚠️ El AACF tiene prioridad sobre este fichero

**El AACF tiene prioridad sobre este fichero.** Este proyecto sigue el *ATEXIS AI-Assisted Coding
Framework* (AACF), copiado en [`aacf/`](aacf/AGENTS.md) (`aacf/VERSION`; fecha y versión de la copia en
`CLAUDE.md`). Donde el AACF y este fichero (o `CLAUDE.md`) choquen, gana el AACF y se corrige este
fichero, salvo las **desviaciones documentadas** de abajo, que son decisiones explícitas del plan.

- **Hard Rules HR0–HR21** (`aacf/rules/atexis-hard-rules.md`): no negociables. Autocomprobar cada cambio.
- Antes de escribir código: `aacf/AGENTS.md`, `aacf/rules/` (`atexis-hard-rules.md`, `python.mdc`,
  `javascript.mdc`, `security.mdc`), `aacf/styles/design-system.md` y `ui-kit.md`,
  `aacf/governance/guardrails.md`.
- Golden path: checklist → implementación completa (sin stubs, `TODO` ni datos simulados) →
  verificación ejecutable → `code-reviewer` (y `security-reviewer` si toca seguridad).

## Qué es AAL

App web para em&e group que soporta el Análisis de Apoyo Logístico de un material del Ejército de
Tierra y genera los entregables del PALI desde una única base de datos. Plan completo:
[`docs/plan/AAL_Plan_Encargos_v0.3.md`](docs/plan/AAL_Plan_Encargos_v0.3.md) (decisiones D1–D15,
modelo de datos, reglas NT, encargos). Cada encargo tal como se entregó: [`docs/encargos/`](docs/encargos/).

## Stack (plantilla AACF `web-app`, D2)

- **Frontend** (raíz, `src/`): React 18 + TypeScript strict + Vite, Tailwind 4 + **shadcn/ui**
  (`components.json`, alias `@/`), **Zustand** para estado de UI global y **React Query** para estado
  de servidor, react-router, react-i18next.
- **Backend** (`backend/`): FastAPI + SQLAlchemy 2 async (asyncpg) + Alembic + PostgreSQL 16.
- Todo on-premise (RNF-03).

## Desviaciones documentadas respecto al AACF

1. **Autenticación propia JWT RS256 en lugar de Keycloak OIDC (D4).** Login email + contraseña
   (bcrypt), access token RS256 corto en memoria y refresh token revocable en cookie HttpOnly (E01).
   La validación del token es la misma que con un IdP (clave pública), así que **IT integrará al final
   el SSO + MFA corporativo sin tocar la autorización**. Desvía de `aacf/rules/security.mdc` y
   `aacf/templates/web-app.md`.
2. **HR11 opcional (D6).** Las reglas NT 10/17 son reglas deterministas de un catálogo configurable,
   no llamadas a un LLM.
3. **Stack de la plantilla AACF `web-app`, no el de brdp-manager.** De brdp-manager se toman la
   organización del repo, la verificación y el flujo de encargos, no su frontend en JS con CSS propio.
   **Zustand solo para estado de UI global, nunca persistido en el navegador** (sin middleware
   `persist`); **el estado de servidor va siempre con React Query**.

## Reglas de dominio

- La NT 10/17 manda sobre la S3000L.
- SNS de 6 caracteres alfanuméricos.
- Clave de posición física = SNS + CO + AL, más el CS (SNS_CS + CO_CS + AL_CS).
- QTY es por unidad del conjunto superior.
- La estructura física es un grafo, no un árbol.

## Datos reales del cliente (D13)

Los ficheros reales del cliente (NT "USO OFICIAL", CONFUNFIS con NOC reales…) van **solo** a
`private/`, ignorado por git (`git ls-files private/` → solo `private/README.md`). Los tests y la demo
usan **fixtures sintéticos** con la misma forma y anomalías. Un `verify-*` que necesite ficheros reales
y no los tenga sale con **código 2 ("NOT RUN")**, nunca 1.

## Estructura

```
src/                 frontend: pages, layouts, components/ui (shadcn), services, hooks, stores, i18n, lib, types, styles
public/brand/        logo em&e
scripts/             run-checks.mjs, run-js-tests.mjs, run-backend-tests.mjs, test-*.mjs, verify-*.mjs, lib/
backend/app/         api/routes, core, db, models, schemas, services
backend/alembic/     migraciones
backend/scripts/     create_test_db.py, check_test_db.py
backend/tests/       unit/, integration/ (con _testdb.py y conftest.py)
docs/                plan/, encargos/, instalacion/ (certificado corporativo, PowerShell), historial-cambios.md
aacf/                copia del framework
private/             IGNORADO: ficheros reales del cliente
```

Previstas y todavía sin crear (llegan con su encargo): `backend/app/repositories/`,
`backend/app/validacion/` (motor de reglas NT, E16), `backend/app/io_excel/` (plantillas NT/SIGLE,
E03), `backend/tests/security/` (E01), `backend/tests/fixtures/`.

## Cómo verificar

- `npm run check` — lint, typecheck, build y `test:js`.
- `npm run check:all` — lo anterior más `test:backend` (pytest contra la BD propia `aal_test`).
- `node scripts/verify-*.mjs` — Chromium real contra Vite + uvicorn arrancados.

Detalle, entorno y reglas de cierre de cada encargo: [`CLAUDE.md`](CLAUDE.md).
