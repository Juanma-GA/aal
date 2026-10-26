# AAL — Análisis de Apoyo Logístico

App web para em&e group que soporta el Análisis de Apoyo Logístico de un
material del Ejército de Tierra (NT 10/17, S3000L parcial) y genera los
entregables del PALI desde una única base de datos.

- Frontend: React 18 + TypeScript + Vite, Tailwind + shadcn/ui, Zustand + React Query.
- Backend: FastAPI + SQLAlchemy 2 async + Alembic, PostgreSQL 16.
- Marco: ATEXIS AACF (`aacf/`). Agentes de código: [`AGENTS.md`](AGENTS.md) y [`CLAUDE.md`](CLAUDE.md).
- Plan y encargos: [`docs/plan/`](docs/plan/), [`docs/encargos/`](docs/encargos/), historial en
  [`docs/historial-cambios.md`](docs/historial-cambios.md).

## Arranque rápido

```bash
docker compose up -d                       # Postgres 16 (o un Postgres local, ver CLAUDE.md)
cd backend
python -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock.txt   # Windows: .venv\Scripts\python.exe
cp .env.example .env
.venv/bin/python scripts/generate_rsa_keypair.py   # claves JWT (backend/keys/, fuera de git)
.venv/bin/python -m alembic upgrade head
.venv/bin/python scripts/create_admin_user.py admin@empresa.es   # pide la contraseña
.venv/bin/uvicorn app.main:app --port 8000
cd ..
npm ci
npx vite --port 5173 --strictPort          # http://localhost:5173
npm run test:db:create                     # base de datos de tests aal_test
npm run check:all                          # lint, typecheck, build, tests JS y backend
```

Siempre `npm ci` (nunca `npm audit fix --force`) y `pip install --require-hashes`.

### Después de un `git pull`

Desde la raíz, el mismo comando en PowerShell y en Linux:

```bash
npm run update              # solo lo necesario: npm ci, pip install, alembic, aal_test
npm run update -- --check   # y además npm run check:all
```

`npm run update` (`scripts/update.mjs`) mira qué ha cambiado desde la última vez que se lanzó (un sello en
`.aal-update/`, ignorado por git) o, la primera vez, desde `ORIG_HEAD` (donde empezó el último `git pull`):

- `npm ci` si cambió `package-lock.json`;
- `pip install --require-hashes -r requirements-dev.lock.txt` si cambió un lockfile de Python (con `uv pip` si
  el virtualenv se creó con uv y no tiene pip);
- `alembic upgrade head` siempre;
- `npm run test:db:create` si hay migraciones nuevas.

Al final da un resumen de lo que hizo y de lo que no hacía falta, y por qué. Si un paso falla, el sello no se
actualiza y la siguiente vez se repite todo. Sin referencia anterior, lo hace todo. Necesita `git` y el Python del
backend (`backend/.venv`); si falta, lo dice y sale con 2.

A mano, lo mismo es: desde `backend/`, `.venv/bin/python -m pip install --require-hashes -r
requirements-dev.lock.txt` y `.venv/bin/python -m alembic upgrade head` (Windows: `.venv\Scripts\python.exe`);
desde la raíz, `npm ci` y `npm run test:db:create`.

Si `check:all` dice `test:backend NOT RUN` porque `aal_test` va por detrás, el propio mensaje da el
comando: es `npm run test:db:create`.

## Node

La versión del proyecto está en `.nvmrc` (24) y en `engines.node` de `package.json` (`>=24.22.1`); la CI
usa la misma (`node-version-file: .nvmrc`). `npm run check` avisa si la instalada es menor.

- Windows: `winget upgrade OpenJS.NodeJS.LTS` o el instalador `.msi` de nodejs.org. Si Defender
  bloquea una versión, **nunca** se permite en Defender: se instala la versión que IT apruebe.
- Con npm 11, los scripts de instalación de las dependencias se aprueban en `allowScripts` de
  `package.json` (hoy solo `esbuild@0.25.12`, que descarga su binario). Uno nuevo sale como aviso en
  `npm ci`: revisarlo y aprobarlo con `npm install-scripts approve <paquete>` (queda fijado a su versión).

## Certificado corporativo

Detrás de la inspección SSL corporativa (Zscaler) las herramientas no conocen
el certificado raíz que re-firma el tráfico. **Nunca se desactiva la
verificación de certificados de forma permanente.** Guía completa, con
PowerShell y servidores: [`docs/instalacion/`](docs/instalacion/README.md#certificado-corporativo).

| Herramienta | Síntoma | Arreglo |
|---|---|---|
| npm / Node | `UNABLE_TO_GET_ISSUER_CERT_LOCALLY` | `npm config set cafile <pem>` o `NODE_EXTRA_CA_CERTS=<pem>`. En Windows, almacén del sistema: `NODE_OPTIONS=--use-system-ca` (Node ≥ 22.15; `NODE_USE_SYSTEM_CA` no existe en Node 22) o, con Node anterior, la librería `win-ca`. `strict-ssl false` solo momentáneo. |
| Python / pip / httpx | `SSLCertVerificationError` | `SSL_CERT_FILE` → fichero con **los certificados públicos más el corporativo** (reemplaza a todos). `REQUESTS_CA_BUNDLE` no lo lee httpx. Va en el entorno del servicio (systemd / servicio de Windows), **no en `.env`**. |
| uv | `invalid peer certificate: UnknownIssuer` | `UV_SYSTEM_CERTS=true` / `--system-certs` (uv 0.11.32; antes `--native-tls`), o `SSL_CERT_FILE`. |

## PowerShell

- `>` escribe en UTF-16: estropea volcados binarios y ficheros `.env`. Usa
  `Set-Content -Encoding utf8` o la opción de fichero de salida del programa.
- Las contraseñas se piden con `Read-Host -AsSecureString` (en Python,
  `getpass`) y nunca se escriben en la línea de comandos. Ningún script del
  proyecto acepta un secreto como argumento: se pide de forma interactiva o
  se lee de una variable de entorno.

## Datos del cliente

Los ficheros reales del cliente van solo a `private/`, que git ignora
(`private/README.md`). Los tests y la demo usan datos sintéticos.
