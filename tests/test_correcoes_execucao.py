"""Correções derivadas das execuções qwen3-1.7b (JSON truncado, think, veredito, timeout)."""

from __future__ import annotations

from benchmark_slms.core.contracts import (
    CategoriaFalha,
    CriterioTipo,
    EvalResult,
)
from benchmark_slms.core.contracts import RunConfig, ModelRunResult
from benchmark_slms.evaluation.veredito import veredito
from benchmark_slms.postprocess.json_task import extrair_e_validar, remover_think
from benchmark_slms.protocol import PROTOCOL_TIMEOUT_DEFAULT_S, PROTOCOL_TIMEOUTS_S
from benchmark_slms.runner.executor import resolver_timeout_s


def test_remover_think_real_tag() -> None:
    tag = "th" + "ink"
    raw = f"<{tag}>\nraciocinio\n</{tag}>\n\n{{\"ok\": true}}"
    assert remover_think(raw).startswith("{")


def test_json_truncado_sem_fechamento_array() -> None:
    # Caso real: falta ] antes do } final
    trunc = (
        '{"questoes": [{"enunciado": "Qual número está entre 24 e 28?", '
        '"alternativas": {"A": "25", "B": "26", "C": "27", "D": "28", "E": "29"}, '
        '"resposta_correta": "A", "resolucao_passo_a_passo": "24 < x < 28 → 25"}}'
    )
    r = extrair_e_validar(trunc)
    assert r.ok is True
    assert r.questoes_validas == 1


def test_json_extra_data_pega_primeiro_objeto_valido() -> None:
    bom = (
        '{"questoes": [{"enunciado": "Q?", "alternativas": '
        '{"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"}, '
        '"resposta_correta": "A", "resolucao_passo_a_passo": "porque."}]}'
    )
    r = extrair_e_validar(bom + "\n" + bom)
    assert r.ok is True
    assert r.questoes_validas == 1


def test_timeout_efetivo_usa_protocolo_quando_override_none() -> None:
    assert resolver_timeout_s("cenario_b", None) == PROTOCOL_TIMEOUTS_S["cenario_b"]
    assert resolver_timeout_s("cenario_a", None) == PROTOCOL_TIMEOUTS_S["cenario_a"]
    assert resolver_timeout_s("desconhecido", None) == PROTOCOL_TIMEOUT_DEFAULT_S
    assert resolver_timeout_s("cenario_b", 30.0) == 30.0


def test_run_config_persiste_timeouts_efetivos() -> None:
    result = ModelRunResult(
        modelo="x/y",
        formato="gguf",
        data="30/08/2026",
        run_config=RunConfig(modelos=["x/y"], timeout_s=None),
    )
    dumped = result.model_dump(mode="json")
    assert dumped["run_config"]["timeout_s"] is None
    assert dumped["run_config"]["timeout_default_s"] == PROTOCOL_TIMEOUT_DEFAULT_S
    assert dumped["run_config"]["timeouts_por_cenario_s"]["cenario_b"] == 120.0


def test_veredito_prioriza_hardware_quando_ram_e_formato_falham() -> None:
    er_b = EvalResult(
        task_id="cenario_b",
        modelo="m",
        json_valido=False,
        utilizavel=False,
        viabilidade={"ram_pico_mb": 2500.0, "tps_medio": 90.0},
        agregado={
            "rodadas": 10,
            "taxa_json_valido_percent": 0.0,
            "contagem_falhas": {"json_invalido": 10},
            "tempo_medio_segundos": 2.0,
        },
    )
    er_c = EvalResult(
        task_id="cenario_c",
        modelo="m",
        json_valido=False,
        utilizavel=False,
        viabilidade={"ram_pico_mb": 2500.0, "tps_medio": 90.0},
        agregado={
            "tentativas": 3,
            "falhou_com_3_tentativas": True,
            "contagem_falhas": {"json_invalido": 3},
        },
    )
    v = veredito({"cenario_b": er_b, "cenario_c": er_c}, modelo="m")
    assert v.apto_mathia is False
    assert CategoriaFalha.HARDWARE in v.categorias_falha
    assert CategoriaFalha.FORMATO in v.categorias_falha
    assert v.categoria_falha == CategoriaFalha.HARDWARE
    assert any("RAM" in (m or "") for m in v.motivos_reprovacao)
