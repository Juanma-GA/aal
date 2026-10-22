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

## E01 — Usuarios, roles por material y Settings (2026-10-22)

**Flecos de E00.** Logo oficial (`public/brand/eme-group-logo.png`, 249 × 95; `verify-health` lo
comprueba). Plan v0.3 rev. 4 en `docs/plan/`; `AGENTS.md` y `CLAUDE.md` recogen D12/D16 (dominio),
D17 (entorno) y D18 (rama única sin PR, etiqueta `eNN` por encargo cerrado en verde; regla de cierre
1 ajustada). CI: gitleaks solo corre si su SHA-256 coincide con el fijado en el workflow y con el
`checksums.txt` de la release (probado también con un hash alterado: el paso falla). Etiqueta `e00`
creada sobre `1833629`, pero **el proxy git del entorno remoto rechaza empujar etiquetas (403)**:
hay que empujarla a mano (ver informe).

**Qué.**
- Backend: migración `0002` (`app_user`, `refresh_token` con familias, `login_failure`, `material`
  mínimo con `version`, `role`, `permission`, `role_permission` con la matriz semilla y los permisos de
  E10–E19, `user_material_role`). `core/security.py` (único sitio que firma y valida el JWT RS256 con
  `iss`/`aud`), `services/sessions.py` (rotación y revocación de familia ante reutilización),
  `services/login_limit.py` (intentos por email e IP en BD), `services/permissions.py`, `api/deps.py`
  (`current_user`, `require_admin`, `require_material_permission`; material ajeno → 404). Rutas
  `/api/auth/*`, `/api/me/password` (abre sesión nueva y cierra las demás), `/api/me/ui-preferences`
  (deep-merge), `/api/users`, `/api/materials` (+ miembros), `/api/roles`, `/api/audit` (+ facets) y
  `/api/parameters`. Parámetros `auth` y `audit` en `PARAMETER_DEFAULTS`. Toda mutación auditada con
  `user_id` e IP, sin contraseñas, hashes ni tokens. 422 de validación saneado (sin valores).
  Scripts `generate_rsa_keypair.py`, `create_admin_user.py`, `seed_dev_data.py` (secretos por entorno o
  `getpass`) y `purge_verify_users.py`; `check_test_db.py` sale con 7 (→ 2) sin claves JWT.
- Frontend: login, cambio de contraseña obligatorio, logout; token solo en memoria (Zustand sin
  `persist`); `apiClient` reintenta una vez tras refresh; refresh serializado (promesa única + Web
  Locks); guardas `RequireAuth` / `RequireAdmin` / `RequireMaterialPermission`;
  `useMaterialPermission`; selector de material en la cabecera con badge de rol (guardado en
  `ui_preferences`); Ajustes con Usuarios, Materiales (+ miembros), Roles y permisos, Auditoría
  (filtros, paginación, detalle antes/después) y Parámetros. Mutaciones optimistas con rollback y
  toast; 409 explicado con "Recargar". Componentes shadcn nuevos del registro oficial, adaptados a
  React 18 (`forwardRef`) y a los tokens (`--overlay`).
- `verify-auth-settings.mjs` y CI que lo ejecuta con contraseñas aleatorias del propio job.

**Por qué.** D4/D5/D10/D11: autenticación propia lista para el SSO corporativo sin tocar la
autorización, roles por material comprobados siempre en el servidor y auditoría de toda mutación.

**Hallazgos.** (1) La cookie `Path=/api/auth` no llega a `/api/me/password`: el cambio de contraseña
cierra todas las sesiones y abre una nueva en su respuesta. (2) El registro shadcn v4 asume React 19:
sin `forwardRef` se perdían los refs de Radix (lo detectó `verify-health`). (3)
`queryClient.clear()` tras el login dejaba la cabecera sin datos: `resetQueries()`. (4) El guarda de
"último administrador" no podía dispararse nunca (quien cambia a otro admin es admin activo y no puede
tocarse a sí mismo): eliminado (HR13).

**Commits.** `59c0c39` (flecos de E00), `4d85d6c` (backend), `cb4e1d8` (frontend, verify, CI y docs;
CI en verde, run 39855384845). Etiqueta `e01` en el último commit del encargo.

**Tests.** `npm run check:all` verde: 105 tests de backend y 6 `test:js`; `tests/security` (login, límite de intentos, JWT,
cookie, rotación y reutilización, logout, cuentas desactivadas o dadas de baja, matriz completa rol ×
permiso × material, ningún secreto en `audit_log` ni en logs) e integración de cada endpoint;
`verify-health` y `verify-auth-settings` en verde con capturas.

## E02 — Shell de la app, catálogo de módulos y Panel del material (2026-10-22)

**Fleco de E01.** Sin etiquetas (D18 rev. 6): borradas `e00`/`e01` en local (nunca se publicaron) y
quitadas de `CLAUDE.md`/`AGENTS.md`; el punto de vuelta atrás es el commit de cierre de cada encargo,
anotado aquí. Plan rev. 6 en `docs/plan/`. Las entradas anteriores que hablan de etiquetas quedan
como historia.

**Qué.**
- Backend: migración `0003` (`module_group`, `module_catalog` con CHECK de estado y de "solo los
  disponibles tienen ruta", `module_requirement`) que carga `app/seeds/module_catalog_seed.yaml` con
  `app/services/module_catalog.py` (validación de códigos, grupos, dependencias sin ciclos y
  RF-01…RF-41; carga idempotente que no pisa estado ni ruta) y `scripts/load_module_catalog.py`.
  `GET /api/modules`, `GET /api/modules/{code}` (requisitos, dependencias y "lo usan" resueltos) y
  `PATCH /api/modules/{code}` (admin, versión, auditado). `GET /api/materials/{id}/activity`
  (`material.ver`, últimas `panel.activity_items` acciones, sin antes/después) y
  `GET /api/materials/{id}/members` abierto a `material.ver` (nombre y rol; el admin ve además id,
  email y fecha). `ui_preferences.sidebar_collapsed_groups`. Limpieza de los verify:
  `purge_verify_data.py` (usuarios y materiales `[verify] …`).
- Frontend: URLs por material (`/materiales/:materialId`, fichas en `…/modulos/:code`; `/` al
  material activo o a "sin materiales"; material ajeno → 404 humanizado); sidebar del PALI (shadcn
  `sidebar` + `collapsible`, sin la cookie del registro, grupos plegables guardados en el servidor,
  icono de estado accesible, panel lateral en móvil, Ajustes al pie para admin); ficha de módulo
  (objetivo, RF, entradas, salidas, entregable, "Depende de" y "Lo usan" con estado, aviso de
  planificado sin botones); Panel (CUF y rol, equipo, avance por estado, fase y grupo, actividad,
  accesos a disponibles); Ajustes → Módulos (filtros, cambio de estado y ruta con diálogo y mutación
  optimista); migas, 404 y título de pestaña por página.

**Decisiones.**
- La semilla entregada traía `panel` y `materiales` como `planificado`; se versiona con los estados
  iniciales de E02 §2.1 (`panel` disponible con `ruta: /materiales/:materialId`, `materiales` en
  desarrollo). `ruta` es una clave nueva y opcional de la semilla.
- `/` sin material activo lleva al primer material asignado (y lo hace activo) en vez de pedir que
  se elija.
- El cargador de la semilla lee solo columnas explícitas: la migración 0003 lo llama y debe seguir
  funcionando cuando un encargo añada columnas.

**Hallazgos.** El `sidebar` del registro guardaba su estado en una cookie (HR1): quitado. Su hook
`use-mobile` y su esqueleto de menú no pasaban el lint de React (setState en efecto,
`Math.random()` en render): reescritos. `verify-navigation` arrastraba el plegado de una ejecución
fallida anterior: ahora restaura las preferencias del analista.

**Commits.** `70019ef` (backend y fleco de etiquetas) y **`df80ea2`, commit de cierre** (frontend,
verify, CI y docs; CI en verde, run 39862479697).

**Tests.** `npm run check:all` verde: 126 tests de backend y 6 `test:js`; backend: semilla (cada validación), carga
idempotente sin pisar estados, permisos de `/api/modules`, `/activity` y `/members` (ajeno → 404),
`/activity` sin antes/después; `verify-navigation`, `verify-auth-settings` y `verify-health` en verde
con capturas de escritorio y móvil.

## E03 — Tablas de referencia y motor de importación/exportación Excel

**Qué.**
- Fleco de E01: `create_admin_user.py` y `seed_dev_data.py` comprueban la política (longitud mínima
  y 72 bytes) en cuanto se escribe la contraseña y la vuelven a pedir; si las dos entradas no
  coinciden piden las dos; Ctrl+C sale con una línea y código 130 (`_common.new_password` y
  `cancellable`). Con contraseña en variable de entorno no hay reintento. Las preguntas se hacen
  fuera de `asyncio.run()`: dentro, el primer Ctrl+C no interrumpe un `getpass` bloqueado.
- Backend: migración `0004` (`reference_table`, `reference_value`, `article_field_definition`,
  `import_job`) que carga `app/seeds/reference_tables_seed.yaml` (15 tablas, 30 campos) con
  `app/services/reference_seed.py`, también desde `scripts/load_reference_tables.py`. API
  `/api/reference-tables` (lectura para todos; alta, edición, activar/desactivar y reordenar solo
  admin, con versión y auditoría; sin borrado), `/api/article-fields`, exportar e importar.
  `reference.resolve()`, `must_be_in()` + `validate_references()` para los esquemas de E10–E19.
- Motor `app/io_excel/` genérico: plantilla declarativa (1 o 2 filas de cabecera), normalización,
  lectura defensiva, exportación exacta, análisis (nuevos / modificados campo a campo / sin cambios /
  errores / avisos) y `ImportTarget`. Dos fases en `app/services/import_jobs.py`; primer consumidor,
  la plantilla "Tabla de referencia". Parámetro `import` (tamaños, filas, caducidad).
- Frontend: Ajustes → Tablas de referencia y Campos del artículo (admin) y las mismas vistas de solo
  lectura para todos en `/tablas-referencia` y `/campos-articulo` (menú de usuario); rejilla con
  búsqueda y filtro de estado, edición en línea optimista, alta, activar/desactivar con
  confirmación, atributos por nombre; Exportar/Importar; `ImportWizard` reutilizable.

**Decisiones.**
- La semilla se versiona con dos cambios: `atributos_definicion` (nombre, tipo y opciones de cada
  atributo, para mostrarlos, validarlos y llevarlos a columnas) y el `09` de D114 entre comillas. La
  carga rechaza cualquier código que no sea texto, así que un `09` o un `0` sin comillas nunca se
  guardan como número.
- Una recarga nunca modifica un valor existente (lista las diferencias); nombre, fuente, nota y
  esquema de atributos de la tabla, y los campos del artículo, siguen a la semilla porque no se
  editan en la app.
- Normalización de celdas (`app/io_excel/cells.py`): se deshacen los escapes `_xHHHH_` de Excel; se
  quitan los espacios de los extremos (los de dentro se quedan); celda vacía = sin valor. Texto: un
  número se escribe sin ".0" y, con `zero_pad`, como código de ese ancho (`2` → `"02"`, con aviso;
  en D114, cuyos códigos numéricos son todos de dos cifras). Entero: `2.0` vale, `2.5` es error.
  Decimal: "." o "," como separador, nunca los dos; más decimales de los declarados es error, nunca
  se redondea. S/N en cualquier caja o VERDADERO/FALSO. Fecha: celda de fecha o AAAAMMDD. Un texto
  largo es error de la fila (HR6). Las opciones de un atributo se exportan por nombre ("No temporal")
  y se leen por nombre o código.
- Exportación: textos y códigos como celdas de texto con formato `@` (también como formato de la
  columna), un texto que empieza por "=" sigue siendo texto; enteros y decimales como números.
- Seguridad: solo `.xlsx`; un `.xlsx` con `vbaProject.bin` se rechaza; tamaño y tamaño
  descomprimido (del directorio del zip, sin expandir) antes de guardar; openpyxl `read_only` con
  `data_only` (y una segunda pasada para detectar fórmulas sin valor) y `defusedxml`. El fichero se
  guarda en `IMPORT_STAGING_DIR` con nombre generado y se borra al terminar el análisis.
- Aplicar comprueba la versión de cada registro analizado: si cambió, 409 `import_stale` y hay que
  volver a analizar. Un análisis colgado caduca a los `import.stale_minutes`.
- Las tablas viven fuera de Ajustes para que el analista las lea; el admin las edita en Ajustes.
- El alta de un valor no es optimista (id y posición del servidor): misma excepción que usuarios.

**Commits.** (se anota el de cierre)

**Tests.** `npm run check:all` verde: 232 tests de backend (semilla con recuentos exactos y
cada validación, recarga idempotente que no pisa ediciones, códigos como texto, API y permisos, sin
borrado físico, `must_be_in`, motor: cabeceras de 1 y 2 filas, cada tipo, errores, `.xlsm`, macros,
tamaños, fórmulas sin valor, round-trip D155 161 sin cambios, 2 modificados con su diff, analizar
no escribe, aplicar con errores 409, análisis caducado) y 6 `test:js`; `verify-reference-tables`,
`verify-navigation`, `verify-auth-settings` y `verify-health` en verde.
