"""CLI.

python -m depuracion depurar --config config.yaml [--estacion EST] [--metodo lineal|ia|auto] [--dry-run]
python -m depuracion evaluar-revision --config config.yaml --archivo revision_outliers.csv
"""

from __future__ import annotations

import argparse
import sys

from .config import ErrorConfiguracion, cargar_config
from .pipeline import ERROR, ejecutar
from .revision import evaluar_archivo
from .salida import tabla_informe


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="depuracion", description="Depuración de demanda eléctrica por estación")
    sub = p.add_subparsers(dest="comando", required=True)

    d = sub.add_parser("depurar", help="detecta y sustituye outliers")
    d.add_argument("--config", required=True)
    d.add_argument("--estacion", action="append", help="procesar solo esta estación (repetible)")
    d.add_argument("--metodo", choices=["lineal", "ia", "auto"])
    d.add_argument("--dry-run", action="store_true", help="no escribe archivos; solo muestra el resumen")

    r = sub.add_parser("evaluar-revision", help="evalúa la revisión manual de outliers")
    r.add_argument("--config", required=True)
    r.add_argument("--archivo", required=True, help="revision_outliers.csv completado por el analista")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        cfg = cargar_config(args.config)
    except ErrorConfiguracion as exc:
        print(f"ERROR de configuración: {exc}", file=sys.stderr)
        return ERROR

    if args.comando == "evaluar-revision":
        res = evaluar_archivo(args.archivo, cfg)
        print(res.to_string(index=False))
        return 0 if (res["resultado"] == "aceptada").all() else ERROR

    res = ejecutar(cfg, estaciones=args.estacion, metodo=args.metodo, dry_run=args.dry_run)
    for err in res.errores:
        print(f"AVISO: {err}", file=sys.stderr)
    if res.estaciones:
        print(tabla_informe(res.estaciones).drop(columns=["comparacion_metodos", "avisos"]).to_string(index=False))
    if res.ruta_salida:
        print(f"\nSalidas en: {res.ruta_salida}")
    return res.codigo


if __name__ == "__main__":
    raise SystemExit(main())
