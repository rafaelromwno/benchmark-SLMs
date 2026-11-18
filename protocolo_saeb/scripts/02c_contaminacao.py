"""Checagem de contaminação: os enunciados gerados são cópias de questões do treino ou entre si?

Compara cada enunciado gerado com (a) os enunciados de um ou mais arquivos de referência (treino, itens já
avaliados) e (b) os demais enunciados gerados. Similaridade = Jaccard de trigramas de palavras; o limiar vem de
config/protocolo.json e foi fixado antes de rodar. Reporta a distribuição, não só a contagem acima do limiar.

Arquivos de referência aceitos: .jsonl no formato de treino (`messages` com a resposta `{"questoes": [...]}`),
ou .jsonl/.json com objetos que tenham `enunciado` ou `questao.enunciado`.

  python 02c_contaminacao.py --referencia caminho/train.jsonl [outro.jsonl ...]
Saídas: dados/avaliacao_auto/contaminacao.jsonl e contaminacao_resumo.json
"""
import argparse
import json
import re
import unicodedata
from pathlib import Path

from comum import CONFIG, DADOS, ler_jsonl

SAIDA = DADOS / "avaliacao_auto" / "contaminacao.jsonl"
RESUMO = DADOS / "avaliacao_auto" / "contaminacao_resumo.json"
N = CONFIG["contaminacao"]["tamanho_ngrama"]
LIMIAR = CONFIG["contaminacao"]["limiar_jaccard"]


def normalizar(texto, molde=False):
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"\d+(?:[.,]\d+)*", "#" if molde else "0", t) if molde else t
    return re.findall(r"[a-z0-9#]+", t)


def trigramas(palavras, n=N):
    return {" ".join(palavras[i:i + n]) for i in range(max(len(palavras) - n + 1, 1))}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def enunciados_do_arquivo(caminho):
    caminho = Path(caminho)
    textos = []
    linhas = ler_jsonl(caminho) if caminho.suffix == ".jsonl" else json.loads(caminho.read_text(encoding="utf-8"))
    for obj in linhas:
        if "messages" in obj:
            resposta = next((m["content"] for m in reversed(obj["messages"]) if m["role"] == "assistant"), "")
            try:
                textos += [q["enunciado"] for q in json.loads(resposta)["questoes"]]
            except (ValueError, KeyError, TypeError):
                continue
        elif "enunciado" in obj:
            textos.append(obj["enunciado"])
        elif isinstance(obj.get("questao"), dict) and "enunciado" in obj["questao"]:
            textos.append(obj["questao"]["enunciado"])
    return textos


def mais_parecido(alvo, colecao, pular=None):
    """(similaridade, índice) do elemento mais parecido de `colecao` (lista de conjuntos)."""
    melhor, idx = 0.0, None
    for k, outro in enumerate(colecao):
        if k == pular:
            continue
        s = jaccard(alvo, outro)
        if s > melhor:
            melhor, idx = s, k
    return melhor, idx


def quantis(valores):
    v = sorted(valores)
    return {f"p{p}": round(v[min(int(len(v) * p / 100), len(v) - 1)], 3) for p in (50, 90, 95, 99)} | {"max": round(v[-1], 3)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--referencia", nargs="+", default=[], help="arquivos com enunciados de referência (treino etc.)")
    a = ap.parse_args()

    gerados = [(r["item_id"], r["questao"]["enunciado"]) for r in ler_jsonl(DADOS / "geracoes" / "questoes.jsonl") if r["questao"]]
    ref = [t for caminho in a.referencia for t in enunciados_do_arquivo(caminho)]
    g_exata = [trigramas(normalizar(t)) for _, t in gerados]
    g_molde = [trigramas(normalizar(t, molde=True)) for _, t in gerados]
    r_exata = [trigramas(normalizar(t)) for t in ref]
    r_molde = [trigramas(normalizar(t, molde=True)) for t in ref]

    if SAIDA.exists():
        SAIDA.unlink()
    linhas = []
    for k, (item_id, _) in enumerate(gerados):
        ie, ie_i = mais_parecido(g_exata[k], g_exata, pular=k)
        im, _ = mais_parecido(g_molde[k], g_molde, pular=k)
        linha = {"item_id": item_id, "interna_exata": round(ie, 3), "interna_molde": round(im, 3),
                 "item_interno_mais_parecido": gerados[ie_i][0] if ie_i is not None else None}
        if ref:
            te, te_i = mais_parecido(g_exata[k], r_exata)
            tm, _ = mais_parecido(g_molde[k], r_molde)
            linha |= {"referencia_exata": round(te, 3), "referencia_molde": round(tm, 3),
                      "enunciado_referencia_mais_parecido": ref[te_i][:160] if te_i is not None else None}
        linhas.append(linha)
        with SAIDA.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")

    resumo = {"n_gerados": len(gerados), "n_referencia": len(ref), "limiar_jaccard": LIMIAR, "ngrama": N,
              "interna_exata": quantis([l["interna_exata"] for l in linhas]),
              "interna_molde": quantis([l["interna_molde"] for l in linhas]),
              "acima_do_limiar_interna_exata": sum(l["interna_exata"] >= LIMIAR for l in linhas),
              "acima_do_limiar_interna_molde": sum(l["interna_molde"] >= LIMIAR for l in linhas)}
    if ref:
        resumo |= {"referencia_exata": quantis([l["referencia_exata"] for l in linhas]),
                   "referencia_molde": quantis([l["referencia_molde"] for l in linhas]),
                   "acima_do_limiar_referencia_exata": sum(l["referencia_exata"] >= LIMIAR for l in linhas),
                   "acima_do_limiar_referencia_molde": sum(l["referencia_molde"] >= LIMIAR for l in linhas)}
    RESUMO.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resumo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
