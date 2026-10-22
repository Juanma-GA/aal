# CLAUDE.md — Contexto para Claude Code

**Lee primero [`AGENTS.md`](AGENTS.md)** (entrada común a cualquier agente: AACF, stack, desviaciones,
reglas de dominio, D13 y estructura). Este fichero añade cómo levantar el entorno, cómo verificar y las
reglas de cierre de cada encargo.

## ⚠️ El AACF tiene prioridad sobre este fichero

**El AACF tiene prioridad sobre este fichero.** Copia local en `aacf/`, tomada del repo
`Juanma-GA/cursoFSD` (carpeta `Proyecto-CCMS-Nav/aacf/`, commit `56e44d3`) el **2026-10-22**, con
**`aacf/VERSION = 2.0.1`**. El framework se sirve normalmente vía el MCP `aacf_fetch`
(`http://10.117.139.1:8200/mcp`, solo red corporativa/VPN); **no está disponible en el entorno remoto
de Claude Code**, así que se trabaja con esta copia, que puede estar desactualizada: comprobar
`aacf/VERSION` contra el MCP en cuanto haya acceso y, si difiere, recopiar la carpeta entera (nunca
mezclar ficheros de versiones distintas).

- Hard Rules HR0–HR21 (`aacf/rules/atexis-hard-rules.md`): autocomprobar cada cambio. Las más
  presentes aquí: HR1 (nada de `localStorage`/`sessionStorage`; Postgres es la fuente de verdad), HR7
  (nada de fallbacks que degraden en silencio), HR8 (nada hardcodeado), HR9 (borrado lógico /
  confirmación), HR10 (`deep_merge`), HR15/HR21 (i18n + humanizar), HR20 (UI optimista).

**Desviaciones documentadas** (detalle en `AGENTS.md`): autenticación propia JWT RS256 en lugar de
Keycloak, con SSO + MFA corporativo que integra IT al final sin tocar la autorización (D4); HR11
opcional (D6); stack de la plantilla AACF `web-app` (no el de brdp-manager), con Zustand solo para
estado de UI global, nunca persistido en el navegador, y el estado de servidor siempre con React Query.

**Reglas de dominio**: la NT 10/17 manda sobre la S3000L · SNS de 6 caracteres alfanuméricos · clave
de posición física = SNS + CO + AL, más el CS (SNS_CS + CO_CS + AL_CS) · QTY es por unidad del conjunto
superior · la estructura física es un grafo, no un árbol.

**D13**: los ficheros reales del cliente van solo a `private/` (ignorado); los tests usan fixtures
sintéticos; un `verify-*` que necesite ficheros reales sale con código 2 ("NOT RUN").

## Cómo levantar el entorno

Requisitos: Node 22, Python 3.11+ y PostgreSQL 16.

**Postgres**, una de dos:

- Docker: `docker compose up -d` (`docker-compose.yml`, solo Postgres 16: rol `aal`/`aal`, BD `aal`).
- Postgres local de servicio (Linux: `service postgresql start`), una vez como superusuario:
  `CREATE ROLE aal LOGIN PASSWORD 'aal' CREATEDB; CREATE DATABASE aal OWNER aal;`
  (`CREATEDB` deja que `npm run test:db:create` cree `aal_test`; sin él, el script imprime el SQL
  para un administrador).

**Backend** (desde `backend/`):

```bash
python -m venv .venv                     # o: uv venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock.txt    # Windows: .venv\Scripts\python.exe
cp .env.example .env                     # y ajustar DATABASE_URL si hace falta
.venv/bin/python -m alembic upgrade head
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Frontend** (desde la raíz): `npm ci` y `npx vite --port 5173 --strictPort` (el proxy `/api` de
`vite.config.ts` va al 8000).

**Base de datos de tests**: `npm run test:db:create` (crea `aal_test` en el mismo servidor, la migra
y la primera vez añade `TEST_DATABASE_URL` a `backend/.env`).

**Dependencias fijadas** (reglas):

- Frontend: siempre `npm ci` (exactamente `package-lock.json`), en CI y en la documentación.
  **Nunca `npm audit fix --force`** (cambia versiones mayores sin revisar); `npm audit fix` sin
  `--force` sí.
- Backend: `pip install --require-hashes` de los lockfiles. Los lockfiles salen de
  `backend/pyproject.toml` con uv (versión usada: 0.11.32) `--universal --generate-hashes`, válidos en
  Windows y Linux; para regenerarlos, desde `backend/`: `uv pip compile pyproject.toml [--extra dev]
  --universal --python-version 3.11 --generate-hashes --exclude-newer <hoy − 30 días> -o
  requirements[-dev].lock.txt`. `backend/tests/unit/test_windows_safety.py` comprueba que son
  universales y con hash.
- Ventana de 30 días para paquetes nuevos (AACF G3): `--exclude-newer` en uv, `npm install
  --before=<fecha>` en npm; una corrección de seguridad (`npm audit fix`) puede saltársela.

## Red corporativa y Windows

**Certificado corporativo** (Zscaler re-firma el HTTPS): la verificación de certificados nunca se
desactiva de forma permanente. Síntomas y arreglos por herramienta (npm/Node con `npm config set
cafile`, `NODE_EXTRA_CA_CERTS` o `NODE_OPTIONS=--use-system-ca`; Python/pip/httpx con `SSL_CERT_FILE`
→ públicos + corporativo, en el entorno del servicio y no en `.env`; uv con `UV_SYSTEM_CERTS=true`):
[`docs/instalacion/README.md`](docs/instalacion/README.md#certificado-corporativo) y `README.md`.

**PowerShell**:

- `>` escribe en UTF-16 (y CRLF): estropea volcados binarios y ficheros `.env`. Para texto,
  `Set-Content -Encoding utf8`; para binarios, la opción de fichero de salida del programa.
- Las contraseñas se piden con `Read-Host -AsSecureString` (en Python, `getpass`) y nunca se
  escriben en la línea de comandos.
- **Regla para todos los scripts del proyecto: los secretos se piden de forma interactiva o se leen
  de variables de entorno, nunca de argumentos.** Lo vigilan `scripts/test-windows-safety.mjs` y
  `backend/tests/unit/test_windows_safety.py`.

## Cómo verificar cambios: `npm run check:all`

Scripts de Node, sin sintaxis de shell: el mismo comando en Linux y en PowerShell.

- `npm run check` — `lint`, `typecheck` (`tsconfig.app.json`), `typecheck:node`
  (`tsconfig.node.json`), `build` y `test:js`, por ese orden, parando en el primer fallo.
- `npm run check:all` — lo mismo más `test:backend`.
- Con `-- --keep-going` se ejecutan todos los pasos y se listan todos los fallos.
- Código de salida: **0** todo bien; **1** algo falla; **2** falta algo del entorno (Python del
  backend; base de datos de tests sin definir, caída o sin migrar; `TEST_DATABASE_URL` que no se puede
  usar): no es un fallo de la app, pero tampoco "todo comprobado". El resumen dice qué Python se usó.
- Por separado: `npm run lint`, `npm run typecheck`, `npm run build`, `npm run test:js`
  (`scripts/test-*.mjs` uno a uno, 180 s máximo por fichero; `-- <texto>` filtra por nombre),
  `npm run test:backend` (pytest; `-- -k audit -x` pasa argumentos a pytest).
- **`test:js`** son scripts Node sin framework (como en brdp-manager): un `scripts/test-*.mjs` nuevo
  entra solo. Node 22 ejecuta `.ts` sin compilar (type stripping), así que un test puede importar un
  módulo de `src/` que no use alias `@/`. Vigilan, entre otros: HR1 (`test-no-browser-storage`),
  HR15 y tokens (`test-ui-text`: ni texto visible en el JSX ni colores crudos en `src/`), claves i18n
  y códigos de error del backend (`test-i18n-keys`), `humanize` (HR21) y Windows
  (`test-windows-safety`).
- **Backend**: `test:backend` usa el Python del backend (`$BACKEND_PYTHON`, si no `backend/.venv`
  — `bin/python` en Linux, `Scripts\python.exe` en Windows —, si no `python3`/`python`) y **su propia
  base de datos, nunca la de la app**: `TEST_DATABASE_URL` (entorno o `backend/.env`), con nombre
  acabado en `_test` y distinta de `DATABASE_URL` (localhost/127.0.0.1/::1 cuentan como el mismo
  servidor). Lo impone `backend/tests/conftest.py` antes de importar la app (también con `pytest` a
  mano); las reglas viven en `backend/tests/_testdb.py`. Antes de pytest, `check_test_db.py` comprueba
  en una línea que la base responde y está en la última migración. Postgres real, sin mocks.
- **Navegador**: `scripts/verify-*.mjs` con `playwright-core` (Chromium real: `CHROMIUM_PATH` si está
  definida; si no, el de Playwright — en el entorno remoto `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`
  lo resuelve solo) contra Vite (`BASE_URL`, por defecto `http://localhost:5173`) y uvicorn
  arrancados. Sin ellos salen con 2 ("NOT RUN"). Capturas en `SHOTS_DIR` (por defecto el temporal del
  sistema, nunca `/tmp` a mano).
- **Windows** (tests de portabilidad): los scripts de Node no pueden usar el `.pathname` de una URL
  de fichero, rutas `/tmp`, `.venv/bin`, ni programas que Windows no tiene (`ps`, `xmllint`, `psql`,
  un shell), y `src/` tampoco esas rutas (`scripts/test-windows-safety.mjs`, que además comprueba
  `.gitattributes`, los secretos como argumento, las notas de certificado/PowerShell de la
  documentación y `npm ci` en CI). En Python (`backend/tests/unit/test_windows_safety.py`): los
  scripts de `backend/scripts` que imprimen escriben UTF-8, todo fichero de texto se abre con
  `encoding="utf-8"`, ninguna ruta `/tmp` / `.venv/bin` ni programa de Linux (`subprocess` con `ps`,
  `psql`…, `shell=True`, `os.system`), ningún secreto como argumento y lockfiles universales con hash.
  `.gitattributes` fija LF en `scripts/`, fixtures y migraciones.
- **CI** (`.github/workflows/check.yml`): escaneo de secretos con gitleaks; Postgres 16 como servicio,
  `npm ci` + `npm run check:all`; y `verify-health` con Chrome contra uvicorn y Vite.

## Reglas de cierre de cada encargo

(Adaptadas de brdp-manager, "Reglas de cierre de cada encargo".)

1. Cada encargo en su rama, integrado por PR a `main`; nunca push directo a `main` (AACF G5).
2. Siempre: `npm run check`.
3. `npm run test:backend` si el encargo toca `backend/` (código, migraciones o tests). Una vez, al
   final. Tras una migración nueva, `npm run test:db:create` pone al día `aal_test`.
4. Navegador: el `verify-*` nuevo del encargo y, como mucho, los dos o tres que cubren las pantallas
   que el encargo cambia. Ninguno más.
5. Si un script antiguo falla: una ejecución sobre el commit anterior al encargo. Si allí también
   falla, va a la lista del informe y no se arregla en el encargo. Si allí pasa, es una regresión y
   se arregla.
6. `code-reviewer` (AACF) sobre el diff antes de darlo por terminado; `security-reviewer` si toca
   autenticación, permisos, entrada de ficheros o secretos.
7. `docs/historial-cambios.md`: una entrada corta al final (qué, por qué, commit y tests). Las reglas
   que sigan vigentes se suben aquí, en una línea.
8. Informe: qué se hizo, qué no y por qué, lo que el encargo pida expresamente, y el resumen final del
   comando tal cual. Sin repetir lo que ya está en los commits.
9. Si un encargo va a pasar de dos partes grandes o el contexto se va a resumir a mitad, decirlo al
   terminar la primera parte y entregar por partes.
10. La regresión completa (`check:all` y todos los `verify-*`) se hace en un encargo aparte antes del
    despliegue o de una demo (E20), no en cada encargo.

## Estructura prevista

Las carpetas del §4 del plan que todavía no tienen contenido no se crean; llegan con su encargo:
`backend/app/repositories/`, `backend/app/validacion/` (motor NT), `backend/app/io_excel/`
(plantillas NT/SIGLE), `backend/tests/security/` y `backend/tests/fixtures/`.

## Historial de cambios

El historial de cada encargo está en [`docs/historial-cambios.md`](docs/historial-cambios.md). Cuando
crezca, búscalo con `grep -n` y lee solo los tramos que salgan.

## Patrones a seguir

- **Datos**: todo dato vive en Postgres y se lee/escribe por la API (`src/services/apiClient.ts`,
  React Query). Nada de `localStorage`/`sessionStorage` en `src/`, ni en comentarios.
- **Errores**: el backend responde errores saneados `{"detail": {"code", "ref"}}`
  (`backend/app/core/errors.py`); el detalle va al log JSON bajo la misma `ref`. El frontend traduce
  `errors.<code>` (`src/services/apiErrors.ts`); un código nuevo necesita su frase en `es.json`
  (`test-i18n-keys` lo exige).
- **Configuración**: todo valor ajustable en `backend/app/core/config.py` (y su línea en
  `backend/.env.example`, que `test_env_example.py` vigila) o, si es de negocio, en `app_parameter`
  con sus valores por defecto en `PARAMETER_DEFAULTS` (`backend/app/services/parameters.py`), que se
  leen siempre con `deep_merge` (HR10) y tienen su sección en Settings (HR0).
- **Auditoría**: toda mutación llama a `audit.record(...)` (`backend/app/services/audit.py`) en la
  misma sesión, antes del commit (D11).
- **UI**: componentes siempre de shadcn/ui (`src/components/ui/`, código del registro oficial; el
  registro `ui.shadcn.com` está bloqueado en el entorno remoto, así que se copian de
  `shadcn-ui/ui`, `apps/v4/registry/new-york-v4/ui/`); solo clases de tokens (`bg-primary`,
  `text-muted-foreground`, `bg-success`…) definidos en `src/styles/globals.css`; textos con `t()`;
  tokens de máquina con `humanize()`.
- **Rutas FastAPI**: sin `from __future__ import annotations`; `app/main.py` solo ensambla.
