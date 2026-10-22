# Historial de cambios

Una entrada corta por encargo, al final: qué, por qué, commit y tests. Las reglas que sigan vigentes
se suben a `CLAUDE.md` en una línea.

## E00 — Arranque del repositorio (2026-10-22)

**Qué.** Cimientos sin lógica de dominio, según `docs/encargos/E00.md` más su ampliación (entorno
corporativo y Windows):

- Repo y documentación: `AGENTS.md` (entrada tool-agnostic: AACF con prioridad, stack, desviaciones
  D4/D6/stack, reglas de dominio, D13), `CLAUDE.md` (entorno, verificación, reglas de cierre adaptadas
  de brdp-manager, PowerShell, dependencias), `README.md`, `docs/instalacion/README.md`, copia del
  AACF en `aacf/` (2.0.1, `cursoFSD@56e44d3`, 2026-10-22), plan y encargo en `docs/`, `private/`
  ignorado salvo su `README.md`, `.gitignore`, `.gitattributes` (LF), `.env.example` y
  `backend/.env.example`.
- Backend: FastAPI (`app/main.py` solo ensambla), `core/config.py` (pydantic-settings; `CORS_ORIGINS`
  rechaza `*`), `core/errors.py` (errores saneados `{"code","ref"}`: `internal_error` 500,
  `database_unavailable` / `database_not_migrated` 503; detalle al log), `core/logging.py` (log JSON
  por línea), `core/merge.py` (`deep_merge`, HR10), migración `0001` (`app_parameter`, `audit_log`),
  `services/parameters.py` (lectura con deep-merge sobre `PARAMETER_DEFAULTS`, vacío en E00),
  `services/audit.py` (`record()` en la transacción del llamante), `GET /api/health` y
  `GET /api/version`. Lockfiles uv `--universal --generate-hashes` (con `--exclude-newer`, ventana de
  30 días de G3). BD de tests `aal_test` con las salvaguardas de brdp-manager (`_testdb.py`,
  `create_test_db.py`, `check_test_db.py`, sin pgvector ni claves JWT).
- Frontend: React 18 + TS strict + Vite 6 + Tailwind 4 + shadcn/ui (`card`, `badge`, `skeleton`,
  `button`, código del registro oficial `new-york-v4`), React Query, Zustand (`uiStore`, sin
  `persist`), react-i18next (`es`), `humanize`, `apiClient`/`apiErrors`. Tema em&e en tokens shadcn
  (grafito + acento azul, claro/oscuro según el sistema). Página `/` con el estado real de la API.
- Verificación: `run-checks.mjs` (lint, typecheck, typecheck:node, build, test:js, test:backend;
  códigos 0/1/2), `run-js-tests.mjs`, `run-backend-tests.mjs`, `create-test-db.mjs`;
  `verify-health.mjs` (Chromium real); CI `.github/workflows/check.yml` (gitleaks, Postgres 16,
  `npm ci` + `check:all`, `verify-health` con Chrome).
- Entorno corporativo y Windows (ampliación): sección "Certificado corporativo" en `README.md` y
  `docs/instalacion/` (npm/Node: `cafile`, `NODE_EXTRA_CA_CERTS`, `NODE_OPTIONS=--use-system-ca` desde
  Node 22.15 —comprobado en 22.22.0, donde `NODE_USE_SYSTEM_CA` no existe— o `win-ca`; Python/pip/
  httpx: `SSL_CERT_FILE` con públicos + corporativo, en el entorno del servicio y no en `.env`,
  `REQUESTS_CA_BUNDLE` no vale para httpx —comprobado en el código de httpx 0.28.1—; uv 0.11.32:
  `--system-certs` / `UV_SYSTEM_CERTS`, antes `--native-tls`), notas de PowerShell (`>` en UTF-16,
  `Read-Host -AsSecureString` / `getpass`) y regla de secretos nunca como argumentos.

**Por qué.** Base común para E01+: verificación en un comando, BD de tests aislada, errores
saneados, auditoría y parámetros listos (D11, HR0/HR10), y desarrollo posible desde el primer día
detrás de Zscaler y en Windows.

**Commit.** `35317a6`.

**Tests.** `npm run check:all`: lint, typecheck y build limpios; 6 `test:js` (Windows: rutas, programas,
secretos como argumento, `.gitattributes`, documentación y CI; HR1 sin `localStorage`/`persist`; HR15 y
tokens: ni texto en el JSX ni colores crudos; claves i18n y códigos de error del backend; `humanize`;
`uiStore`); 47 pytest (deep_merge, audit, parámetros, `/api/health` y `/api/version`, BD caída →
503 saneado, 500 saneado, migraciones up/down, `.env.example`, config, log JSON, versiones, Windows:
UTF-8, `encoding="utf-8"`, rutas y programas de Linux, secretos como argumento, lockfiles
universales con hash). `verify-health.mjs` en verde con capturas (estado conectado y 503 saneado).

**Decisiones y notas.**

- La rama de trabajo es `claude/new-session-bl3tt3` (la que fija el entorno remoto), no
  `e00-arranque`.
- El logo `eme-group-logo.png` no llegó con el encargo: `public/brand/eme-group-logo.png` es un
  logotipo de texto provisional (ver `public/brand/README.md`); el tema em&e queda pendiente de
  confirmar (D8).
- El registro de shadcn (`ui.shadcn.com`) está bloqueado en el entorno remoto: los componentes se
  copiaron del repo `shadcn-ui/ui` (`apps/v4/registry/new-york-v4/ui/`), con el import de `cn`
  resuelto a `@/lib/utils` y `text-white` cambiado por `text-destructive-foreground` (tokens).
- `npm audit fix` (sin `--force`) subió vite a 6.4.5 por avisos de seguridad, saltándose la ventana
  de 30 días a propósito.
- MCP `aacf_fetch` no disponible: no se pudo contrastar la versión del AACF.
