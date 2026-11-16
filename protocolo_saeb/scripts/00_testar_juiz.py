"""Teste de sanidade do juiz: 1 questão boa e 1 ruim devem receber notas bem diferentes em `intencao_uso`.

Roda poucas chamadas ao juiz. Use antes de avaliar as 120 questões.
  python 00_testar_juiz.py --juiz-url http://localhost:11434/v1 --juiz-modelo gpt-oss:20b
"""
import argparse
import importlib.util
import sys
import time

from deepeval.test_case import LLMTestCase

from comum import CRITERIOS, RAIZ, texto_item

spec = importlib.util.spec_from_file_location("geval", RAIZ / "scripts" / "03_geval.py")
geval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geval)

ENTRADA = "Ano: 5º ano. Habilidade: H03 — Calcular o resultado de adições ou subtrações envolvendo números naturais de até 6 ordens."
BOA = {"enunciado": "Em uma padaria foram vendidos 12.450 pães na segunda e 8.760 pães na terça. Quantos pães foram vendidos nos dois dias?",
       "alternativas": {"A": "21.210", "B": "20.210", "C": "21.200", "D": "20.000", "E": "22.210"},
       "resolucao_passo_a_passo": "12.450 + 8.760 = 21.210.", "resposta_correta": "A"}
RUIM = {"enunciado": "Em uma padaria foram vendidos 12.450 pães na segunda e 8.760 pães na terça. Quantos pães foram vendidos nos dois dias?",
        "alternativas": {"A": "21.210", "B": "20.210", "C": "21.200", "D": "20.000", "E": "22.210"},
        "resolucao_passo_a_passo": "12.450 + 8.760 = 21.210, que corresponde à alternativa C.", "resposta_correta": "C"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--juiz-url", required=True)
    ap.add_argument("--juiz-modelo", required=True)
    ap.add_argument("--juiz-chave", default="sem-chave")
    ap.add_argument("--esforco", choices=["low", "medium", "high"])
    a = ap.parse_args()
    juiz = geval.JuizOpenAICompat(a.juiz_url, a.juiz_modelo, a.juiz_chave, a.esforco)
    crit = next(c for c in CRITERIOS if c["id"] == "correcao_matematica")
    notas = {}
    for nome, q in (("boa", BOA), ("ruim (gabarito errado)", RUIM)):
        t0 = time.time()
        m = geval.montar_metrica(crit, juiz)
        m.measure(LLMTestCase(input=ENTRADA, actual_output=texto_item(q)))
        notas[nome] = geval.nota_1a5(m.score * 10)
        print(f"{nome}: nota {notas[nome]} (score {m.score * 10:.1f}, {time.time() - t0:.0f}s) — {m.reason}")
    ok = notas["boa"] >= 4 and notas["ruim (gabarito errado)"] <= 2
    print("JUIZ OK" if ok else "JUIZ NÃO DISCRIMINA: revisar modelo/critério antes de avaliar")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
