"""Logger estruturado JSONL transversal ao pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmark_slms import __version__


class BenchmarkLogger:
    """Escreve eventos estruturados em logs/<run_id>.jsonl."""

    def __init__(
        self,
        logs_dir: str | Path = "logs",
        run_id: str | None = None,
        seed: int | None = None,
    ):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.seed = seed
        self._file = self.logs_dir / f"{self.run_id}.jsonl"

    def log(
        self,
        fase: str,
        evento: str,
        *,
        modelo: str | None = None,
        task: str | None = None,
        quantizacao: str | None = None,
        inferencia: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        registro = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "versao_protocolo": __version__,
            "fase": fase,
            "evento": evento,
            "modelo": modelo,
            "task": task,
            "seed": self.seed,
            "quantizacao": quantizacao,
            "inferencia": inferencia or {},
        }
        if extra:
            registro.update(extra)

        with open(self._file, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")

    @property
    def path(self) -> Path:
        return self._file
