"""Gera as questões de cada célula (n em config/celulas.json; 40 por ano) (ano x habilidade de operação, config/celulas.json) com o modelo servido por llama-server.

Uma chamada por questão, com o prompt de produção do app (app/cliente_llama_server.py).
Determinístico dado o config: seed, dificuldade e slot (subtema/tipo/contexto) dependem só da célula e do índice.
Retoma de onde parou (pula item_id já gravado).

  python 01_gerar.py --url http://127.0.0.1:8080 --modelo-info "Qwen3-4B-Q4_K_M + lora_4b_v7b_s44"
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

from comum import APP, CELULAS, CONFIG, DADOS, anexar_jsonl, ler_jsonl

sys.path.insert(0, str(APP))
import cliente_llama_server as app  # noqa: E402

SAIDA = DADOS / "geracoes" / "questoes.jsonl"


def celulas(tax):
    for c in CELULAS:
        h = tax["habilidades"][f"{c['ano']}|{c['habilidade']}"]
        yield c["ano"], c["habilidade"], h["descricoes"][0], c["operacao"], c["n"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8080")
    ap.add_argument("--modelo-info", required=True, help="texto livre gravado em cada registro (modelo, lora, hashes)")
    ap.add_argument("--limite-celulas", type=int, help="só as N primeiras células (teste rápido)")
    a = ap.parse_args()

    g = CONFIG["geracao"]
    tax = json.loads((APP / "taxonomia_subtemas.json").read_text(encoding="utf-8"))
    gramatica = (APP / "questao.gbnf").read_text(encoding="utf-8")
    cels = list(celulas(tax))[: a.limite_celulas]
    feitos = {r["item_id"] for r in ler_jsonl(SAIDA)}
    print(f"{len(cels)} células, {sum(c[4] for c in cels)} questões")

    for idx_celula, (ano, hab, descricao, operacao, n_celula) in enumerate(cels):
        hist = []
        for i in range(n_celula):
            item_id = f"{ano[0]}-{hab}-{i:02d}"
            seed = g["seed_base"] + idx_celula * 1000 + i
            dificuldade = g["rotacao_dificuldade"][i % len(g["rotacao_dificuldade"])]
            slot = app.sortear_slot(tax, ano, hab, hist, random.Random(seed))
            hist.append(slot)
            if item_id in feitos:
                continue
            prompt = app.montar_prompt(tax, ano, hab, descricao, dificuldade, slot)
            questao, tentativa, falha = None, 0, None
            for tentativa in range(1, g["tentativas_max_por_questao"] + 1):
                try:
                    obj = app.pedir(a.url, prompt, gramatica, seed * 10 + tentativa)
                except Exception as e:  # servidor/JSON inválido conta como tentativa
                    falha = repr(e)
                    continue
                if app.estrutura_ok(obj):
                    questao, falha = obj["questoes"][0], None
                    break
                falha = "estrutura_invalida"
            anexar_jsonl(SAIDA, {
                "item_id": item_id, "ano": ano, "habilidade": hab, "descricao_habilidade": descricao, "operacao": operacao,
                "dificuldade_pedida": dificuldade, "slot": slot, "prompt": prompt, "seed": seed,
                "tentativas": tentativa, "falha": falha, "questao": questao,
                "modelo_info": a.modelo_info, "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
            })
        print(f"  {ano} {hab} ok")


if __name__ == "__main__":
    main()
