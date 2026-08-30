"""Executor: roda inferência, classifica falhas e respeita timeout."""

from __future__ import annotations

import concurrent.futures

from benchmark_slms.core.contracts import CodigoFalha, InferenceMetrics, Prediction, Prompt, UsageStats
from benchmark_slms.core.logging import BenchmarkLogger
from benchmark_slms.protocol import PROTOCOL_TIMEOUT_DEFAULT_S, PROTOCOL_TIMEOUTS_S
from benchmark_slms.runner.backends import GenerationResult, ModelBackend
from benchmark_slms.runner.metricas import MetricasInferencia


def resolver_timeout_s(task_id: str | None, override: float | None = None) -> float:
    if override is not None and override > 0:
        return float(override)
    if task_id and task_id in PROTOCOL_TIMEOUTS_S:
        return PROTOCOL_TIMEOUTS_S[task_id]
    return PROTOCOL_TIMEOUT_DEFAULT_S


def classificar_excecao(exc: BaseException) -> tuple[CodigoFalha, str]:
    nome = type(exc).__name__
    detalhe = str(exc).strip() or repr(exc)
    if isinstance(exc, MemoryError):
        return "oom", f"OOM: {detalhe}"
    if isinstance(exc, TimeoutError):
        return "timeout", detalhe if detalhe not in {"", "TimeoutError()"} else "timeout"
    msg = detalhe.lower()
    if "timed out" in msg or "timeout" in msg:
        return "timeout", f"timeout: {detalhe}"
    if "out of memory" in msg or msg.startswith("oom") or "cannot allocate memory" in msg:
        return "oom", f"OOM: {detalhe}"
    # Sempre inclui o tipo — evita crash_motivo="" quando str(exc) é vazio
    return "crash_motor", f"{nome}: {detalhe}"


def executar_prompt(
    backend: ModelBackend,
    prompt: Prompt,
    modelo: str,
    metricas: MetricasInferencia | None = None,
    rodada: int | None = None,
    logger: BenchmarkLogger | None = None,
    timeout_s: float | None = None,
) -> Prediction:
    """Executa um prompt e retorna Prediction com codigo_falha."""
    codigo: CodigoFalha = "ok"
    crash = False
    crash_motivo: str | None = None
    result: GenerationResult | None = None
    limite = resolver_timeout_s(prompt.task_id, timeout_s)

    if metricas is not None and hasattr(backend, "definir_metricas"):
        backend.definir_metricas(metricas)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(backend.gerar, prompt)
            try:
                result = fut.result(timeout=limite)
            except concurrent.futures.TimeoutError:
                crash = True
                codigo = "timeout"
                crash_motivo = f"timeout: excedeu {limite}s"
                result = None
            else:
                if metricas:
                    metricas.tokens_entrada = result.usage.prompt_tokens
                    if rodada is not None:
                        metricas.finalizar_rodada(result.usage.completion_tokens)
                    else:
                        metricas.finalizar(result.usage.completion_tokens)
        if crash and metricas:
            if rodada is not None:
                metricas.finalizar_rodada(0)
            else:
                metricas.finalizar(0)
    except BaseException as e:
        codigo, crash_motivo = classificar_excecao(e)
        crash = True
        if metricas:
            if rodada is not None:
                metricas.finalizar_rodada(0)
            else:
                metricas.finalizar(0)

    # Stream/backend às vezes “conclui” sem texto — trata como falha explícita
    if (
        not crash
        and result is not None
        and not (result.text or "").strip()
    ):
        crash = True
        codigo = "crash_motor"
        crash_motivo = "resposta_vazia: backend retornou texto vazio"

    metrics = metricas.to_inference_metrics() if metricas else InferenceMetrics()
    metrics.crash = crash
    metrics.crash_motivo = crash_motivo
    metrics.codigo_falha = codigo

    if logger:
        logger.log(
            "execucao",
            "inferencia_concluida" if codigo == "ok" else "inferencia_falha",
            modelo=modelo,
            task=prompt.task_id,
            inferencia=metrics.model_dump(),
        )

    return Prediction(
        sample_id=prompt.sample_id,
        task_id=prompt.task_id,
        modelo=modelo,
        raw_output=result.text if result else "",
        usage=result.usage if result else UsageStats(),
        metrics=metrics,
        rodada=rodada,
    )


def executar_rodadas(
    backend: ModelBackend,
    prompts: list[Prompt],
    modelo: str,
    logger: BenchmarkLogger | None = None,
    timeout_s: float | None = None,
) -> tuple[list[Prediction], MetricasInferencia]:
    """Executa múltiplas rodadas; falhas entram como linhas (não aborta o lote)."""
    metricas = MetricasInferencia()
    predictions: list[Prediction] = []

    for i, prompt in enumerate(prompts):
        metricas.iniciar_rodada()
        pred = executar_prompt(
            backend,
            prompt,
            modelo,
            metricas=metricas,
            rodada=i,
            logger=logger,
            timeout_s=timeout_s,
        )
        predictions.append(pred)

    return predictions, metricas
