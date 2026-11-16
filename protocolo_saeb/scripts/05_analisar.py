"""Análise: qualidade da geração (G-Eval em tudo), concordância entre professores e entre G-Eval e professores.

Entrada: dados/avaliacao_auto/*.jsonl e planilhas preenchidas dados/humana/folha_<prof>.csv (+ chave.csv).
Saída: resultados/resumo.json e resultados/resumo.md. Só biblioteca padrão.
"""
import csv
import json
import math
from collections import Counter, defaultdict

from comum import CONFIG, CRITERIOS, DADOS, RAIZ, ler_jsonl

LIMIAR = CONFIG["avaliacao_automatica"]["limiar_aprovacao_nota"]
BINARIOS = [c["id"] for c in CRITERIOS if c["tipo"] == "binario"]
SAIDA = RAIZ / "resultados"


def wilson(s, n, z=1.96):
    if n == 0:
        return None
    p = s / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - m), 1), round(100 * (c + m), 1)]


def taxa(bools):
    bools = list(bools)
    s = sum(bools)
    return {"n": len(bools), "s": s, "pct": round(100 * s / len(bools), 1) if bools else None,
            "ic95_pct": wilson(s, len(bools))}


def pearson(x, y):
    n = len(x)
    if n < 3:
        return None
    mx, my = sum(x) / n, sum(y) / n
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return round(sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy), 3) if sx and sy else None


def ranks(v):
    ordem = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[ordem[j + 1]] == v[ordem[i]]:
            j += 1
        for k in range(i, j + 1):
            r[ordem[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x, y):
    return pearson(ranks(x), ranks(y))


def kappa(a, b, categorias, pesos="nenhum"):
    n = len(a)
    if n == 0:
        return None
    k = len(categorias)
    ix = {c: i for i, c in enumerate(categorias)}

    def w(i, j):
        if pesos == "quadratico":
            return 1 - ((i - j) / (k - 1)) ** 2
        return 1.0 if i == j else 0.0

    obs = sum(w(ix[x], ix[y]) for x, y in zip(a, b)) / n
    pa, pb = Counter(a), Counter(b)
    esp = sum(w(ix[i], ix[j]) * pa[i] * pb[j] for i in categorias for j in categorias) / (n * n)
    return round((obs - esp) / (1 - esp), 3) if esp != 1 else None


def ler_humano():
    chave = {}
    try:
        with (DADOS / "humana" / "chave.csv").open(encoding="utf-8") as f:
            for l in csv.DictReader(f):
                chave[l["codigo"]] = l["item_id"]
    except FileNotFoundError:
        return {}
    notas = defaultdict(dict)  # item_id -> professor -> {criterio: valor}
    for caminho in sorted((DADOS / "humana").glob("folha_*.csv")):
        prof = caminho.stem.replace("folha_", "")
        with caminho.open(encoding="utf-8") as f:
            for l in csv.DictReader(f):
                if not l["intencao_uso"].strip():
                    continue
                reg = {"intencao_uso": int(l["intencao_uso"])}
                for b in BINARIOS:
                    reg[b] = l[b].strip().lower().startswith("s")
                notas[chave[l["codigo"]]][prof] = reg
    return notas


def main():
    questoes = {r["item_id"]: r for r in ler_jsonl(DADOS / "geracoes" / "questoes.jsonl")}
    estrutura = {r["item_id"]: r for r in ler_jsonl(DADOS / "avaliacao_auto" / "estrutura.jsonl")}
    geval = defaultdict(dict)
    for r in ler_jsonl(DADOS / "avaliacao_auto" / "geval.jsonl"):
        geval[r["item_id"]][r["criterio"]] = r["nota_1a5"]
    res = {"n_geradas": len(questoes)}

    res["geracao"] = {ano: taxa(estrutura[i]["estrutura_ok"] for i, q in questoes.items() if q["ano"] == ano)
                      for ano in CONFIG["geracao"]["anos"]}
    res["geracao"]["tentativas_media"] = round(sum(q["tentativas"] for q in questoes.values()) / max(len(questoes), 1), 2)

    aprov = {i: g["intencao_uso"] >= LIMIAR for i, g in geval.items() if "intencao_uso" in g}
    res["geval_aprovacao_por_ano"] = {
        ano: taxa(v for i, v in aprov.items() if questoes[i]["ano"] == ano) for ano in CONFIG["geracao"]["anos"]}
    celulas = defaultdict(list)
    for i, v in aprov.items():
        celulas[f"{questoes[i]['ano']}|{questoes[i]['habilidade']}"].append(v)
    res["geval_aprovacao_por_celula"] = {c: taxa(v) for c, v in sorted(celulas.items())}
    res["geval_aprovacao_por_criterio"] = {
        c["id"]: taxa(g[c["id"]] >= LIMIAR for g in geval.values() if c["id"] in g) for c in CRITERIOS}

    por_op = defaultdict(list)
    for i, v in aprov.items():
        por_op[questoes[i]["operacao"]].append(v)
    res["geval_aprovacao_por_operacao"] = {o: taxa(v) for o, v in sorted(por_op.items())}

    humano = ler_humano()
    res["humana"] = {"n_itens_avaliados": len(humano)}
    pares = [(i, list(p.values())) for i, p in humano.items() if len(p) >= 2]
    if pares:
        l1 = [p[0]["intencao_uso"] for _, p in pares]
        l2 = [p[1]["intencao_uso"] for _, p in pares]
        res["humana"]["concordancia_entre_professores"] = {
            "n_itens": len(pares),
            "kappa_ponderado_likert": kappa(l1, l2, [1, 2, 3, 4, 5], "quadratico"),
            "kappa_aprovacao": kappa([x >= LIMIAR for x in l1], [x >= LIMIAR for x in l2], [False, True]),
            "concordancia_aprovacao_pct": round(100 * sum((x >= LIMIAR) == (y >= LIMIAR) for x, y in zip(l1, l2)) / len(l1), 1),
            "kappa_por_criterio_binario": {
                b: kappa([p[0][b] for _, p in pares], [p[1][b] for _, p in pares], [False, True]) for b in BINARIOS},
        }

    ref = {i: sum(r["intencao_uso"] for r in p.values()) / len(p) for i, p in humano.items() if i in aprov}
    if ref:
        ids = sorted(ref)
        h_aprov = {i: ref[i] >= LIMIAR for i in ids}
        res["humana"]["aprovacao_por_ano"] = {
            ano: taxa(h_aprov[i] for i in ids if questoes[i]["ano"] == ano) for ano in CONFIG["geracao"]["anos"]}
        ho = defaultdict(list)
        hc = defaultdict(list)
        for i in ids:
            ho[questoes[i]["operacao"]].append(h_aprov[i])
            hc[f"{questoes[i]['ano']}|{questoes[i]['habilidade']}"].append(h_aprov[i])
        res["humana"]["aprovacao_por_operacao"] = {o: taxa(v) for o, v in sorted(ho.items())}
        res["humana"]["aprovacao_por_celula"] = {c: taxa(v) for c, v in sorted(hc.items())}
        hx = [ref[i] for i in ids]
        gx = [geval[i]["intencao_uso"] for i in ids]
        tp = sum(h_aprov[i] and aprov[i] for i in ids)
        tn = sum(not h_aprov[i] and not aprov[i] for i in ids)
        fp = sum(not h_aprov[i] and aprov[i] for i in ids)
        fn = sum(h_aprov[i] and not aprov[i] for i in ids)
        res["geval_vs_humano"] = {
            "n": len(ids), "pearson": pearson(hx, gx), "spearman": spearman(hx, gx),
            "acuracia_pct": round(100 * (tp + tn) / len(ids), 1),
            "kappa": kappa([h_aprov[i] for i in ids], [aprov[i] for i in ids], [False, True]),
            "sensibilidade_pct": round(100 * tp / (tp + fn), 1) if tp + fn else None,
            "especificidade_pct": round(100 * tn / (tn + fp), 1) if tn + fp else None,
            "matriz": {"VP": tp, "VN": tn, "FP": fp, "FN": fn},
            "por_ano": {ano: {"pearson": pearson([ref[i] for i in ids if questoes[i]["ano"] == ano],
                                                 [geval[i]["intencao_uso"] for i in ids if questoes[i]["ano"] == ano])}
                        for ano in CONFIG["geracao"]["anos"]},
            "por_criterio_binario": {
                b: {"kappa": kappa([all(r[b] for r in humano[i].values()) for i in ids],
                                   [geval[i][b] >= LIMIAR for i in ids], [False, True])}
                for b in BINARIOS if all(b in geval[i] for i in ids)},
        }

    SAIDA.mkdir(exist_ok=True)
    (SAIDA / "resumo.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    linhas = ["# Resumo", "", "| Ano | G-Eval aprova (≥4) | IC95 | Geração estruturalmente válida |", "|---|---|---|---|"]
    for ano in CONFIG["geracao"]["anos"]:
        a, g = res["geval_aprovacao_por_ano"][ano], res["geracao"][ano]
        linhas.append(f"| {ano} | {a['pct']}% ({a['s']}/{a['n']}) | {a['ic95_pct']} | {g['pct']}% |")
    (SAIDA / "resumo.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
