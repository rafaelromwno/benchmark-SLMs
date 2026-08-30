"""Testes do protocolo acadêmico (#21–#24): falhas, distribuição, IC95%, quadro."""

from __future__ import annotations

import json
from pathlib import Path

from benchmark_slms.core.contracts import EvalResult, InferenceMetrics, Prediction, UsageStats
from benchmark_slms.evaluation.metrics import avaliar_predicao, avaliar_rodadas
from benchmark_slms.evaluation.veredito import veredito
from benchmark_slms.report.aggregate import gerar_leaderboard, gerar_quadro_principal
from benchmark_slms.report.stats import bootstrap_ic_mediana, resumo_continuo, wilson_ic95
from benchmark_slms.runner.executor import classificar_excecao, resolver_timeout_s

JSON_OK = (
    '{"questoes":[{"enunciado":"2+2?","alternativas":{"A":"1","B":"2","C":"3","D":"4","E":"5"},'
    '"resposta_correta":"D","resolucao_passo_a_passo":"2+2=4"}]}'
)


def _pred(
    raw: str,
    *,
    codigo: str = "ok",
    crash: bool = False,
    motivo: str | None = None,
    tps: float = 10.0,
) -> Prediction:
    return Prediction(
        sample_id="s1",
        task_id="cenario_b",
        modelo="m",
        raw_output=raw,
        usage=UsageStats(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        metrics=InferenceMetrics(
            tps=tps,
            tempo_prefill_s=0.1,
            tempo_resposta_s=1.0,
            ram_pico_mb=100.0,
            codigo_falha=codigo,  # type: ignore[arg-type]
            crash=crash,
            crash_motivo=motivo,
        ),
    )


def test_wilson_ic95_formato_parecer() -> None:
    out = wilson_ic95(8, 10)
    assert out["numerador"] == 8
    assert out["denominador"] == 10
    assert out["unidade_analise"] == "execucao"
    assert out["formato"] == "80.0% [49.0–94.3]"


def test_resumo_continuo_mediana_iqr_p95() -> None:
    out = resumo_continuo([1, 2, 3, 4, 5, 100])
    assert out["n"] == 6
    assert out["mediana"] == 3.5
    assert out["iqr"] == 2.5
    assert out["p95"] is not None
    assert out["max"] == 100.0
    assert out["media"] is not None


def test_bootstrap_ic_mediana_requer_n5() -> None:
    curto = bootstrap_ic_mediana([1, 2, 3])
    assert curto["formato"] is None
    assert curto["ic95"] == [None, None]

    longo = bootstrap_ic_mediana([1, 2, 3, 4, 5, 6, 7, 8])
    assert longo["mediana"] is not None
    assert longo["formato"] is not None
    assert longo["ic95"][0] is not None


def test_timeout_por_cenario_e_taxonomia() -> None:
    assert resolver_timeout_s("cenario_a") == 180.0
    assert resolver_timeout_s("cenario_b") == 120.0
    assert resolver_timeout_s("cenario_b", 30.0) == 30.0
    assert classificar_excecao(TimeoutError("x"))[0] == "timeout"
    assert classificar_excecao(MemoryError())[0] == "oom"
    assert classificar_excecao(RuntimeError("boom"))[0] == "crash_motor"


def test_falhas_entram_no_denominador_e_codigo() -> None:
    timeout = avaliar_predicao(
        _pred("", codigo="timeout", crash=True, motivo="timeout: 120s")
    )
    assert timeout.codigo_falha == "timeout"
    assert timeout.utilizavel is False

    ruim = avaliar_predicao(_pred("not json"))
    assert ruim.codigo_falha == "json_invalido"
    assert ruim.utilizavel is False

    bom = avaliar_predicao(_pred(JSON_OK), quantidade_esperada=1)
    assert bom.codigo_falha == "ok"
    assert bom.json_valido is True
    assert bom.gabarito_ok is True
    assert bom.utilizavel is True

    preds = [
        _pred(JSON_OK, tps=10),
        _pred(JSON_OK, tps=12),
        _pred("nope", tps=11),
        _pred("", codigo="timeout", crash=True, motivo="timeout", tps=0),
        _pred(JSON_OK, tps=14),
    ]
    agg = avaliar_rodadas(preds, quantidade_esperada=1).agregado
    assert agg["rodadas"] == 5
    assert agg["contagem_falhas"]["timeout"] == 1
    assert agg["contagem_falhas"]["json_invalido"] == 1
    assert agg["utilizaveis"] == 3
    assert agg["taxa_utilizavel_percent"] == 60.0
    assert "formato" in agg["utilizavel_ic95"]
    assert agg["tps"]["mediana"] is not None
    assert agg["tps"]["p95"] is not None
    assert agg["ttft"]["mediana"] is not None


def test_veredito_conta_timeout_e_crash_motor() -> None:
    er = EvalResult(
        task_id="cenario_b",
        modelo="m",
        json_valido=True,
        utilizavel=True,
        viabilidade={"ram_pico_mb": 500.0, "tps_medio": 20.0},
        agregado={
            "rodadas": 10,
            "taxa_json_valido_percent": 100.0,
            "contagem_falhas": {"ok": 8, "timeout": 1, "crash_motor": 1},
            "tempo_medio_segundos": 5.0,
        },
    )
    v = veredito({"cenario_b": er}, modelo="m")
    crash_criterio = next(c for c in v.criterios if c.nome == "crashes_oom")
    assert crash_criterio.valor == 2
    assert crash_criterio.passou is False


def test_quadro_principal_preenche_colunas_do_artigo(tmp_path: Path) -> None:
    pasta = tmp_path / "org--m-gguf" / "balanceado"
    pasta.mkdir(parents=True)
    agg = avaliar_rodadas(
        [
            _pred(JSON_OK, tps=10),
            _pred(JSON_OK, tps=12),
            _pred(JSON_OK, tps=11),
            _pred(JSON_OK, tps=13),
            _pred(JSON_OK, tps=14),
        ],
        quantidade_esperada=1,
    ).agregado
    (pasta / "execucao_1.json").write_text(
        json.dumps(
            {
                "modelo": "org/m",
                "formato": "gguf",
                "eliminado": False,
                "veredito": {"apto_mathia": True, "categoria_falha": "nenhuma"},
                "run_config": {"seed": 42},
                "inferencia": {"perfil": {"name": "balanceado"}},
                "tasks": {
                    "cenario_b": {
                        "agregado": agg,
                        "viabilidade": {"ram_pico_mb": 130},
                        "predictions": [],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    quadro = gerar_quadro_principal(tmp_path)
    assert quadro["unidade_analise"] == "execucao"
    assert quadro["total_modelos"] == 1
    row = quadro["quadro_principal"][0]
    assert row["utilizaveis_fmt"] and "%" in row["utilizaveis_fmt"] and "[" in row["utilizaveis_fmt"]
    assert row["json_fmt"]
    assert row["gabarito_fmt"]
    assert row["tps_mediana"] is not None
    assert row["tps_p95"] is not None
    assert row["ttft_mediana"] is not None
    assert "ok" in row["contagem_falhas"]

    lb = gerar_leaderboard(tmp_path)
    assert lb["total"] == 1
    assert lb["leaderboard"][0]["tps_mediana"] is not None
    assert lb["leaderboard"][0]["utilizavel_ic95"] is not None
