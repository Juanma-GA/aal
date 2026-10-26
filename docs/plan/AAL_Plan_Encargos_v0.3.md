# AAL — Análisis de Apoyo Logístico · Plan de encargos para Claude Code

**Versión 0.3 · 22-oct-2026** · Repo: `github.com/Juanma-GA/aal` · Cliente: em&e group · Marco: AACF 2.0.x (ATEXIS)
Referencia de patrones de implementación: `Juanma-GA/brdp-manager`, rama `v2-multiproyecto` (misma persona, mismo flujo con CC).

**Cambios en v0.3 (rev. 6):** sin etiquetas (D18): cada encargo se identifica por su commit de cierre.

**Cambios en v0.3 (rev. 5):** el catálogo de módulos se siembra desde `module_catalog_seed.yaml` (E02).

**Cambios en v0.3 (rev. 4):** D18, rama de trabajo única con etiqueta por encargo; el repo es público (ver D13).

**Cambios en v0.3 (rev. 3):** E01 crea la entidad `material` mínima (CUF: NOC, nombre, P/N, NCAGE, baja lógica), porque los roles se asignan por material; E11 la completa (subcategorías, configuración normalizada, copia de CUF).

**Cambios en v0.3 (rev. 2):** D17, entorno corporativo (Zscaler) y Windows, aplicado en E00.

**Cambios en v0.3 (rev. 1):** una CONFUNFIS por CUF; "Crear CUF a partir de otro" para variantes; marca de CUF montado con enlace a su propia CONFUNFIS; maestro de artículos único y común a todos los CUF.

**Cambios en v0.3:**
- Stack = plantilla AACF `web-app` (React 18 + TS + Vite, Tailwind + shadcn/ui, Zustand + React Query, FastAPI + SQLAlchemy 2 async + Alembic, PostgreSQL 16), como mejora sobre brdp-manager.
- La NT 10/17 de 2017 es la referencia válida.
- Se incorporan los *Campos Ficha Datos Básicos SIGLE Contratista*: tablas D106, D107, D112, D113, D114, D155 y POL completas, y reglas entre campos del artículo (AR-002…AR-008).

**Cambios en v0.2:**
- Se añade el rol Revisor.
- La CIL incluye requisitos de tarea (opción completa).
- No hay Keycloak: autenticación propia preparada para el SSO + MFA corporativo, que IT integrará al final.
- HR11 es opcional.
- RBAC con roles semilla fijos, que se afinarán más adelante.
- **Prioridad: demo al cliente de RF-01 a RF-05.** El resto es capa superficial mínima.
- Stack y estructura alineados con brdp-manager v2.
- Encargos reordenados por hitos de demo.

---

## 1. Decisiones de partida

| ID | Tema | Decisión | Estado |
|----|------|----------|--------|
| D1 | Norma que manda | La NT 10/17 se cumple íntegra. La S3000L se aplica parcialmente (CIL, criterios de candidatos, requisitos de tarea, gestión de cambios). La navegación se organiza por planes del PALI. | C |
| D2 | Stack | **Plantilla AACF `web-app`:** React 18 + TypeScript + Vite, Tailwind + **shadcn/ui**, **Zustand** (solo estado de UI global, nunca persistido en el navegador) + **React Query** (estado de servidor), react-router y react-i18next. Backend FastAPI + SQLAlchemy 2 async (asyncpg) + Alembic + PostgreSQL 16. Supone una mejora sobre brdp-manager (que usa JS, CSS propio y sin shadcn/Zustand); de brdp-manager se toman la organización, la verificación y el flujo de encargos. | C |
| D3 | Estructura | Como brdp-manager: frontend en la raíz (`src/`) y backend en `backend/app/{api/routes, core, db, models, repositories, schemas, services}`, con `backend/alembic`, `backend/scripts` y `backend/tests`. Se añaden `backend/app/validacion/` (motor NT) e `backend/app/io_excel/` (plantillas NT/SIGLE). | C |
| D4 | Autenticación | **JWT propio**, como brdp-manager: login email + contraseña (bcrypt), access token RS256 corto en memoria y refresh token revocable en cookie HttpOnly. La validación del token es estructuralmente la misma que con un IdP (clave pública), de modo que **IT conecte al final el SSO + MFA corporativo sin reescribir la autorización.** Es una desviación documentada de `security.mdc` (Keycloak). | C |
| D5 | Roles | `is_admin` global (Settings) y, por material, uno de **Analista, Revisor, Observador** (`user_material_role`, mismo patrón que `UserProjectRole`). La matriz de permisos se siembra fija y se afinará más adelante. | C |
| D6 | HR11 | Opcional en este proyecto. Las reglas NT se implementan como reglas deterministas en un catálogo. | C |
| D7 | Capa superficial | Sin pantallas simuladas (AACF). El sidebar muestra todo el PALI; los módulos no implementados abren su ficha (RF, entradas, salidas, entregable, fase) desde una tabla `modulo_catalogo`. Es un encargo pequeño. | C |
| D8 | Marca | Tokens del AACF como variables CSS de shadcn/ui (capa 1 → capa 2 del design system), con el tema **"azul marino em&e"** (E15b, variante C, la que eligió Juanma: azul marino solo en botones principales, línea de la cabecera, ítem activo del sidebar, pestaña activa y chip principal; fondos, bordes y hover en un azul casi gris; contenido en blanco; AA en claro y oscuro; la variante A, cabecera y sidebar en azul marino, queda como alternativa por tokens) y el logo em&e group en la cabecera. Componentes siempre desde shadcn/ui, nunca primitivas hechas a mano. | P |
| D9 | i18n | react-i18next con `es` poblado (RNF-05), nunca tokens crudos (HR21). | C |
| D10 | Concurrencia | Bloqueo optimista (`version`, 409) y UI optimista (HR20). | C |
| D11 | Cambios y revisión | Auditoría de toda mutación desde E00/E01. Baselines de CONFUNFIS y CIL con flujo **Borrador → En revisión → Revisado** (el Revisor aprueba; adelanto de RF-33). Tocar algo ya baselined exige motivo y referencia de autorización (S3000L cap. 4). | C |
| D12 | Contenedor raíz | **Material = CUF**, equivalente al "proyecto" de brdp-manager: **una CONFUNFIS por CUF**, con su CIL y sus baselines. Cada variante es un CUF distinto (otro NOC) con su propia CONFUNFIS (DEL v02); "Crear CUF a partir de otro" copia CONFUNFIS, partes y productos funcionales. Un CUF montado (NT §9.1.12) es una fila de la CONFUNFIS de la plataforma, marcada y con enlace a su propia CONFUNFIS si existe como material. Los sistemas de sistemas (Anexo III §6) son una sola CONFUNFIS. | C |
| D16 | Artículos | **Maestro de artículos único y común a todos los CUF** (un NOC tiene un único juego de datos básicos en SIGLE). Clave: NOC/NPC o, si no hay, P/N + NCAGE. Vista "dónde se usa" (CUF y posiciones). Puede editarlo un analista con al menos un CUF donde se use; queda auditado y se avisa si afecta a CUF con baseline. | C |
| D17 | Entorno corporativo y Windows | Se aplican las propuestas de mejora al AACF de brdp-manager (18/10/2026): funcionamiento detrás de la inspección SSL de Zscaler sin desactivar nunca la verificación (npm `cafile` / `NODE_EXTRA_CA_CERTS`; Python `SSL_CERT_FILE` con certificados públicos + corporativo, en el entorno del servicio y no en `.env`); Windows como entorno de desarrollo (portabilidad comprobada por tests, UTF-8, LF, PowerShell sin `>` para volcados y contraseñas con `Read-Host`); lockfiles uv `--universal` con hashes, `npm ci` y nunca `npm audit fix --force`. Se monta en E00. | C |
| D18 | Ramas | **Rama de trabajo única** (`claude/new-session-bl3tt3`, rama por defecto del repo), sin PR: Claude Code hace commit y push directamente, con la CI en cada push. **Sin etiquetas**: el punto de vuelta atrás de cada encargo es su commit de cierre, anotado en `docs/historial-cambios.md`. Desviación consciente de G5 del AACF (sin revisión por PR). | C |
| D13 | Datos sensibles | Los ficheros reales (NT "USO OFICIAL", CONFUNFIS con NOC reales) van a `private/`, ignorado por git. Los tests y la demo usan datos **sintéticos** con la misma forma y anomalías. Los `verify-*` que necesitan ficheros reales salen con código 2 ("NOT RUN"), como los de Navantia en brdp-manager. | C |
| D14 | Datos de demo | Script `seed_demo` con un material sintético completo (CUF tipo vehículo de ruedas, unas 150 posiciones con alternativos, CS alternativos, partes, productos funcionales y algunas anomalías intencionadas para enseñar el validador). La demo nunca depende de ficheros del cliente. | C |
| D15 | Tablas SIGLE de referencia | D106, D107, D112, D113, D114, D155 y POL se versionan en el repo como semilla JSON, extraída por script del Excel de campos. Son tablas de codificación OTAN/SIGLE, no contenido "USO OFICIAL"; si prefieres no subirlas, el script lee el Excel desde `private/`. | P |

---

## 2. Documento de cambio respecto al mockup SmartLSA v03

GEIA-STD-0007 se elimina por completo. El asistente IA simulado y el selector de rol de cabecera se retiran; el RBAC es real.

| Mockup (S3000L puro) | Destino en AAL | Nuevo nombre | Plan | RF | Fase |
|---|---|---|---|---|---|
| Panel del programa | Se mantiene, con datos reales | Panel del material | — | — | 1 |
| LSA Guidance Conference | Se transforma | Perfil de misión y concepto de apoyo | PAAL | RF-06 | 2 |
| LSA Program Plan (PP) | Se elimina | — | — | — | — |
| LSA Guidance Document (GD) | Se transforma en reglas parametrizables | Settings → Tablas de referencia / Reglas | Transversal | RNF-07 | 1 |
| Breakdown structures | Se transforma (SNS + CO/AL + CS) | Configuración funcional física | Base común | RF-02 | 1 |
| Variantes y configuraciones | Se reduce (una CONFUNFIS por variante) | — (alternativos AL y CS alternativos) | Base común | RF-02 | 1 |
| Part list (E-BOM/S-BOM) | Se transforma | Tabla de partes | Base común | RF-02 | 1 |
| — | Nuevo | Configuración funcional normalizada | Base común | RF-01 | 1 |
| — | Nuevo | Productos funcionales | Base común | RF-02 | 1 |
| — | Nuevo | Artículos (datos básicos) | Base común | RF-04 | 1 |
| — | Nuevo | Validación NT 10/17 | Base común | RF-03 | 1 |
| CIL vs. actividad | Se mantiene con cambios (criterios, justificación, actividades PALI, requisitos de tarea) | Candidatos AAL | PAAL | RF-05 | 1 |
| RAMT / RAMS | Se divide | Mantenibilidad e indicadores · Diagramas de fiabilidad · Datos de fiabilidad | PRAMT | RF-14…17 | 2 |
| Factores humanos | Se absorbe | Mantenibilidad (ergonomía, accesibilidad) | PRAMT | RF-14 | 2 |
| Mto. correctivo (CMA) | Se absorbe | AMFEC + RCM | PRAMT | RF-08/10 | 2 |
| — (zona RAMS) | Nuevo | AMFEC · FTA · RCM | PRAMT | RF-08…10 | 2 |
| Eventos especiales y daños | Se mantiene (módulo único) | Eventos especiales y daños | PAAL/PRAMT | RF-07/11 | 2 |
| Soporte operacional (OSA) | Se absorbe | Tareas no derivadas de fallo | PMAN | RF-18 | 2 |
| Programa de mto. preventivo | Se transforma | Plan de mantenimiento | PMAN | RF-19 | 2 |
| Nivel de reparación (LORA) | Se mantiene | LORA | PRAMT | RF-13 | 2 |
| Análisis de tareas (MTA) | Se mantiene con codificación SIGLE | MTA | PRAMT | RF-12 | 2 |
| — | Nuevo | Codificación de tareas | PMAN | RF-18 | 2 |
| Soporte de software (SSA) | Se transforma | Recursos informáticos | PRINF | RF-26 | 3 |
| Coste de ciclo de vida (LCC) | Se mantiene | Coste de ciclo de vida | MCCV | RF-31 | 4 |
| Obsolescencia | Se aparca | — | — | — | — |
| Disposal (DA) | Se absorbe | Fase "baja" del MCCV | MCCV | RF-31 | 4 |
| In-Service LSA / ISSO | Se transforma | Datos de uso real | Transversal | RF-37 | 4 |
| Revisión LSA cliente–contratista | Se transforma | Entregas SIGLE | Entregas SIGLE | RF-38…41 | 1b |
| Interfaces S-Series | Se transforma | Documentación técnica · TeamCenter | PDT / Transversal | RF-30/32 | 4 |
| — | Nuevo | PABA, PMAT, PINST, PGCAT, PIC, PPF | Varios | RF-20…29 | 3–4 |

**Nivel de personalización:** de 23 servicios, 6 se mantienen con ajustes, 10 se transforman, 5 se absorben y 2 se eliminan o aparcan. La especificación añade más de 15 pantallas sin equivalente en el mockup.

---

## 3. Navegación

```
Inicio            · Panel del material
Base común        · Configuración funcional normalizada (RF-01) · Materiales / CUF
                  · Configuración funcional física (RF-02) · Tabla de partes · Productos funcionales
                  · Artículos — datos básicos (RF-04) · Validación NT 10/17 (RF-03)
PAAL              · Candidatos AAL (RF-05) · Requisitos de tarea (RF-05)
                  · Perfil de misión y concepto de apoyo [ficha] · Eventos especiales y daños [ficha]
PRAMT · PMAN · PABA · PMAT · PINST · PRINF · PGCAT · PIC · PPF · PDT · MCCV      [fichas]
Entregas SIGLE    [ficha, fase 1b]
Settings          · Usuarios y asignaciones · Tablas de referencia · Reglas de validación
                  · Criterios de candidatos · Plantillas de informe · Auditoría · Módulos
```

---

## 4. Arquitectura y repositorio

Monolito modular: PostgreSQL es la fuente de verdad. En producción, nginx sirve el build y hace de proxy de `/api` hacia FastAPI. Las importaciones grandes son *jobs* en BD con analyze → apply (patrón `import_jobs` de brdp-manager). Todo funciona on-premise (RNF-03).

```
aal/
├── AGENTS.md  CLAUDE.md          # AACF + dominio + desviaciones + cómo levantar, verificar y cerrar encargos
├── aacf/                         # copia del framework (VERSION)
├── docs/
│   ├── plan/                     # este plan, cambio vs mockup, reglas NT, modelo de datos
│   ├── encargos/                 # texto de cada encargo tal como se entregó
│   ├── historial-cambios.md      # una entrada corta por encargo (qué, por qué, commit, tests)
│   └── instalacion/
├── private/                      # IGNORADO por git: ficheros reales del cliente
├── src/                          # frontend: pages, components, layouts, services, hooks, i18n, types, lib
├── public/brand/                 # logo em&e
├── scripts/                      # run-checks.mjs, verify-*.mjs (playwright-core), lib/
├── backend/
│   ├── app/{api/routes, core, db, models, repositories, schemas, services, validacion, io_excel}
│   ├── alembic/  scripts/  tests/{unit,integration,security,fixtures}
│   └── pyproject.toml  requirements[-dev].lock.txt (uv, hashes, --universal)
└── .github/workflows/check.yml
```

**Verificación (igual que brdp-manager):**
- `npm run check`: lint, typecheck, build y `test:js`.
- `npm run check:all`: lo anterior más `test:backend`, con una BD propia `aal_test` y las reglas de `_testdb.py`.
- Scripts `verify-*.mjs` con Chromium real.
- Compatibilidad con Windows vigilada por tests.
- Reglas de cierre de encargo copiadas de brdp-manager (en `CLAUDE.md`).

---

## 5. Modelo de datos — fase 1

**Transversal:** `user` (is_admin, baja lógica), `refresh_token`, `user_material_role` (analista / revisor / observador), `audit_log` (quién, qué, cuándo, antes/después), `app_parameter`, `reference_table` + `reference_value`, `report_template`, `module_catalog`.

**RF-01:**
- `catalog_version` (fichero de origen, hash, fecha, activo, diff con la anterior).
- `material_category` y `material_subcategory`.
- `sns_position` (sns, nombre, descripción, nivel declarado, nivel derivado del código, padre derivado).
- `subcategory_sns` (N:M) y `sns_extra_name` (filas de nivel "ELEMENTO" y nombres alternativos).

**Materiales:** `material` (= CUF: NOC, nombre, P/N, NCAGE; versión de catálogo; `copied_from_material_id` si se creó a partir de otro), `material_subcategory_link` y `sns_request` (solicitud de SNS nuevo a JIMALE). En `physical_position`, si el artículo de una fila es a su vez el CUF de otro material, ese enlace se obtiene por el NOC (o P/N + NCAGE) del CUF, sin duplicar datos.

**RF-04:** `article` (**global**, no cuelga de ningún material, D16): NOC (13, opcional hasta catalogarse), P/N, NCAGE (5), nombre y origen del nombre (coloquial / aprobado / comercial), y los 30 campos del Fichero Carga con su código PRISMA, su número de campo de la guía MAR06, tipo, longitud y tabla de referencia. Control de vida con hasta 3 pares código/cantidad (D114), como permite SIGLE; el Fichero Carga exporta el primero y la decisión queda anotada. Unicidad por NOC (o NPC provisional) si existe, y siempre por (P/N, NCAGE).

**RF-02:**
- `physical_position` (material, sns, co, al, qty, article_id, función, ct_sigle, cs_sns, cs_co, cs_al, `version`). Es un grafo: una misma pieza puede tener varias filas, una por cada CS alternativo.
- `extra_function` (componente multifunción) e `incompatibility`.
- `part` (artículo de configuración, COP, ALP, artículo parte, cantidad).
- `functional_product` (designación GTPF, código OTAN/nacional, N/A/E, NOC, unidad de suministro D155, cantidad, unidad de medida).

**RF-03:** `validation_rule` (código, severidad, activa, referencia NT, parámetros), `validation_run` y `finding`.

**RF-05:**
- `candidate_criterion` (pregunta, grupo completo / parcial / familia / procedimiento estándar, obligatoriedad, umbral, activo).
- `candidate_evaluation` (material, posición, respuestas, categoría propuesta por el motor, categoría decidida, **justificación obligatoria**, autor, fecha).
- `analysis_activity` (columnas configurables: AMFEC, RCM, FTA, eventos especiales, MTA, LORA, mantenibilidad, RBD, PHST, formación, CCV…) y `activity_recommendation` (candidato × actividad 0/1/2 + estado de avance).
- `task_requirement` (S3000L, "CIL con tareas"): candidato, actividad de origen, tipo C/P, acción M101, descripción (≤ 35 caracteres en el campo SIGLE, con texto largo aparte), escalón propuesto 1–4, NOC de gestión propuesto (reglas de NT §12.1), cadencia propuesta si es preventiva, origen legal o reglamentario, estado y justificación.

**Cambios y revisión:** `baseline` (material, ámbito CONFUNFIS/CIL, instantánea, estado borrador / en revisión / revisado, autor, revisor, fechas) y `change_authorization` (código, tipo diseño / LSA / preventivo / waiver, descripción).

---

## 6. Catálogo inicial de reglas NT 10/17 (RF-03)

Medido sobre el ejemplo real (714 filas); el fixture sintético reproduce las mismas cifras.

| Código | Regla | Severidad | Ref. NT | Ejemplo |
|---|---|---|---|---|
| CF-001 | El SNS pertenece a la configuración normalizada del CUF | Bloqueante | §8, §9.1.1 | — |
| CF-002 | Formato SNS: 6 caracteres alfanuméricos (también en el CS) | Bloqueante | §6 | 2 |
| CF-003 | CO entre 01 y 99 | Bloqueante | §9.1.5 | — |
| CF-004 | AL = 00 sin alternativos; 01–99 con alternativos, sin mezclar | Bloqueante | §9.1.6 | 0 |
| CF-005 | QTY entero > 0 | Bloqueante | §9.1.7 | — |
| CF-006 | QTY igual entre alternativos del mismo (SNS, CO, CS) | Bloqueante | §9.1.6–7 | 0 |
| CF-007 | El CS referenciado existe | Bloqueante | §9.1.8 | 6 |
| CF-008 | Toda fila salvo el CUF principal tiene CS | Bloqueante | §9.1.8 | 46 |
| CF-009 | CUF principal en 000000 (o SNS propio si es CUF montado) y sin CS | Bloqueante | §9.1.12 | — |
| CF-010 | Sin ciclos en la cadena de CS | Bloqueante | §9.1.8 | — |
| CF-011 | El CS tiene NOC o P/N (LRU/SRU) | Aviso | §9.1.8 | — |
| CF-012 | NOC de 13 caracteres, o vacío con P/N + NCAGE | Bloqueante | §9.1.3 | 52 |
| CF-013 | NCAGE de 5 caracteres | Bloqueante | §9.1.3 | — |
| CF-014 | Nombre y función del artículo obligatorios | Bloqueante | DEL v02 | 52 |
| CF-015 | Sin filas duplicadas | Bloqueante | — | 21 |
| CF-016 | Datos del CUF idénticos en todas las filas | Bloqueante | §9 | — |
| CF-017 | Un componente multifunción ocupa una sola posición | Aviso | §9.1.1 | — |
| CF-018 | CT SIGLE informado | Aviso | §9.1.9 | 46 |
| TP-001 | Tabla de partes coherente | Bloqueante | §9.1.10 | — |
| PF-001 | Productos funcionales coherentes (N/A/E, D155, NOC, cantidad) | Bloqueante | §9.1.11 | — |
| AR-001 | Datos básicos del artículo: obligatorios, tipo, longitud y valores en tablas D1xx / POL | Aviso (bloqueante en paquete SIGLE) | Campos Ficha | — |
| AR-002 | Reparable = S → al menos un escalón de mantenimiento = S, y si tiene escalón n también los siguientes | Bloqueante | Campos 25, 58 | — |
| AR-003 | Peso → unidad de peso; largo/ancho/alto → unidad de longitud; volumen → unidad de volumen (D112) | Bloqueante | Campos 40–47 | — |
| AR-004 | Control unitario = S → código de control unitario (D113) | Bloqueante | Campos 59–60 | — |
| AR-005 | Control de vida = S → 1 a 3 pares código de vida (D114) + cantidad | Bloqueante | Campos 63–65 | — |
| AR-006 | Mantenimiento preventivo = S exige control de vida = S | Bloqueante | Campos 53, 63 | — |
| AR-007 | Configuración teórica = S exige control unitario = S y grupo estructural 0 o 7 (D107) | Aviso | Campo 57 | — |
| AR-008 | Código de seguridad vacío → "U" (no clasificado) por defecto | Autocorrección registrada | Campo 19 | — |
| CN-001 | Catálogo: SNS con varios nombres | Aviso de importación | §6 | 19 |
| CN-002 | Catálogo: nivel declarado ≠ nivel derivado | Aviso de importación | §6 | 18 (+53 "ELEMENTO") |
| CN-003 | Catálogo: SNS sin padre | Aviso de importación | §6 | 2 |

---

## 7. Encargos y hitos de demo

Todos los encargos se trabajan en la rama única (D18) y se cierran con un commit anotado en el historial. CC sigue el golden path AACF (checklist → implementación → `code-reviewer`) y las reglas de cierre de `CLAUDE.md`. El texto completo de cada encargo se entrega aparte (`docs/encargos/Exx.md`); aquí va el resumen.

### Base (necesaria para cualquier demo)

| Encargo | Contenido | Verificación clave |
|---|---|---|
| **E00** Arranque | Entorno Zscaler + Windows (D17), repo, `AGENTS.md`, `CLAUDE.md`, `aacf/`, docs del plan, backend mínimo con BD + Alembic + `audit_log` + `app_parameter`, frontend mínimo con i18n y marca, `run-checks.mjs`, BD de tests, CI | `npm run check:all` en verde; `verify-health` |
| **E01** Usuarios, roles y Settings | JWT RS256 + refresh en cookie HttpOnly, `create_admin_user`, **entidad `material` mínima**, `user_material_role`, catálogo de roles y permisos sembrado (matriz de solo lectura), Settings → Usuarios y asignaciones, Materiales, Auditoría; dependencias de permiso por material | tests de seguridad (rol × material); `verify-settings-users` |
| **E02** Shell y módulos | Sidebar PALI desde `module_catalog` (45 módulos sembrados desde la especificación), fichas de módulos planificados, URLs por material, Panel del material con datos reales (equipo, avance, actividad) | `verify-navigation` |
| **E03** Tablas de referencia y Excel | `reference_table` editable con semilla completa: niveles, categorías del Anexo I, M101, escalones, operatividad, criticidad, N/A/E, **D106, D107, D112, D113, D114 (temporales / no temporales), D155 y POL** (D15); motor `io_excel` analyze → apply con informe | recuentos de cada tabla; round-trip |

### Hito demo 1 — "Catálogo y CONFUNFIS navegable"

| Encargo | Contenido | Verificación clave |
|---|---|---|
| **E10** RF-01 | Importador CONF_FUN (Anexo II) con versión, diff y avisos CN; árbol por categoría y subcategoría; búsqueda; detalle; exportación | fixture: recuentos y avisos esperados; fichero real en `private/` → 19 CN-001 |
| **E11** Materiales | Completa la entidad `material` de E01: subcategorías, configuración normalizada del CUF (unión), solicitud de SNS, asignación de usuarios; **"Crear CUF a partir de otro"** (variantes) | caso LMV Lince (NT §8.1); la copia es independiente del original |
| **E12** RF-04 Artículos | **Maestro único para todos los CUF** (D16) con vista "dónde se usa" y aviso de impacto en CUF con baseline; maestro con los 30 campos del Fichero Carga (ayuda en línea con la definición MAR06 de cada campo), unicidad, regla de denominación, reglas AR-001…AR-008, rejilla masiva, importación y exportación en formato Fichero Carga | exportación idéntica a la plantilla; tests de cada regla AR |
| **E13** RF-02 núcleo | Posiciones, rejilla Anexo XI, árbol funcional y árbol físico (grafo con CS alternativos), asistentes CO/AL, cantidad total derivada, multifunción, sistemas de sistemas, **CUF montado marcado con enlace a su CONFUNFIS** | ejemplos de NT §9.1.6–9.1.8 (pistón × segmentos = 18, láser 3 × 2…) |
| **E14** RF-02 complementos | Tabla de partes, productos funcionales, incompatibilidades | ejemplos bomba de agua y keroseno |
| **E15** Anexo XI + datos de demo | Importación y exportación del libro CONFUNFIS (cabecera de dos filas) con round-trip exacto; plantilla vacía para subcontratistas; **`seed_demo`** (D14) | round-trip celda a celda; demo sembrada en un comando |

### Hito demo 2 — "Validación NT y control de cambios"

| Encargo | Contenido | Verificación clave |
|---|---|---|
| **E16** RF-03 | Motor de reglas (§6) configurable en Settings, informe en pantalla con salto a la fila, exportación Excel/PDF, exportación SIGLE bloqueada si hay bloqueantes | fixture: CF-002 = 2, CF-007 = 6, CF-008 = 46, CF-012 = 52, CF-014 = 52, CF-015 = 21 |
| **E17** Baselines y revisión | Congelar baseline, flujo Borrador → En revisión → Revisado (Revisor), diff, autorización de cambio obligatoria tras la baseline, historial por fila | edición sin autorización → 422; solo el Revisor aprueba |

### Hito demo 3 — "Candidatos AAL con tareas" (cierre RF-05)

| Encargo | Contenido | Verificación clave |
|---|---|---|
| **E18** RF-05 Candidatos | Criterios parametrizables (S3000L tablas 7–10, fig. 16–17, NT §9.1.2), preevaluación automática con los datos del artículo, cuestionario completo → parcial → no candidato, justificación obligatoria, categorías (completo, parcial, familia, procedimiento estándar, no candidato), matriz candidato × actividad 0/1/2 con suma y avance | tabla de verdad de los flujogramas; no se guarda sin justificación |
| **E19** Requisitos de tarea | Requisitos de tarea por candidato y actividad (tipo C/P, M101, descripción ≤ 35, escalón, NOC de gestión propuesto según §12.1, cadencia), un requisito preventivo exige artículo con control de vida (AR-006) y no se asignan tareas a un NOC no reparable (campo 25); **vista previa no vinculante del código SIGLE de 10 caracteres** (SNS + operatividad + criticidad manual + M101 + secuencial), baseline de la CIL; entregable PAAL "Lista de candidatos AAL justificada" en Excel y Word/PDF con plantilla editable | reglas §12.1 (desmontaje / reparación / montaje → 3 tareas con NOC correctos); secuencial 0-9/A-Z |
| **E20** Panel y cierre | Panel con datos reales; E2E de la demo completa; regresión completa; guía de instalación on-premise; guion de demo para el cliente | `check:all` + todos los `verify-*` |

---

## 8. Capa superficial — resto del PALI

Cada línea es un encargo futuro; hasta entonces es una ficha en `module_catalog`.

| Fase | Encargo futuro | RF | Notas ya identificadas |
|---|---|---|---|
| 1b | Entregas SIGLE (paquete, validación, registro, observaciones, extracciones) | RF-38…41 | La especificación lo sitúa en su fase 1; se recomienda hacerlo justo después de E20. |
| 2 | Perfil de misión y concepto de apoyo | RF-06 | |
| 2 | Eventos especiales y daños | RF-07/11 | Módulo único. |
| 2 | AMFEC + NPR | RF-08 | Anexos IV, V, VII y VIII; criticidad 1/2/3 a partir del NPR (sustituye a la criticidad manual de E19). |
| 2 | FTA · RCM | RF-09/10 | Árbol del Anexo IX. |
| 2 | MTA | RF-12 | Tarea madre: unión de especialidades, máximo de cantidades, horas = Σ(h·cant)/cant_madre. |
| 2 | LORA · Mantenibilidad · RBD · Predicción · Datos de fiabilidad | RF-13…17 | |
| 2 | Codificación definitiva y plan de mantenimiento | RF-18/19 | Anexo X (TAREA, ESPEC, EQUIPO, RPTO, CADENCIA, MODTAREA, STPRO). |
| 3 | PABA · PMAT · PINST · PRINF · PGCAT · PIC | RF-20…28 | |
| 4 | PPF · PDT · MCCV · TeamCenter · flujo de entregables completo · versionado · trazabilidad · Excel masivo · datos de uso real | RF-29…37 | |
| IT | SSO + MFA corporativo | RNF-04 | Lo integra IT al final, sobre D4. |
| Final | Funcionalidades IA | — | LLM local on-premise. |

---

## 9. Preguntas abiertas

1. **CONFUNFIS física:** ¿la elabora el contratista partiendo de la normalizada que da el Ejército? (contradicción entre DEL v02 y RF-02). No bloquea: la app permite crearla e importarla.
2. **Repositorio:** `aal` es **público**. Se recomienda pasarlo a privado (ENS, RNF-04): expone la copia del AACF, con la IP interna del MCP, y el plan, que cita la NT "USO OFICIAL".
3. **Marca:** ¿confirmas el tema em&e (D8)?
4. **Tablas SIGLE en el repo (D15):** ¿se pueden versionar?
