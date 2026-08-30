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
    """Agrega contagens entre seeds. `taxa_*=None` (ex.: gabarito sem JSON) não entra no float()."""
    ok = n = 0
    for r in execs:
        agg = _agg_b(r)
        if chave_n in agg:
            n_i = int(agg.get(chave_n) or 0)
            if n_i <= 0:
                continue
            ok += int(agg.get(chave_ok) or 0)
            n += n_i
            continue
        taxa = agg.get(chave_taxa)
        rodadas = agg.get("rodadas")
        if taxa is not None and rodadas:
            n_i = int(rodadas)
            ok += int(round(float(taxa) / 100.0 * n_i))
            n += n_i
            continue
        # Sem denominador explícito: conta 1 tentativa (falha/ausência)
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


def _slug_modelo(modelo: str) -> str:
    return (
        modelo.replace("/", "--")
        .replace(":", "-")
        .replace(" ", "-")
        .lower()
    )


def _linha_quadro(modelo: str, perfil: str | None, execs: list[dict]) -> dict[str, Any]:
    """Uma linha do artigo: agrega todas as seeds de (modelo × perfil)."""
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

    seeds = sorted({s for s in (_seed(r) for r in execs) if s is not None})
    return {
        "modelo": modelo,
        "perfil": perfil,
        "n_execucoes": len(execs),
        "seeds": seeds,
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
        "tps_media": tps.get("media"),
        "tps_p95": tps.get("p95"),
        "ttft_mediana": ttft.get("mediana"),
        "ttft_media": ttft.get("media"),
        "ttft_p95": ttft.get("p95"),
        "ram_pico_mb": ram.get("max") or ram.get("mediana"),
    }


def gerar_quadro_principal(resultados_dir: str | Path = "resultados") -> dict:
    """1 linha por (modelo × perfil), agregando seeds — JSON único da issue #26."""
    from datetime import datetime, timezone

    dados = carregar_resultados(resultados_dir)
    por_celula: dict[tuple[str, str | None], list[dict]] = defaultdict(list)
    for r in dados:
        modelo = r.get("modelo") or "desconhecido"
        por_celula[(modelo, _perfil(r))].append(r)

    linhas = [
        _linha_quadro(modelo, perfil, execs)
        for (modelo, perfil), execs in sorted(
            por_celula.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")
        )
    ]

    return {
        "schema": "benchmark_slms.quadro_principal.v1",
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "quadro_principal": linhas,
        "unidade_analise": "execucao",
        "unidade_linha": "modelo × perfil",
        "nota": (
            "Utilizável = JSON ∧ gabarito estrutural ∧ codigo_falha=ok. "
            "Gabarito é consistência interna (proxy até GT curado em M8). "
            "Proporções: Wilson IC95% sobre rodadas/seeds; "
            "TPS/TTFT: mediana+IQR+p95 e bootstrap IC95% da mediana. "
            "Não ranquear modelos quando ICs de utilizáveis se sobrepõem."
        ),
        "total_linhas": len(linhas),
        "total_modelos": len({row["modelo"] for row in linhas}),
    }


def salvar_quadro_principal(
    resultados_dir: str | Path = "resultados",
    *,
    quadro: dict | None = None,
) -> Path:
    """Persiste o JSON único + `resumo.json` por pasta modelo/perfil."""
    pasta = Path(resultados_dir)
    pasta.mkdir(parents=True, exist_ok=True)
    quadro = quadro or gerar_quadro_principal(pasta)
    destino = pasta / "quadro_principal.json"
    destino.write_text(
        json.dumps(quadro, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    for row in quadro.get("quadro_principal") or []:
        perfil = row.get("perfil") or "sem_perfil"
        celula = pasta / _slug_modelo(row["modelo"]) / perfil
        # se a pasta da célula ainda não existe (slug divergente), grava só o global
        if not celula.exists():
            # tenta localizar pasta existente do modelo
            candidatos = [
                p for p in pasta.iterdir()
                if p.is_dir() and row["modelo"].replace("/", "--") in p.name
            ] if pasta.exists() else []
            celula = (candidatos[0] / perfil) if candidatos else celula
        celula.mkdir(parents=True, exist_ok=True)
        resumo = {
            "schema": "benchmark_slms.resumo_celula.v1",
            "modelo": row["modelo"],
            "perfil": row.get("perfil"),
            "n_execucoes": row["n_execucoes"],
            "seeds": row.get("seeds") or [],
            "metricas": {
                "utilizaveis": row["utilizaveis"],
                "json": row["json"],
                "gabarito": row["gabarito"],
                "estaveis": row["estaveis"],
                "tps": row["tps"],
                "ttft": row["ttft"],
                "ram_pico": row["ram_pico"],
                "contagem_falhas": row["contagem_falhas"],
            },
            "formatos": {
                "utilizaveis": row.get("utilizaveis_fmt"),
                "json": row.get("json_fmt"),
                "gabarito": row.get("gabarito_fmt"),
                "estaveis": row.get("estaveis_fmt"),
            },
        }
        (celula / "resumo.json").write_text(
            json.dumps(resumo, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    return destino


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
    caminho = salvar_quadro_principal(resultados_dir, quadro=quadro)
    print(f"\n{'='*72}")
    print("QUADRO PRINCIPAL (1 linha / modelo × perfil) — unidade: execução")
    print(f"{'='*72}")
    print(quadro["nota"])
    print(f"JSON: {caminho}")
    for row in quadro["quadro_principal"]:
        perfil = row.get("perfil") or "?"
        print(f"\n{row['modelo']} [{perfil}] (n={row['n_execucoes']} seeds={row.get('seeds')})")
        print(f"  Utilizáveis: {row['utilizaveis_fmt']}")
        print(f"  JSON:        {row['json_fmt']}")
        print(f"  Gabarito:    {row['gabarito_fmt']}")
        print(f"  Estáveis:    {row['estaveis_fmt']}")
        print(
            f"  TPS mediana/p95: {row['tps_mediana']} / {row['tps_p95']} | "
            f"TTFT mediana/p95: {row['ttft_mediana']} / {row['ttft_p95']} | "
            f"RAM pico: {row['ram_pico_mb']}"
        )
