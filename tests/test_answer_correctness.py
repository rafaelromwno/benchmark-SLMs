"""Auditoria de conteúdo: a alternativa marcada resolve o enunciado gerado."""

from __future__ import annotations

import json
from pathlib import Path

from benchmark_slms.core.contracts import Alternativas, Questao
from benchmark_slms.evaluation.answer_correctness import (
    auditar_celula_cenario_b,
    grade_conteudo,
)


def _q(
    enunciado: str,
    mark: str = "C",
    *,
    alts: dict[str, str] | None = None,
    resol: str = "x = 2",
) -> Questao:
    base = {"A": "1", "B": "0", "C": "2", "D": "4", "E": "8"}
    if alts is not None:
        base = alts
    return Questao(
        enunciado=enunciado,
        alternativas=Alternativas.model_validate(base),
        resposta_correta=mark,  # type: ignore[arg-type]
        resolucao_passo_a_passo=resol,
    )


def test_grade_conteudo_aceita_equacao_linear_com_chave_correta() -> None:
    q = _q("Resolva 2x + 1 = 5.", mark="C", alts={"A": "1", "B": "0", "C": "2", "D": "4", "E": "8"})
    assert grade_conteudo(q) is True


def test_grade_conteudo_rejeita_equacao_linear_com_chave_errada() -> None:
    q = _q("Resolva 2x + 1 = 5.", mark="A", alts={"A": "1", "B": "0", "C": "2", "D": "4", "E": "8"})
    assert grade_conteudo(q) is False


def test_grade_conteudo_intervalo_abre_marca_valor_interior() -> None:
    q = _q(
        "Qual número está entre 3 e 7?",
        mark="C",
        alts={"A": "1", "B": "2", "C": "5", "D": "9", "E": "10"},
    )
    assert grade_conteudo(q) is True


def test_grade_conteudo_intervalo_rejeita_extremo_fora() -> None:
    q = _q(
        "Qual número está entre 3 e 7?",
        mark="D",
        alts={"A": "1", "B": "2", "C": "5", "D": "9", "E": "10"},
    )
    assert grade_conteudo(q) is False


def test_grade_conteudo_falha_estrutural_e_falso() -> None:
    q = _q("Resolva 2x = 4.", mark="C", alts={"A": "1", "B": "1", "C": "2", "D": "4", "E": "8"})
    assert grade_conteudo(q) is False


def test_grade_conteudo_enunciado_sem_regra_devolve_none() -> None:
    q = _q(
        "Qual figura representa um triângulo retângulo?",
        mark="A",
        alts={"A": "abc", "B": "def", "C": "ghi", "D": "jkl", "E": "mno"},
        resol="figura A",
    )
    assert grade_conteudo(q) is None


def test_grade_conteudo_resolucao_diverge_da_chave_e_falso() -> None:
    q = _q(
        "Quanto é 9 mais 1?",
        mark="C",
        alts={"A": "1", "B": "0", "C": "2", "D": "4", "E": "8"},
        resol="x = 10",
    )
    assert grade_conteudo(q) is False


def test_auditar_celula_cenario_b_conta_somente_json_de_tres_itens(tmp_path: Path) -> None:
    raw_ok = json.dumps(
        {
            "questoes": [
                {
                    "enunciado": "Resolva 2x + 1 = 5.",
                    "alternativas": {"A": "1", "B": "0", "C": "2", "D": "4", "E": "8"},
                    "resposta_correta": "C",
                    "resolucao_passo_a_passo": "x = 2",
                },
                {
                    "enunciado": "Resolva 2x + 1 = 5.",
                    "alternativas": {"A": "1", "B": "0", "C": "2", "D": "4", "E": "8"},
                    "resposta_correta": "A",
                    "resolucao_passo_a_passo": "x = 2",
                },
                {
                    "enunciado": "Resolva 2x + 1 = 5.",
                    "alternativas": {"A": "1", "B": "0", "C": "2", "D": "4", "E": "8"},
                    "resposta_correta": "C",
                    "resolucao_passo_a_passo": "x = 2",
                },
            ]
        }
    )
    raw_duas = json.dumps(
        {
            "questoes": [
                {
                    "enunciado": "Resolva 2x + 1 = 5.",
                    "alternativas": {"A": "1", "B": "0", "C": "2", "D": "4", "E": "8"},
                    "resposta_correta": "C",
                    "resolucao_passo_a_passo": "x = 2",
                },
                {
                    "enunciado": "Resolva 2x + 1 = 5.",
                    "alternativas": {"A": "1", "B": "0", "C": "2", "D": "4", "E": "8"},
                    "resposta_correta": "C",
                    "resolucao_passo_a_passo": "x = 2",
                },
            ]
        }
    )
    payload = {
        "tasks": {
            "cenario_b": {
                "predictions": [
                    {"raw_output": raw_ok, "metrics": {"crash": False}},
                    {"raw_output": raw_duas, "metrics": {"crash": False}},
                    {"raw_output": raw_ok, "metrics": {"crash": True}},
                ]
            }
        }
    }
    (tmp_path / "execucao_42.json").write_text(json.dumps(payload), encoding="utf-8")
    ok, tot = auditar_celula_cenario_b(tmp_path)
    assert tot == 3
    assert ok == 2
