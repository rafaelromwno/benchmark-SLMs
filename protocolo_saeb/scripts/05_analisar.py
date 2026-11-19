"""Análise: qualidade da geração, teto humano, concordância juiz × professores e triagem.

Ordem de leitura (PROTOCOLO.md §7): 1) teto humano; 2) pares de professores; 3) juiz × humanos com AC1 de Gwet
como medida primária, comparado ao AC1 entre professores; 4) por dimensão, com bootstrap pareado por itens e
correção de Holm; 5) Spearman, descritivo (as notas do juiz ficam quase só nos extremos); 6) triagem (RQ3).

Entradas: dados/avaliacao_auto/{geval,estrutura,aritmetica}.jsonl e as planilhas preenchidas
dados/humana/folha_<prof>.csv com dados/humana/chave.csv. Saídas: resultados/resumo.json e resumo.md.
Só biblioteca padrão.
"""
import csv
import json
import math
import random
from collections import Counter, defaultdict
from itertools import combinations

from comum import (CELULAS, CONFIG, CRITERIOS, DADOS, LEGADO, LIMIAR, NUCLEO, RAIZ, intencao_com_teto, ler_jsonl,
                   notas_do_juiz, nucleo_aprovado)

BINARIOS = [c["id"] for c in CRITERIOS if c["tipo"] == "binario"]
SAIDA = RAIZ / "resultados"
REPETICOES_BOOTSTRAP = 2000
SEMENTE_BOOTSTRAP = 20260401
COLUNA_MOTIVO = "motivo_reprovacao"


# ---------- estatísticas básicas ----------

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


# ---------- concordância binária e entre vários avaliadores ----------

def concordancia_binaria(a, b):
    """p0, AC1 de Gwet, κ de Cohen e índices de prevalência e viés entre dois vetores booleanos."""
    n = len(a)
    if n == 0:
        return None
    p0 = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pi = (pa + pb) / 2
    pe = 2 * pi * (1 - pi)
    ac1 = round((p0 - pe) / (1 - pe), 3) if pe != 1 else None
    ambos_sim = sum(x and y for x, y in zip(a, b))
    ambos_nao = sum(not x and not y for x, y in zip(a, b))
    return {"n": n, "p0": round(p0, 3), "ac1": ac1, "kappa": kappa(a, b, [False, True]),
            "prevalencia_a": round(pa, 3), "prevalencia_b": round(pb, 3),
            "indice_prevalencia": round(abs(ambos_sim - ambos_nao) / n, 3),
            "indice_vies": round(abs(sum(x and not y for x, y in zip(a, b)) - sum(y and not x for x, y in zip(a, b))) / n, 3)}


def ac1_multi(itens):
    """AC1 de Gwet para vários avaliadores (binário). `itens` = lista de listas de bool (>= 2 por item)."""
    itens = [i for i in itens if len(i) >= 2]
    if not itens:
        return None
    pa = sum(sum(1 for x, y in combinations(i, 2) if x == y) / (len(i) * (len(i) - 1) / 2) for i in itens) / len(itens)
    total = sum(len(i) for i in itens)
    pi = sum(sum(i) for i in itens) / total
    pe = 2 * pi * (1 - pi)
    return round((pa - pe) / (1 - pe), 3) if pe != 1 else None


def fleiss_kappa(itens):
    """κ de Fleiss; usa só os itens com o número de avaliações mais comum."""
    if not itens:
        return None
    r = Counter(len(i) for i in itens).most_common(1)[0][0]
    itens = [i for i in itens if len(i) == r]
    if r < 2 or not itens:
        return None
    categorias = sorted({x for i in itens for x in i})
    n = len(itens)
    pj = {c: sum(i.count(c) for i in itens) / (n * r) for c in categorias}
    pi = [(sum(i.count(c) ** 2 for c in categorias) - r) / (r * (r - 1)) for i in itens]
    pbar, pe = sum(pi) / n, sum(v * v for v in pj.values())
    return round((pbar - pe) / (1 - pe), 3) if pe != 1 else None


def krippendorff_alpha(itens, metrica="nominal"):
    """α de Krippendorff. `itens` = lista de listas de valores; metrica 'nominal' ou 'intervalo'."""
    def delta(c, k):
        return (0.0 if c == k else 1.0) if metrica == "nominal" else float(c - k) ** 2

    coincidencia = defaultdict(float)
    for i in itens:
        m = len(i)
        if m < 2:
            continue
        for x in range(m):
            for y in range(m):
                if x != y:
                    coincidencia[(i[x], i[y])] += 1 / (m - 1)
    marginal = defaultdict(float)
    for (c, _), v in coincidencia.items():
        marginal[c] += v
    n = sum(marginal.values())
    if n <= 1:
        return None
    do = sum(v * delta(c, k) for (c, k), v in coincidencia.items())
    de = sum(marginal[c] * marginal[k] * delta(c, k) for c in marginal for k in marginal) / (n - 1)
    return round(1 - do / de, 3) if de else None


def holm(p_valores):
    """Correção de Holm: {chave: p} -> {chave: p ajustado}."""
    ordem = sorted(p_valores, key=p_valores.get)
    m, ajustado, maximo = len(ordem), {}, 0.0
    for posicao, chave in enumerate(ordem):
        maximo = max(maximo, min(1.0, (m - posicao) * p_valores[chave]))
        ajustado[chave] = round(maximo, 4)
    return ajustado


def bootstrap(ids, estatistica, repeticoes=REPETICOES_BOOTSTRAP, semente=SEMENTE_BOOTSTRAP):
    """Reamostra itens com reposição. Devolve (valores ordenados, intervalo 95%) sem os None."""
    rng = random.Random(semente)
    ids = list(ids)
    valores = []
    for _ in range(repeticoes):
        v = estatistica([ids[rng.randrange(len(ids))] for _ in ids])
        if v is not None:
            valores.append(v)
    if not valores:
        return [], None
    valores.sort()
    return valores, [round(valores[int(0.025 * len(valores))], 3), round(valores[min(int(0.975 * len(valores)), len(valores) - 1)], 3)]


def p_bootstrap(valores):
    """p bilateral de H0: diferença = 0, pela fração dos valores bootstrap de cada lado do zero."""
    if not valores:
        return None
    return round(min(1.0, 2 * min(sum(v <= 0 for v in valores), sum(v >= 0 for v in valores)) / len(valores)), 4)


def maioria(votos):
    """Maioria estrita; empate conta como não."""
    votos = list(votos)
    return sum(votos) * 2 > len(votos)


# ---------- leitura das planilhas ----------

def ler_humano():
    """(humano, ancoras): humano[item][prof][criterio] e ancoras[prof] = [(item, original, repeticao)]."""
    try:
        with (DADOS / "humana" / "chave.csv").open(encoding="utf-8") as f:
            chave = {(l["professor"], l["codigo"]): l for l in csv.DictReader(f)}
    except FileNotFoundError:
        return {}, {}
    humano = defaultdict(dict)
    originais, repeticoes = defaultdict(dict), defaultdict(dict)
    for caminho in sorted((DADOS / "humana").glob("folha_*.csv")):
        prof = caminho.stem.replace("folha_", "")
        with caminho.open(encoding="utf-8") as f:
            for l in csv.DictReader(f):
                if not l["intencao_uso"].strip():
                    continue
                reg = {"intencao_uso": int(l["intencao_uso"]), "motivo": l.get(COLUNA_MOTIVO, "").strip()}
                for b in BINARIOS:
                    reg[b] = l[b].strip().lower().startswith("s")
                k = chave[(prof, l["codigo"])]
                if k["ancora"] == "1":
                    repeticoes[prof][k["item_id"]] = reg
                else:
                    humano[k["item_id"]][prof] = reg
                    originais[prof][k["item_id"]] = reg
    ancoras = {p: [(i, originais[p][i], r) for i, r in reps.items() if i in originais[p]] for p, reps in repeticoes.items()}
    return dict(humano), ancoras


def aprovado_professor(reg):
    return all(reg[c] for c in NUCLEO)


def consistencia_ancoras(ancoras):
    resultado = {}
    for prof, pares in ancoras.items():
        if not pares:
            continue
        resultado[prof] = {
            "n_ancoras": len(pares),
            "binarios_iguais_pct": round(100 * sum(o[b] == r[b] for _, o, r in pares for b in BINARIOS) / (len(pares) * len(BINARIOS)), 1),
            "likert_igual_pct": round(100 * sum(o["intencao_uso"] == r["intencao_uso"] for _, o, r in pares) / len(pares), 1),
            "likert_diferenca_ate_1_pct": round(100 * sum(abs(o["intencao_uso"] - r["intencao_uso"]) <= 1 for _, o, r in pares) / len(pares), 1)}
    return resultado


# ---------- análises humanas e juiz × humanos ----------

def teto_humano(humano):
    profs = sorted({p for r in humano.values() for p in r})
    ids = sorted(i for i, r in humano.items() if len(r) == len(profs) and len(profs) >= 2)
    saida = {"professores": profs, "n_itens_com_todos": len(ids)}
    if not ids:
        return saida
    dimensoes = {c: (lambda i, c=c: [humano[i][p][c] for p in profs]) for c in BINARIOS}
    dimensoes["nucleo"] = lambda i: [aprovado_professor(humano[i][p]) for p in profs]
    dimensoes["intencao_aprovada"] = lambda i: [humano[i][p]["intencao_uso"] >= LIMIAR for p in profs]
    saida["por_dimensao"] = {nome: {"fleiss_kappa": fleiss_kappa([f(i) for i in ids]),
                                    "krippendorff_alpha_nominal": krippendorff_alpha([[int(x) for x in f(i)] for i in ids]),
                                    "ac1": ac1_multi([f(i) for i in ids])} for nome, f in dimensoes.items()}
    saida["intencao_uso_likert"] = {"krippendorff_alpha_intervalo": krippendorff_alpha(
        [[humano[i][p]["intencao_uso"] for p in profs] for i in ids], "intervalo")}
    saida["pares_de_professores"] = {}
    for p, q in combinations(profs, 2):
        a, b = [aprovado_professor(humano[i][p]) for i in ids], [aprovado_professor(humano[i][q]) for i in ids]
        saida["pares_de_professores"][f"{p}-{q}"] = {
            "kappa_nucleo": kappa(a, b, [False, True]), "ac1_nucleo": (concordancia_binaria(a, b) or {}).get("ac1"),
            "kappa_ponderado_likert": kappa([humano[i][p]["intencao_uso"] for i in ids], [humano[i][q]["intencao_uso"] for i in ids],
                                            [1, 2, 3, 4, 5], "quadratico")}
    return saida


def referencia_humana(humano, ids):
    ref = {c: {i: maioria(humano[i][p][c] for p in humano[i]) for i in ids} for c in BINARIOS}
    ref["nucleo"] = {i: maioria(aprovado_professor(r) for r in humano[i].values()) for i in ids}
    ref["intencao_aprovada"] = {i: maioria(r["intencao_uso"] >= LIMIAR for r in humano[i].values()) for i in ids}
    return ref


def voto_professor(reg, dimensao):
    if dimensao == "nucleo":
        return aprovado_professor(reg)
    if dimensao == "intencao_aprovada":
        return reg["intencao_uso"] >= LIMIAR
    return reg[dimensao]


def juiz_binario(juiz, i, dimensao):
    if dimensao == "nucleo":
        return nucleo_aprovado(juiz[i])
    if dimensao == "intencao_aprovada":
        return intencao_com_teto(juiz[i]) >= LIMIAR if "intencao_uso" in juiz[i] else None
    return juiz[i][dimensao] >= LIMIAR if dimensao in juiz[i] else None


def juiz_vs_humanos(humano, juiz):
    profs = sorted({p for r in humano.values() for p in r})
    saida, p_brutos = {}, {}
    for d in [*BINARIOS, "nucleo", "intencao_aprovada"]:
        ids = sorted(i for i in humano if i in juiz and len(humano[i]) == len(profs) and juiz_binario(juiz, i, d) is not None)
        if len(ids) < 5:
            continue
        ref = referencia_humana(humano, ids)[d]
        j = [juiz_binario(juiz, i, d) for i in ids]
        h = [ref[i] for i in ids]
        tp = sum(x and y for x, y in zip(j, h)); tn = sum(not x and not y for x, y in zip(j, h))
        fp = sum(x and not y for x, y in zip(j, h)); fn = sum(y and not x for x, y in zip(j, h))
        saida[d] = {"n": len(ids), "juiz_vs_maioria": concordancia_binaria(j, h),
                    "sensibilidade_pct": round(100 * tp / (tp + fn), 1) if tp + fn else None,
                    "especificidade_pct": round(100 * tn / (tn + fp), 1) if tn + fp else None,
                    "matriz": {"VP": tp, "VN": tn, "FP": fp, "FN": fn}}
        por_prof = {p: {i: voto_professor(humano[i][p], d) for i in ids} for p in profs}
        jd = dict(zip(ids, j))

        def diferenca(amostra, jd=jd, por_prof=por_prof):
            ac_jp = [(concordancia_binaria([jd[i] for i in amostra], [por_prof[p][i] for i in amostra]) or {}).get("ac1") for p in profs]
            ac_pp = [(concordancia_binaria([por_prof[p][i] for i in amostra], [por_prof[q][i] for i in amostra]) or {}).get("ac1")
                     for p, q in combinations(profs, 2)]
            if None in ac_jp or None in ac_pp or not ac_pp:
                return None
            return sum(ac_jp) / len(ac_jp) - sum(ac_pp) / len(ac_pp)

        observado = diferenca(ids)
        valores, ic = bootstrap(ids, diferenca)
        saida[d]["ac1_juiz_vs_professor_menos_ac1_entre_professores"] = {
            "diferenca": round(observado, 3) if observado is not None else None, "ic95": ic}
        p_brutos[d] = p_bootstrap(valores)
    for d, p in holm({k: v for k, v in p_brutos.items() if v is not None}).items():
        saida[d]["ac1_juiz_vs_professor_menos_ac1_entre_professores"]["p_holm"] = p
    ids = sorted(i for i in humano if i in juiz and "intencao_uso" in juiz[i])
    if len(ids) >= 5:
        saida["spearman_descritivo"] = {
            "n": len(ids), "observacao": "notas do juiz quase só nos extremos: restrição de amplitude",
            "rho": spearman([sum(r["intencao_uso"] for r in humano[i].values()) / len(humano[i]) for i in ids],
                            [intencao_com_teto(juiz[i]) for i in ids])}
    return saida


def metricas_triagem(aprova, referencia, ids):
    """Sensibilidade, especificidade, VPP, VPN, taxa de descarte de itens válidos e fração descartada."""
    tp = sum(aprova[i] and referencia[i] for i in ids); fp = sum(aprova[i] and not referencia[i] for i in ids)
    tn = sum(not aprova[i] and not referencia[i] for i in ids); fn = sum(not aprova[i] and referencia[i] for i in ids)
    n = len(ids)

    def razao(a, b):
        return round(a / b, 3) if b else None

    return {"taxa_base_aprovados": razao(tp + fn, n), "sensibilidade": razao(tp, tp + fn), "especificidade": razao(tn, tn + fp),
            "vpp": razao(tp, tp + fp), "vpn": razao(tn, tn + fn), "descarte_de_validos": razao(fn, tp + fn),
            "fracao_descartada": razao(tn + fn, n)}


def triagem(humano, juiz, aritmetica):
    ids = sorted(i for i in humano if i in juiz and nucleo_aprovado(juiz[i]) is not None and i in aritmetica)
    if len(ids) < 10:
        return {"n": len(ids), "observacao": "itens insuficientes com juiz, verificador e professores"}
    referencia = referencia_humana(humano, ids)["nucleo"]
    triadores = {"juiz": {i: nucleo_aprovado(juiz[i]) for i in ids},
                 "verificacao_aritmetica": {i: aritmetica[i]["veredito"] != "erro" for i in ids}}
    triadores["juiz_e_verificacao"] = {i: triadores["juiz"][i] and triadores["verificacao_aritmetica"][i] for i in ids}
    saida = {"n": len(ids), "referencia": "núcleo aprovado pela maioria dos professores", "triadores": {}}
    for nome, aprova in triadores.items():
        resultado = metricas_triagem(aprova, referencia, ids)
        resultado["ic95"] = {m: bootstrap(ids, lambda amostra, m=m, aprova=aprova: metricas_triagem(aprova, referencia, amostra)[m])[1]
                             for m in ("sensibilidade", "especificidade", "vpp", "vpn", "descarte_de_validos")}
        saida["triadores"][nome] = resultado
    return saida


# ---------- programa principal ----------

def main():
    questoes = {r["item_id"]: r for r in ler_jsonl(DADOS / "geracoes" / "questoes.jsonl")}
    estrutura = {r["item_id"]: r for r in ler_jsonl(DADOS / "avaliacao_auto" / "estrutura.jsonl")}
    aritmetica = {r["item_id"]: r for r in ler_jsonl(DADOS / "avaliacao_auto" / "aritmetica.jsonl")}
    juiz, legado = defaultdict(dict), defaultdict(dict)
    ids_legado = {c["id"] for c in LEGADO}
    linhas_juiz = ler_jsonl(DADOS / "avaliacao_auto" / "geval.jsonl")
    for r in linhas_juiz:
        if r["criterio"] in ids_legado:
            legado[r["item_id"]][r["criterio"]] = r["nota_1a5"]
    for (item_id, criterio), r in notas_do_juiz(r for r in linhas_juiz if r["criterio"] not in ids_legado).items():
        juiz[item_id][criterio] = r["nota_1a5"]
    anos = CONFIG["geracao"]["anos"]
    res = {"n_geradas": len(questoes)}

    res["geracao"] = {ano: taxa(estrutura[i]["estrutura_ok"] for i, q in questoes.items() if q["ano"] == ano) for ano in anos}
    res["geracao"]["tentativas_media"] = round(sum(q["tentativas"] for q in questoes.values()) / max(len(questoes), 1), 2)

    res["distribuicao_notas_juiz"] = {}
    for c in CRITERIOS:
        notas = [g[c["id"]] for g in juiz.values() if c["id"] in g]
        res["distribuicao_notas_juiz"][c["id"]] = {
            "contagem": dict(sorted(Counter(notas).items())),
            "pct_extremos_1_2_5": round(100 * sum(n in (1, 2, 5) for n in notas) / len(notas), 1) if notas else None}

    aprov = {i: intencao_com_teto(g) >= LIMIAR for i, g in juiz.items() if "intencao_uso" in g}
    res["geval_aprovacao_por_ano"] = {ano: taxa(v for i, v in aprov.items() if questoes[i]["ano"] == ano) for ano in anos}
    celulas, por_op = defaultdict(list), defaultdict(list)
    for i, v in aprov.items():
        celulas[f"{questoes[i]['ano']}|{questoes[i]['habilidade']}"].append(v)
        por_op[questoes[i]["operacao"]].append(v)
    res["geval_aprovacao_por_celula"] = {c: taxa(v) for c, v in sorted(celulas.items())}
    res["geval_aprovacao_por_criterio"] = {c["id"]: taxa(g[c["id"]] >= LIMIAR for g in juiz.values() if c["id"] in g) for c in CRITERIOS}
    res["geval_aprovacao_por_operacao"] = {o: taxa(v) for o, v in sorted(por_op.items())}
    nucleo = {i: nucleo_aprovado(g) for i, g in juiz.items() if nucleo_aprovado(g) is not None}
    if nucleo:
        res["geval_nucleo_por_ano"] = {ano: taxa(v for i, v in nucleo.items() if questoes[i]["ano"] == ano) for ano in anos}
    if legado:
        res["geval_legado_correcao_matematica"] = taxa(g["correcao_matematica"] >= LIMIAR for g in legado.values() if "correcao_matematica" in g)

    ver = [a for a in aritmetica.values() if a["verificavel"]]
    if aritmetica:
        res["verificacao_aritmetica"] = {"n": len(aritmetica), "verificaveis": len(ver),
                                         "cobertura_pct": round(100 * len(ver) / len(aritmetica), 1),
                                         "erro_entre_verificaveis": taxa(a["veredito"] == "erro" for a in ver)}

    humano, ancoras = ler_humano()
    res["humana"] = {"n_itens_avaliados": len(humano)}
    if humano:
        res["humana"]["teto_humano"] = teto_humano(humano)
        res["humana"]["consistencia_ancoras"] = consistencia_ancoras(ancoras)
        res["juiz_vs_humanos"] = juiz_vs_humanos(humano, juiz)
        res["triagem_rq3"] = triagem(humano, juiz, aritmetica)
        ids = sorted(humano)
        ref = referencia_humana(humano, ids)
        res["humana"]["aprovacao_nucleo_por_ano"] = {ano: taxa(ref["nucleo"][i] for i in ids if questoes[i]["ano"] == ano) for ano in anos}
        res["humana"]["aprovacao_por_criterio"] = {c: taxa(ref[c].values()) for c in BINARIOS}

    SAIDA.mkdir(exist_ok=True)
    (SAIDA / "resumo.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    linhas = ["# Resumo", "", "| Ano | G-Eval aprova intenção de uso (≥4) | IC95 | Geração estruturalmente válida |", "|---|---|---|---|"]
    for ano in anos:
        a, g = res["geval_aprovacao_por_ano"][ano], res["geracao"][ano]
        linhas.append(f"| {ano} | {a['pct']}% ({a['s']}/{a['n']}) | {a['ic95_pct']} | {g['pct']}% |")
    linhas += ["", "## Aprovação por célula (ano e habilidade)", "",
               "| Ano | Habilidade | Código Matriz Saeb | G-Eval aprova intenção de uso (≥4) |", "|---|---|---|---|"]
    for c in CELULAS:
        t = res["geval_aprovacao_por_celula"].get(f"{c['ano']}|{c['habilidade']}")
        if t:
            linhas.append(f"| {c['ano']} | {c['habilidade']} | {c.get('codigo_matriz_saeb') or 'sem código (Saeb não avalia o 1º ano)'} "
                          f"| {t['pct']}% ({t['s']}/{t['n']}) |")
    linhas += ["", "## Distribuição das notas do juiz", "", "| Critério | Contagem por nota | % em 1, 2 ou 5 |", "|---|---|---|"]
    for c, d in res["distribuicao_notas_juiz"].items():
        linhas.append(f"| {c} | {d['contagem']} | {d['pct_extremos_1_2_5']}% |")
    if "verificacao_aritmetica" in res:
        v = res["verificacao_aritmetica"]
        e = v["erro_entre_verificaveis"]
        linhas += ["", f"Verificação aritmética: cobertura {v['cobertura_pct']}% ({v['verificaveis']}/{v['n']}); "
                       f"erro entre verificáveis {e['pct']}% ({e['s']}/{e['n']})."]
    if not humano:
        linhas += ["", "Avaliação humana: ainda sem planilhas preenchidas (`dados/humana/`)."]
    (SAIDA / "resumo.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
