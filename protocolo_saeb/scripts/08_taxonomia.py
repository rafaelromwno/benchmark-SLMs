"""Taxonomia de falhas: por que cada questão foi reprovada, segundo o juiz e segundo os professores.

Cinco causas, ligadas aos critérios do núcleo e à aderência:
  conta_ou_conceito_errado          <- resolucao_correta (e, no legado, correcao_matematica)
  gabarito_incoerente               <- gabarito_coerente
  mais_de_uma_alternativa_correta   <- resposta_unica
  enunciado_mal_posto_ou_sem_dados  <- dados_suficientes
  inadequacao_ano_ou_habilidade     <- aderencia_ano_habilidade

Gera dados/taxonomia/codificacao.csv: uma linha por questão reprovada pelo juiz ou pela maioria dos professores,
com as causas de cada lado, a justificativa do juiz, o motivo livre (Q7) dos professores e uma marca de dupla
codificação (fração `dupla_codificacao` de config/protocolo.json, sorteada com seed fixa) para um segundo
codificador preencher `causa_codificador2`. A concordância de causas entre juiz e professores é calculada aqui.
"""
import csv
import json
import random
from collections import Counter, defaultdict

from comum import CONFIG, CRITERIOS, DADOS, LIMIAR, ler_jsonl, notas_do_juiz
from importlib import import_module

CAUSA = {"resolucao_correta": "conta_ou_conceito_errado", "correcao_matematica": "conta_ou_conceito_errado",
         "gabarito_coerente": "gabarito_incoerente", "resposta_unica": "mais_de_uma_alternativa_correta",
         "dados_suficientes": "enunciado_mal_posto_ou_sem_dados", "aderencia_ano_habilidade": "inadequacao_ano_ou_habilidade"}
PASTA = DADOS / "taxonomia"


def causas(criterios_reprovados):
    return sorted({CAUSA[c] for c in criterios_reprovados if c in CAUSA})


def main():
    analise = import_module("05_analisar")
    questoes = {r["item_id"]: r for r in ler_jsonl(DADOS / "geracoes" / "questoes.jsonl")}
    notas, justificativas = defaultdict(dict), defaultdict(dict)
    for r in notas_do_juiz(ler_jsonl(DADOS / "avaliacao_auto" / "geval.jsonl")).values():
        notas[r["item_id"]][r["criterio"]] = r["nota_1a5"]
        justificativas[r["item_id"]][r["criterio"]] = r["justificativa"]
    humano, _ = analise.ler_humano()

    linhas = []
    for item_id in sorted(questoes):
        falhas_juiz = [c for c, n in notas.get(item_id, {}).items() if n < LIMIAR and c in CAUSA]
        profs = humano.get(item_id, {})
        falhas_prof = sorted({c for c in analise.BINARIOS if profs and analise.maioria(not r[c] for r in profs.values())})
        if not falhas_juiz and not falhas_prof:
            continue
        linhas.append({
            "item_id": item_id, "ano": questoes[item_id]["ano"], "habilidade": questoes[item_id]["habilidade"],
            "criterios_reprovados_juiz": "|".join(sorted(falhas_juiz)), "causas_juiz": "|".join(causas(falhas_juiz)),
            "criterios_reprovados_professores": "|".join(falhas_prof), "causas_professores": "|".join(causas(falhas_prof)),
            "justificativa_juiz": " || ".join(f"{c}: {justificativas[item_id][c]}" for c in sorted(falhas_juiz)),
            "motivo_professores": " || ".join(f"{p}: {r['motivo']}" for p, r in sorted(profs.items()) if r.get("motivo")),
            "causa_codificador2": ""})
    rng = random.Random(CONFIG["taxonomia"]["seed_dupla_codificacao"])
    marcados = set(rng.sample(range(len(linhas)), round(CONFIG["taxonomia"]["dupla_codificacao"] * len(linhas))))
    for k, l in enumerate(linhas):
        l["dupla_codificacao"] = int(k in marcados)

    PASTA.mkdir(parents=True, exist_ok=True)
    cab = ["item_id", "ano", "habilidade", "criterios_reprovados_juiz", "causas_juiz", "criterios_reprovados_professores",
           "causas_professores", "justificativa_juiz", "motivo_professores", "dupla_codificacao", "causa_codificador2"]
    with (PASTA / "codificacao.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cab)
        w.writeheader()
        w.writerows(linhas)

    com_ambos = [l for l in linhas if l["causas_professores"]]
    resumo = {"n_reprovadas": len(linhas), "causas_juiz": dict(Counter(c for l in linhas for c in l["causas_juiz"].split("|") if c)),
              "causas_professores": dict(Counter(c for l in linhas for c in l["causas_professores"].split("|") if c)),
              "n_dupla_codificacao": len(marcados),
              "reprovadas_pelos_dois": len(com_ambos),
              "mesmas_causas_juiz_e_professores_pct": round(100 * sum(l["causas_juiz"] == l["causas_professores"] for l in com_ambos) / len(com_ambos), 1) if com_ambos else None}
    (PASTA / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resumo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
