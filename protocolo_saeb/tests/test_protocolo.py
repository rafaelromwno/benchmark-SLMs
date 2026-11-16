import json
import random

import pytest

from conftest import carregar
from comum import CELULAS, CONFIG, CRITERIOS, LETRAS, nota_1a5, texto_item

estrutura = carregar("02_checar_estrutura.py")
amostra = carregar("04_amostra_humana.py")
analise = carregar("05_analisar.py")


def questao(**kw):
    q = {"enunciado": "Quanto é 2+2?", "alternativas": dict(zip(LETRAS, ["1", "2", "3", "4", "5"])),
         "resolucao_passo_a_passo": "Somando 2+2 temos 4, que é a alternativa D, a correta.", "resposta_correta": "D"}
    q.update(kw)
    return {"item_id": "x", "questao": q, "falha": None}


@pytest.mark.parametrize("score,nota", [(0, 1), (1, 1), (1.1, 2), (3, 2), (5, 3), (7, 4), (7.01, 5), (10, 5)])
def test_faixas_do_artigo(score, nota):
    assert nota_1a5(score) == nota


def test_config_consistente():
    assert len(CELULAS) == 8 and len(CRITERIOS) == 5
    assert [c["id"] for c in CRITERIOS if c.get("principal")] == ["intencao_uso"]
    assert CONFIG["geracao"]["questoes_por_celula"] == 20


def test_texto_item_traz_gabarito_e_alternativas():
    t = texto_item(questao()["questao"])
    assert "D) 4" in t and "Gabarito: D" in t


def test_estrutura_valida_e_sinalizadores():
    r = estrutura.checar(questao())
    assert r["estrutura_ok"] and r["alternativas_distintas"] and not r["resolucao_cita_outra_letra"]
    assert estrutura.checar(questao(alternativas=dict(zip(LETRAS, ["1", "1", "3", "4", "5"]))))["alternativas_distintas"] is False
    assert estrutura.checar(questao(resposta_correta="B"))["resolucao_cita_outra_letra"] is True
    assert estrutura.checar({"questao": None, "falha": "estrutura_invalida"})["estrutura_ok"] is False


def test_amostra_cobre_todas_as_celulas_sem_repetir():
    regs = [{"item_id": f"{c['ano']}-{c['habilidade']}-{i}", "ano": c["ano"], "habilidade": c["habilidade"]}
            for c in CELULAS for i in range(20)]
    sel = amostra.sortear(regs, 20, random.Random(1))
    assert len(sel) == 160 and len({r["item_id"] for r in sel}) == 160
    assert len(amostra.sortear(regs, 5, random.Random(1))) == 40


def test_estatisticas_conhecidas():
    assert analise.pearson([1, 2, 3, 4], [2, 4, 6, 8]) == 1.0
    assert analise.spearman([1, 2, 3, 4], [1, 4, 9, 16]) == 1.0
    assert analise.pearson([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0
    assert analise.kappa([True, False, True, False], [True, False, True, False], [False, True]) == 1.0
    assert analise.kappa([True, True, False, False], [True, False, True, False], [False, True]) == 0.0
    assert analise.kappa([1, 2, 3, 4, 5], [1, 2, 3, 4, 5], [1, 2, 3, 4, 5], "quadratico") == 1.0


def test_wilson_e_taxa():
    t = analise.taxa([True] * 8 + [False] * 2)
    assert t["pct"] == 80.0 and t["ic95_pct"][0] < 80 < t["ic95_pct"][1]
    assert analise.taxa([])["pct"] is None


def test_gerar_importa_e_usa_prompt_de_producao():
    gerar = carregar("01_gerar.py")
    tax = json.loads((gerar.APP / "taxonomia_subtemas.json").read_text(encoding="utf-8"))
    cels = list(gerar.celulas(tax))
    assert len(cels) == 8
    ano, hab, desc, op = cels[0]
    slot = gerar.app.sortear_slot(tax, ano, hab, [], random.Random(1))
    prompt = gerar.app.montar_prompt(tax, ano, hab, desc, "Fácil", slot)
    assert prompt.startswith("Gere 1 questão(ões) de matemática. Ano: 1º ano. Habilidade: EF01MA06")
    assert gerar.app.montar_prompt(tax, ano, hab, desc, "Fácil", slot) == prompt  # determinístico
