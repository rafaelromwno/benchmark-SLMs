"""Sorteia a amostra para professores e gera as planilhas CEGAS (sem nota do G-Eval, sem dificuldade/subtema).

Amostra por célula (padrão 20 = todas as questões geradas; reduza em config se faltar professor).
Cada item vai para `avaliacoes_por_item` professores diferentes; a carga fica equilibrada.
Saídas: dados/humana/folha_<professor>.csv (entregar) e dados/humana/chave.csv (NÃO entregar).

  python 04_amostra_humana.py --professores P1 P2 P3
"""
import argparse
import csv
import random
from collections import defaultdict

from comum import CONFIG, CRITERIOS, DADOS, LETRAS, ler_jsonl

PASTA = DADOS / "humana"


def sortear(registros, por_celula, rng):
    grupos = defaultdict(list)
    for r in registros:
        grupos[(r["ano"], r["habilidade"])].append(r)
    return [r for g in grupos.values() for r in rng.sample(g, min(por_celula, len(g)))]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--professores", nargs="+", required=True)
    a = ap.parse_args()
    h = CONFIG["avaliacao_humana"]
    if len(a.professores) < h["avaliacoes_por_item"]:
        raise SystemExit("professores insuficientes para a dupla avaliação")

    estrutura = {r["item_id"]: r for r in ler_jsonl(DADOS / "avaliacao_auto" / "estrutura.jsonl")}
    validos = [r for r in ler_jsonl(DADOS / "geracoes" / "questoes.jsonl") if estrutura[r["item_id"]]["estrutura_ok"]]
    rng = random.Random(h["seed_amostra"])
    amostra = sortear(validos, h["amostra_por_celula"], rng)
    rng.shuffle(amostra)

    PASTA.mkdir(parents=True, exist_ok=True)
    colunas_nota = [c["id"] for c in CRITERIOS] + ["comentario"]
    cab = ["codigo", "ano", "habilidade", "descricao_habilidade", "enunciado", *LETRAS, "resolucao", "gabarito", *colunas_nota]
    folhas = {p: [] for p in a.professores}
    chave = []
    for k, r in enumerate(amostra):
        codigo = f"Q{k + 1:03d}"
        q = r["questao"]
        linha = [codigo, r["ano"], r["habilidade"], r["descricao_habilidade"], q["enunciado"],
                 *[q["alternativas"][l] for l in LETRAS], q["resolucao_passo_a_passo"], q["resposta_correta"]]
        designados = [a.professores[(k + j) % len(a.professores)] for j in range(h["avaliacoes_por_item"])]
        for p in designados:
            folhas[p].append(linha + [""] * len(colunas_nota))
        chave.append([codigo, r["item_id"], *designados])

    for p, linhas in folhas.items():
        with (PASTA / f"folha_{p}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cab)
            w.writerows(linhas)
    with (PASTA / "chave.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["codigo", "item_id", *[f"professor_{j + 1}" for j in range(h["avaliacoes_por_item"])]])
        w.writerows(chave)
    print(f"{len(amostra)} itens; " + ", ".join(f"{p}: {len(v)}" for p, v in folhas.items()))


if __name__ == "__main__":
    main()
