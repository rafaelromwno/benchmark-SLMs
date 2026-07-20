"""Executor: roda inferência e coleta métricas."""

from __future__ import annotations

from benchmark_slms.core.contracts import InferenceMetrics, Prediction, Prompt, UsageStats
from benchmark_slms.core.logging import BenchmarkLogger
from benchmark_slms.runner.backends import GenerationResult, ModelBackend
from benchmark_slms.runner.metricas import MetricasInferencia


def executar_prompt(
    backend: ModelBackend,
    prompt: Prompt,
    modelo: str,
    metricas: MetricasInferencia | None = None,
    rodada: int | None = None,
    logger: BenchmarkLogger | None = None,
) -> Prediction:
    """Executa um prompt e retorna Prediction com métricas."""
    crash = False
    crash_motivo = None
    result: GenerationResult | None = None

    try:
        result = backend.gerar(prompt)
        if metricas:
            metricas.tokens_entrada = result.usage.prompt_tokens
            if rodada is not None:
                metricas.finalizar_rodada(result.usage.completion_tokens)
            else:
                metricas.finalizar(result.usage.completion_tokens)
    except MemoryError as e:
        crash = True
        crash_motivo = f"OOM: {e}"
        if metricas:
            if rodada is not None:
                metricas.finalizar_rodada(0)
            else:
                metricas.finalizar(0)
    except Exception as e:
        crash = True
        crash_motivo = str(e)
        if metricas:
            if rodada is not None:
                metricas.finalizar_rodada(0)
            else:
                metricas.finalizar(0)

    metrics = metricas.to_inference_metrics() if metricas else InferenceMetrics()
    metrics.crash = crash
    metrics.crash_motivo = crash_motivo

    if logger:
        logger.log(
            "execucao",
            "inferencia_concluida" if not crash else "inferencia_crash",
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
) -> tuple[list[Prediction], MetricasInferencia]:
    """Executa múltiplas rodadas com métricas agregadas."""
    metricas = MetricasInferencia()
    predictions = []

    for i, prompt in enumerate(prompts):
        metricas.iniciar_rodada()
        pred = executar_prompt(
            backend, prompt, modelo, metricas=metricas, rodada=i, logger=logger
        )
        predictions.append(pred)
        if pred.metrics.crash:
            break

    return predictions, metricas
