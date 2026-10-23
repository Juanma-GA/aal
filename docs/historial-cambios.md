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

**Revisión (code-reviewer y security-reviewer del AACF).** Sin bloqueantes. Corregido: un análisis
que acaba tras ser dado por caducado ya no lo resucita (escribe solo sobre un trabajo
`analyzing`); aplicar con una plantilla distinta de la analizada da 409 `import_template_changed`;
reordenar bloquea los valores; números enormes son error de celda y no "fichero dañado"; los
atributos de texto tienen su longitud máxima al importar; la app no arranca si openpyxl no usa
defusedxml o usa lxml (test de entidades XML). Pendiente para el despliegue (E20): limitar el
tamaño del cuerpo en nginx (`client_max_body_size`), porque Starlette guarda la subida en disco
antes de que la ruta lea los primeros bytes.

**Commits.** `85e96e9` (todo el encargo) y **`20fd46f`, commit de cierre** (correcciones de la
revisión; CI en verde, run 39870405885).

**Tests.** `npm run check:all` verde: 236 tests de backend (semilla con recuentos exactos y
cada validación, recarga idempotente que no pisa ediciones, códigos como texto, API y permisos, sin
borrado físico, `must_be_in`, motor: cabeceras de 1 y 2 filas, cada tipo, errores, `.xlsm`, macros,
tamaños, fórmulas sin valor, round-trip D155 161 sin cambios, 2 modificados con su diff, analizar
no escribe, aplicar con errores 409, análisis caducado) y 6 `test:js`; `verify-reference-tables`,
`verify-navigation`, `verify-auth-settings` y `verify-health` en verde.

## E10 — Configuración funcional normalizada (catálogo SNS)

**Qué.**
- Flecos:
  - Material: NOC y NCAGE se normalizan (mayúsculas, sin espacios) antes de validarse, en backend y
    formulario; un material guardado antes sin formato se conserva y el listado lo marca con
    "Formato no válido" (`format_problems`). La validación de formato existía desde E01: lo nuevo es
    normalizar y avisar.
  - i18n: los textos de `es.json` ya decían "artículos" ("articulos" solo queda en códigos internos
    de permisos). `test-i18n-keys` vigila ahora una lista de palabras que solo existen con tilde.
  - `demo/` versionada con los cuatro adjuntos (D14) y `scripts/seed_demo_materials.py`, que crea
    los 5 materiales del LEEME con los tres usuarios de desarrollo y es idempotente.
  - Panel: "Estado de la herramienta" · "Módulos del PALI disponibles en la aplicación".
- Backend:
  - Migración `0005` (`catalog_version`, `material_category`, `material_subcategory`,
    `sns_position`, `subcategory_sns`, `sns_extra_name`); el módulo `catalogo-normalizado` pasa a
    disponible con ruta `/configuracion-funcional`.
  - Plantilla `io_excel` "CONF_FUN (Anexo II)", con su análisis propio contra la versión activa:
    nuevos, modificados campo a campo, sin cambios, eliminados y avisos CN-001…CN-006.
  - Aplicar crea una versión nueva y la deja activa; las anteriores se conservan.
  - API de lectura: versiones, categorías, árbol por niveles, búsqueda paginada, ficha del SNS,
    avisos, diff entre versiones y exportación (versión o subcategoría).
  - El motor Excel admite ahora una columna extra sin cabecera, mayúsculas, claves repetidas,
    `analyze()` y `after_apply()` propios del consumidor, y avisa de datos fuera de la plantilla.
- Frontend: pantalla en tres paneles (categorías → subcategorías; árbol virtualizado con carga
  perezosa; ficha), buscador, selector de versión, "Importar nueva versión" (admin), "Avisos de la
  versión", "Comparar versiones" y "Exportar a Excel". El `ImportWizard` gana la pestaña "Eliminados"
  y paginación.

**Decisiones.**
- **Categorías y subcategorías comunes a todas las versiones y reconciliadas:** se añaden las
  nuevas, se actualiza un nombre que cambie y nunca se borra ninguna. E11 ligará cada CUF a
  subcategorías estables.
- **Ruta del módulo fuera del material** (`/configuracion-funcional`): el sidebar de cualquier
  material la abre; la página no cambia de material activo.
- **CN-002 y CN-003 dan 2 en la demo, no 1.**
  - `B34510` es CONJUNTO por su código y está declarado SUBCONJUNTO, así que es también CN-002.
  - `D53000` cuelga de `D50000`, que no está en el fichero, así que es también CN-003.
  - Las reglas se aplican tal cual (HR7); `demo/` no se toca. Los tests fijan 2 y 2.
- **Un nombre distinto en otra subcategoría** se guarda como nombre adicional con origen
  `OTRA_SUBCATEGORIA`. CN-001 queda para el mismo SNS con otro nombre dentro de la misma
  subcategoría, filas ELEMENTO incluidas.
- **Las filas sin categoría (CN-004)** se guardan, cuentan como SNS y no entran en CN-002 ni CN-003
  (no tienen árbol).
- **CN-005** une la descripción y la novena columna con ", " y quita las comillas sobrantes.
- **El diff compara además las filas de cada SNS** (subcategoría, nivel, nombre y descripción): un
  cambio en una sola subcategoría también cuenta.
- **Recuentos y tiempos del fichero real:** no ejecutado, porque `private/CONF_FUN_V3_0.xlsx` no
  está en este entorno (`verify-conf-fun-real` sale con 2). Con un fichero sintético de 7 750 filas:
  análisis 3,4–3,8 s en segundo plano, aplicar 1,1–1,3 s y raíz del árbol 118 ms (con `ANALYZE` tras
  la carga masiva).

**Revisión (code-reviewer y security-reviewer).** Sin bloqueantes. Corregido:
- el diff no veía el cambio de una fila concreta;
- la primera importación podía cruzarse con otra (ahora hay un bloqueo consultivo);
- la exportación y el armado del catálogo bloqueaban la API (ahora van en un hilo);
- el diff cargaba objetos ORM completos;
- el `ImportWizard` pintaba miles de filas;
- se perdían en silencio datos más allá de la novena columna;
- se aceptaba un nivel desactivado;
- `repair_split` con una descripción vacía;
- un fallo de `ANALYZE` daba 500;
- el endpoint de etiqueta y notas no tenía interfaz (se retira);
- un error del árbol se tragaba;
- el purge solo borra versiones `verify-…` y restaura los nombres de categorías.

**Commits.** **`1878125`, commit de cierre** (CI en verde, run 39877127761).

**Tests.** `npm run check:all` verde: 268 tests de backend y 7 `test:js`. `verify-conf-fun`, `verify-navigation` (ahora
abre también el catálogo desde el sidebar), `verify-reference-tables`, `verify-auth-settings` y
`verify-health` en verde.

## E11 — Materiales / CUF: subcategorías, configuración normalizada, variantes y solicitudes de SNS

**Qué.**
- Flecos:
  - Usabilidad: token `--link` (azul, AA en claro y oscuro, `test-contrast`) en todos los enlaces.
    Filas navegables (`NavRow`) en Tablas de referencia, Materiales, Módulos y la nueva pestaña
    "Versiones" del catálogo. "Campos del artículo" compacto, sin scroll horizontal (tipo con su
    longitud, detalle en tooltip).
  - Demo: `demo/LEEME_DATOS_DEMO.md` sustituido (CN-002 = 2, CN-003 = 2).
- Backend:
  - Migración `0006`: `material.catalog_version_id`, `grupo_clase` y `copied_from_material_id`;
    `material_subcategory_link`; `sns_request`. "Materiales / CUF" pasa a disponible en
    `/materiales/:materialId/ficha`.
  - Subcategorías del CUF (`material.editar`, solo las que tienen SNS en su versión).
  - Cambio de versión del catálogo con informe de impacto y confirmación (admin).
  - Configuración normalizada calculada: árbol por niveles con su origen, recuentos, búsqueda y
    exportación CONF_FUN.
  - "Crear a partir de otro" con registro de copiadores.
  - Solicitudes de SNS: borrador → enviada → aceptada/rechazada; los borradores se descartan con
    borrado lógico; exportación de las enviadas.
  - `seed_demo_materials.py`: asigna las subcategorías si hay catálogo y crea el Puesto de mando
    como copia del Tramontana.
- Frontend:
  - Ficha del CUF (datos, familia, versión, equipo, subcategorías con mutación optimista).
  - Pestañas "Configuración normalizada" (árbol de E10 reutilizado con insignias de origen) y
    "Solicitudes de SNS".
  - "Crear a partir de otro" en Ajustes → Materiales; subcategorías y número de SNS en el Panel.
- `scripts/import-demo-catalog.mjs` (importa la demo por la API si no es ya la activa) y
  `verify-materials` en la CI.

**Decisiones.**
- **La configuración normalizada no se guarda:** se calcula de la versión del CUF y sus
  subcategorías.
- **Exportación de la configuración normalizada:** lleva las filas del fichero de esas
  subcategorías (69 para el Tramontana, porque `000000` está en tres y hay dos repeticiones CN-001).
  Los SNS únicos son 65.
- **Al cambiar de versión, las subcategorías que no existen en la nueva salen del CUF.** Están en el
  informe de impacto y en la auditoría.
- **Las variantes y el "Variante de" solo se muestran si el usuario tiene acceso a ese material.**
- **El alta de una solicitud y "Crear a partir de otro" no son optimistas** (el id lo da el
  servidor); sí lo son los cambios de subcategorías y los pasos de una solicitud.
- **Quitar una subcategoría usada por la CONFUNFIS** queda preparado
  (`SUBCATEGORY_REMOVAL_GUARDS`, con un test que lo documenta). El bloqueo real llega en E13.
- **Grupo-Clase** es informativo (4 cifras) y lo edita el admin en el formulario del material.

**Revisión (code-reviewer + security-reviewer).** Sin bloqueantes. Corregido:
- El material se relee bajo el bloqueo (`populate_existing`). El permiso ya lo había cargado, así que
  la comprobación de `version` podía usar datos viejos y perder un cambio concurrente.
- Los códigos de subcategoría se validan uno a uno; un 422 ya no devuelve lo enviado.
- No se resuelve una solicitud de un material borrado.
- La auditoría de la copia lista los miembros copiados con su rol.
- El seed audita la versión que asigna y no reescribe subcategorías vacías (idempotente).
- Las subcategorías no admiten un segundo cambio hasta que vuelve el primero (evita un 409 falso).
- Un clic en el menú de una fila (portal) ya no abre la fila.

**Commits.** `4bfd9cb` (E11) y `0f25900` (revisión). **Commit de cierre: `0f25900`** (CI verde, run 39925845986).

**Tests.** `npm run check:all` verde (ver el informe). `verify-materials`, `verify-reference-tables`
(entra por la fila), `verify-conf-fun`, `verify-navigation` (ahora fija el material activo del
analista y espera "Materiales / CUF" disponible), `verify-auth-settings` y `verify-health` en verde.
