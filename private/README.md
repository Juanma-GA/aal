# private/ — ficheros reales del cliente (nunca en git)

Aquí van los ficheros **reales** de em&e y del Ejército que el desarrollo o
algún `verify-*` necesita: la NT 10/17 ("USO OFICIAL"), CONFUNFIS con NOC
reales, el Excel de *Campos Ficha Datos Básicos SIGLE Contratista*, ficheros
de carga SIGLE, etc. (decisión D13 del plan).

- Todo lo que hay en esta carpeta, salvo este `README.md`, está ignorado por
  git (`.gitignore`: `private/*` con la excepción `!private/README.md`).
  Compruébalo con `git ls-files private/`: solo debe salir este fichero.
- **Nunca** se sube: ni a una rama, ni a un PR, ni a un issue, ni copiado
  dentro de un test.
- Los tests y la demo usan datos **sintéticos** con la misma forma y las
  mismas anomalías (`backend/tests/fixtures/`, `seed_demo`).
- Un `verify-*` que necesita un fichero de aquí y no lo encuentra sale con
  código 2 ("NOT RUN"), nunca 1: no es un fallo de la app.
