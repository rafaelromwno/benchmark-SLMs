"""Leaderboard e quadro principal (parecer v1 §4.1) a partir de resultados/*.json."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmark_slms.report.stats import bootstrap_ic_mediana, resumo_continuo, wilson_ic95


def carregar_resultados(resultados_dir: str | Path) -> list[dict]:
    from benchmark_slms.runner.calling import migrar_resultados_legados

    pasta = Path(resultados_dir)
    if not pasta.exists():
        return []
    migrar_resultados_legados(pasta)
    arquivos = sorted({*pasta.glob("*/execucao_*.json"), *pasta.glob("*/*/execucao_*.json")})
    out: list[dict] = []
    for arquivo in arquivos:
        with open(arquivo, encoding="utf-8") as f:
            out.append(json.load(f))
    return out


def _ram_pico(tasks: dict) -> float | None:
    picos: list[float] = []
    for task in tasks.values():
        for fonte in (task.get("viabilidade") or {}, task.get("agregado") or {}):
            ram = fonte.get("ram_pico_mb")
            if isinstance(ram, dict):
                ram = ram.get("max") or ram.get("mediana")
            if ram and ram > 0:
                picos.append(float(ram))
            resumo = fonte.get("ram_pico")
            if isinstance(resumo, dict) and resumo.get("max"):
                picos.append(float(resumo["max"]))
    return max(picos) if picos else None


def _perfil(resultado: dict) -> str | None:
    inferencia = resultado.get("inferencia") or {}
    perfil = inferencia.get("perfil")
    if isinstance(perfil, dict) and perfil.get("name"):
        return perfil["name"]
    rc = (resultado.get("run_config") or {}).get("inference_profile") or {}
    if isinstance(rc, dict) and rc.get("name"):
        return rc["name"]
    return inferencia.get("profile")


def _seed(resultado: dict) -> int | None:
    rc = resultado.get("run_config") or {}
    if "seed" in rc:
        return rc["seed"]
    return ((resultado.get("inferencia") or {}).get("backend") or {}).get("seed")


def _agg_b(resultado: dict) -> dict:
    return ((resultado.get("tasks") or {}).get("cenario_b") or {}).get("agregado") or {}


def _proporcao(execs: list[dict], chave_taxa: str, chave_ok: str, chave_n: str) -> dict[str, Any]:
    ok = n = 0
    for r in execs:
        agg = _agg_b(r)
        if chave_ok in agg and chave_n in agg and agg[chave_n]:
            ok += int(agg[chave_ok])
            n += int(agg[chave_n])
        elif chave_taxa in agg and agg.get("rodadas"):
            rodadas = int(agg["rodadas"])
            ok += int(round(float(agg[chave_taxa]) / 100.0 * rodadas))
            n += rodadas
        else:
            n += 1
    return wilson_ic95(ok, n)


def _lista(execs: list[dict], chave_resumo: str, chave_lista: str) -> list[float]:
    vals: list[float] = []
    for r in execs:
        agg = _agg_b(r)
        lista = agg.get(chave_lista) or []
        if lista:
            vals.extend(float(x) for x in lista)
            continue
        resumo = agg.get(chave_resumo)
        if isinstance(resumo, dict) and resumo.get("mediana") is not None:
            vals.append(float(resumo["mediana"]))
    return vals


def _estaveis(execs: list[dict]) -> dict[str, Any]:
    if len(execs) < 2:
        out = wilson_ic95(0, 0)
        out["nota"] = "requer ≥2 seeds"
        return out

    por_idx: dict[int, list[bool]] = defaultdict(list)
    for r in execs:
        task = (r.get("tasks") or {}).get("cenario_b") or {}
        preds = task.get("predictions") or []
        if preds:
            for i, p in enumerate(preds):
                codigo = (p.get("metrics") or {}).get("codigo_falha", "ok")
                por_idx[i].append(codigo == "ok")
        else:
            agg = task.get("agregado") or {}
            taxa = float(agg.get("taxa_utilizavel_percent") or agg.get("taxa_json_valido_percent") or 0)
            por_idx[0].append(taxa >= 100)

    estaveis = total = 0
    for flags in por_idx.values():
        if len(flags) < 2:
            continue
        total += 1
        if len(set(flags)) == 1:
            estaveis += 1
    return wilson_ic95(estaveis, total)


def gerar_leaderboard(resultados_dir: str | Path = "resultados") -> dict:
    dados = carregar_resultados(resultados_dir)
    if not dados:
        return {
            "leaderboard": [],
            "contagem_categoria_falha": {},
            "contagem_codigo_falha": {},
            "total": 0,
            "aptos": 0,
            "reprovados": 0,
            "unidade_analise": "execucao",
        }

    linhas = []
    categorias: Counter[str] = Counter()
    codigos: Counter[str] = Counter()

    for r in dados:
        veredito = r.get("veredito") or {}
        apto = veredito.get("apto_mathia", not r.get("eliminado", True))
        cat = veredito.get("categoria_falha", "nenhuma")
        if not apto:
            categorias[cat] += 1

        agg = _agg_b(r)
        for codigo, n in (agg.get("contagem_falhas") or {}).items():
            codigos[codigo] += int(n)

        tps = agg.get("tps") or {}
        ttft = agg.get("ttft") or {}
        linhas.append(
            {
                "modelo": r.get("modelo"),
                "profile": _perfil(r),
                "seed": _seed(r),
                "formato": r.get("formato"),
                "apto_mathia": apto,
                "categoria_falha": cat if not apto else None,
                "motivo_eliminacao": r.get("motivo_eliminacao"),
                "ram_pico_mb": _ram_pico(r.get("tasks") or {}),
                "tps_mediana": tps.get("mediana"),
                "tps_p95": tps.get("p95"),
                "tps_iqr": tps.get("iqr"),
                "tps_medio": agg.get("tps_medio") or tps.get("media"),
                "ttft_mediana": ttft.get("mediana"),
                "ttft_p95": ttft.get("p95"),
                "taxa_json_valido_percent": agg.get("taxa_json_valido_percent"),
                "json_valido_ic95": agg.get("json_valido_ic95"),
                "taxa_utilizavel_percent": agg.get("taxa_utilizavel_percent"),
                "utilizavel_ic95": agg.get("utilizavel_ic95"),
                "contagem_falhas": agg.get("contagem_falhas") or {},
            }
        )

    linhas.sort(
        key=lambda x: (not x["apto_mathia"], -(x.get("tps_mediana") or x.get("tps_medio") or 0))
    )
    return {
        "leaderboard": linhas,
        "contagem_categoria_falha": dict(categorias),
        "contagem_codigo_falha": dict(codigos),
        "total": len(linhas),
        "aptos": sum(1 for l in linhas if l["apto_mathia"]),
        "reprovados": sum(1 for l in linhas if not l["apto_mathia"]),
        "unidade_analise": "execucao",
    }


def gerar_quadro_principal(resultados_dir: str | Path = "resultados") -> dict:
    dados = carregar_resultados(resultados_dir)
    por_modelo: dict[str, list[dict]] = defaultdict(list)
    for r in dados:
        por_modelo[r.get("modelo") or "desconhecido"].append(r)

    linhas = []
    for modelo, execs in sorted(por_modelo.items()):
        utilizavel = _proporcao(execs, "taxa_utilizavel_percent", "utilizaveis", "rodadas")
        json_prop = _proporcao(execs, "taxa_json_valido_percent", "json_validos", "rodadas")
        gabarito = _proporcao(execs, "taxa_gabarito_percent", "gabarito_ok", "gabarito_avaliados")
        estaveis = _estaveis(execs)

        tps_vals = _lista(execs, "tps", "tps_por_rodada")
        ttft_vals = _lista(execs, "ttft", "ttft_por_rodada")
        ram_vals = _lista(execs, "ram_pico", "ram_por_rodada")
        if not ram_vals:
            for r in execs:
                pico = _ram_pico(r.get("tasks") or {})
                if pico:
                    ram_vals.append(pico)

        tps = resumo_continuo(tps_vals)
        ttft = resumo_continuo(ttft_vals)
        ram = resumo_continuo(ram_vals)

        falhas: Counter[str] = Counter()
        for r in execs:
            for k, v in (_agg_b(r).get("contagem_falhas") or {}).items():
                falhas[k] += int(v)

        linhas.append(
            {
                "modelo": modelo,
                "n_execucoes": len(execs),
                "utilizaveis": utilizavel,
                "json": json_prop,
                "gabarito": gabarito,
                "estaveis": estaveis,
                "tps": {**tps, "ic95_mediana": bootstrap_ic_mediana(tps_vals)},
                "ttft": {**ttft, "ic95_mediana": bootstrap_ic_mediana(ttft_vals)},
                "ram_pico": ram,
                "contagem_falhas": dict(falhas),
                "utilizaveis_fmt": utilizavel.get("formato"),
                "json_fmt": json_prop.get("formato"),
                "gabarito_fmt": gabarito.get("formato"),
                "estaveis_fmt": estaveis.get("formato"),
                "tps_mediana": tps.get("mediana"),
                "tps_p95": tps.get("p95"),
                "ttft_mediana": ttft.get("mediana"),
                "ttft_p95": ttft.get("p95"),
                "ram_pico_mb": ram.get("max") or ram.get("mediana"),
            }
        )

    return {
        "quadro_principal": linhas,
        "unidade_analise": "execucao",
        "nota": (
            "Utilizável = JSON ∧ gabarito estrutural ∧ codigo_falha=ok. "
            "Gabarito é consistência interna (proxy até GT curado em M8). "
            "Não ranquear modelos quando ICs de utilizáveis se sobrepõem."
        ),
        "total_modelos": len(linhas),
    }


def imprimir_leaderboard(resultados_dir: str | Path = "resultados") -> None:
    lb = gerar_leaderboard(resultados_dir)
    print(f"\n{'='*60}")
    print(f"LEADERBOARD — {lb['total']} execuções ({lb['aptos']} aptas, {lb['reprovados']} reprovadas)")
    print(f"{'='*60}")
    for i, row in enumerate(lb["leaderboard"], 1):
        status = "✓ APTO" if row["apto_mathia"] else "✗ REPROVADO"
        perfil = f" | perfil: {row['profile']}" if row.get("profile") else ""
        seed = f" | seed: {row['seed']}" if row.get("seed") is not None else ""
        print(f"{i:2}. [{status}] {row['modelo']} ({row['formato']}){perfil}{seed}")
        tps_m = row.get("tps_mediana") or row.get("tps_medio")
        if tps_m is not None or row.get("ram_pico_mb"):
            tps = f"{tps_m:.2f}" if tps_m is not None else "N/A"
            p95 = f"{row['tps_p95']:.2f}" if row.get("tps_p95") is not None else "N/A"
            ram = f"{row['ram_pico_mb']:.1f}" if row.get("ram_pico_mb") else "N/A"
            print(f"     TPS mediana: {tps} | p95: {p95} | RAM pico: {ram} MB")


def imprimir_quadro_principal(resultados_dir: str | Path = "resultados") -> None:
    quadro = gerar_quadro_principal(resultados_dir)
    print(f"\n{'='*72}")
    print("QUADRO PRINCIPAL (1 linha/modelo) — unidade: execução")
    print(f"{'='*72}")
    print(quadro["nota"])
    for row in quadro["quadro_principal"]:
        print(f"\n{row['modelo']} (n={row['n_execucoes']})")
        print(f"  Utilizáveis: {row['utilizaveis_fmt']}")
        print(f"  JSON:        {row['json_fmt']}")
        print(f"  Gabarito:    {row['gabarito_fmt']}")
        print(f"  Estáveis:    {row['estaveis_fmt']}")
        print(
            f"  TPS mediana/p95: {row['tps_mediana']} / {row['tps_p95']} | "
            f"TTFT mediana/p95: {row['ttft_mediana']} / {row['ttft_p95']} | "
            f"RAM pico: {row['ram_pico_mb']}"
        )
