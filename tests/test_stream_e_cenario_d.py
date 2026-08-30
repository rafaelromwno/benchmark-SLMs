"""Regressões: stream GGUF vazio + utilizavel no cenário D."""

from __future__ import annotations

from unittest.mock import MagicMock

from benchmark_slms.core.contracts import (
    EvalResult,
    InferenceMetrics,
    Prediction,
    Prompt,
    PromptMessage,
    UsageStats,
)
from benchmark_slms.runner.backends import GGUDBackend, GenerationResult
from benchmark_slms.runner.executor import classificar_excecao, executar_prompt


def test_classificar_excecao_nunca_motivo_vazio() -> None:
    codigo, motivo = classificar_excecao(Exception())
    assert codigo == "crash_motor"
    assert motivo
    assert "Exception" in motivo

    codigo, motivo = classificar_excecao(RuntimeError(""))
    assert codigo == "crash_motor"
    assert "RuntimeError" in motivo


def test_executar_prompt_marca_resposta_vazia() -> None:
    backend = MagicMock()
    backend.definir_metricas = MagicMock()
    backend.gerar.return_value = GenerationResult(
        text="   ",
        usage=UsageStats(),
        raw={},
    )
    prompt = Prompt(
        sample_id="s",
        task_id="cenario_d",
        messages=[PromptMessage(role="user", content="oi")],
    )
    pred = executar_prompt(backend, prompt, modelo="m")
    assert pred.metrics.crash is True
    assert pred.metrics.codigo_falha == "crash_motor"
    assert "resposta_vazia" in (pred.metrics.crash_motivo or "")


def test_gguf_stream_vazio_faz_fallback_bloqueante() -> None:
    backend = GGUDBackend.__new__(GGUDBackend)
    backend._metricas = None
    backend._llm = MagicMock()

    # Stream sem conteúdo
    backend._llm.create_chat_completion.side_effect = [
        iter([]),  # stream
        {  # bloqueante
            "choices": [{"message": {"content": '{"questoes":[]}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        },
    ]

    prompt = Prompt(
        sample_id="s",
        task_id="cenario_b",
        messages=[PromptMessage(role="user", content="x")],
        generation={"max_tokens": 64, "temperature": 0.0, "top_p": 1.0, "repeat_penalty": 1.0, "top_k": 20},
    )
    result = backend.gerar(prompt)
    assert result.text.startswith("{")
    assert backend._llm.create_chat_completion.call_count == 2


def test_cenario_d_propaga_utilizavel(monkeypatch) -> None:
    from benchmark_slms import tasks as tasks_mod

    class FakeSample:
        habilidade_id = "EF08MA05"
        quantity = 1
        id = "s1"

    class FakeSample2:
        habilidade_id = "EF06MA17"
        quantity = 1
        id = "s2"

    def fake_load(_cenario):
        return [FakeSample(), FakeSample2()]

    def fake_prompt(sample, *a, **k):
        return Prompt(
            sample_id=sample.id,
            task_id="cenario_d",
            messages=[PromptMessage(role="user", content="x")],
        )

    calls = {"n": 0}

    def fake_executar(backend, prompt, modelo, metricas=None, rodada=None, timeout_s=None):
        calls["n"] += 1
        return Prediction(
            sample_id=prompt.sample_id,
            task_id="cenario_d",
            modelo=modelo,
            raw_output='{"questoes":[{"enunciado":"Q?","alternativas":{"A":"1","B":"2","C":"3","D":"4","E":"5"},"resposta_correta":"A","resolucao_passo_a_passo":"ok."}]}',
            usage=UsageStats(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            metrics=InferenceMetrics(tps=10.0, codigo_falha="ok"),
            rodada=rodada,
        )

    def fake_avaliar(pred, qtd):
        return EvalResult(
            task_id="cenario_d",
            modelo=pred.modelo,
            json_valido=True,
            utilizavel=True,
            codigo_falha="ok",
            gabarito_ok=True,
        )

    monkeypatch.setattr(tasks_mod, "load_for_cenario", fake_load)
    monkeypatch.setattr(tasks_mod, "sample_to_prompt", fake_prompt)
    monkeypatch.setattr(tasks_mod, "executar_prompt", fake_executar)
    monkeypatch.setattr(tasks_mod, "avaliar_predicao", fake_avaliar)

    # MetricasInferencia no-ops
    class FakeMetricas:
        def iniciar_rodada(self):
            return None

        def media_rodadas(self):
            return {
                "ram_pico_mb": 100.0,
                "tps_medio": 10.0,
                "tempo_medio_segundos": 1.0,
                "crashes_oom": 0,
            }

    monkeypatch.setattr(tasks_mod, "MetricasInferencia", FakeMetricas)
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

    ev = tasks_mod.task_cenario_d(backend=MagicMock(), modelo="m")
    assert ev.json_valido is True
    assert ev.utilizavel is True
    assert ev.agregado["taxa_utilizavel_percent"] == 100.0
    assert ev.agregado["utilizavel_por_habilidade"]["EF08MA05"] is True
