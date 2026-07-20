"""Métricas de avaliação: viabilidade + JSON válido -> EvalResult."""

from __future__ import annotations

from benchmark_slms.core.contracts import EvalResult, Prediction
from benchmark_slms.core.registry import register_metric
from benchmark_slms.postprocess.json_task import extrair_e_validar, validar_quantidade


def avaliar_predicao(
    pred: Prediction,
    quantidade_esperada: int = 1,
) -> EvalResult:
    valido, parsed, erro = extrair_e_validar(pred.raw_output)
    qtd_ok, qtd_erro = (True, None)
    if valido and parsed:
        qtd_ok, qtd_erro = validar_quantidade(parsed, quantidade_esperada)

    return EvalResult(
        task_id=pred.task_id,
        modelo=pred.modelo,
        json_valido=valido and qtd_ok,
        json_erro=erro or qtd_erro,
        quantidade_ok=qtd_ok,
        quantidade_erro=qtd_erro,
        parsed=parsed,
        viabilidade=pred.metrics.model_dump(),
        predictions=[pred],
    )


def avaliar_rodadas(
    preds: list[Prediction],
    quantidade_esperada: int,
    metricas_agregadas: dict | None = None,
) -> EvalResult:
    if not preds:
        return EvalResult(
            task_id="unknown",
            modelo="unknown",
            agregado={"rodadas": 0, "json_validos": 0, "crashes_oom": 0},
        )

    json_validos = 0
    json_invalidos = 0
    crashes = 0

    for pred in preds:
        if pred.metrics.crash:
            crashes += 1
            continue
        ev = avaliar_predicao(pred, quantidade_esperada)
        if ev.json_valido:
            json_validos += 1
        else:
            json_invalidos += 1

    n = len(preds)
    agregado = {
        "rodadas": n,
        "json_validos": json_validos,
        "json_invalidos": json_invalidos,
        "taxa_json_valido_percent": round(json_validos / n * 100, 1) if n else 0,
        "crashes_oom": crashes,
    }
    if metricas_agregadas:
        agregado.update(metricas_agregadas)

    return EvalResult(
        task_id=preds[0].task_id,
        modelo=preds[0].modelo,
        json_valido=json_validos == n and crashes == 0,
        viabilidade=metricas_agregadas or {},
        agregado=agregado,
        predictions=preds,
    )


@register_metric("viabilidade")
def metrica_viabilidade(eval_result: EvalResult) -> dict:
    agg = eval_result.agregado
    viab = eval_result.viabilidade
    return {
        "ram_pico_mb": viab.get("ram_pico_mb", agg.get("ram_pico_mb", 0)),
        "tps_medio": viab.get("tps_medio", agg.get("tps_medio", viab.get("tps", 0))),
        "crashes_oom": agg.get("crashes_oom", 0),
        "tempo_medio_segundos": viab.get("tempo_medio_segundos", viab.get("tempo_resposta_s", 0)),
        "ttft_medio_segundos": viab.get("ttft_medio_segundos", viab.get("tempo_prefill_s", 0)),
    }


@register_metric("json_valido")
def metrica_json_valido(eval_result: EvalResult) -> dict:
    return {
        "json_valido": eval_result.json_valido,
        "taxa_json_valido_percent": eval_result.agregado.get("taxa_json_valido_percent", 0),
    }
