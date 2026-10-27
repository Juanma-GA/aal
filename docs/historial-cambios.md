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

## E12 — Artículos (RF-04): maestro único con los 30 campos del Fichero Carga y reglas AR

**Qué.**
- **Flecos:**
  1. Versiones del catálogo: borrado lógico (admin, confirmación, auditoría antes/después). No se borra
     la activa ni una que use un CUF; el error nombra los CUF y remite a "Cambiar versión". Como no
     existía, se añade "Activar esta versión" (admin), para poder borrar la que estaba activa.
  2. Solicitudes de SNS: el autor (o quien tenga `material.editar`) descarta su borrador con un botón
     visible ("Descartar borrador"). Una enviada, aceptada o rechazada solo la anula el admin, con motivo
     obligatorio: borrado lógico, fuera de la lista y de la exportación, en la auditoría, y vuelve con
     "Mostrar anuladas".
  3. "Comparar versiones": en el caso (b) el diff ya era correcto; el problema era el caso (a). Ahora:
     - el bloque FILAS es una tabla alineada por subcategoría, con las columnas cambiadas resaltadas;
     - un campo que varía entre subcategorías muestra "Varía por subcategoría" con cada valor (también en
       la ficha del SNS);
     - aviso CN-007 (0 en la demo, 1 en la copia a).
  4. Sidebar: redimensionable por el borde, plegable a iconos con tooltips (botón al pie y `Ctrl+B`) y
     "Panel a la derecha", guardado por usuario en `ui_preferences`.
  5. Entorno:
     - Node: `.nvmrc` 24, `engines.node >=24.22.1`, CI con `node-version-file` y `check-latest`, y aviso
       en `run-checks`.
     - README: Node, Defender y la secuencia "después de un `git pull`".
     - `npm audit fix` (zod 4.6.7; fast-uri ya no está): 0 vulnerabilidades.
     - `allowScripts` de `esbuild@0.25.12`.
     - ESLint 10.11 sin tocar la configuración.
  6. `demo/`: FICHERO_CARGA_DEMO.xlsx y LEEME_DATOS_DEMO.md nuevos.
- **Backend:**
  - Migraciones `0007` (flecos) y `0008` (artículos).
  - `article` y `article_life_control`.
  - Cabecera, valores S/N y ayuda MAR06 en `article_field_definition`.
  - Validación genérica y reglas AR-001…AR-008.
  - API `/api/articles`: lista y filtros, ficha, alta, edición, borrado lógico, avisos, historial, lote
    de la rejilla, exportación Fichero Carga / Maestro AAL con resumen previo, e importación.
  - "Dónde se usa" como registro.
  - `seed_demo_articles.py`.
- **Frontend:**
  - `/articulos`: lista virtualizada con buscador, filtros y badges por regla; filas clicables.
  - Ficha con los campos agrupados, número MAR06, código PRISMA, ayuda, selectores de tabla, avisos con
    enlace al campo, "Dónde se usa" e historial.
  - Rejilla con validación por celda, "Aplicar a la selección" y guardado por lotes.
  - Asistente de importación con las pestañas "Rechazadas", "Avisos AR" y "Autocorrecciones".
- `verify-articles` en la CI; `verify-conf-fun`, `verify-materials` y `verify-navigation` ampliados.

**Decisiones.**
- **Migraciones:** la `0007` lleva los flecos y la `0008` los artículos. La parte 1 se subió aparte, sin
  reescribir una migración ya aplicada; el encargo hablaba de una sola `0007`.
- **Ancho de los campos numéricos:** el ancho de la definición cuenta todas las cifras, decimales
  incluidos (como el motor de E03): `Numeric(longitud, decimales)`.
  - `vaUsoArt` (2, 2) admite como máximo 0,99 €/h. Probable error de la plantilla: la guía dice
    tamaño 5. Manda E03.
- **Controles de vida:** solo el primer par va al Fichero Carga. Los pares 2 y 3, en el Maestro AAL.
- **Lo que no se puede guardar se rechaza** (un texto largo, un tipo imposible: HR6). Lo que falta, o un
  código que no está en su tabla, se guarda y lo avisa AR-001.
  - En la importación, una fila así es "rechazada" y el resto se aplica.
  - En la ficha, un código nuevo que no está en su tabla da 422; el valor ya guardado sigue valiendo.
- **Clave de importación:** NOC; si falta, P/N + NCAGE (Maestro); si falta, el nombre exacto entre los
  artículos sin NOC ni P/N.
- **Importar es solo del admin**, como E03/E10. Editar necesita `articulos.editar` en algún material.
- **S/N:** un campo es S/N por sus `valores` en la semilla. La tabla D114 de `snCtrlVidaArt` es la del
  campo relacionado (64): no se valida contra ella.
- **Duplicado de AR-001 y AR-004:** AR-001 incluye los obligatorios condicionales del encargo (p. ej.
  `cdCtrlUniArt` si control unitario = S), así que un mismo hueco lo avisan AR-001 y AR-004.
- **Formato de exportación:** la cabecera del Fichero Carga sigue la oficial (Calibri 8, negrita, fila
  de códigos en blanco, sin paneles fijados). Los códigos van como texto.

**Diferencias entre `article_field_help.yaml` y `article_field_definition`** (manda E03):
- peso, largo, ancho y alto (campos 40, 42, 43, 44): tamaño 8 en la guía, 7 en la definición;
- volumen (campo 46): 8 frente a 6;
- `vaUsoArt` (campo 56): "Opcional", tamaño 5, frente a "Recomendado", longitud 2;
- `cdCtrlUniArt` (campo 60): la guía dice "S o N", pero es un código D113;
- `snCtrlVidaArt` (campo 63): la definición tiene tabla D114, la guía dice S/N;
- `cdPolEl`: no tiene ficha en la guía ("Sin ayuda en la guía").

**ESLint:** 10.11 funciona sin cambios en `eslint.config.js`; los plugins admiten 10.

**Revisión (code-reviewer + security-reviewer).** Sin bloqueantes. Corregido:
- **Controles de vida:** se guardan en su posición. Un Fichero Carga sin primer par ya no corría el
  segundo a su sitio ni lo borraba al reimportar.
- **P/N + NCAGE en la importación:** se comprueba en el fichero y contra la base. La fila se rechaza con
  su motivo, en vez de un 500 al aplicar.
- **Versiones borradas:** un CUF no puede pasar a una versión borrada. Además se bloquea la versión,
  sin carrera con su borrado.
- **Rejilla optimista:** muestra al momento y cada fila toma la respuesta del servidor. Las filas
  rechazadas conservan lo tecleado. Se envía en tandas según el parámetro `articles.max_batch_rows`.
- **Borrado de un artículo:** ahora es optimista.
- **Errores 500 que pasan a 4xx:**
  - nombre nulo → 422;
  - la carrera en la unicidad → 409 por fila, con las filas bloqueadas en orden.
- **Importación del Maestro:** sin NOC ni un P/N conocido, cae en el nombre. Un "Origen del nombre"
  vacío ya no sale como modificado.
- **"Dónde se usa":** solo los materiales a los que el usuario tiene acceso.
- **Avisos AR:** nombran los campos, nunca los códigos PRISMA (HR21).
- **Sin valores fijados en el código:** el patrón de la regla se construye desde `RULES` y el máximo de
  controles de vida lo da el servidor.
- **`purge_verify_data --restore-articles`:** solo borra lo creado durante la comprobación.

Anotado sin cambiar:
- Una fila con NOC no casa con un artículo provisional del mismo nombre, como dice el encargo.
- Los filtros usan los hallazgos guardados; la ficha los recalcula.
- `check-latest` en la CI coge el último 24.x.

**Commits.** `c388e7a` (parte 1), `5d3c3da` (parte 2), `a28829f` (parte 3) y `d505d42` (revisión).
**Commit de cierre: `d505d42`** (CI verde, run 40310023457).

**Tests.** `npm run check:all` verde (ver el informe). `verify-articles`, `verify-materials`,
`verify-conf-fun`, `verify-navigation`, `verify-reference-tables`, `verify-auth-settings` y `verify-health`
en verde.

## E13 — CONFUNFIS (RF-02): configuración funcional física de cada CUF

**Qué.** Los cuatro flecos de artículos y la CONFUNFIS completa (backend, pantalla y demo).

- **Rejilla de artículos (fleco 1):** cada tecla re-renderizaba toda la rejilla (~500 selectores Radix
  montados), cada celda reconstruía el conjunto de códigos de su tabla en cada render y `useFieldCodes`
  devolvía un objeto nuevo en cada render (rompía la memorización). Filas memorizadas, conjuntos una vez,
  selectores montados solo al editar: de 3 280 ms a 32 ms por tecla; "Aplicar a la selección" sobre 200
  filas, 72 ms. `verify-articles-perf` (2 000 artículos) lo mide en la CI.
- **Longitudes (fleco 2):** `vaUsoArt` 5,2 y volumen 8 (migración 0009); convención: longitud = dígitos
  sin la coma (la guía cuenta la coma). Columnas del artículo sin longitud: la valida la definición, que el
  admin corrige en Ajustes (auditado; nunca deja datos sin caber; la semilla ya no la pisa).
- **Revalidación (fleco 3):** botón del admin y automática tras tablas de referencia o definiciones; informe
  de avisos que aparecen y desaparecen por regla.
- **Referencias (fleco 4):** `article_reference` (varios P/N por NOC); el Maestro AAL exporta la hoja
  `Referencias` y el round trip sigue exacto.
- **CONFUNFIS:** `physical_position` (0010), grafo calculado (totales con CS alternativos y AL una vez,
  huérfanas, ciclos), enlace con el maestro (NOC → P/N → nombre → provisional), observaciones OF-001…OF-011,
  API, puntos de extensión (copia, guarda de subcategorías, impacto, dónde se usa), `seed_demo_confunfis.py`
  y la pantalla (árbol, vista funcional, tabla, ficha, edición). Cifras del §2.3 reproducidas; CUF
  montados: 2 (la radio y el motor, cuyo NOC es el CUF del material MOTOR DIESEL), confirmado por Juanma:
  se mantiene la regla. Permisos `confunfis.*` y hoja `Referencias` solo de exportación, aprobados.

**Por qué.** Encargo E13 (`docs/encargos/E13.md`).

**Revisión (AACF).** Seguridad: QTY acotada (parámetro `confunfis.qty`), CUF montado de un material sin
acceso desconocido, auditoría del enlace con material e IP. Código: la edición solo envía lo cambiado,
observaciones recalculadas tras cambios de otras pantallas, referencias/artículos usados por la CONFUNFIS
protegidos, revalidación sin perder cambios, escrituras serializadas por material, duplicados con CS vacío.

**Commits.** `a85ea4b`, `f0c1932`, `3de3d9a`, `12f0ecc`, `333ca37` y `51b4163` (revisión).
**Commit de cierre: `51b4163`.**

**Tests.** `npm run check:all` verde (343 tests de backend). `verify-confunfis`, `verify-articles`,
`verify-articles-perf`, `verify-materials`, `verify-navigation` y `verify-reference-tables` en verde.

## E14 — Partes, productos funcionales, multifunción e incompatibilidades (resto de RF-02)

**Qué.**
- **Flecos de E13:** un alternativo que se queda solo ofrece volver a AL 00 (con el CS de las hijas),
  observación OF-012 y botón en la ficha; buscador del árbol físico (ruta abierta, resaltado, "n de m",
  expandir/contraer todo) y de la vista funcional. Demo: unidad `L` → `LI` en productos funcionales.
- **Backend (0011, 0012):** `article_part` (del artículo, global), `functional_product`, `extra_function` e
  `incompatibility` (del CUF), con versión, borrado lógico y auditoría; observaciones OP-001…007, OPF-001…006
  y OI-001…003; total de una parte en el CUF; copia remapeada, baja de fila con lo que cuelga, guarda de
  subcategorías y "dónde se usa"; tabla `CRITERIO_MULTIFUNCION`; módulos "Tabla de partes" y "Productos
  funcionales" encendidos. `seed_demo_confunfis.py` carga las dos hojas nuevas, los ejemplos y su copia al
  Puesto de mando (idempotente). Cifras del §2.3 reproducidas.
- **Frontend:** pestañas "Tabla de partes" y "Productos funcionales" (agrupados por POL, N/A/E juntos),
  secciones de la ficha de fila (partes, funciones adicionales, incompatibilidades), badge multifunción e
  icono de incompatibilidad, "por función adicional" en la vista funcional, tarjeta "Partes" en la ficha del
  artículo, contadores en el Panel.
- **Arreglo previo (E13):** `purge_verify_data.py --restore-articles` dejaba las filas de CONFUNFIS sin
  referencia (`ON DELETE SET NULL`); ahora guarda y repone el enlace, y las tablas de E14.

**Decisiones.** La "pestaña Partes" del artículo es una tarjeta de su ficha (la ficha no tiene pestañas).
Las P/N enlazadas desde una tabla de partes llevan origen `confunfis`. OP-005 se calcula con todos los CUF
(la tabla de partes es global): revela un sí/no sobre materiales ajenos, sin nombres. OI-002 no puede darse
hoy (la baja de una fila se lleva sus incompatibilidades) y se mantiene porque lo pide el encargo.

**Por qué.** Encargo E14 (`docs/encargos/E14.md`).

**Revisión (AACF).** Seguridad: refresco de partes acotado, cantidades extremas (422, nunca 500), parte sin
identidad rechazada, dígitos ASCII en COP/ALP, filas de otro material excluidas, desenlace de productos
auditado. Código: ciclos por componentes fuertemente conexos (y solo aristas del ciclo), total de una parte
sin cifras parciales (HR7), confirmación al quitar funciones adicionales e incompatibilidades (HR9), límites
del parámetro `confunfis.qty` (HR8), productos que siguen a sus tablas y al maestro, auditoría completa de
"Duplicar como alternativo", ficha que no relee una fila borrada (el 404 de la CI).

**Commits.** `ed9d507` (LEEME de la demo), `267143f`, `abbace6` (parte 1), `e85b743` (parte 2), `a1aa691`
(parte 3), `71025ef` y `8d459a9` (revisión). **Commit de cierre: `8d459a9`** (CI en verde).

**Tests.** `npm run check:all` verde (360 tests de backend). `verify-confunfis`, `verify-navigation`,
`verify-articles` y `verify-reference-tables` en verde, y todos los `verify-*` de la CI.

## E15 — Libro CONFUNFIS (Anexo XI): importación, exportación y plantilla para subcontratistas

- **Flecos:** `npm run update` (`scripts/update.mjs`: tras un `git pull`, solo lo necesario, con resumen);
  ficha lateral acoplada (`DetailPanel`: desde 1024 px a la derecha, la lista sigue pulsable, ancho guardado
  en `ui_preferences`); tabla de referencia `UNIDAD_MEDIDA_PF` (migración 0013, 88 valores con su equivalencia
  D112); importación de la hoja `Referencias` del Maestro AAL.
- **Backend:** libro por material sobre el motor de E03 (`anexo_xi_sheets.py`, `anexo_xi_import.py`,
  `anexo_xi_export.py`, `routes/confunfis_book.py`). Importar en dos fases, "Fusionar" (`confunfis.editar`)
  o "Sustituir" (admin, nombre del CUF tecleado), con informe por hoja y tipo de cambio, observaciones,
  provisionales, P/N nuevos y partes compartidas; CUF del fichero distinto con confirmación; una transacción
  auditada con la importación como origen (`audit.origin`); `IMPORT_GUARDS`. Exportar Anexo XI, Libro AAL
  (más funciones adicionales e incompatibilidades) y plantilla vacía (SNS PERMITIDOS, TABLAS, listas
  desplegables). Migración 0014 (`clock_timestamp()` en `created_at` de la CONFUNFIS y sus tablas).
- **Frontend:** menús Importar (Anexo XI / Libro AAL) y Exportar (Anexo XI, Libro AAL, Plantilla vacía) en la
  CONFUNFIS; `BookImportDialog` con los dos modos explicados, confirmaciones, pestañas por hoja y por tipo de
  cambio y pestaña "Resultado".
- **verify:** `verify-confunfis` comprueba la ficha acoplada, exporta el Anexo XI, lo reimporta en Fusionar
  con 0 cambios, lo aplica y descarga la plantilla; `verify-confunfis-real.mjs` nuevo (NOT RUN sin
  `private/CON_FUN_FIS2_ejemplo.xlsx`; probado con un fichero simulado de 714 filas).

**Cifras del §2.3** (en `test_anexo_xi.py`): demo en el Tramontana con Fusionar, 46 / 8 / 3 sin cambios; QTY
cambiada y fila borrada, Fusionar 1 modificada, 45 sin cambios, 0 bajas y Sustituir 1 / 44 / 1; demo en un CUF
vacío (0601+0201+0102), 46 nuevas, 8 nuevos, partes 3 sin cambios y "CUF del fichero distinto"; exportación del
Tramontana = el fichero de demo, celda a celda salvo el orden de filas (comparado como multiconjunto).

**Decisiones.** El orden de las filas exportadas es el del árbol; el de la demo no lo es, así que el round trip
se compara como multiconjunto. La TABLA DE PARTES se exporta como la demo (PARTES desde la columna F), no con el
reparto A–C / D–I del encargo. En "Sustituir", las partes solo se dan de baja para los padres que trae el
fichero (la tabla de partes es del artículo y global). Las hojas propias del Libro AAL nombran la fila por
SNS+CO+AL+CS; con duplicados, la primera. "Sustituir" no se aplica si hay filas rechazadas (borraría lo que
esas filas describen). Las filas ya cargadas antes de la migración 0014 conservan su `created_at` empatado: el
orden de sus duplicados se fija en cuanto se vuelvan a crear (una importación o una copia).

**Por qué.** Encargo E15 (`docs/encargos/E15.md`).

**Revisión (AACF).** Seguridad: celdas de texto exportadas siempre como texto (inyección de fórmulas);
aplicar vuelve a comprobar `confunfis.editar` y exige `articulos.editar` con hoja de partes; huella ampliada
(artículos y referencias de las filas, identidad del CUF), padres de las partes bloqueados y 409
`import_book_stale` si lo escrito no es lo del informe; origen de auditoría en `import_origin`; las partes
compartidas solo nombran CUF accesibles; `verify-confunfis-real` y `compare_books.py` sin datos del cliente
en la consola. Código: "Sustituir" con filas rechazadas rechazado; hoja `Referencias` con artículos
rechazados; orden estable de duplicados (0014); comparación de textos como texto; cabeceras del libro y
textos en español en el informe; "antes" correcto en incompatibilidades; bajas en cascada contadas; límites
de la plantilla en `confunfis.template` (HR8); `update.mjs` hace todo si `git diff` falla y distingue el 2
de `check:all`; mismo artículo por nombre al analizar y al aplicar. No arreglado: el análisis en seco
mantiene bloqueos mientras dura (ver informe).

**Commits.** `324c993` (parte 1), `ad6b5e4` (parte 2), `c6325a2` (parte 3), `62fb386` (revisión).
**Commit de cierre: `62fb386`** (CI en verde).

**Tests.** `npm run check:all` verde (381 tests de backend). `verify-confunfis`, `verify-articles` y
`verify-reference-tables` en verde. `verify-confunfis-real`: NOT RUN sin `private/CON_FUN_FIS2_ejemplo.xlsx`
(probado con un fichero simulado de 714 filas).

## E15b — Tema con los estados en azul y fleco del round trip del Maestro AAL

- **Tema (D8):** tras tres rondas con Juanma (azul marino A, C sobria), el **término medio**: el aspecto de siempre
  (neutros grafito, cabecera blanca con su borde gris fino, sidebar y fondo blancos, botones grafito) con los
  **estados en azul**. Badges CT SIGLE, Alternativo y CUF montado en azul pálido (`info`) y observaciones en ámbar
  (`warning`); fila seleccionada `row-selected` (azul muy pálido y barra fina en `--brand`); ítem activo del sidebar en
  azul muy pálido y seminegrita, sin barra; módulos disponibles en azul, planificados en gris. C (azul marino) y A (C
  con cabecera y sidebar en azul marino) quedan como alternativas: `data-theme-variant="c"` o `"a"` en `<html>`; lo que
  las distingue va por tokens. `test-contrast.mjs` comprueba todos los pares texto/fondo (AA) e iconos (3:1) en claro y
  oscuro con las tres.
- **Fleco de E15:** AR-008 se aplica en toda alta de artículo (`autocorrect_article`: también los provisionales desde
  la CONFUNFIS y las tablas de partes); migración 0015 para los ya guardados (versión +1, auditada como
  `article.autocorrected` con el valor que había y el origen en `import_origin`). Maestro AAL exportado y reimportado
  = 0 cambios, también con provisionales. En el informe, un valor vacío se ve "(vacío)"; las pestañas que pasan a dos
  filas ya no se salen.

**Decisiones.** La B (sidebar azul claro bajo cabecera azul marino) se descartó en la primera ronda. Las barras del
ítem activo y de la fila seleccionada se pintan como fondo, no como `box-shadow`, para no tapar el anillo de foco. El
borde de la cabecera es decorativo: el test de contraste no lo mide.

**Por qué.** Encargo E15b (`docs/encargos/E15b.md`), antes de enseñar la app al cliente.

**Revisión (AACF).** Código: anillo de foco del ítem activo (bloqueante) y barra de la fila seleccionada con la
búsqueda; pestañas inactivas por debajo de AA (`foreground/60`); "Sin materiales" ilegible en la variante A; la
migración auditaba el origen en `origin` y un `before` fijo. Todo arreglado.

**Commits.** `e971a2b` (variante C), `f162f14` (revisión), `5aaba0c` (término medio). **Commit de cierre:
`5aaba0c`** (CI en verde).

**Tests.** `npm run check:all` verde (383 tests de backend); `test-contrast` AA en todos los pares con las tres
variantes; los nueve `verify-*` de la CI en verde sobre `e971a2b`, y `verify-navigation`, `verify-confunfis` y
`verify-articles` otra vez sobre `5aaba0c`.

## E16 — RF-03: validador NT 10/17 de la CONFUNFIS, con informe y bloqueo de la entrega

- **Flecos:**
  - El análisis del libro Anexo XI se hace en memoria (`anexo_xi_dry.py`, la misma pasada del `Runner` sobre copias),
    dentro de una transacción `REPEATABLE READ READ ONLY`: no escribe ni bloquea. Un test lo comprueba con las filas y
    los artículos bloqueados por otra sesión; el umbral de 714 filas está en un test.
  - "Partes compartidas" solo nombra los CUF que el usuario puede abrir (test pendiente de E15).
  - El informe de importación se lee mejor: antes/después con contraste AA y el cambio resaltado, nombre del
    artículo, leyenda de la clave, diálogo ancho o a pantalla completa (también en el asistente de E03).
  - El 500 "ha fallado" venía de un P/N de más de 32 caracteres: ahora es una fila rechazada. Hay aviso de CUF sin
    subcategorías y la referencia del error se puede buscar en el log.
  - Los nombres de módulo del sidebar van en dos líneas, con tooltip.
- **Motor:**
  - `app/validacion/` tiene un catálogo de 30 reglas (CF-001…CF-021, TP-001, PF-001, AR-001…AR-007) y comprobaciones
    puras sobre una instantánea, la de lo guardado o la que dejaría una importación.
  - Se configuran en `validation_rule` (migración 0016; Ajustes → Reglas de validación, auditado).
  - Ejecuciones y hallazgos con huella de datos y hash de reglas: cualquier cambio posterior las deja "desactualizadas".
  - Avisos aceptados con justificación.
  - Validación automática al aplicar un libro.
- **Entrega:**
  - "Exportar para entrega" (Anexo XI y Fichero Carga en un zip) responde 409 con los motivos si hay bloqueantes o la
    validación está desactualizada. Queda el punto `DELIVERY_GUARDS` para E17.
  - Las exportaciones de trabajo empiezan con la hoja ESTADO DE VALIDACIÓN.
  - Informes en Excel y PDF (reportlab).
- **Pantallas:**
  - Validación NT 10/17 (migración 0017): semáforo, resumen por regla, hallazgos con filtros, "Ir a" a la fila del
    árbol con su ficha y el campo señalado, aceptar aviso e informes.
  - CONFUNFIS: "n errores · n avisos", badges con el código de la regla, filtro por severidad y botón de entrega.
  - Panel con el semáforo.
- Los códigos OF-*, OP-*, OPF-* y OI-* pasan a las reglas nuevas. La tabla de equivalencias está en CLAUDE.md, y
  `refresh_findings.py` (lo lanza `npm run update`) recalcula los hallazgos guardados.

**Decisiones.**
- **reportlab** para el PDF: licencia BSD, Python puro, sin dependencias de sistema (ni navegador, ni Cairo); está
  en los lockfiles con hash.
- **Permisos:**
  - Validar pide `confunfis.ver` y aceptar avisos `confunfis.editar`, como dice el encargo. La matriz ya tenía
    `validacion.ejecutar` (sin el Observador): queda a decisión de Juanma pasarlo a ese permiso.
  - La entrega pide `exportar`, el permiso de la matriz para exportar, porque el encargo no lo fija.
- **OF-009 y OPF-002** (el nombre o la designación distintos de los del maestro) desaparecen: no son reglas de la NT.
- **CF-015** marca solo la segunda aparición de un duplicado. Así sale la cifra del §2.3.
- **Hallazgos AR:** cuentan los de los artículos de las filas y los de los artículos de sus partes.
- **Textos de los documentos del backend:** salen del mismo `es.json` (`I18N_ES_PATH`). Sin ese fichero, el backend no
  arranca.

**Cifras (§2.3).** Con la demo recién sembrada salen exactas:
- bloqueantes de la CONFUNFIS: CF-001, 002, 007, 012, 014 y 015 (1 cada una);
- PF-001: 1 (ZZ);
- CF-017: 1 (el neumático);
- AR-002, 003 y 006 (bloqueantes), y AR-001 y 007 (avisos);
- TP-001 y el resto de reglas: 0.

En total, 10 bloqueantes y 3 avisos.

**Revisión (AACF).** Sin bloqueantes. Corregido:
- el PDF fallaba con una justificación o un texto largos (filas que se parten y textos cortados a 300 caracteres);
- los parámetros de una regla se comprueban por tipo;
- la huella incluye los hallazgos AR de los artículos y los códigos de las tablas de productos;
- el reloj del análisis en memoria va siempre después de lo guardado;
- análisis y validación cuentan las mismas partes;
- las ubicaciones de los hallazgos salen de `es.json`;
- el backend comprueba al arrancar que tiene sus textos;
- en Ajustes, los cambios de regla van de uno en uno.

Queda anotado: no hay límite de validaciones por CUF.

**Por qué.** Encargo E16 (`docs/encargos/E16.md`): "lo que no cumple la norma no sale de la herramienta" (hito de demo 2).

**Commits.** `3b0abb2` (parte 1, flecos), `2c24db5` (parte 2, backend), `727c48a` (parte 3, pantallas; su CI
falló por `test_module_seed`, corregido en el siguiente) y `9420a9c` (revisión). **Commit de cierre: `9420a9c`**
(CI en verde).

**Tests.** `npm run check:all` verde (425 tests de backend, entre ellos cada regla con su caso bueno y malo y los tres
casos del §9.1.8, las cifras del §2.3, la entrega bloqueada y en verde, el análisis sin bloqueos y 714 filas en < 3 s).
`verify-validation`, `verify-navigation` y `verify-confunfis` en verde; `verify-validation-real`: NOT RUN sin
`private/CON_FUN_FIS2_ejemplo.xlsx` (flujo probado con un libro sintético).

## E16 — Fleco: el backend no arrancaba en Windows

- `validation_report.py` resolvía `ZoneInfo("Europe/Madrid")` al importarse; Windows no trae base de zonas horarias y
  el backend no arrancaba (`ZoneInfoNotFoundError`). La CI en Linux no lo veía.
- **Arreglo:** `tzdata` en `pyproject.toml` y en los dos lockfiles (con hash, sin marcador de plataforma: `npm run
  update` lo instala al cambiar el lockfile, también en Windows); la zona es el ajuste `TIMEZONE` (por defecto
  `Europe/Madrid`), se resuelve al usarse (`app/core/timezone.py`) y se comprueba al arrancar con un mensaje claro (HR7).
- **Para que no se repita:** `tests/unit/test_timezone.py` simula Windows (sin base de zonas del sistema, y también sin
  `tzdata`) y un job nuevo de la CI en `windows-latest` instala el lockfile, importa `app.main` y pasa los tests
  unitarios. Los unitarios ya no limpian `login_failure` al acabar (no tocan la base), así que corren sin ella.

**Commit:** `9f84447`, con la CI en verde en sus tres jobs (`secrets`, `windows` y `check`). `npm run check:all` pasó
en verde, con 428 tests de backend. En `windows-latest`, el backend arranca y pasan los 217 tests unitarios.

## E17 — Baselines, revisión y autorización de cambios de la CONFUNFIS (cierra el hito de demo 2)

- **Flecos de E16:** validar pide `validacion.ejecutar`; "Exportar para entrega", `confunfis.entregar` (el Observador conserva
  `exportar`); se conservan las últimas `validation.keep_runs` validaciones por CUF (50) y las de cada baseline, el resto se
  purga con auditoría. El job de Windows no había fallado: nada que corregir.
- **Baselines** (migraciones 0018–0020): vN inmutable, instantánea en **un documento JSONB por baseline** con su SHA-256
  (filas, productos, funciones adicionales, incompatibilidades, artículos y partes, y las hojas ya calculadas del Anexo XI y
  del Fichero Carga: la entrega es exactamente lo aprobado); cuatro ojos (nunca el autor, ni siendo admin); rechazar con
  comentario; aprobar cierra las autorizaciones incluidas.
- **Control de cambios** en un solo sitio (`app/services/changes.py`, `before_flush`): en revisión, solo lectura; tras una
  revisada, cada cambio de filas, productos, funciones adicionales, incompatibilidades, libro o copia necesita una autorización
  aprobada del CUF (`X-Change-Authorization`), que queda ligada a cada registro y en la auditoría. Partes y artículos, globales,
  no se bloquean: salen en el diff y "Dónde se usa" avisa.
- **Autorizaciones** `AC-<CUF>-NNN` (tipos en `TIPO_AUTORIZACION`), **diff** por entidad y campo (también a Excel), **entrega** de
  la última revisada con "ENTREGA — baseline vN revisada por …" y el aviso de cambios no incluidos.
- **Pantallas:** módulo "Baselines y cambios", banda y selector de autorización en la CONFUNFIS (botones deshabilitados con su
  motivo), historial de la fila con autorización y baseline, Panel con el estado de configuración.
- **Demo:** `demo_corregir_hallazgos.py` (10 bloqueantes, `--dejar CF-007`) y `seed_demo_confunfis.py --reset`.
- **Revisión:** la carrera entre "Crear baseline" y una edición (bloqueos FOR SHARE), la auditoría de las bajas, la fuga del
  código de una autorización de otro CUF y el alcance de `purge_verify_data.py`, corregidos.
- **Interpretación:** rechazar una baseline levanta el solo lectura; si ya había una revisada, sigue haciendo falta autorización.
  Subcategorías y versión del catálogo del CUF no se bloquean (son del material), pero salen en el diff.

**Por qué.** Encargo E17 (`docs/encargos/E17.md`).

**Commits.** `973e1b2` (parte 1; su CI falló por `test_parameters`, corregido en la parte 2), `75855a3` (parte 2, backend),
`d741136` (parte 3, pantallas y `verify-baselines`) y `a624726` (revisión). **Commit de cierre: `a624726`** (CI en verde en
Linux y Windows).

**Tests.** `npm run check:all` verde (438 tests de backend; `test_baselines.py` recorre el flujo del §2.3 entero más
inmutabilidad, cuatro ojos, estados ilegales, copia sin baselines, retención, permisos y `--reset`). `verify-baselines`,
`verify-validation`, `verify-confunfis` y `verify-reference-tables` en verde.

## E17b — Flecos de las pruebas de E17

- **Admin:** tiene todos los permisos del catálogo en todos los materiales; lo único que se le niega son los cuatro ojos. Con
  el código de E17 ya era así (no se reprodujo el "Crear baseline" que faltaba: probablemente una sesión abierta antes de `npm
  run update`); ahora lo vigilan un test que recorre el catálogo de la base, también con un rol propio, y otro de los cuatro ojos.
- **Botones, para toda la app:** ocultos solo sin permiso; con permiso y una condición pendiente, deshabilitados con el motivo y
  el enlace que lo desbloquea (`GatedButton` / `BlockedReason`): ficha de fila, funciones adicionales e incompatibilidades,
  productos funcionales, subcategorías y versión del catálogo del CUF, Crear / Aprobar / Rechazar / Retirar y las autorizaciones.
  La tarjeta Partes no cambia (las partes son globales y no se bloquean).
- **Material tras una baseline revisada:** subcategorías y versión del catálogo piden una autorización (la misma guarda),
  quedan ligadas a ella y salen en el diff; nombre, descripción y Grupo-Clase, libres.

**Por qué.** Encargo E17b (`docs/encargos/E17b.md`), correcciones de Juanma al probar E17.

**Commits.** `0b40202` y `6037d6d` (revisión). **Commit de cierre: `6037d6d`** (CI en verde en Linux y Windows).

**Tests.** `npm run check:all` verde (441 tests de backend). `verify-baselines` (ampliado), `verify-materials`,
`verify-confunfis` y `verify-validation` en verde.
