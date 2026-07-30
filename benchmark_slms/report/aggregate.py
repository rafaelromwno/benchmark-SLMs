"""Leaderboard consolidando resultados/*.json."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def carregar_resultados(resultados_dir: str | Path) -> list[dict]:
    """Carrega execuções em resultados/<modelo>/execucao_N.json."""
    from benchmark_slms.runner.calling import migrar_resultados_legados

    pasta = Path(resultados_dir)
    if not pasta.exists():
        return []

    migrar_resultados_legados(pasta)
    arquivos = sorted(pasta.glob("*/execucao_*.json"))

    resultados = []
    for arquivo in arquivos:
        with open(arquivo, encoding="utf-8") as f:
            resultados.append(json.load(f))
    return resultados


def _ram_pico_de_tasks(tasks: dict) -> float | None:
    picos = []
    for task in tasks.values():
        viab = task.get("viabilidade") or {}
        agreg = task.get("agregado") or {}
        for fonte in (viab, agreg):
            ram = fonte.get("ram_pico_mb")
            if ram and ram > 0:
                picos.append(ram)
    return max(picos) if picos else None


def gerar_leaderboard(resultados_dir: str | Path = "resultados") -> dict:
    """Consolida resultados num leaderboard ordenável."""
    dados = carregar_resultados(resultados_dir)
    if not dados:
        return {
            "leaderboard": [],
            "contagem_categoria_falha": {},
            "total": 0,
            "aptos": 0,
            "reprovados": 0,
        }

    linhas = []
    categorias = Counter()

    for r in dados:
        veredito = r.get("veredito") or {}
        apto = veredito.get("apto_mathia", not r.get("eliminado", True))
        cat = veredito.get("categoria_falha", "nenhuma")
        if not apto:
            categorias[cat] += 1

        tasks = r.get("tasks", {})
        cenario_b = tasks.get("cenario_b", {}).get("agregado", {})

        linhas.append(
            {
                "modelo": r.get("modelo"),
                "formato": r.get("formato"),
                "apto_mathia": apto,
                "categoria_falha": cat if not apto else None,
                "motivo_eliminacao": r.get("motivo_eliminacao"),
                "ram_pico_mb": _ram_pico_de_tasks(tasks),
                "tps_medio": cenario_b.get("tps_medio")
                or tasks.get("cenario_b", {}).get("viabilidade", {}).get("tps_medio"),
                "taxa_json_valido_percent": cenario_b.get("taxa_json_valido_percent"),
            }
        )

    linhas.sort(key=lambda x: (not x["apto_mathia"], -(x.get("tps_medio") or 0)))

    return {
        "leaderboard": linhas,
        "contagem_categoria_falha": dict(categorias),
        "total": len(linhas),
        "aptos": sum(1 for l in linhas if l["apto_mathia"]),
        "reprovados": sum(1 for l in linhas if not l["apto_mathia"]),
    }


def imprimir_leaderboard(resultados_dir: str | Path = "resultados") -> None:
    lb = gerar_leaderboard(resultados_dir)
    print(f"\n{'='*60}")
    print(f"LEADERBOARD — {lb['total']} modelos ({lb['aptos']} aptos, {lb['reprovados']} reprovados)")
    print(f"{'='*60}")

    for i, row in enumerate(lb["leaderboard"], 1):
        status = "✓ APTO" if row["apto_mathia"] else "✗ REPROVADO"
        print(f"{i:2}. [{status}] {row['modelo']} ({row['formato']})")
        if not row["apto_mathia"]:
            print(f"     categoria: {row['categoria_falha']} — {row['motivo_eliminacao']}")
        if row.get("tps_medio") or row.get("ram_pico_mb"):
            tps = f"{row['tps_medio']:.2f}" if row.get("tps_medio") else "N/A"
            ram = f"{row['ram_pico_mb']:.1f}" if row.get("ram_pico_mb") else "N/A"
            print(f"     TPS: {tps} | RAM pico: {ram} MB")

    if lb["contagem_categoria_falha"]:
        print(f"\nContagem por categoria_falha:")
        for cat, n in sorted(lb["contagem_categoria_falha"].items()):
            print(f"  {cat}: {n}")
