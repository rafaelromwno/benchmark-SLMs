"""Sorteia a amostra para professores e gera as planilhas CEGAS.

Todos os professores avaliam todos os itens, cada um em ordem própria, divididos em blocos. Em cada bloco,
`ancoras_por_bloco` itens são repetidos mais adiante com outro código, para medir a consistência de cada
professor consigo mesmo. A planilha não mostra nota do G-Eval, dificuldade pedida, subtema nem modelo.

Saídas em dados/humana/:
  folha_<professor>.csv   entregar (uma por professor)
  chave.csv               NÃO entregar: liga (professor, código) ao item e marca as âncoras
  calibracao.csv          10 itens fora da amostra (excedente), para a calibração em grupo

  python 04_amostra_humana.py --professores P1 P2 P3
"""
import argparse
import csv
import random
import string
from collections import defaultdict

from importlib import import_module

from comum import CONFIG, CRITERIOS, DADOS, QUESTOES, ler_jsonl

derivacao = import_module("09_derivar_4_alternativas")
aritmetica = import_module("02b_verificar_aritmetica")

PASTA = DADOS / "humana"
COLUNA_MOTIVO = "motivo_reprovacao"


def sortear(registros, por_celula, rng):
    grupos = defaultdict(list)
    for r in registros:
        grupos[(r["ano"], r["habilidade"])].append(r)
    return [r for g in grupos.values() for r in rng.sample(g, min(por_celula, len(g)))]


def montar_ordem(item_ids, rng, itens_por_bloco, ancoras_por_bloco):
    """Ordem de apresentação de um professor: [(item_id, bloco, eh_ancora)].

    Cada item aparece uma vez como original. Em cada bloco, `ancoras_por_bloco` originais voltam
    na segunda metade do bloco, depois da posição original.
    """
    ids = list(item_ids)
    rng.shuffle(ids)
    ordem = []
    for b, ini in enumerate(range(0, len(ids), itens_por_bloco)):
        bloco = [(i, b, False) for i in ids[ini:ini + itens_por_bloco]]
        escolhidos = [bloco[k] for k in rng.sample(range(len(bloco)), min(ancoras_por_bloco, len(bloco)))]
        for item in escolhidos:  # escolhidos antes de inserir: a lista muda a cada inserção
            original = bloco.index(item)
            bloco.insert(rng.randint(max(original + 1, len(bloco) // 2), len(bloco)), (item[0], b, True))
        ordem.extend(bloco)
    return ordem


def gerar_codigos(quantidade, rng):
    alfabeto = string.ascii_uppercase.replace("O", "").replace("I", "") + string.digits.replace("0", "").replace("1", "")
    codigos = set()
    while len(codigos) < quantidade:
        codigos.add("".join(rng.choice(alfabeto) for _ in range(5)))
    codigos = sorted(codigos)
    rng.shuffle(codigos)
    return codigos


def cabecalho(letras="ABCD"):
    return ["codigo", "bloco", "ano", "habilidade", "descricao_habilidade", "enunciado", *letras,
            "resolucao", "gabarito", *[c["id"] for c in CRITERIOS], COLUNA_MOTIVO]


def linha_item(codigo, bloco, r):
    q = r["questao"]
    return [codigo, bloco + 1, r["ano"], r["habilidade"], r["descricao_habilidade"], q["enunciado"],
            *[q["alternativas"][l] for l in sorted(q["alternativas"])], q["resolucao_passo_a_passo"], q["resposta_correta"],
            *[""] * (len(CRITERIOS) + 1)]


def escrever(caminho, linhas, cab):
    with caminho.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cab)
        w.writerows(linhas)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--professores", nargs="+", required=True)
    a = ap.parse_args()
    h = CONFIG["avaliacao_humana"]
    if len(a.professores) < h["professores_minimos"]:
        raise SystemExit(f"são necessários ao menos {h['professores_minimos']} professores")

    estrutura = {r["item_id"]: r for r in ler_jsonl(DADOS / "avaliacao_auto" / "estrutura.jsonl")}
    validos = [r for r in ler_jsonl(QUESTOES) if estrutura[r["item_id"]]["estrutura_ok"]]
    rng = random.Random(h["seed_amostra"])
    amostra = {r["item_id"]: r for r in sortear(validos, h["amostra_por_celula"], rng)}

    PASTA.mkdir(parents=True, exist_ok=True)
    cab = cabecalho()
    ordens = {p: montar_ordem(sorted(amostra), random.Random(f"{h['seed_amostra']}-{p}"),
                              h["itens_por_bloco"], h["ancoras_por_bloco"]) for p in a.professores}
    codigos = iter(gerar_codigos(sum(len(o) for o in ordens.values()), rng))
    chave = []
    for p, ordem in ordens.items():
        linhas = []
        for posicao, (item_id, bloco, ancora) in enumerate(ordem, start=1):
            codigo = next(codigos)
            linhas.append(linha_item(codigo, bloco, amostra[item_id]))
            chave.append([p, codigo, bloco + 1, posicao, item_id, int(ancora)])
        escrever(PASTA / f"folha_{p}.csv", linhas, cab)
    escrever(PASTA / "chave.csv", chave, ["professor", "codigo", "bloco", "posicao", "item_id", "ancora"])

    excedente = ler_jsonl(DADOS / "geracoes" / "excedente_5ano.jsonl")
    sorteados = random.Random(h["seed_amostra"]).sample(excedente, min(h["calibracao_itens"], len(excedente)))
    verificacao = {r["item_id"]: aritmetica.verificar(r["questao"]) for r in sorteados}
    calibracao, _ = derivacao.derivar_todos(sorteados, verificacao, CONFIG["derivacao_4_alternativas"]["seed"])
    escrever(PASTA / "calibracao.csv", [linha_item(f"C{k + 1:02d}", 0, r) for k, r in enumerate(calibracao)], cab)

    print(f"{len(amostra)} itens por professor; " + ", ".join(f"{p}: {len(o)} linhas" for p, o in ordens.items())
          + f"; calibração: {len(calibracao)} itens")


if __name__ == "__main__":
    main()
