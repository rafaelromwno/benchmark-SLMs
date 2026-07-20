"""Limpeza de arquivos temporários gerados pelo benchmark."""

from __future__ import annotations

import shutil
from pathlib import Path


def _remover_glob(pasta: Path, pattern: str) -> tuple[int, list[str]]:
    if not pasta.exists():
        return 0, []
    removidos = []
    for arq in pasta.glob(pattern):
        if arq.is_file():
            arq.unlink()
            removidos.append(str(arq))
    return len(removidos), removidos


def _remover_pycache(raiz: Path) -> tuple[int, list[str]]:
    removidos = []
    for cache in raiz.rglob("__pycache__"):
        if cache.is_dir():
            shutil.rmtree(cache)
            removidos.append(str(cache))
    return len(removidos), removidos


def _remover_hf_cache_modelos(models_dir: Path) -> tuple[int, list[str]]:
    """Remove .cache do huggingface_hub dentro de modelos_local_gguf/."""
    removidos = []
    if not models_dir.exists():
        return 0, removidos
    for cache in models_dir.rglob(".cache"):
        if cache.is_dir():
            shutil.rmtree(cache)
            removidos.append(str(cache))
    return len(removidos), removidos


def limpar_temporarios(
    *,
    resultados_dir: Path | str = "resultados",
    logs_dir: Path | str = "logs",
    models_dir: Path | str = "modelos_local_gguf",
    raiz_projeto: Path | str = ".",
    limpar_resultados: bool = True,
    limpar_logs: bool = True,
    limpar_pycache: bool = True,
    limpar_hf_cache: bool = False,
) -> dict:
    """Remove artefatos temporários. Nunca apaga arquivos .gguf."""
    resultados_dir = Path(resultados_dir)
    logs_dir = Path(logs_dir)
    models_dir = Path(models_dir)
    raiz = Path(raiz_projeto)

    relatorio: dict = {"removidos": {}, "total": 0}

    if limpar_resultados:
        n, files = _remover_glob(resultados_dir, "*.json")
        relatorio["removidos"]["resultados_json"] = {"count": n, "files": files}

    if limpar_logs:
        n, files = _remover_glob(logs_dir, "*.jsonl")
        n2, files2 = _remover_glob(logs_dir, "*.log")
        relatorio["removidos"]["logs"] = {
            "count": n + n2,
            "files": files + files2,
        }

    if limpar_pycache:
        n, dirs = _remover_pycache(raiz / "benchmark_slms")
        relatorio["removidos"]["pycache"] = {"count": n, "dirs": dirs}

    if limpar_hf_cache:
        n, dirs = _remover_hf_cache_modelos(models_dir)
        relatorio["removidos"]["hf_cache"] = {"count": n, "dirs": dirs}

    relatorio["total"] = sum(
        sec.get("count", 0) for sec in relatorio["removidos"].values()
    )
    return relatorio


def resumo_limpeza(relatorio: dict) -> str:
    linhas = [f"Total removido: {relatorio['total']} item(ns)\n"]
    rotulos = {
        "resultados_json": "Resultados (resultados/*.json)",
        "logs": "Logs (logs/*.jsonl, *.log)",
        "pycache": "Cache Python (__pycache__)",
        "hf_cache": "Cache HF (.cache em modelos_local_gguf/)",
    }
    for chave, sec in relatorio.get("removidos", {}).items():
        n = sec.get("count", 0)
        if n:
            linhas.append(f"  • {rotulos.get(chave, chave)}: {n}")
    if relatorio["total"] == 0:
        linhas.append("  (nada para remover)")
    linhas.append("\n  Modelos .gguf NÃO são apagados.")
    return "\n".join(linhas)
