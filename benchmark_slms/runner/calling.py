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


def _slug_modelo(modelo: str, formato: str) -> str:
    nome = modelo.replace("/", "--")
    if formato == "gguf":
        nome += "-gguf"
    return nome


def _pasta_modelo(resultados_dir: Path, modelo: str, formato: str) -> Path:
    return resultados_dir / _slug_modelo(modelo, formato)


def _pasta_resultado(resultados_dir: Path, modelo: str, formato: str, profile_name: str | None) -> Path:
    pasta_modelo = _pasta_modelo(resultados_dir, modelo, formato)
    return pasta_modelo / profile_name if profile_name else pasta_modelo


def contar_execucoes(pasta_modelo: Path) -> int:
    """Conta arquivos execucao_*.json já existentes na pasta do modelo."""
    if not pasta_modelo.exists():
        return 0
    return sum(1 for p in pasta_modelo.glob("execucao_*.json") if p.is_file())


def _proxima_execucao(pasta_modelo: Path) -> int:
    return contar_execucoes(pasta_modelo) + 1


def migrar_resultados_legados(resultados_dir: Path | str) -> list[Path]:
    """Move resultados/<slug>.json → resultados/<slug>/execucao_N.json.

    Preserva o conteúdo e numera a partir das execuções já existentes na pasta.
    """
    pasta = Path(resultados_dir)
    if not pasta.exists():
        return []

    movidos: list[Path] = []
    for legado in sorted(p for p in pasta.glob("*.json") if p.is_file()):
        destino_dir = pasta / legado.stem
        destino_dir.mkdir(parents=True, exist_ok=True)
        destino = destino_dir / f"execucao_{_proxima_execucao(destino_dir)}.json"
        legado.rename(destino)
        movidos.append(destino)
    return movidos


def _salvar_resultado(result: ModelRunResult, resultados_dir: Path) -> Path:
    migrar_resultados_legados(resultados_dir)
    profile_name = result.run_config.inference_profile.name if result.run_config.inference_profile else None
    pasta = _pasta_resultado(resultados_dir, result.modelo, result.formato, profile_name)
    pasta.mkdir(parents=True, exist_ok=True)
    n = _proxima_execucao(pasta)
    path = pasta / f"execucao_{n}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(mode="json"), f, indent=2, ensure_ascii=False, default=str)
    return path


def _carregar_resultado(
    resultados_dir: Path, modelo: str, formato: str, profile_name: str | None = None
) -> ModelRunResult | None:
    """Carrega a execução mais recente do modelo (maior número)."""
    migrar_resultados_legados(resultados_dir)
    pasta = _pasta_resultado(resultados_dir, modelo, formato, profile_name)
    if not pasta.exists():
        return None
    arquivos = [p for p in pasta.glob("execucao_*.json") if p.is_file()]
    if not arquivos:
        return None

    def _num(p: Path) -> int:
        try:
            return int(p.stem.split("_", 1)[1])
        except (IndexError, ValueError):
            return -1

    path = max(arquivos, key=_num)
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
            profile=config.inference_profile,
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
    """Loop perfis × seeds × modelos (unidade de réplica = seed)."""
    from benchmark_slms.protocol import PROTOCOL_SEEDS

    seeds = tuple(PROTOCOL_SEEDS) if config.multi_seed else (config.seed,)
    logger = BenchmarkLogger(logs_dir=config.logs_dir, seed=config.seed)
    logger.log(
        "calling",
        "matriz_inicio",
        extra={
            "modelos": config.modelos,
            "tasks": config.tasks,
            "seeds": list(seeds),
            "unidade_replicacao": "modelo × perfil × seed",
            "n_seeds": len(seeds),
        },
    )

    resultados = []
    perfis = config.inference_profiles or [None]
    for perfil in perfis:
        config_perfil = config
        if perfil is not None:
            # Perfis vencem parâmetros de amostragem avulsos; max_tokens continua global.
            config_perfil = config.model_copy(
                update={
                    "generation_overrides": {
                        **config.generation_overrides,
                        **perfil.generation_overrides(),
                    },
                    "inference_profiles": [],
                    "inference_profile": perfil,
                }
            )
        for seed in seeds:
            config_seed = config_perfil.model_copy(
                update={
                    "seed": seed,
                    "generation_overrides": {
                        **config_perfil.generation_overrides,
                        "seed": seed,
                    },
                }
            )
            for modelo in config_seed.modelos:
                result = executar_modelo(config_seed, modelo, logger=logger)
                resultados.append(result)

    logger.log("calling", "matriz_concluida", extra={"total": len(resultados)})
    return resultados
