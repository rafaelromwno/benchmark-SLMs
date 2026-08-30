"""Métricas de avaliação: viabilidade + JSON + gabarito + utilizável."""

from __future__ import annotations

from collections import Counter

from benchmark_slms.core.contracts import CodigoFalha, EvalResult, Prediction
from benchmark_slms.core.registry import register_metric
from benchmark_slms.data.ground_truth import gabarito_estrutural_ok
from benchmark_slms.postprocess.json_task import extrair_e_validar, validar_quantidade
from benchmark_slms.report.stats import resumo_continuo, wilson_ic95


def _codigo_infra(pred: Prediction) -> CodigoFalha:
    codigo = pred.metrics.codigo_falha
    if codigo and codigo != "ok":
        return codigo  # type: ignore[return-value]
    if pred.metrics.crash:
        motivo = (pred.metrics.crash_motivo or "").lower()
        if "oom" in motivo:
            return "oom"
        if "timeout" in motivo:
            return "timeout"
        return "crash_motor"
    return "ok"


def avaliar_predicao(
    pred: Prediction,
    quantidade_esperada: int = 1,
) -> EvalResult:
    codigo = _codigo_infra(pred)
    if codigo != "ok":
        pred.metrics.codigo_falha = codigo
        return EvalResult(
            task_id=pred.task_id,
            modelo=pred.modelo,
            json_valido=False,
            json_erro=pred.metrics.crash_motivo,
            gabarito_ok=None,
            utilizavel=False,
            codigo_falha=codigo,
            viabilidade=pred.metrics.model_dump(),
            predictions=[pred],
        )

    extracao = extrair_e_validar(pred.raw_output)
    qtd_ok, qtd_erro = (True, None)
    if extracao.ok and extracao.parsed:
        qtd_ok, qtd_erro = validar_quantidade(extracao.parsed, quantidade_esperada)

    json_valido = bool(extracao.ok and qtd_ok)
    if not json_valido:
        codigo = "json_invalido"

    gabarito_ok = gabarito_estrutural_ok(extracao.parsed) if json_valido else None
    utilizavel = bool(json_valido and gabarito_ok is True and codigo == "ok")

    erro = extracao.erro or qtd_erro
    if extracao.questoes_invalidas and extracao.ok and qtd_ok:
        n_inv = len(extracao.questoes_invalidas)
        erro = f"{n_inv} questão(ões) inválida(s) descartada(s)"

    pred.metrics.codigo_falha = codigo

    return EvalResult(
        task_id=pred.task_id,
        modelo=pred.modelo,
        json_valido=json_valido,
        json_erro=erro,
        quantidade_ok=qtd_ok,
        quantidade_erro=qtd_erro,
        gabarito_ok=gabarito_ok,
        utilizavel=utilizavel,
        codigo_falha=codigo,
        parsed=extracao.parsed,
        viabilidade=pred.metrics.model_dump(),
        agregado={
            "questoes_validas": extracao.questoes_validas,
            "questoes_geradas": extracao.questoes_geradas,
            "questoes_invalidas": extracao.questoes_invalidas,
        },
        predictions=[pred],
    )


def _listas_continuas(preds: list[Prediction]) -> dict[str, list[float]]:
    tps, ttft, tempo, ram = [], [], [], []
    for p in preds:
        if _codigo_infra(p) in {"oom", "timeout", "crash_motor"}:
            continue
        m = p.metrics
        tps.append(float(m.tps))
        ttft.append(float(m.tempo_prefill_s))
        tempo.append(float(m.tempo_resposta_s))
        ram.append(float(m.ram_pico_mb))
    return {"tps": tps, "ttft": ttft, "tempo": tempo, "ram_pico": ram}


def avaliar_rodadas(
    preds: list[Prediction],
    quantidade_esperada: int,
    metricas_agregadas: dict | None = None,
) -> EvalResult:
    if not preds:
        return EvalResult(
            task_id="unknown",
            modelo="unknown",
            agregado={"rodadas": 0, "json_validos": 0, "contagem_falhas": {}},
        )

    por_codigo: Counter[str] = Counter()
    json_validos = 0
    gabarito_ok_n = 0
    gabarito_avaliados = 0
    utilizaveis = 0

    for pred in preds:
        ev = avaliar_predicao(pred, quantidade_esperada)
        por_codigo[ev.codigo_falha] += 1
        if ev.json_valido:
            json_validos += 1
        if ev.gabarito_ok is not None:
            gabarito_avaliados += 1
            if ev.gabarito_ok:
                gabarito_ok_n += 1
        if ev.utilizavel:
            utilizaveis += 1

    n = len(preds)
    listas = _listas_continuas(preds)
    if metricas_agregadas:
        if metricas_agregadas.get("tps_por_rodada"):
            listas["tps"] = [float(x) for x in metricas_agregadas["tps_por_rodada"]]
        if metricas_agregadas.get("ttft_por_rodada"):
            listas["ttft"] = [float(x) for x in metricas_agregadas["ttft_por_rodada"]]
        if metricas_agregadas.get("tempo_por_rodada"):
            listas["tempo"] = [float(x) for x in metricas_agregadas["tempo_por_rodada"]]
        if metricas_agregadas.get("ram_por_rodada"):
            listas["ram_pico"] = [float(x) for x in metricas_agregadas["ram_por_rodada"]]

    tps_r = resumo_continuo(listas["tps"])
    ttft_r = resumo_continuo(listas["ttft"])
    tempo_r = resumo_continuo(listas["tempo"])
    ram_r = resumo_continuo(listas["ram_pico"])

    agregado: dict = {
        "rodadas": n,
        "json_validos": json_validos,
        "json_invalidos": int(por_codigo.get("json_invalido", 0)),
        "taxa_json_valido_percent": round(json_validos / n * 100, 1) if n else 0.0,
        "json_valido_ic95": wilson_ic95(json_validos, n),
        "gabarito_ok": gabarito_ok_n,
        "gabarito_avaliados": gabarito_avaliados,
        "taxa_gabarito_percent": (
            round(gabarito_ok_n / gabarito_avaliados * 100, 1) if gabarito_avaliados else None
        ),
        "gabarito_ic95": wilson_ic95(gabarito_ok_n, gabarito_avaliados)
        if gabarito_avaliados
        else None,
        "utilizaveis": utilizaveis,
        "taxa_utilizavel_percent": round(utilizaveis / n * 100, 1) if n else 0.0,
        "utilizavel_ic95": wilson_ic95(utilizaveis, n),
        "contagem_falhas": dict(por_codigo),
        "crashes_oom": int(por_codigo.get("oom", 0)),
        "tps": tps_r,
        "ttft": ttft_r,
        "tempo": tempo_r,
        "ram_pico": ram_r,
        "tps_medio": tps_r.get("media") or 0.0,
        "ttft_medio_segundos": ttft_r.get("media") or 0.0,
        "tempo_medio_segundos": tempo_r.get("media") or 0.0,
        "ram_pico_mb": ram_r.get("max") or 0.0,
        "tps_por_rodada": listas["tps"],
        "ttft_por_rodada": listas["ttft"],
        "tempo_por_rodada": listas["tempo"],
        "ram_por_rodada": listas["ram_pico"],
    }
    if metricas_agregadas:
        for k, v in metricas_agregadas.items():
            agregado.setdefault(k, v)

    return EvalResult(
        task_id=preds[0].task_id,
        modelo=preds[0].modelo,
        json_valido=json_validos == n and int(por_codigo.get("ok", 0) + por_codigo.get("json_invalido", 0)) >= 0,
        utilizavel=utilizaveis == n and n > 0,
        codigo_falha="ok" if utilizaveis == n and n > 0 else "json_invalido",
        viabilidade={
            "tps": tps_r,
            "ttft": ttft_r,
            "tempo": tempo_r,
            "ram_pico": ram_r,
            "tps_medio": agregado["tps_medio"],
            "ttft_medio_segundos": agregado["ttft_medio_segundos"],
            "tempo_medio_segundos": agregado["tempo_medio_segundos"],
            "ram_pico_mb": agregado["ram_pico_mb"],
        },
        agregado=agregado,
        predictions=preds,
    )


@register_metric("viabilidade")
def metrica_viabilidade(eval_result: EvalResult) -> dict:
    agg = eval_result.agregado
    viab = eval_result.viabilidade
    return {
        "ram_pico_mb": viab.get("ram_pico_mb", agg.get("ram_pico_mb", 0)),
        "tps_medio": viab.get("tps_medio", agg.get("tps_medio", 0)),
        "tps": viab.get("tps", agg.get("tps")),
        "ttft": viab.get("ttft", agg.get("ttft")),
        "contagem_falhas": agg.get("contagem_falhas", {}),
        "crashes_oom": agg.get("crashes_oom", 0),
        "tempo_medio_segundos": viab.get("tempo_medio_segundos", 0),
        "ttft_medio_segundos": viab.get("ttft_medio_segundos", 0),
    }


@register_metric("json_valido")
def metrica_json_valido(eval_result: EvalResult) -> dict:
    return {
        "json_valido": eval_result.json_valido,
        "taxa_json_valido_percent": eval_result.agregado.get("taxa_json_valido_percent", 0),
        "json_valido_ic95": eval_result.agregado.get("json_valido_ic95"),
    }


@register_metric("utilizavel")
def metrica_utilizavel(eval_result: EvalResult) -> dict:
    return {
        "utilizavel": eval_result.utilizavel,
        "taxa_utilizavel_percent": eval_result.agregado.get("taxa_utilizavel_percent", 0),
        "utilizavel_ic95": eval_result.agregado.get("utilizavel_ic95"),
        "taxa_gabarito_percent": eval_result.agregado.get("taxa_gabarito_percent"),
    }
