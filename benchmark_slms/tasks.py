"""Tasks de benchmark (cenários A–D) registradas como plugins."""

from __future__ import annotations

import random

from benchmark_slms.core.contracts import EvalResult, Prediction
from benchmark_slms.core.registry import register_task
from benchmark_slms.data.loader import load_for_cenario
from benchmark_slms.data.preprocess import (
    RESOLUCAO_CORRIDA,
    RESOLUCAO_NUMERADA,
    RESOLUCAO_OBJETIVA,
    sample_to_prompt,
)
from benchmark_slms.evaluation.metrics import avaliar_predicao, avaliar_rodadas
from benchmark_slms.runner.backends import ModelBackend
from benchmark_slms.runner.executor import executar_prompt, executar_rodadas
from benchmark_slms.runner.metricas import MetricasInferencia


def _sample_cenario_b(seed: int) -> list:
    ds = load_for_cenario("B")
    rng = random.Random(seed)
    return [rng.choice(list(ds)) for _ in range(10)]


def _viabilidade_de_rodadas(
    metricas: MetricasInferencia,
    preds: list[Prediction],
) -> dict:
    """Agrega RAM/TPS/tempo de inferência (sem carga do modelo) + crashes."""
    agg = metricas.media_rodadas
    agg["tps_por_rodada"] = list(metricas.TPS_por_rodada)
    agg["crashes_oom"] = sum(1 for p in preds if p.metrics.crash)
    return agg


@register_task("cenario_a")
def task_cenario_a(
    backend: ModelBackend,
    modelo: str,
    seed: int = 42,
    metricas_load: MetricasInferencia | None = None,
    **_kwargs,
) -> EvalResult:
    """Cold start — 1 questão, mede RAM/tempo de carga."""
    samples = list(load_for_cenario("A"))
    sample = samples[0]

    prompt = sample_to_prompt(
        sample,
        "cenario_a",
        modelo,
        sufixo_resolucao=RESOLUCAO_CORRIDA,
        generation={"max_tokens": 1024, "temperature": 0, "top_p": 1, "repeat_penalty": 1.1},
    )

    # Reutiliza metricas_load (monitor ligado antes do load do GGUF em calling.py)
    metricas = metricas_load if metricas_load is not None else MetricasInferencia()
    if metricas_load is None:
        metricas.iniciar()

    metricas.marcar_inicio_resposta()
    pred = executar_prompt(backend, prompt, modelo, metricas=metricas)
    ev = avaliar_predicao(pred, sample.quantity)
    viab = metricas.to_inference_metrics().model_dump()
    viab["tempo_carregamento_s"] = metricas.tempo_carregamento_modelo
    ev.viabilidade = viab
    ev.agregado = {
        "cold_start_segundos": metricas.tempo_total,
        "tempo_carregamento_s": metricas.tempo_carregamento_modelo,
        "tempo_resposta_s": metricas.tempo_resposta_modelo,
        "ram_pico_mb": metricas.ram_pico_mb,
        "ram_inicio_mb": metricas.ram_inicio_mb,
        "ttft_segundos": metricas.tempo_prefill,
    }
    return ev


@register_task("cenario_b")
def task_cenario_b(backend: ModelBackend, modelo: str, seed: int = 42, **_kwargs) -> EvalResult:
    """Geração em série — 10 rodadas, JSON + viabilidade."""
    samples = _sample_cenario_b(seed)
    prompts = [
        sample_to_prompt(
            s,
            "cenario_b",
            modelo,
            sufixo_resolucao=RESOLUCAO_NUMERADA,
            generation={"max_tokens": 1024, "temperature": 0.7, "top_p": 0.9, "repeat_penalty": 1.1},
        )
        for s in samples
    ]

    preds, metricas = executar_rodadas(backend, prompts, modelo)
    agg = metricas.media_rodadas
    agg["tps_por_rodada"] = metricas.TPS_por_rodada
    ev = avaliar_rodadas(preds, quantidade_esperada=3, metricas_agregadas=agg)
    return ev


@register_task("cenario_c")
def task_cenario_c(backend: ModelBackend, modelo: str, seed: int = 42, **_kwargs) -> EvalResult:
    """Pressão de JSON — até 3 tentativas para 5 questões."""
    ds = load_for_cenario("C")
    sample = list(ds)[0] if len(ds) > 0 else None
    if not sample:
        return EvalResult(task_id="cenario_c", modelo=modelo, json_valido=False)

    execucoes = 0
    tentativas = 0
    json_valido = False
    preds: list[Prediction] = []
    metricas = MetricasInferencia()

    while tentativas < 3 and not json_valido:
        execucoes += 1
        prompt = sample_to_prompt(
            sample,
            "cenario_c",
            modelo,
            sufixo_resolucao=RESOLUCAO_NUMERADA,
            generation={"max_tokens": 1024, "temperature": 0.7, "top_p": 0.9, "repeat_penalty": 1.1},
        )
        # Modelo já carregado em A — mede só tempo de inferência por tentativa
        metricas.iniciar_rodada()
        pred = executar_prompt(
            backend, prompt, modelo, metricas=metricas, rodada=execucoes - 1
        )
        preds.append(pred)
        ev = avaliar_predicao(pred, sample.quantity)

        if ev.json_valido:
            json_valido = True
        else:
            tentativas += 1

    viab = _viabilidade_de_rodadas(metricas, preds)
    return EvalResult(
        task_id="cenario_c",
        modelo=modelo,
        json_valido=json_valido,
        viabilidade=viab,
        agregado={
            "execucoes": execucoes,
            "quantidade_de_questoes": sample.quantity,
            "tentativas": tentativas,
            "valido_primeira_tentativa": json_valido and execucoes == 1,
            "precisou_retry": json_valido and execucoes > 1,
            "falhou_com_3_tentativas": not json_valido,
            "aprovado": json_valido,
            "ram_pico_mb": viab["ram_pico_mb"],
            "tps_medio": viab["tps_medio"],
            "tempo_medio_segundos": viab["tempo_medio_segundos"],
            "crashes_oom": viab["crashes_oom"],
        },
        predictions=preds,
    )


@register_task("cenario_d")
def task_cenario_d(backend: ModelBackend, modelo: str, **_kwargs) -> EvalResult:
    """Sem contexto BNCC — habilidades sem exemplos."""
    samples = list(load_for_cenario("D"))
    preds: list[Prediction] = []
    outputs = {}
    json_flags = {}
    metricas = MetricasInferencia()

    for i, sample in enumerate(samples):
        prompt = sample_to_prompt(
            sample,
            "cenario_d",
            modelo,
            sufixo_resolucao=RESOLUCAO_NUMERADA,
            generation={"max_tokens": 1024, "temperature": 0.7, "top_p": 0.9, "repeat_penalty": 1.1},
        )
        # Modelo já carregado em A — mede só tempo de inferência por habilidade
        metricas.iniciar_rodada()
        pred = executar_prompt(backend, prompt, modelo, metricas=metricas, rodada=i)
        preds.append(pred)
        ev = avaliar_predicao(pred, sample.quantity)
        json_flags[sample.habilidade_id] = ev.json_valido
        outputs[sample.habilidade_id] = (
            ev.parsed.model_dump() if ev.parsed else {"erro": ev.json_erro, "output_bruto": pred.raw_output[:500]}
        )

    viab = _viabilidade_de_rodadas(metricas, preds)
    all_valid = all(json_flags.values()) if json_flags else False
    return EvalResult(
        task_id="cenario_d",
        modelo=modelo,
        json_valido=all_valid,
        viabilidade=viab,
        agregado={
            "habilidades_testadas": list(json_flags.keys()),
            "outputs": outputs,
            "json_valido_por_habilidade": json_flags,
            "ram_pico_mb": viab["ram_pico_mb"],
            "tps_medio": viab["tps_medio"],
            "tempo_medio_segundos": viab["tempo_medio_segundos"],
            "crashes_oom": viab["crashes_oom"],
            "taxa_json_valido_percent": (
                round(sum(1 for v in json_flags.values() if v) / len(json_flags) * 100, 1)
                if json_flags
                else 0.0
            ),
        },
        predictions=preds,
    )
