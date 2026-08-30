"""Regressões dos ruídos de telemetria/veredito observados nas execuções."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from benchmark_slms.core.contracts import (
    EvalResult,
    InferenceMetrics,
    Prediction,
    Prompt,
    PromptMessage,
    UsageStats,
)
from benchmark_slms.evaluation.veredito import veredito
from benchmark_slms.runner.backends import GenerationResult
from benchmark_slms.runner.executor import executar_prompt
from benchmark_slms.runner.metricas import MetricasInferencia


def test_veredito_prioriza_hardware_e_lista_categorias() -> None:
    ers = {
        "cenario_a": EvalResult(
            task_id="cenario_a",
            modelo="m",
            json_valido=False,
            viabilidade={"ram_pico_mb": 2573.0, "tps_medio": 40.0},
            agregado={"ram_pico_mb": 2573.0, "crashes_oom": 0},
        ),
        "cenario_b": EvalResult(
            task_id="cenario_b",
            modelo="m",
            json_valido=False,
            viabilidade={"ram_pico_mb": 2560.0, "tps_medio": 80.0, "tempo_medio_segundos": 2.0},
            agregado={
                "taxa_json_valido_percent": 10.0,
                "rodadas": list(range(10)),
                "ram_pico_mb": 2560.0,
                "tempo_medio_segundos": 2.0,
                "crashes_oom": 0,
            },
        ),
        "cenario_c": EvalResult(
            task_id="cenario_c",
            modelo="m",
            json_valido=False,
            viabilidade={"ram_pico_mb": 2569.0, "tps_medio": 90.0},
            agregado={
                "tentativas": 3,
                "falhou_com_3_tentativas": True,
                "ram_pico_mb": 2569.0,
                "crashes_oom": 0,
            },
        ),
    }
    v = veredito(ers, "m", offline=True)
    dump = v.model_dump(mode="json")
    assert dump["categoria_falha"] == "hardware"
    assert "hardware" in dump["categorias_falha"]
    assert "formato" in dump["categorias_falha"]


def test_executar_prompt_liga_metricas_no_backend_e_registra_prefill() -> None:
    metricas = MetricasInferencia()
    metricas.iniciar_rodada()
    backend = MagicMock()

    def _gerar(_prompt):
        backend.definir_metricas.assert_called()
        m = backend.definir_metricas.call_args[0][0]
        m.marcar_inicio_resposta()
        time.sleep(0.02)
        m.marcar_primeiro_token()
        time.sleep(0.01)
        return GenerationResult(
            text='{"questoes":[]}',
            usage=UsageStats(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            raw={},
        )

    backend.gerar.side_effect = _gerar
    prompt = Prompt(
        sample_id="s",
        task_id="cenario_b",
        messages=[PromptMessage(role="user", content="x")],
    )
    pred = executar_prompt(backend, prompt, modelo="m", metricas=metricas, rodada=0)
    assert pred.metrics.tempo_prefill_s > 0
    assert metricas.ttft_por_rodada and metricas.ttft_por_rodada[-1] > 0


def test_cenario_c_propaga_codigo_falha(monkeypatch) -> None:
    from benchmark_slms import tasks as tasks_mod

    class FakeSample:
        quantity = 5
        id = "s1"

    monkeypatch.setattr(tasks_mod, "load_for_cenario", lambda _c: [FakeSample()])
    monkeypatch.setattr(
        tasks_mod,
        "sample_to_prompt",
        lambda sample, *a, **k: Prompt(
            sample_id=sample.id,
            task_id="cenario_c",
            messages=[PromptMessage(role="user", content="x")],
        ),
    )

    def fake_executar(backend, prompt, modelo, metricas=None, rodada=None, timeout_s=None, logger=None):
        return Prediction(
            sample_id=prompt.sample_id,
            task_id="cenario_c",
            modelo=modelo,
            raw_output='{"questoes":[{"enunciado":"Q?"}]}',
            usage=UsageStats(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            metrics=InferenceMetrics(tps=10.0, codigo_falha="json_invalido"),
            rodada=rodada,
        )

    monkeypatch.setattr(tasks_mod, "executar_prompt", fake_executar)
    monkeypatch.setattr(
        tasks_mod,
        "avaliar_predicao",
        lambda pred, qtd: EvalResult(
            task_id="cenario_c",
            modelo=pred.modelo,
            json_valido=False,
            utilizavel=False,
            codigo_falha="json_invalido",
        ),
    )
    monkeypatch.setattr(
        tasks_mod,
        "_viabilidade_de_rodadas",
        lambda m, p: {
            "ram_pico_mb": 100.0,
            "tps_medio": 10.0,
            "tempo_medio_segundos": 1.0,
            "crashes_oom": 0,
        },
    )
    monkeypatch.setattr(tasks_mod, "MetricasInferencia", lambda: MagicMock(iniciar_rodada=MagicMock()))

    ev = tasks_mod.task_cenario_c(backend=MagicMock(), modelo="m")
    assert ev.json_valido is False
    assert ev.utilizavel is False
    assert ev.codigo_falha == "json_invalido"
    assert ev.agregado["falhou_com_3_tentativas"] is True
    assert ev.agregado["contagem_falhas"]["json_invalido"] == 3


def test_codigo_falha_dominante_nao_empata_com_ok() -> None:
    from benchmark_slms.tasks import _codigo_falha_dominante

    ok = Prediction(
        sample_id="1",
        task_id="cenario_d",
        modelo="m",
        raw_output="{}",
        usage=UsageStats(),
        metrics=InferenceMetrics(codigo_falha="ok"),
    )
    bad = Prediction(
        sample_id="2",
        task_id="cenario_d",
        modelo="m",
        raw_output="{}",
        usage=UsageStats(),
        metrics=InferenceMetrics(codigo_falha="json_invalido"),
    )
    assert _codigo_falha_dominante([ok, bad]) == "json_invalido"
    assert _codigo_falha_dominante([bad, ok]) == "json_invalido"
    assert _codigo_falha_dominante([ok, ok]) == "ok"
    assert _codigo_falha_dominante([bad, bad, ok]) == "json_invalido"
