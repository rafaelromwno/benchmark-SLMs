"""Ponto de entrada — menu interativo."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from benchmark_slms.data.models import DEFAULT_MODELS_DIR

# Registra plugins ao importar o pacote
import benchmark_slms.tasks  # noqa: F401
import benchmark_slms.postprocess.json_task  # noqa: F401
import benchmark_slms.evaluation.metrics  # noqa: F401


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="benchmark-slms",
        description="Protocolo experimental de benchmark de SLMs — menu interativo",
    )
    parser.add_argument(
        "--models-dir",
        default=str(DEFAULT_MODELS_DIR),
        help=f"Pasta local de modelos GGUF (default: {DEFAULT_MODELS_DIR})",
    )
    args = parser.parse_args(argv)

    from benchmark_slms.interactive import menu_interativo

    try:
        return menu_interativo(Path(args.models_dir))
    except KeyboardInterrupt:
        print("\n\nEncerrado.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
