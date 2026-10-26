# Flecos pendientes para E14 (pruebas de E13 hechas por Juanma)

Recibidos el 2026-10-26, tras el cierre de E13 (`51b4163`). Se aplican en E14.

1. **Alternativo huérfano.** Si se duplica una fila como alternativo (AL 01 y AL 02) y luego se borra la
   copia, la original se queda en AL 01 con el badge "Alternativo" y sin alternativos (caso real:
   `A22120 01 01` RADIADOR VTL).
   - Según la NT §9.1.6, una pieza sin alternativos va con AL `00`.
   - Al dar de baja una fila que deja un único AL en su hueco (SNS+CO), ofrecer en la confirmación "Volver
     a AL 00 la fila que queda", marcado por defecto y auditado.
   - Añadir la observación "Alternativo único" para los casos ya existentes o importados.
   - El badge "Alternativo" solo se muestra si el hueco tiene ≥ 2 AL.
2. **Buscador en el árbol físico.**
   - Busca por SNS, nombre, NOC o P/N.
   - Expande la ruta hasta cada coincidencia, la resalta y permite ir a la anterior o la siguiente
     ("3 de 7").
   - Añadir además "Expandir todo / Contraer todo".
   - Si es razonable, el mismo buscador va también en la vista funcional.

Notas para E14 (de cómo quedó E13):
- Hoy el badge sale de `Graph.is_alternative` (`app/services/confunfis_graph.py`): AL ≠ 00 o varios AL en el
  hueco. El fleco 1 lo deja en "≥ 2 AL"; la observación nueva sería la siguiente libre (OF-012).
- La baja está en `DELETE /api/materials/{id}/confunfis/rows/{row_id}` (`app/api/routes/confunfis.py`); al
  volver a AL 00 hay que mover también el CS de las filas que cuelgan de ella (como hace
  `duplicate_alternative` al revés).
- El árbol (`src/components/confunfis/PhysicalTree.tsx`) carga por posiciones: el buscador necesitará la
  ruta de CS de cada coincidencia desde el servidor (cadena de padres del grafo).
