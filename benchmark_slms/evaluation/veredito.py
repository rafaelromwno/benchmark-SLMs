"""Veredito apto_mathia — função pura derivada de critérios hard/soft."""

from __future__ import annotations

from benchmark_slms.core.contracts import (
    CategoriaFalha,
    Criterio,
    CriterioTipo,
    EvalResult,
    Veredito,
)

DEFAULT_THRESHOLDS = {
    "ram_pico_mb_max": 2048.0,
    "tps_min": 5.0,
    "crashes_max": 0,
    "taxa_json_valido_min_percent": 60.0,
    "tempo_medio_max_segundos": 90.0,
    "degradacao_tps_max_percent": 40.0,
    "tentativas_json_max": 3,
    "offline": True,
}


def _criterio(
    nome: str,
    tipo: CriterioTipo,
    passou: bool,
    valor,
    limite,
    motivo: str | None,
    categoria: CategoriaFalha,
) -> Criterio:
    return Criterio(
        nome=nome,
        tipo=tipo,
        passou=passou,
        valor=valor,
        limite=limite,
        motivo=None if passou else motivo,
        categoria_falha=CategoriaFalha.NENHUMA if passou else categoria,
    )


def veredito(
    eval_results: dict[str, EvalResult],
    modelo: str,
    thresholds: dict | None = None,
    *,
    offline: bool = True,
    tps_por_rodada: list[float] | None = None,
) -> Veredito:
    """Deriva apto_mathia a partir das métricas agregadas de todas as tasks."""
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    criterios: list[Criterio] = []

    # offline (hard)
    criterios.append(
        _criterio(
            "offline",
            CriterioTipo.HARD,
            offline == t["offline"],
            offline,
            t["offline"],
            "Execução requer conexão externa",
            CategoriaFalha.HARDWARE,
        )
    )

    # Agregar viabilidade de todas as tasks
    ram_pico = 0.0
    tps_medio = float("inf")
    crashes = 0
    tempo_medio = 0.0
    taxa_json = 100.0

    for er in eval_results.values():
        viab = er.viabilidade
        agg = er.agregado
        ram_pico = max(ram_pico, viab.get("ram_pico_mb", agg.get("ram_pico_mb", 0)))
        tps = viab.get("tps_medio", viab.get("tps", float("inf")))
        if isinstance(tps, dict):
            tps = tps.get("media", float("inf"))
        if isinstance(tps, (int, float)) and tps < tps_medio:
            tps_medio = float(tps)
        falhas = agg.get("contagem_falhas") or {}
        if falhas:
            crashes += sum(
                int(falhas.get(c, 0)) for c in ("oom", "timeout", "crash_motor")
            )
        else:
            crashes += int(agg.get("crashes_oom", 0)) + int(agg.get("falhas_infra", 0))
        if agg.get("tempo_medio_segundos"):
            tempo_medio = max(tempo_medio, agg["tempo_medio_segundos"])
        if "taxa_json_valido_percent" in agg:
            taxa_json = min(taxa_json, agg["taxa_json_valido_percent"])

    # cenario_c: tentativas
    c_result = eval_results.get("cenario_c")
    if c_result and c_result.agregado:
        tentativas = c_result.agregado.get("tentativas", 0)
        falhou = c_result.agregado.get("falhou_com_3_tentativas", False)
        passou_json_c = not falhou and tentativas <= t["tentativas_json_max"]
        criterios.append(
            _criterio(
                "json_retry_cenario_c",
                CriterioTipo.HARD,
                passou_json_c,
                tentativas,
                t["tentativas_json_max"],
                f"Falha de JSON recorrente — {tentativas} tentativas",
                CategoriaFalha.FORMATO,
            )
        )

    # RAM (hard)
    criterios.append(
        _criterio(
            "ram_pico_mb",
            CriterioTipo.HARD,
            ram_pico < t["ram_pico_mb_max"],
            round(ram_pico, 1),
            t["ram_pico_mb_max"],
            f"RAM pico {ram_pico:.1f} MB — limite {t['ram_pico_mb_max']} MB",
            CategoriaFalha.HARDWARE,
        )
    )

    # TPS (hard)
    criterios.append(
        _criterio(
            "tps_min",
            CriterioTipo.HARD,
            tps_medio >= t["tps_min"] if tps_medio != float("inf") else True,
            round(tps_medio, 2) if tps_medio != float("inf") else None,
            t["tps_min"],
            f"TPS {tps_medio:.2f} abaixo do mínimo {t['tps_min']}",
            CategoriaFalha.PERFORMANCE,
        )
    )

    # Crashes (hard)
    criterios.append(
        _criterio(
            "crashes_oom",
            CriterioTipo.HARD,
            crashes <= t["crashes_max"],
            crashes,
            t["crashes_max"],
            f"Crash/OOM detectado — {crashes} ocorrência(s)",
            CategoriaFalha.HARDWARE,
        )
    )

    # JSON válido taxa (hard para cenario_b)
    b_result = eval_results.get("cenario_b")
    if b_result and b_result.agregado.get("rodadas"):
        criterios.append(
            _criterio(
                "taxa_json_valido",
                CriterioTipo.HARD,
                taxa_json >= t["taxa_json_valido_min_percent"],
                taxa_json,
                t["taxa_json_valido_min_percent"],
                f"Taxa JSON válido {taxa_json}% abaixo de {t['taxa_json_valido_min_percent']}%",
                CategoriaFalha.FORMATO,
            )
        )

    # Tempo médio (soft)
    if tempo_medio > 0:
        criterios.append(
            _criterio(
                "tempo_medio_rodada",
                CriterioTipo.SOFT,
                tempo_medio < t["tempo_medio_max_segundos"],
                round(tempo_medio, 2),
                t["tempo_medio_max_segundos"],
                f"Tempo médio {tempo_medio:.1f}s acima de {t['tempo_medio_max_segundos']}s",
                CategoriaFalha.PERFORMANCE,
            )
        )

    # Degradação TPS (soft)
    if tps_por_rodada and len(tps_por_rodada) >= 2:
        tps_ini, tps_fim = tps_por_rodada[0], tps_por_rodada[-1]
        if tps_ini > 0:
            degradacao = (tps_ini - tps_fim) / tps_ini * 100
            criterios.append(
                _criterio(
                    "degradacao_tps",
                    CriterioTipo.SOFT,
                    degradacao <= t["degradacao_tps_max_percent"],
                    round(degradacao, 1),
                    t["degradacao_tps_max_percent"],
                    f"Degradação TPS {degradacao:.1f}% entre 1ª e última geração",
                    CategoriaFalha.PERFORMANCE,
                )
            )

    hard_falhas = [c for c in criterios if c.tipo == CriterioTipo.HARD and not c.passou]
    apto = len(hard_falhas) == 0
    motivos = [c.motivo for c in criterios if not c.passou and c.motivo]

    # Todas as categorias hard que falharam (dedup, ordem estável)
    categorias: list[CategoriaFalha] = []
    for c in hard_falhas:
        if c.categoria_falha != CategoriaFalha.NENHUMA and c.categoria_falha not in categorias:
            categorias.append(c.categoria_falha)

    # Primária: hardware > formato > performance > qualidade > primeira
    _prio = {
        CategoriaFalha.HARDWARE: 0,
        CategoriaFalha.FORMATO: 1,
        CategoriaFalha.PERFORMANCE: 2,
        CategoriaFalha.QUALIDADE_CONTEUDO: 3,
    }
    categoria = CategoriaFalha.NENHUMA
    if categorias:
        categoria = sorted(categorias, key=lambda x: _prio.get(x, 99))[0]

    return Veredito(
        apto_mathia=apto,
        criterios=criterios,
        motivos_reprovacao=motivos,
        categoria_falha=categoria,
        categorias_falha=categorias,
        modelo=modelo,
    )
