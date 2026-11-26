"""Práctica 9 — cobertura de sentencias y de ramas por módulo (copia para la evidencia).

Igual que docs/pruebas/cobertura_por_modulo.py, salvo que recibe la ruta del JSON
como argumento: python cobertura_por_modulo.py RUTA_AL_JSON

Separa la cobertura de sentencias y la de ramas, que el reporte de terminal
mezcla en una sola columna «Cover».
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
datos = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))  # JSON de `coverage json`

por_modulo = defaultdict(lambda: [0, 0, 0, 0])
for archivo, valores in datos["files"].items():
    partes = Path(archivo).parts  # backend/apps/<módulo>/...
    modulo = partes[2] if len(partes) > 3 else "(apps, raíz)"
    resumen = valores["summary"]
    fila = por_modulo[modulo]
    fila[0] += resumen["num_statements"]
    fila[1] += resumen["covered_lines"]
    fila[2] += resumen["num_branches"]
    fila[3] += resumen["covered_branches"]


def porcentaje(cubiertas, total):
    return 100 * cubiertas / total if total else 100.0


print(f"{'Módulo':<14}{'Sent.':>7}{'Cubier.':>9}{'% sent.':>9}"
      f"{'Ramas':>7}{'Cubier.':>9}{'% ramas':>9}")
for modulo, (sent, cub_s, ramas, cub_r) in sorted(por_modulo.items()):
    print(f"{modulo:<14}{sent:>7}{cub_s:>9}{porcentaje(cub_s, sent):>9.2f}"
          f"{ramas:>7}{cub_r:>9}{porcentaje(cub_r, ramas):>9.2f}")
t = datos["totals"]
print(f"{'TOTAL':<14}{t['num_statements']:>7}{t['covered_lines']:>9}"
      f"{porcentaje(t['covered_lines'], t['num_statements']):>9.2f}"
      f"{t['num_branches']:>7}{t['covered_branches']:>9}"
      f"{porcentaje(t['covered_branches'], t['num_branches']):>9.2f}")
print(f"\nCobertura combinada (sentencias + ramas, la columna Cover): {t['percent_covered']:.2f} %")
