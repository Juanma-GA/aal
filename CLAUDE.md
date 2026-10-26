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
opcional (D6); rama única sin PR, en lugar de G5 (D18); stack de la plantilla AACF `web-app` (no el de brdp-manager), con Zustand solo para
estado de UI global, nunca persistido en el navegador, y el estado de servidor siempre con React Query.

**Reglas de dominio**: la NT 10/17 manda sobre la S3000L · material = CUF, con una CONFUNFIS por CUF
(D12) · SNS de 6 caracteres alfanuméricos · clave de posición física = SNS + CO + AL, más el CS
(SNS_CS + CO_CS + AL_CS) · QTY es por unidad del conjunto superior · la estructura física es un grafo,
no un árbol · maestro de artículos único y común a todos los CUF, con clave NOC/NPC o, si no hay,
P/N + NCAGE (D16).

**Entorno (D17)**: funciona detrás de Zscaler sin desactivar nunca la verificación de certificados y
en Windows como entorno de desarrollo: ver "Red corporativa y Windows".

**D13**: los ficheros reales del cliente van solo a `private/` (ignorado); los tests usan fixtures
sintéticos; un `verify-*` que necesite ficheros reales sale con código 2 ("NOT RUN"). **D14**: `demo/`
sí va al repo porque todos sus datos son inventados; `demo/LEEME_DATOS_DEMO.md` es la referencia de la
demo y `demo/` no se modifica.

## Rama de trabajo única (D18)

- Todo el trabajo va a una sola rama, `claude/new-session-bl3tt3` (la rama por defecto del repo):
  Claude Code hace commit y push directamente, **sin PR**. Si el entorno asigna otra rama, se parte
  de esta y al terminar se integra en ella con fast-forward.
- **Sin etiquetas** (ni de Claude Code ni de Juanma): el punto de vuelta atrás de cada encargo es su
  **commit de cierre**, anotado en `docs/historial-cambios.md`.
- Es una desviación consciente de G5 del AACF (sin revisión por PR), mitigada con la CI en cada push.

## Cómo levantar el entorno

Requisitos: Node 24 (`.nvmrc`; `engines.node` `>=24.22.1`; la CI usa `node-version-file: .nvmrc` y
`run-checks.mjs` avisa si la instalada es menor), Python 3.11+ y PostgreSQL 16.

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
.venv/bin/python scripts/generate_rsa_keypair.py          # claves JWT en backend/keys/ (una vez; no están en git)
.venv/bin/python -m alembic upgrade head
.venv/bin/python scripts/create_admin_user.py admin@empresa.es   # contraseña: INITIAL_ADMIN_PASSWORD o se pide
.venv/bin/python scripts/seed_dev_data.py                 # material sintético + analista/revisor/observador
.venv/bin/python scripts/seed_demo_materials.py           # los 5 materiales de demo/LEEME_DATOS_DEMO.md
.venv/bin/python scripts/seed_demo_articles.py            # los 45 artículos de demo/FICHERO_CARGA_DEMO.xlsx
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`seed_dev_data.py` crea "Material de desarrollo (sintético)" y `analista.dev@aal-dev.es`,
`revisor.dev@aal-dev.es` y `observador.dev@aal-dev.es`; sus contraseñas salen de
`DEV_ANALISTA_PASSWORD`, `DEV_REVISOR_PASSWORD` y `DEV_OBSERVADOR_PASSWORD` o se piden (nunca como
argumento). Se niega con `ENVIRONMENT=production`.

Para reiniciar uvicorn en el entorno remoto: guardar su PID al arrancarlo (`… & echo $! > uvicorn.pid`)
y matarlo por PID. `pkill -f uvicorn` o un `ps | grep` dentro del mismo comando que lo arranca matan
también al propio shell (el patrón está en su línea de órdenes).

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
- npm 11: los scripts de instalación se aprueban en `allowScripts` de `package.json` (`npm
  install-scripts approve <paquete>`, fijado a su versión; hoy solo `esbuild`).
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
  entra solo. Node (≥ 22) ejecuta `.ts` sin compilar (type stripping), así que un test puede importar un
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
- **`verify-auth-settings.mjs`** (E01): el admin crea un usuario, le da Observador en el material de
  desarrollo, el usuario cambia la contraseña obligatoria, ve su material con el badge y nada de
  edición ni Ajustes, y el admin lo ve en Auditoría. Credenciales del admin por entorno:
  `VERIFY_ADMIN_EMAIL` y `VERIFY_ADMIN_PASSWORD` (sin ellas, 2 "NOT RUN"). Deja la base como estaba:
  borra su usuario (dominio `@verify.aal-dev.es`) con `backend/scripts/purge_verify_data.py`, que
  también borra los materiales `[verify] …`; solo quedan sus filas de `audit_log`, que es de solo añadir.
- **`verify-navigation.mjs`** (E02): el analista de desarrollo aterriza en el Panel de su material,
  recorre tres grupos del sidebar y la ficha de "Configuración funcional física", un material ajeno da
  404, el admin cambia FTA a "en desarrollo" y el analista lo ve; también el plegado de grupos tras
  recargar y la vista móvil. Credenciales por entorno: `VERIFY_ADMIN_EMAIL`, `VERIFY_ADMIN_PASSWORD` y
  `DEV_ANALISTA_PASSWORD`. Deja la base como estaba (material `[verify] …` borrado, FTA de vuelta a
  "planificado", preferencias del analista restauradas).
- **`verify-reference-tables.mjs`** (E03): el admin abre D114 (13 valores con su tipo por nombre),
  edita en línea una descripción de D112, exporta D112, el script lo cambia con openpyxl
  (`backend/scripts/verify_edit_xlsx.py`), lo importa, ve 1 modificado y aplica; el analista ve las
  tablas sin edición. Mismas credenciales que `verify-navigation`. Deja la base como estaba: guarda
  D112 antes y la restaura después, versiones incluidas (`purge_verify_data.py --save-reference` /
  `--restore-reference`), y borra su `import_job`.
- **`verify-conf-fun.mjs`** (E10): el admin importa `demo/CONF_FUN_DEMO.xlsx` (informe con los
  recuentos), recorre Vehículos de ruedas hasta `A21031`, busca `A27010` y `A21030` (ruedas y cadenas),
  abre "Avisos de la versión", y el analista ve el catálogo sin "Importar". Deja la base como estaba
  (`purge_verify_data.py --catalog-versions`). **`verify-conf-fun-real.mjs`**: importa
  `private/CONF_FUN_V3_0.xlsx` por la API, coteja las cifras del encargo y mide tiempos; sin el fichero,
  2 (NOT RUN). No está en la CI.
- **`verify-materials.mjs`** (E11): con el catálogo de demo importado (`scripts/import-demo-catalog.mjs`) y
  `seed_demo_materials.py`, el analista abre la ficha del Tramontana, quita 0102 (62 SNS) y la vuelve a
  poner (65), busca `E12300` en la configuración normalizada, crea y envía una solicitud de SNS, y el admin
  crea un CUF "a partir de otro" y comprueba que es independiente; (E12) descarta un borrador y el admin anula
  la solicitud enviada con motivo y la ve con "Mostrar anuladas". Deja la base como estaba (subcategorías
  devueltas; solicitudes y CUF `[verify] …` borrados). `verify-conf-fun` (E12) importa además una copia con
  `A22140` cambiado en 06-01 (CN-007 = 1, filas alineadas por subcategoría, "Varía por subcategoría") y borra
  la primera versión desde "Versiones"; `verify-navigation` (E12) arrastra el borde del sidebar, lo pliega con
  `Ctrl+B`, lo pasa a la derecha y comprueba que todo se conserva al recargar.
- **`verify-articles.mjs`** (E12): el admin importa `demo/FICHERO_CARGA_DEMO.xlsx` (45 artículos; AR-001,
  002, 003, 006 y 007 uno cada uno), el analista abre la `BIELA DM-6` desde su fila, ve AR-006 y la ayuda del
  campo 53, activa el control de vida (D114 + cantidad) y AR-006 desaparece; en la rejilla aplica "Escalón 4 =
  S" a dos artículos y exporta el Fichero Carga. Deja la base como estaba (`purge_verify_data.py
  --save-articles` / `--restore-articles` y su `import_job` borrado). (E13) El admin pulsa "Revalidar todos los
  artículos" y lee el informe por regla; el analista añade una referencia (P/N + NCAGE) a la biela.
- **`verify-articles-perf.mjs`** (E13): siembra 2 000 artículos sintéticos (`seed_synthetic_articles.py`) y mide
  con la Event Timing API del navegador que teclear en una celda de la rejilla responde en < 100 ms
  (`ARTICLES_PERF_KEY_MS`) y "Aplicar a la selección" sobre 200 filas tarda < 1 s (`ARTICLES_PERF_APPLY_MS`);
  falla si se supera. Deja la base como estaba (`--save-articles` / `--restore-articles`).
- **CI** (`.github/workflows/check.yml`): gitleaks con su SHA-256 comprobado (fijado en el workflow y
  contra el fichero de checksums de la release); Postgres 16 como servicio, claves JWT, `npm ci` +
  `npm run check:all`; admin y datos de desarrollo con contraseñas aleatorias generadas en el propio
  job (enmascaradas); y `verify-health` + `verify-auth-settings` + `verify-navigation` + `verify-reference-tables` + `verify-conf-fun` + `verify-materials` (tras importar el catálogo y los materiales de demo) + `verify-articles` + `verify-articles-perf` con Chrome
  contra uvicorn y Vite.

## Reglas de cierre de cada encargo

(Adaptadas de brdp-manager, "Reglas de cierre de cada encargo".)

1. Rama de trabajo única (D18, ver arriba): commit y push en `claude/new-session-bl3tt3`, sin PR. El
   encargo se cierra **con la CI en verde en el último push**; ese commit es el de cierre y va al
   historial (regla 7).
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
7. `docs/historial-cambios.md`: una entrada corta al final (qué, por qué, commit de cierre y tests). Las reglas
   que sigan vigentes se suben aquí, en una línea.
8. Informe: qué se hizo, qué no y por qué, lo que el encargo pida expresamente, y el resumen final del
   comando tal cual. Sin repetir lo que ya está en los commits.
9. Si un encargo va a pasar de dos partes grandes o el contexto se va a resumir a mitad, decirlo al
   terminar la primera parte y entregar por partes.
10. La regresión completa (`check:all` y todos los `verify-*`) se hace en un encargo aparte antes del
    despliegue o de una demo (E20), no en cada encargo.

## Estructura prevista

Las carpetas del §4 del plan que todavía no tienen contenido no se crean; llegan con su encargo:
`backend/app/repositories/`, `backend/app/validacion/` (motor NT) y `backend/tests/fixtures/`.

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
- **Rutas FastAPI**: sin `from __future__ import annotations`; `app/main.py` solo ensambla. Los
  cuerpos de petición heredan de `StrictModel` (`app/schemas/common.py`: campos inesperados → 422) y
  un 422 de validación nunca devuelve los valores enviados (`validation_error_handler`).
- **Autenticación (D4)**: el access token (RS256, `iss`/`aud`) vive solo en memoria
  (`src/stores/authStore.ts`, Zustand sin `persist`); el refresh token, en la cookie `aal_refresh`
  (HttpOnly, Secure, SameSite=Strict, Path=/api/auth), guardado en BD como SHA-256, rota en cada
  refresh y su reutilización revoca la familia (`app/services/sessions.py`). El frontend serializa
  los refrescos (una promesa por pestaña y Web Locks entre pestañas: `src/services/session.ts`) para
  no disparar esa detección por error. Duraciones, política de contraseñas y límite de intentos son
  el parámetro `auth` (`PARAMETER_DEFAULTS`), contados en BD (`login_failure`).
- **El día del SSO + MFA corporativo**: toda la firma y validación del JWT está en
  `backend/app/core/security.py`. Solo cambia de dónde salen las claves públicas
  (`_verification_keys()`: el JWKS del IdP en lugar de `keys/jwt_public.pem`) y los valores de
  `JWT_ISSUER` / `JWT_AUDIENCE`; el login propio se retira. La autorización (`app/api/deps.py`:
  `current_user`, `require_admin`, `require_material_permission`) y la matriz no cambian, siempre que
  el `sub` del IdP se asocie al `app_user` (por email, en ese encargo).
- **Permisos (D5)**: la matriz vive en BD (`role_permission`, sembrada en la migración 0002 con los
  permisos de E10–E19); ninguna regla de rol se escribe en código. Una ruta de material pide su
  permiso con `require_material_permission("confunfis.editar")` (un material ajeno o inexistente →
  404; sin el permiso → 403). En el frontend, `useMaterialPermission("…")` oculta lo que no se puede
  hacer; el servidor lo impide igual. Nombres de roles, permisos, áreas y acciones de auditoría en
  `es.json` (`test-i18n-keys` los exige todos), mostrados con `catalogLabel()`.
- **Mutaciones (HR20)**: `useOptimisticMutation` (lista en caché, rollback y toast; un 409 de versión
  ofrece recargar). Crear un usuario o material y restablecer una contraseña no son optimistas: el id
  y la contraseña temporal los da el servidor (excepción documentada de HR20); tampoco el alta de un
  valor de referencia (id y posición del servidor).
- **Catálogo de módulos (E02, D7)**: grupos y módulos del PALI salen de
  `backend/app/seeds/module_catalog_seed.yaml` (textos de la especificación del cliente), que carga
  `app/services/module_catalog.py` desde la migración `0003` o con `scripts/load_module_catalog.py`.
  Antes de cargar valida códigos, grupos, dependencias sin ciclos y cobertura RF-01…RF-41. Al recargar
  añade lo nuevo y actualiza los textos, pero **nunca pisa el estado ni la ruta** que haya puesto un
  admin; un módulo que sale de la semilla se conserva y se avisa. Los textos solo se editan en la
  semilla. Solo un módulo `disponible` tiene `route` (lo garantiza una CHECK en BD). **"Encender" un
  módulo** en un encargo: su página bajo `/materiales/:materialId/...`, su ruta en la semilla
  (`ruta:`, con `:materialId`) y `estado: disponible`, y un `scripts/load_module_catalog.py` (o una
  migración que lo cargue) para las BD ya creadas.
- **Tablas de referencia (E03, RNF-07)**: `reference_table` / `reference_value` /
  `article_field_definition`, de `backend/app/seeds/reference_tables_seed.yaml` (cargador
  `app/services/reference_seed.py`, migración `0004` y `scripts/load_reference_tables.py`). Una recarga
  añade tablas y valores, **nunca modifica un valor existente** (lista las diferencias); nombre,
  fuente, nota, `atributos_definicion` y campos del artículo siguen a la semilla. Códigos siempre
  texto (un código no texto en el YAML para la carga). Un valor nunca se borra: se desactiva. Lectura
  para cualquiera (`/tablas-referencia`, `/campos-articulo`; en Ajustes para el admin), edición solo
  admin. En los esquemas de los módulos: `Annotated[str | None, must_be_in("D112")]` y
  `await validate_references(db, body, current=…)` (`app/services/reference.py`; activos para datos
  nuevos, el valor ya guardado sigue valiendo).
- **Excel (E03, `backend/app/io_excel/`)**: una plantilla declarativa (`template.py`: hoja, 1 o 2 filas
  de cabecera, columnas con tipo, longitud, obligatoriedad, tabla de referencia, clave) sirve para
  exportar (`writer.py`, códigos como texto `@`) e importar en dos fases: `POST …/import` → análisis
  en segundo plano (`app/services/import_jobs.py`, `import_job`, sondeo `GET /api/import-jobs/{id}`)
  → `POST /api/import-jobs/{id}/apply` (sin errores, una transacción, auditoría por registro; 409 si
  algo cambió). Reglas de normalización en `cells.py`; nunca se recorta (HR6). Un consumidor nuevo
  implementa `ImportTarget` (`targets.py`, `register()`), como `app/services/reference_import.py`, y
  usa `src/components/import/ImportWizard.tsx` con su `start`. Límites: parámetro `import`. Un
  consumidor cuyos registros no son una fila cada uno (CONF_FUN) define su propio `analyze()` y,
  si hace carga masiva, `after_apply()` (estadísticas de la tabla).
- **Configuración funcional normalizada (E10)**: catálogo SNS común (no cuelga de ningún material),
  por versiones (`catalog_version`, una sola activa; las anteriores se conservan). Cada importación de
  CONF_FUN crea una versión; categorías y subcategorías (`material_category`/`material_subcategory`)
  son comunes a todas y se reconcilian sin borrar. Nivel y padre salen del código
  (`app/services/catalog.py` y `src/lib/sns.ts`, la misma regla); avisos CN-001…CN-006 guardados en la
  versión. Ruta `/configuracion-funcional`, fuera de `/materiales/:id`: el sidebar de cualquier material
  la abre. El árbol se pide por niveles (`GET …/tree?subcategory&parent`) y se virtualiza.
- **CUF (E11)**: cada material tiene su `catalog_version_id` (la activa al crearse; la cambia el admin
  tras ver el impacto, con `confirm`), sus subcategorías (`material_subcategory_link`, las edita quien
  tiene `material.editar`) y su configuración normalizada, **calculada, nunca guardada**: la unión de los
  SNS de sus subcategorías con su origen (`app/services/cuf.py`). Puntos de extensión:
  `SUBCATEGORY_REMOVAL_GUARDS` (E13 impedirá quitar una subcategoría cuyos SNS usa la CONFUNFIS) y
  `MATERIAL_COPIERS` (`register_copier`: E12–E15 añaden lo suyo a "Crear a partir de otro" sin tocar el
  endpoint). Ficha en `/materiales/:materialId/ficha`.
- **Artículos (E12, RF-04, D16)**: maestro único global en `/articulos` (como el catálogo, no cambia el
  material activo). `article` tiene una columna tipada por campo del Fichero Carga (`FIELD_COLUMNS`, PRISMA →
  columna; tipos y longitudes iguales a `article_field_definition`, lo vigila `test_article_model.py`) y los
  controles de vida en `article_life_control` (1–3 pares; el Fichero Carga lleva el primero). La validación es
  genérica, por la definición (`app/services/article_fields.py`, sobre `io_excel`): lo que no se puede guardar
  se rechaza (HR6); lo que falta o no está en su tabla es AR-001. Reglas AR-001…AR-008 en
  `app/validacion/articulos.py` (código, severidad, campos MAR06 y parámetros; los campos por código PRISMA,
  nunca por columna; los textos en `es.json` `articles.rules`/`articles.problems`). Los hallazgos se guardan
  en el artículo (`findings`, `finding_codes` para filtrar) y la ficha los recalcula. "Dónde se usa" es un
  registro (`USAGE_PROVIDERS`, `register_usage`): E13/E14/E17 añaden lo suyo. Editar: `articulos.editar` en
  algún material (o admin); importar: admin. Importación Fichero Carga / Maestro AAL
  (`app/services/article_import.py`): las filas rechazadas se listan y no bloquean el resto.
- **Artículos (E13)**: las columnas de `article` no tienen longitud (texto y `numeric`): la longitud y los
  decimales son los de `article_field_definition`, que el admin corrige en Ajustes → "Campos del artículo"
  (`PATCH /api/article-fields/{código}`, auditado, con versión; nunca deja datos guardados que no quepan;
  `edited_by_admin` hace que una recarga de la semilla no lo pise y liste la diferencia). Convención de los
  numéricos: `longitud` = dígitos sin la coma (el "tamaño" de la guía MAR06 cuenta la coma). P/N + NCAGE en
  `article_reference` (0..n por artículo, una principal = `pn`/`ncage` del artículo, (P/N, NCAGE) único entre las
  vivas; `set_principal`, `reference_owner` en `app/services/articles.py`); el Maestro AAL lleva la principal y
  la hoja `Referencias` (solo exportación). Revalidación de todos los artículos en segundo plano
  (`app/services/revalidation.py`, tabla `article_revalidation`): botón del admin, y sola tras importar o editar
  (activar/desactivar) una tabla de referencia que lean los artículos o corregir una definición de campo; el
  informe da por regla cuántos avisos aparecen y desaparecen. No sube la versión del artículo.
- **Sidebar (E12)**: ancho (borde arrastrable, límites en el parámetro `ui`), plegado a iconos (botón al pie y
  `Ctrl+B`) y lado, en `ui_preferences` (`useSidebarLayout`); `/api/me/ui-settings` da los límites.
- **Listas navegables y enlaces (E11)**: toda fila que abre algo es un `NavRow`
  (`src/components/layout/NavRow.tsx`: fila entera clicable con chevron); los enlaces usan el token
  `text-link` (contraste AA en ambos temas, `scripts/test-contrast.mjs`), nunca `text-primary`.
- **URLs por material (E02)**: las páginas de un material cuelgan de `/materiales/:materialId`
  (`src/layouts/MaterialLayout.tsx`: un material sin acceso es el 404 humanizado; abrir uno por URL lo
  hace material activo). `/` lleva al material activo (o al primero, o a "sin materiales"); `/ajustes`
  queda fuera del material. Cada página pone sus migas y su título con `PageHeader`.
- **Sidebar del PALI**: `src/components/layout/AppSidebar.tsx` sobre el `sidebar` de shadcn, al que se
  le quitó la cookie con que guardaba su estado (HR1). Los grupos plegados viven en el `uiStore`
  (Zustand sin `persist`) y se guardan en `ui_preferences.sidebar_collapsed_groups`
  (`useSidebarGroups`).
- **shadcn/ui con React 18**: el registro `new-york-v4` asume React 19 (`ref` como prop). Un
  componente que recibe un `ref` de Radix (`asChild`, `FormControl`, `Presence`) se convierte a
  `React.forwardRef` (ya: `button`, `input`, `switch` y los overlays de `dialog`, `sheet`,
  `alert-dialog`); los `verify-*` fallan con el aviso "Function components cannot be given refs".
  Los textos de los componentes (p. ej. "Close") pasan por `t()`.
