# Instalación — entorno corporativo y Windows

Guía para montar AAL en un portátil de desarrollo (Windows o Linux) detrás de
la red corporativa. La instalación en servidor de producción (nginx +
FastAPI) llega con E20; lo que hay aquí ya vale para ella en lo que toca a
certificados y a PowerShell.

**Regla fija: la verificación de certificados nunca se desactiva de forma
permanente.** Si algo falla por certificado, se le da el certificado
corporativo; no se apaga la comprobación.

## Certificado corporativo

La red corporativa inspecciona el tráfico HTTPS (Zscaler): re-firma cada
conexión con el certificado raíz corporativo, que las herramientas no
conocen. El síntoma es un error de certificado al instalar dependencias o al
llamar a un servicio externo; no es un problema del código.

**Antes de nada, el fichero `.pem` del certificado raíz corporativo.** Pídelo
a IT, o expórtalo en Windows: `certmgr.msc` → *Entidades de certificación
raíz de confianza* → *Certificados* → el de Zscaler → *Todas las tareas* →
*Exportar* → "X.509 codificado base 64 (.CER)". Guárdalo, por ejemplo, en
`C:\certs\corporativo.pem` (Linux: `/etc/ssl/certs/corporativo.pem`). Es un
certificado público, no un secreto, pero no se sube al repo.

### npm / Node

Síntoma: `npm ci` o `npm install` falla con
`UNABLE_TO_GET_ISSUER_CERT_LOCALLY` (o `SELF_SIGNED_CERT_IN_CHAIN`); un
script de Node que hace `fetch` a fuera falla con el mismo código.

Arreglo, uno de estos:

1. **Solo npm**: `npm config set cafile "C:\certs\corporativo.pem"`.
   npm sustituye su lista de autoridades por ese fichero, así que vale para
   el registro de npm a través del proxy corporativo.
2. **npm y cualquier proceso de Node** (scripts `verify-*`, Vite):
   la variable de entorno `NODE_EXTRA_CA_CERTS` apuntando al `.pem`. Se
   **añade** a las autoridades que Node ya trae.
   - PowerShell, para la sesión: `$env:NODE_EXTRA_CA_CERTS = "C:\certs\corporativo.pem"`
   - Permanente para tu usuario: `[Environment]::SetEnvironmentVariable("NODE_EXTRA_CA_CERTS", "C:\certs\corporativo.pem", "User")` (abre una consola nueva después).
   - Linux: `export NODE_EXTRA_CA_CERTS=/etc/ssl/certs/corporativo.pem` en `~/.profile`.
3. **Windows, usando el almacén de certificados del sistema** (donde IT ya
   instala el certificado corporativo), sin exportar nada:
   - **Node ≥ 22.15** (y ≥ 23.8) tiene la opción `--use-system-ca`. El
     proyecto usa Node 24 (`.nvmrc`, `>=24.22.1`); se activa para todos los
     procesos con `$env:NODE_OPTIONS = "--use-system-ca"` (o permanente con
     `SetEnvironmentVariable`, como arriba). En Node 24 también vale
     `NODE_USE_SYSTEM_CA=1`, que en Node 22.22 no existía.
   - Con un Node anterior a 22.15: la librería
     [`win-ca`](https://www.npmjs.com/package/win-ca), que lee el almacén de
     Windows (`npm install -g win-ca` y seguir su README para npm). Mejor
     actualizar Node.

`npm config set strict-ssl false` **solo** de forma momentánea, para salir
de un bloqueo y siempre seguido de `npm config set strict-ssl true` en el
mismo momento; nunca se deja así. Y nunca `npm audit fix --force`.

### Python / uv / pip / httpx

Síntoma: `pip install`, `uv pip compile` o una llamada con `httpx` falla con
`SSLCertVerificationError` / `CERTIFICATE_VERIFY_FAILED: unable to get local
issuer certificate`.

Arreglo para pip, httpx y cualquier `ssl` de Python: la variable
`SSL_CERT_FILE` apuntando a un fichero con **los certificados públicos más el
corporativo**. `SSL_CERT_FILE` **reemplaza** a todas las autoridades: si
apunta solo al corporativo, todo lo que no pase por el proxy (o un servicio
interno con otro certificado) deja de verificarse. Se construye así, con el
Python del backend:

```powershell
# PowerShell (desde backend\, con la .venv creada)
$publicos = & .venv\Scripts\python.exe -c "import certifi; print(certifi.where())"
Get-Content $publicos, C:\certs\corporativo.pem | Set-Content -Encoding ascii C:\certs\bundle.pem
$env:SSL_CERT_FILE = "C:\certs\bundle.pem"
```

```bash
# Linux
cat "$(.venv/bin/python -c 'import certifi; print(certifi.where())')" /etc/ssl/certs/corporativo.pem > /etc/ssl/certs/aal-bundle.pem
export SSL_CERT_FILE=/etc/ssl/certs/aal-bundle.pem
```

(Si `certifi` aún no está instalado porque es justo `pip` lo que falla, el
fichero de autoridades públicas del sistema vale igual: en Linux
`/etc/ssl/certs/ca-certificates.crt`.)

- **`REQUESTS_CA_BUNDLE` no sirve**: es de la librería `requests`; `httpx`
  (el cliente HTTP del backend y de sus tests) no la lee. httpx sí lee
  `SSL_CERT_FILE` (y `SSL_CERT_DIR`).
- **`SSL_CERT_FILE` va en el entorno del proceso, no en `backend/.env`**:
  `.env` lo lee la configuración de la app (pydantic-settings) para sus
  propios campos, no lo convierte en variables de entorno, así que el módulo
  `ssl` de Python nunca lo vería. En un servidor:
  - systemd: en la unidad del servicio, `Environment=SSL_CERT_FILE=/etc/ssl/certs/aal-bundle.pem`
    (`systemctl daemon-reload` y reiniciar).
  - Servicio de Windows (p. ej. con NSSM): `nssm set aal-backend AppEnvironmentExtra SSL_CERT_FILE=C:\certs\bundle.pem`.
- **pip** acepta además `pip config set global.cert C:\certs\bundle.pem`.
- **uv** (versión con la que se generan los lockfiles: **0.11.32**) puede usar
  el almacén de certificados del sistema: `--system-certs` o
  `UV_SYSTEM_CERTS=true` (comprobado en 0.11.32; en versiones anteriores la
  opción se llamaba `--native-tls` / `UV_NATIVE_TLS=true`, que 0.11.32 aún
  acepta). También respeta `SSL_CERT_FILE`.

## PowerShell

- **`>` escribe en UTF-16** (Windows PowerShell 5.1) y con fin de línea CRLF:
  estropea un volcado binario (un `pg_dump`, un `.xlsx`) y un `.env` (la
  app leería claves con bytes nulos). Para ficheros de texto usa
  `Set-Content -Encoding utf8` / `Out-File -Encoding utf8`; para binarios, el
  propio programa con su opción de fichero de salida (`pg_dump -f
  copia.dump`), nunca `>`.
- **Las contraseñas nunca se escriben en la línea de comandos** (quedan en el
  historial de PowerShell y en la lista de procesos). Se piden de forma
  interactiva: en PowerShell
  `$clave = Read-Host -AsSecureString "Contraseña"` (nunca `$pwd`, que en PowerShell es la carpeta actual); en los scripts de Python,
  `getpass.getpass()`.
- **Regla para todos los scripts del proyecto**: un secreto (contraseña,
  token, clave) se pide de forma interactiva o se lee de una variable de
  entorno, **nunca de un argumento**. Lo vigilan
  `backend/tests/unit/test_windows_safety.py` y
  `scripts/test-windows-safety.mjs`.
- Activar la `.venv`: `backend\.venv\Scripts\Activate.ps1` (si la política lo
  impide, `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`), o llamar
  directamente a `backend\.venv\Scripts\python.exe`.
- Todos los comandos de verificación (`npm run check`, `npm run check:all`,
  `npm run test:db:create`) son scripts de Node sin sintaxis de shell: se
  escriben igual en PowerShell que en Linux.

## Dependencias

- Frontend: siempre `npm ci` (instala exactamente `package-lock.json`).
  Nunca `npm audit fix --force`.
- Backend: `python -m pip install --require-hashes -r requirements-dev.lock.txt`
  (desarrollo) o `requirements.lock.txt` (servidor). Los lockfiles se generan
  con uv `--universal --generate-hashes`, así que los mismos hashes valen en
  Windows y en Linux.
