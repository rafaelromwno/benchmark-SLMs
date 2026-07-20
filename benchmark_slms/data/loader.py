"""Universal Data Loader: converte fontes variadas em Dataset[Sample]."""

from __future__ import annotations

import json
from pathlib import Path

from benchmark_slms.core.contracts import Sample

_DATASETS_DIR = Path(__file__).parent / "datasets"


class Dataset:
    """Coleção imutável de Samples."""

    def __init__(self, samples: list[Sample]):
        self._samples = samples

    def __iter__(self):
        return iter(self._samples)

    def __len__(self) -> int:
        return len(self._samples)

    def __getitem__(self, idx: int) -> Sample:
        return self._samples[idx]

    def filter(self, **kwargs) -> Dataset:
        result = []
        for s in self._samples:
            match = all(getattr(s, k, s.meta.get(k)) == v for k, v in kwargs.items())
            if match:
                result.append(s)
        return Dataset(result)

    def filter_meta(self, **kwargs) -> Dataset:
        result = [s for s in self._samples if all(s.meta.get(k) == v for k, v in kwargs.items())]
        return Dataset(result)

    def sample_random(self, n: int = 1, seed: int = 42) -> list[Sample]:
        import random

        rng = random.Random(seed)
        if n >= len(self._samples):
            return list(self._samples)
        return rng.sample(self._samples, n)


def _parse_jsonl(path: Path) -> list[Sample]:
    samples = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            samples.append(
                Sample(
                    id=data.get("id", f"{path.stem}-{i}"),
                    habilidade_id=data["habilidade_id"],
                    unidade_tematica=data["unidade_tematica"],
                    prerequisites=data.get("prerequisites", []),
                    examples=data.get("examples", []),
                    quantity=data.get("quantity", 1),
                    meta=data.get("meta", {}),
                    golden=data.get("golden"),
                )
            )
    return samples


def load_jsonl(path: str | Path) -> Dataset:
    return Dataset(_parse_jsonl(Path(path)))


def load_bncc() -> Dataset:
    """Carrega o dataset BNCC versionado."""
    return load_jsonl(_DATASETS_DIR / "bncc.jsonl")


def load_for_cenario(cenario: str) -> Dataset:
    """Retorna samples filtrados por cenario (A/B/C/D) no meta."""
    return load_bncc().filter_meta(cenario=cenario)
