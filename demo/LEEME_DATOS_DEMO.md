# Datos de demostración AAL — VTL 4X4 TRAMONTANA (ficticio)

Todos los datos de esta carpeta son **inventados**: el material, los NOC, los P/N, los NCAGE y los fabricantes. Siguen el formato y las reglas de la NT 10/17 para que la demo sea realista, pero no corresponden a ningún material real.

- Los NOC son NPC provisionales con una `X` en la posición 7: `NNNN33X9xxxxx` (13 caracteres).
- Los NCAGE son `DEMO1`…`DEMO5`.
- Los códigos SNS siguen la estructura de la NT (6 caracteres, 5 niveles).
- Los códigos de las tablas SIGLE (D107, D112, D113, D114, D155, POL) son valores válidos de las tablas de referencia de la app.

## 1. Materiales a dar de alta (Settings → Materiales → Nuevo material)

| # | Nombre | NOC | P/N | NCAGE | Descripción | Para qué sirve en la demo |
|---|---|---|---|---|---|---|
| 1 | VTL 4X4 TRAMONTANA | 232033X900001 | TRM-4X4-A | DEMO1 | Vehículo táctico ligero 4x4 para transporte de personal y carga en cualquier terreno. Motor diésel de 6 cilindros y 280 CV, transmisión automática y tracción total. Subcategorías: 0601 vehículos de ruedas, 0201 telecomunicaciones y mando y control, 0102 armamento secundario. | Material principal: tiene catálogo, artículos y CONFUNFIS completos en esta carpeta. |
| 2 | VTL 4X4 TRAMONTANA PUESTO DE MANDO | 232033X900002 | TRM-4X4-PC | DEMO1 | Variante puesto de mando del VTL 4X4 Tramontana, con ordenador de misión y radios de mando adicionales. Tiene CONFUNFIS propia. Subcategorías: 0601, 0201 y 0102. | Variante: cada variante es un CUF con su propia CONFUNFIS. En E11 se creará "a partir de otro". |
| 3 | RADIO VHF RT-500 | 582033X901001 | RT-500-V2 | DEMO3 | Radioteléfono VHF vehicular de voz y datos. CUF montado en la posición E12300 del VTL 4X4 Tramontana. Subcategoría: 0201. | CUF montado (NT §9.1.12): es material propio y a la vez una fila de la CONFUNFIS del Tramontana. |
| 4 | MOTOR DIESEL 6 CIL DM-6 280 CV | 281533X900101 | DM6-280-00 | DEMO2 | Motor diésel de 6 cilindros y 280 CV del VTL 4X4 Tramontana, gestionado como material reparable independiente, con control de vida por horas. Subcategoría: 0601. | Componente reparable de alto valor que se gestiona aparte. |
| 5 | VTO GREGAL | 235033X900003 | GRG-VTO-A | DEMO1 | Vehículo de transporte sobre orugas. Comparte el grupo motor DM-6 con el Tramontana y monta cadenas. Subcategoría: 0602 vehículos de cadenas. | Otra plataforma que comparte el grupo motor (SNS A2…) pero usa cadenas (B35…): muestra que un SNS es común a varias subcategorías. |

Asigna a cada uno los usuarios de desarrollo: `analista.dev` como Analista, `revisor.dev` como Revisor y `observador.dev` como Observador.

## 2. Ficheros para importar cuando llegue cada módulo

| Fichero | Formato | Se importa en | Contenido |
|---|---|---|---|
| `CONF_FUN_DEMO.xlsx` | Anexo II (hoja `CONF_FUN`) | E10 · Configuración funcional normalizada | 101 filas, 68 SNS, 4 categorías y 5 subcategorías (00-00, 01-02, 02-01, 06-01, 06-02). |
| `FICHERO_CARGA_DEMO.xlsx` | Fichero Carga / PRISMA PB06 (2 filas de cabecera: nombre + código PRISMA) | E12 · Artículos | 45 artículos con sus 30 campos MAR06. |
| `CONFUNFIS_DEMO_TRAMONTANA.xlsx` | Anexo XI: hojas `CON_FUN_FIS`, `TABLA PRODUCTOS FUNCIONALES` y `TABLA DE PARTES` | E15 · Importación CONFUNFIS (E13–E14 para verla) | 46 posiciones, 8 productos funcionales y la tabla de partes de la bomba de agua. |

La hoja `TABLA DE PARTES` sigue la estructura de la NT §9.1.10 (ARTÍCULO NOC/P/N/NCAGE · COP · ALP · PARTES NOC/P/N/NCAGE · CANTIDAD); el ejemplo del Anexo XI que recibimos no la incluía.

## 3. Qué ilustra la CONFUNFIS del Tramontana (ejemplos de la NT reproducidos)

| Concepto NT | Filas |
|---|---|
| CUF principal en `000000`, sin conjunto superior (§9.1.12) | `000000 01 00` VTL 4X4 TRAMONTANA |
| Cantidad por unidad del conjunto superior (§9.1.7) | 6 pistones (`A21030`) con CS motor, y 3 segmentos (`A21031`) con CS pistón → 18 segmentos en total |
| Huecos físicos (CO) y alternativos (AL) (§9.1.5–9.1.6) | Silentblocks `A27010` CO 01–03; en el CO 03, AL 01 (antiguo) y AL 02 (mejorado), con la misma QTY |
| Alternativos del mismo hueco | Filtro de combustible `A23120` 01/01 y 01/02 de dos fabricantes |
| Agregación de funciones (§9.1.4) | Conjunto ventilador `A22210`, con ventilador `A22211` y acoplamiento `A22212` colgando de él |
| Mismo NOC en dos huecos con distinto CS (§9.1.8, caso 1) | Switch Ethernet `E19200` CO 01 en la unidad de control y CO 02 en el ordenador de misión |
| Mismo componente en CS alternativos (§9.1.8, caso 2) | Ordenador de misión `L41100` repetido con CS armario 10U (`L48000 01 01`) y 12U (`L48000 01 02`) |
| Software y firmware (Anexo III §5.6) | `L41120` software de misión (FLS) y `L41130` firmware, con CS el ordenador |
| CUF montado (§9.1.12) | 2: Radio VHF RT-500 en `E12300` y Motor DM-6 en `A20000` (los dos son materiales propios con su CONFUNFIS) |
| Interfaz de armamento en la plataforma (§9.1.12) | Afuste para arma ligera en `C66100` |
| Tabla de partes (§9.1.10) | Bomba de agua: junta (COP 01) y racor con dos alternativos (COP 02, ALP 01/02) |
| Productos funcionales (§9.1.11) | Aceite motor O-1236 (N) y O-1178 (A), ATF H-548, líquido de frenos H-542, anticongelante S-750, gasóleo TF-03, grasa G-403 |

## 4. Anomalías puestas a propósito (para enseñar los validadores)

**Catálogo `CONF_FUN_DEMO.xlsx` (avisos de importación, E10):**

| Aviso | Caso |
|---|---|
| CN-001 SNS con varios nombres | `A21031` (SEGMENTOS / JUEGO DE SEGMENTOS) y `B33011` (NEUMÁTICO / VÁLVULA DE INFLADO, fila ELEMENTO) |
| CN-002 nivel declarado ≠ nivel del código | 2: `A22200` declarado CONJUNTO en vehículos de ruedas (por su código es SUBSUBSISTEMA), y `B34510` declarado SUBCONJUNTO (por su código es CONJUNTO) |
| CN-003 SNS sin padre | 2: `B34510` (no existe `B34500`) y `D53000` (no existe el sistema `D50000`) |
| CN-004 fila sin categoría | `ZDM100` |
| CN-005 descripción partida en dos columnas | `E11000` RADIO |
| CN-006 descripción pendiente | 6 filas `PTE` (4 SNS: `A22140`, `A72000`, `B33012`, `L41130`) y 1 `TBD` |

**CONFUNFIS `CONFUNFIS_DEMO_TRAMONTANA.xlsx` (validación NT, E16):** exactamente 6 errores bloqueantes.

| Regla | Fila |
|---|---|
| CF-001 SNS fuera de la configuración normalizada del CUF | `B35010` (eslabones de cadena: solo existe en vehículos de cadenas) |
| CF-002 SNS del conjunto superior mal formado | Amortiguador `B31010` con CS `B300000000` (10 caracteres) |
| CF-007 conjunto superior inexistente | Filtro de aire `A24110` con CS `A24000 01 00`, que no está en la configuración |
| CF-012 sin NOC ni P/N | Tapón de llenado (`A22140` CO 02) |
| CF-014 sin función | Mazo de cables principal `D53000` |
| CF-015 fila duplicada | Disco de freno `B32020` |

Productos funcionales (PF-001): el último aceite usa la unidad de suministro `ZZ`, que no existe en D155.

**Artículos `FICHERO_CARGA_DEMO.xlsx` (reglas AR, E12):**

| Regla | Artículo |
|---|---|
| AR-002 reparable sin ningún escalón de mantenimiento | Depósito de expansión |
| AR-003 peso sin unidad de peso | Acoplamiento viscoso |
| AR-006 mantenimiento preventivo sin control de vida | Biela DM-6 |
| AR-001 sin NOC (aviso) | Tapón de llenado |
| AR-007 control de configuración = S sin grupo estructural 0 o 7 (aviso) | Caja de cambios automática 6V (grupo 3) |

No hay más avisos AR: solo el Tramontana, la Radio RT-500 y el Motor DM-6 (los tres son CUF, grupo 0) tienen control de configuración.

## 5. Guion corto para la demo

1. Panel del material del Tramontana: equipo, roles y estado de la herramienta.
2. Settings: usuarios, roles por material y auditoría.
3. Tablas de referencia SIGLE (D114, D155, POL) y su exportación e importación con informe.
4. Con E10: importar `CONF_FUN_DEMO.xlsx`, ver el árbol, buscar `A27010` y abrir **Avisos de la versión**. Mensaje: "la app detecta incoherencias del propio catálogo antes de usarlo".
5. Resto de ficheros, a medida que lleguen E12, E15 y E16.
