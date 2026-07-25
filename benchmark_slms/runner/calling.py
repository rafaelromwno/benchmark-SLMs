"""Orquestrador: matriz N modelos × M tasks via RunConfig."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from benchmark_slms.core.contracts import (
    ModoExecucao,
    ModelRunResult,
    RunConfig,
)
from benchmark_slms.core.logging import BenchmarkLogger
from benchmark_slms.core.registry import get_task, list_tasks
from benchmark_slms.evaluation.veredito import veredito
from benchmark_slms.runner.backends import criar_backend
from benchmark_slms.runner.ambiente import coletar_ambiente
from benchmark_slms.runner.metricas import MetricasInferencia

# Import registra tasks
import benchmark_slms.tasks  # noqa: F401
from benchmark_slms.tasks import snapshot_inferencia


def _nome_arquivo(modelo: str, formato: str) -> str:
    nome = modelo.replace("/", "--")
    if formato == "gguf":
        nome += "-gguf"
    return f"{nome}.json"


def _salvar_resultado(result: ModelRunResult, resultados_dir: Path) -> Path:
    resultados_dir.mkdir(parents=True, exist_ok=True)
    path = resultados_dir / _nome_arquivo(result.modelo, result.formato)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(mode="json"), f, indent=2, ensure_ascii=False, default=str)
    return path


def _carregar_resultado(resultados_dir: Path, modelo: str, formato: str) -> ModelRunResult | None:
    path = resultados_dir / _nome_arquivo(modelo, formato)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return ModelRunResult.model_validate(data)


def _modelo_reprovado(result: ModelRunResult) -> bool:
    if result.veredito:
        return not result.veredito.apto_mathia
    return result.eliminado


def executar_modelo(
    config: RunConfig,
    modelo: str,
    logger: BenchmarkLogger | None = None,
) -> ModelRunResult:
    """Executa todas as tasks configuradas para um modelo."""
    formato = config.backend.value
    model_path = config.modelo_paths.get(modelo)
    if not model_path:
        raise ValueError(f"Caminho do modelo não configurado para '{modelo}'")

    if logger:
        logger.log("calling", "modelo_inicio", modelo=modelo)

    metricas_load = MetricasInferencia()
    backend_kwargs = {
        "n_ctx": config.n_ctx,
        "n_threads": config.n_threads,
        "n_gpu_layers": config.n_gpu_layers,
    }

    if formato == "gguf":
        backend = criar_backend(formato, model_path, metricas=metricas_load, **backend_kwargs)
    else:
        backend = criar_backend(formato, model_path, metricas=metricas_load)

    result = ModelRunResult(
        modelo=modelo,
        formato=formato,
        data=datetime.now().strftime("%d/%m/%Y"),
        run_config=config,
        inferencia=snapshot_inferencia(
            config.generation_overrides,
            n_ctx=config.n_ctx,
            n_threads=config.n_threads,
            n_gpu_layers=config.n_gpu_layers,
            quantizacao=config.quantizacao,
            seed=config.seed,
        ),
        ambiente=coletar_ambiente(),
    )

    tps_por_rodada: list[float] = []

    for task_id in config.tasks:
        if task_id not in list_tasks():
            if logger:
                logger.log("calling", "task_desconhecida", modelo=modelo, task=task_id)
            continue

        if config.modo == ModoExecucao.SELECTION and _modelo_reprovado(result):
            if logger:
                logger.log("calling", "short_circuit", modelo=modelo, task=task_id)
            break

        if logger:
            logger.log("calling", "task_inicio", modelo=modelo, task=task_id)

        task_fn = get_task(task_id)
        eval_result = task_fn(
            backend=backend,
            modelo=modelo,
            seed=config.seed,
            metricas_load=metricas_load,
            generation_overrides=config.generation_overrides or None,
        )
        result.tasks[task_id] = eval_result

        if task_id == "cenario_b":
            tps_por_rodada = eval_result.agregado.get("tps_por_rodada", [])

        if logger:
            logger.log(
                "calling",
                "task_concluida",
                modelo=modelo,
                task=task_id,
                extra={"json_valido": eval_result.json_valido},
            )

        if config.modo == ModoExecucao.SELECTION:
            v_parcial = veredito(
                result.tasks,
                modelo,
                offline=config.offline,
                tps_por_rodada=tps_por_rodada or None,
            )
            if not v_parcial.apto_mathia:
                result.veredito = v_parcial
                result.eliminado = True
                result.motivo_eliminacao = "; ".join(v_parcial.motivos_reprovacao)
                break

    backend.unload()

    if not result.veredito:
        result.veredito = veredito(
            result.tasks,
            modelo,
            offline=config.offline,
            tps_por_rodada=tps_por_rodada or None,
        )

    result.eliminado = not result.veredito.apto_mathia
    if result.eliminado:
        result.motivo_eliminacao = "; ".join(result.veredito.motivos_reprovacao)

    path = _salvar_resultado(result, Path(config.resultados_dir))
    if logger:
        logger.log(
            "calling",
            "modelo_concluido",
            modelo=modelo,
            extra={"apto_mathia": result.veredito.apto_mathia, "resultado": str(path)},
        )

    return result


def executar_matriz(config: RunConfig) -> list[ModelRunResult]:
    """Loop N modelos × M tasks."""
    logger = BenchmarkLogger(logs_dir=config.logs_dir, seed=config.seed)
    logger.log("calling", "matriz_inicio", extra={"modelos": config.modelos, "tasks": config.tasks})

    resultados = []
    for modelo in config.modelos:
        result = executar_modelo(config, modelo, logger=logger)
        resultados.append(result)

    logger.log("calling", "matriz_concluida", extra={"total": len(resultados)})
    return resultados
