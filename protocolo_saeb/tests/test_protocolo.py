import json
import random

import pytest

from conftest import carregar
from comum import (CELULAS, CONFIG, CRITERIOS, DADOS, LEGADO, LETRAS, NUCLEO, QUESTOES_ORIGINAIS, VERSAO, intencao_com_teto, ler_jsonl,
                   nota_1a5, notas_do_juiz, nucleo_aprovado, texto_item)

estrutura = carregar("02_checar_estrutura.py")
amostra = carregar("04_amostra_humana.py")
analise = carregar("05_analisar.py")
aritmetica = carregar("02b_verificar_aritmetica.py")
contaminacao = carregar("02c_contaminacao.py")
taxonomia = carregar("08_taxonomia.py")
derivacao = carregar("09_derivar_4_alternativas.py")


def questao(**kw):
    q = {"enunciado": "Quanto é 2+2?", "alternativas": dict(zip(LETRAS, ["1", "2", "3", "4", "5"])),
         "resolucao_passo_a_passo": "Somando 2+2 temos 4, que é a alternativa D, a correta.", "resposta_correta": "D"}
    q.update(kw)
    return {"item_id": "x", "questao": q, "falha": None}


@pytest.mark.parametrize("score,nota", [(0, 1), (1, 1), (1.1, 2), (3, 2), (5, 3), (7, 4), (7.01, 5), (10, 5)])
def test_faixas_do_artigo(score, nota):
    assert nota_1a5(score) == nota


def test_config_consistente():
    assert len(CELULAS) == 10 and len(CRITERIOS) == 6
    assert [c["id"] for c in CRITERIOS if c.get("principal")] == ["intencao_uso"]
    por_ano = {}
    for c in CELULAS:
        por_ano[c["ano"]] = por_ano.get(c["ano"], 0) + c["n"]
    assert por_ano == {"1º": 40, "2º": 40, "5º": 40, "9º": 40} and CONFIG["geracao"]["questoes_por_ano"] == 40


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
            for c in CELULAS for i in range(c["n"])]
    sel = amostra.sortear(regs, 20, random.Random(1))
    assert len(sel) == 160 and len({r["item_id"] for r in sel}) == 160
    assert len(amostra.sortear(regs, 5, random.Random(1))) == 50  # 10 células x 5


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
    assert len(cels) == 10
    ano, hab, desc, op, n_celula = cels[0]
    slot = gerar.app.sortear_slot(tax, ano, hab, [], random.Random(1))
    prompt = gerar.app.montar_prompt(tax, ano, hab, desc, "Fácil", slot)
    assert prompt.startswith("Gere 1 questão(ões) de matemática. Ano: 1º ano. Habilidade: EF01MA06")
    assert gerar.app.montar_prompt(tax, ano, hab, desc, "Fácil", slot) == prompt  # determinístico


# ---------- critérios, núcleo e teto em código ----------

def test_criterios_nucleo_e_legado():
    assert NUCLEO == ["resolucao_correta", "gabarito_coerente", "resposta_unica", "dados_suficientes"]
    assert [c["id"] for c in LEGADO] == ["correcao_matematica"]
    assert all(c["passos_geval"] for c in CRITERIOS) and "correcao_matematica" not in [c["id"] for c in CRITERIOS]
    assert CRITERIOS[-1]["id"] == "intencao_uso"  # ordem da folha: Q1..Q6


def test_teto_por_codigo():
    reprovado = {"resolucao_correta": 1, "gabarito_coerente": 5, "resposta_unica": 5, "dados_suficientes": 5, "intencao_uso": 5}
    assert nucleo_aprovado(reprovado) is False and intencao_com_teto(reprovado) == 2
    aprovado = {**reprovado, "resolucao_correta": 5}
    assert nucleo_aprovado(aprovado) is True and intencao_com_teto(aprovado) == 5
    incompleto = {"resposta_unica": 1, "intencao_uso": 5}
    assert nucleo_aprovado(incompleto) is None and intencao_com_teto(incompleto) == 5  # sem núcleo completo, não corta


def test_codigo_matriz_saeb_nas_celulas_e_questoes():
    por_celula = {(c["ano"], c["habilidade"]): c["codigo_matriz_saeb"] for c in CELULAS}
    assert all(v is None for (ano, _), v in por_celula.items() if ano == "1º")
    assert all(v for (ano, _), v in por_celula.items() if ano != "1º")
    assert por_celula[("2º", "H06")] == "2N1.7" and por_celula[("5º", "H04")] == "5N1.6"
    for r in ler_jsonl(DADOS / "geracoes" / "questoes.jsonl"):
        assert r["codigo_matriz_saeb"] == por_celula[(r["ano"], r["habilidade"])]


# ---------- folha dos professores ----------

def test_ordem_de_apresentacao_com_ancoras():
    ids = [f"i{k}" for k in range(80)]
    ordem = amostra.montar_ordem(ids, random.Random(3), 40, 2)
    originais = [i for i, _, ancora in ordem if not ancora]
    ancoras = [(i, b) for i, b, ancora in ordem if ancora]
    assert sorted(originais) == sorted(ids) and len(ordem) == 84
    assert len(ancoras) == 4 and {b for _, b in ancoras} == {0, 1}
    for item, bloco in ancoras:  # a repetição vem depois do original e no mesmo bloco
        pos = [k for k, (i, b, a) in enumerate(ordem) if i == item]
        assert len(pos) == 2 and not ordem[pos[0]][2] and ordem[pos[1]][2] and ordem[pos[0]][1] == ordem[pos[1]][1] == bloco
    assert amostra.montar_ordem(ids, random.Random(3), 40, 2) == ordem  # determinístico
    assert amostra.montar_ordem(ids, random.Random(4), 40, 2) != ordem  # cada professor, ordem própria


def test_codigos_anonimos_unicos_e_cabecalho_sem_pistas():
    codigos = amostra.gerar_codigos(500, random.Random(1))
    assert len(set(codigos)) == 500 and all(len(c) == 5 for c in codigos)
    cab = amostra.cabecalho()
    assert cab[-1] == "motivo_reprovacao" and cab[-2] == "intencao_uso"
    proibidos = {"dificuldade_pedida", "subtema", "slot", "geval", "modelo_info", "nota_juiz"}
    assert not proibidos & set(cab)


# ---------- coeficientes de concordância ----------

def test_ac1_concordancia_total_e_sem_paradoxo_de_prevalencia():
    a = [True] * 8 + [False] * 2
    assert analise.concordancia_binaria(a, a)["ac1"] == 1.0
    # prevalência alta dos dois lados: kappa desaba, AC1 continua alto
    x = [True] * 18 + [True, False]
    y = [True] * 18 + [False, True]
    c = analise.concordancia_binaria(x, y)
    assert c["p0"] == 0.9 and c["ac1"] > 0.85 and c["kappa"] < 0.1


def test_fleiss_alpha_e_ac1_multi_com_concordancia_perfeita_e_total_discordancia():
    perfeito = [[True, True, True], [False, False, False], [True, True, True], [False, False, False]]
    assert analise.fleiss_kappa(perfeito) == 1.0
    assert analise.krippendorff_alpha([[int(x) for x in i] for i in perfeito]) == 1.0
    assert analise.ac1_multi(perfeito) == 1.0
    assert analise.krippendorff_alpha([[1, 1, 1], [5, 5, 5], [3, 3, 3]], "intervalo") == 1.0
    assert analise.krippendorff_alpha([[1, 2], [2, 1], [1, 2], [2, 1]]) < 0


def test_holm_e_bootstrap_deterministico():
    assert analise.holm({"a": 0.01, "b": 0.04, "c": 0.03}) == {"a": 0.03, "c": 0.06, "b": 0.06}
    ids = list(range(50))
    f = lambda amostra: sum(amostra) / len(amostra)
    v1, ic1 = analise.bootstrap(ids, f, repeticoes=300)
    v2, ic2 = analise.bootstrap(ids, f, repeticoes=300)
    assert ic1 == ic2 and ic1[0] < 24.5 < ic1[1]
    assert analise.maioria([True, True, False]) and not analise.maioria([True, False])  # empate = não


def humano_sintetico(n_itens=40, profs=("P1", "P2", "P3"), discordante=None):
    rng = random.Random(5)
    humano, juiz = {}, {}
    for k in range(n_itens):
        bom = k % 4 != 0
        humano[f"i{k}"] = {}
        for p in profs:
            erra = discordante == p and rng.random() < 0.5
            ok = bom != erra
            reg = {c: ok for c in analise.BINARIOS}
            reg["intencao_uso"] = 5 if ok else 2
            reg["motivo"] = "" if ok else "erro de conta"
            humano[f"i{k}"][p] = reg
        juiz[f"i{k}"] = {c: (5 if bom else 1) for c in analise.BINARIOS} | {"intencao_uso": 5 if bom else 2}
    return humano, juiz


def test_teto_humano_e_juiz_vs_humanos_com_dados_sinteticos():
    humano, juiz = humano_sintetico()
    teto = analise.teto_humano(humano)
    assert teto["n_itens_com_todos"] == 40 and teto["por_dimensao"]["nucleo"]["ac1"] == 1.0
    assert set(teto["pares_de_professores"]) == {"P1-P2", "P1-P3", "P2-P3"}
    r = analise.juiz_vs_humanos(humano, juiz)
    assert r["nucleo"]["juiz_vs_maioria"]["ac1"] == 1.0 and r["nucleo"]["sensibilidade_pct"] == 100.0
    assert r["nucleo"]["ac1_juiz_vs_professor_menos_ac1_entre_professores"]["diferenca"] == 0.0
    assert r["spearman_descritivo"]["n"] == 40


def test_triagem_com_dados_sinteticos_e_descarte_de_validos():
    humano, juiz = humano_sintetico()
    aritmetica_ = {i: {"veredito": "ok" if int(i[1:]) % 4 else "erro"} for i in humano}
    t = analise.triagem(humano, juiz, aritmetica_)
    assert t["n"] == 40 and t["triadores"]["juiz"]["vpp"] == 1.0 and t["triadores"]["juiz"]["descarte_de_validos"] == 0.0
    assert t["triadores"]["juiz"]["taxa_base_aprovados"] == 0.75 and t["triadores"]["juiz"]["fracao_descartada"] == 0.25
    m = analise.metricas_triagem({"a": True, "b": True, "c": False, "d": False}, {"a": True, "b": False, "c": True, "d": False}, list("abcd"))
    assert m["vpp"] == 0.5 and m["descarte_de_validos"] == 0.5 and m["fracao_descartada"] == 0.5


def test_consistencia_das_ancoras():
    original = {c: True for c in analise.BINARIOS} | {"intencao_uso": 5}
    repetido = {**original, "intencao_uso": 4, "resposta_unica": False}
    r = analise.consistencia_ancoras({"P1": [("i1", original, original), ("i2", original, repetido)]})
    assert r["P1"]["likert_igual_pct"] == 50.0 and r["P1"]["likert_diferenca_ate_1_pct"] == 100.0
    assert r["P1"]["binarios_iguais_pct"] == round(100 * (5 + 4) / 10, 1)


# ---------- verificação aritmética ----------

def test_avaliar_expressoes_em_formato_brasileiro():
    assert aritmetica.avaliar("12.450 + 8.760") == 21210
    assert aritmetica.avaliar("3,5 × 2") == 7 and aritmetica.avaliar("(2 + 3) x 4") == 20
    assert aritmetica.avaliar("x + 2") is None and aritmetica.avaliar("2 +") is None and aritmetica.avaliar("1 / 0") is None


def test_equacoes_ignoram_variaveis_potencias_e_cadeias():
    assert aritmetica.equacoes("Somando: 12 + 8 = 20.") == [("12 + 8", "20")]
    assert aritmetica.equacoes("Como 2^4 × 2,5 = 40, então") == []
    assert aritmetica.equacoes("x + 2 = 6") == []
    assert aritmetica.equacoes("12 + 8 = 20 + 5 = 25") == [("20 + 5", "25")]


def questao_aritmetica(resolucao, chave, alternativas=("21.210", "20.210", "21.200", "20.000", "22.210")):
    return {"enunciado": "x", "alternativas": dict(zip(LETRAS, alternativas)),
            "resolucao_passo_a_passo": resolucao, "resposta_correta": chave}


def test_verificacao_ok_erro_e_nao_verificavel():
    ok = aritmetica.verificar(questao_aritmetica("12.450 + 8.760 = 21.210. Logo, foram vendidos 21.210 pães.", "A"))
    assert ok["veredito"] == "ok" and ok["verificavel"] and ok["alternativas_com_resultado"] == ["A"]
    chave_errada = aritmetica.verificar(questao_aritmetica("12.450 + 8.760 = 21.210. Logo, 21.210.", "C"))
    assert chave_errada["veredito"] == "erro" and chave_errada["gabarito_confere"] is False
    conta_errada = aritmetica.verificar(questao_aritmetica("12.450 + 8.760 = 20.210. Logo, 20.210.", "B"))
    assert conta_errada["veredito"] == "erro" and conta_errada["equacoes_erradas"]
    fora = aritmetica.verificar(questao_aritmetica("12.450 + 8.760 = 21.210. Logo, 21.210.", "A", ("1", "2", "3", "4", "5")))
    assert fora["veredito"] == "erro" and fora["resultado_fora_das_alternativas"]
    sem_conta = aritmetica.verificar(questao_aritmetica("Pensando um pouco, a resposta é a primeira.", "A"))
    assert sem_conta["veredito"] == "nao_verificavel" and not sem_conta["verificavel"]
    arredondado = aritmetica.verificar(questao_aritmetica("10.000 ÷ 2.400 = 4,166... Logo 4,166.", "A", ("4,166", "1", "2", "3", "5")))
    assert not arredondado["equacoes_erradas"]


# ---------- contaminação ----------

def test_similaridade_exata_e_de_molde():
    a = "Em uma padaria foram vendidos 12 pães na segunda e 8 pães na terça. Quantos pães foram vendidos?"
    b = "Em uma padaria foram vendidos 30 pães na segunda e 45 pães na terça. Quantos pães foram vendidos?"
    ga, gb = (contaminacao.trigramas(contaminacao.normalizar(t)) for t in (a, b))
    ma, mb = (contaminacao.trigramas(contaminacao.normalizar(t, molde=True)) for t in (a, b))
    assert contaminacao.jaccard(ga, ga) == 1.0
    assert contaminacao.jaccard(ma, mb) == 1.0 > contaminacao.jaccard(ga, gb)
    assert contaminacao.jaccard(ga, contaminacao.trigramas(contaminacao.normalizar("Calcule 3 + 4 mentalmente agora"))) < 0.2
    assert CONFIG["contaminacao"]["limiar_jaccard"] == 0.8 and CONFIG["contaminacao"]["tamanho_ngrama"] == 3


# ---------- taxonomia ----------

def test_taxonomia_liga_criterios_a_cinco_causas():
    assert len(set(taxonomia.CAUSA.values())) == 5
    assert taxonomia.causas(["resolucao_correta", "correcao_matematica", "resposta_unica"]) == [
        "conta_ou_conceito_errado", "mais_de_uma_alternativa_correta"]
    assert taxonomia.causas(["intencao_uso"]) == []


# ---------- derivação para 4 alternativas ----------

def registro_5alt(item_id, alternativas, chave, ano="5º"):
    return {"item_id": item_id, "ano": ano, "questao": {
        "enunciado": "x", "alternativas": dict(zip(LETRAS, alternativas)), "resposta_correta": chave,
        "resolucao_passo_a_passo": "Somando, o resultado é o da chave."}}


def derivar_sinteticos(registros):
    verificacao = {r["item_id"]: {"alternativas_com_resultado": [r["questao"]["resposta_correta"]]} for r in registros}
    return derivacao.derivar_todos(registros, verificacao, 7)[0]


def test_derivacao_nao_remove_chave_nem_muda_o_texto_dela():
    regs = [registro_5alt(f"i{k}", ["10", "20", "30", "40", "50"], LETRAS[k % 5]) for k in range(40)]
    for antes, depois in zip(regs, derivar_sinteticos(regs)):
        q0, q1 = antes["questao"], depois["questao"]
        assert len(q1["alternativas"]) == 4 and sorted(q1["alternativas"]) == list("ABCD")
        assert q1["alternativas"][q1["resposta_correta"]] == q0["alternativas"][q0["resposta_correta"]]
        assert set(q1["alternativas"].values()) < set(q0["alternativas"].values())


def test_derivacao_prefere_repetida_e_nenhuma_e_balanceia_a_chave():
    repetida = registro_5alt("r", ["12", "15", "12", "18", "21"], "B")
    nenhuma = registro_5alt("n", ["12", "15", "17", "18", "Nenhuma das alternativas anteriores"], "A")
    d_rep, d_nen = derivar_sinteticos([repetida, nenhuma])
    assert d_rep["transformacao"]["motivo"] == "alternativa_repetida" and len(set(d_rep["questao"]["alternativas"].values())) == 4
    assert d_nen["transformacao"]["motivo"] == "nenhuma_das_alternativas"
    assert "Nenhuma das alternativas anteriores" not in d_nen["questao"]["alternativas"].values()
    regs = [registro_5alt(f"i{k}", [str(10 + 7 * k + 3 * j) for j in (2, 0, 4, 1, 3)], "A", ano="9º") for k in range(40)]
    letras = [d["questao"]["resposta_correta"] for d in derivar_sinteticos(regs)]
    assert {l: letras.count(l) for l in "ABCD"} == {"A": 10, "B": 10, "C": 10, "D": 10}


def test_derivacao_protege_alternativa_com_o_resultado_da_resolucao():
    # chave errada: o resultado da resolução (E) não é a chave; remover a E esconderia o defeito
    r = registro_5alt("p", ["10", "20", "30", "40", "50"], "A")
    verificacao = {"p": {"alternativas_com_resultado": ["E"]}}
    d = derivacao.derivar_todos([r], verificacao, 7)[0][0]
    assert "50" in d["questao"]["alternativas"].values() and d["transformacao"]["alternativa_removida"] != "E"


def test_derivacao_reescreve_referencias_a_letras():
    r = registro_5alt("l", ["10", "20", "30", "40", "50"], "C")
    r["questao"]["resolucao_passo_a_passo"] = "O resultado é 30, que corresponde à alternativa C."
    d = derivar_sinteticos([r])[0]
    assert f"alternativa {d['questao']['resposta_correta']}" in d["questao"]["resolucao_passo_a_passo"]


def test_questoes_derivadas_reais_preservam_chave_e_ficam_balanceadas():
    originais = {r["item_id"]: r for r in ler_jsonl(QUESTOES_ORIGINAIS)}
    derivadas = ler_jsonl(DADOS / "geracoes" / "questoes_saeb4.jsonl")
    assert len(derivadas) == len(originais) == 160 and VERSAO == "saeb4"
    for d in derivadas:
        q0, q1 = originais[d["item_id"]]["questao"], d["questao"]
        assert sorted(q1["alternativas"]) == list("ABCD")
        assert len({str(v).strip().lower() for v in q1["alternativas"].values()}) == 4
        assert q1["alternativas"][q1["resposta_correta"]] == q0["alternativas"][q0["resposta_correta"]]
        assert d["transformacao"]["revisar"] is False
        assert q1["enunciado"] == q0["enunciado"]
    for ano in CONFIG["geracao"]["anos"]:
        letras = [d["questao"]["resposta_correta"] for d in derivadas if d["ano"] == ano]
        assert sorted(letras.count(l) for l in "ABCD") == [10, 10, 10, 10]
    veredito = {a["item_id"]: a["veredito"] for a in ler_jsonl(DADOS / "avaliacao_auto" / "aritmetica.jsonl")}
    for d in derivadas:
        assert aritmetica.verificar(d["questao"])["veredito"] == veredito[d["item_id"]]


def test_notas_do_juiz_reaproveita_so_criterios_independentes_das_alternativas():
    linhas = [{"item_id": "i", "criterio": "dados_suficientes", "nota_1a5": 5},
              {"item_id": "i", "criterio": "resposta_unica", "nota_1a5": 1},
              {"item_id": "j", "criterio": "resposta_unica", "nota_1a5": 2, "versao": VERSAO},
              {"item_id": "j", "criterio": "dados_suficientes", "nota_1a5": 3, "versao": VERSAO},
              {"item_id": "j", "criterio": "dados_suficientes", "nota_1a5": 1}]
    validas = notas_do_juiz(linhas)
    assert ("i", "dados_suficientes") in validas and ("i", "resposta_unica") not in validas
    assert validas[("j", "dados_suficientes")]["nota_1a5"] == 3 and validas[("j", "resposta_unica")]["nota_1a5"] == 2
