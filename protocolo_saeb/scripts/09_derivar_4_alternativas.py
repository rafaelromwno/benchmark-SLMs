"""Deriva a versão de 4 alternativas (A–D, como o Saeb) das questões geradas com 5, sem descartar nenhuma.

Transformação determinística e auditável (a geração original em questoes.jsonl não é alterada):

1. Remove UMA alternativa que não seja a chave nem uma alternativa que contenha o resultado da resolução
   (assim a correção da questão não muda). Ordem de preferência: alternativa repetida, "Nenhuma das alternativas",
   a letra E, e, se a E for a chave ou o resultado, o distrator numericamente mais distante da chave.
2. Reordena as alternativas para balancear a letra do gabarito por ano (A–D, ~25% cada), respeitando restrições:
   alternativas numéricas em ordem monotônica mantêm a ordem; "Nenhuma das alternativas" que reste fica por último.
3. Reescreve referências a letras na resolução, se houver (hoje não há), e sinaliza `revisar` quando a referência
   é à alternativa removida.

Salvaguardas verificadas aqui: o texto da chave não muda; só se removem textos; a verificação aritmética de cada
questão dá o mesmo veredito antes e depois, exceto as que eram erro por alternativas repetidas.
Saídas: dados/geracoes/questoes_saeb4.jsonl e dados/geracoes/DERIVACAO_4_ALTERNATIVAS.md
"""
import json
import random
import re
from collections import Counter, defaultdict
from importlib import import_module

from comum import CONFIG, DADOS, ler_jsonl

ORIGEM = DADOS / "geracoes" / "questoes.jsonl"
SAIDA = DADOS / "geracoes" / "questoes_saeb4.jsonl"
RELATORIO = DADOS / "geracoes" / "DERIVACAO_4_ALTERNATIVAS.md"
LETRAS5, LETRAS4 = "ABCDE", "ABCD"
REFERENCIA_LETRA = re.compile(r"\b(alternativa|letra|op[cç][aã]o)(\s+)\(?([A-E])\b")

aritmetica = import_module("02b_verificar_aritmetica")


def eh_nenhuma(texto):
    return "nenhuma d" in str(texto).lower()


def normalizado(texto):
    return re.sub(r"\s+", " ", str(texto).strip().lower())


def escolher_remocao(q, protegidas, rng):
    """(letra, motivo) da alternativa removida. Nunca a chave nem as protegidas."""
    alts = q["alternativas"]
    livres = [l for l in LETRAS5 if l not in protegidas]
    textos = Counter(normalizado(alts[l]) for l in LETRAS5)
    # cópia exata de outra alternativa pode sair mesmo se protegida: o texto continua presente em outra letra
    repetidas = [l for l in LETRAS5 if l != q["resposta_correta"] and textos[normalizado(alts[l])] > 1]
    if repetidas:
        return repetidas[-1], "alternativa_repetida"
    nenhuma = [l for l in livres if eh_nenhuma(alts[l])]
    if nenhuma:
        return nenhuma[-1], "nenhuma_das_alternativas"
    if "E" in livres:
        return "E", "letra_E"
    valores = {l: aritmetica.valor_alternativa(alts[l]) for l in LETRAS5}
    chave = valores[q["resposta_correta"]]
    if chave is not None and all(valores[l] is not None for l in livres):
        return max(livres, key=lambda l: (abs(valores[l] - chave), l)), "distrator_mais_distante_da_chave"
    return rng.choice(livres), "distrator_sorteado"


def ordem_monotonica(textos):
    valores = [aritmetica.valor_alternativa(t) for t in textos]
    if None in valores:
        return False
    return valores == sorted(valores) or valores == sorted(valores, reverse=True)


def derivar(registro, protegidas, rng):
    """(questão de 4 alternativas, auditoria, letra desejada ou restrições) — a letra da chave é definida depois."""
    q = registro["questao"]
    removida, motivo = escolher_remocao(q, protegidas, rng)
    restantes = [l for l in LETRAS5 if l != removida]
    textos = [q["alternativas"][l] for l in restantes]
    monotonica = ordem_monotonica(textos)
    nenhuma_no_fim = any(eh_nenhuma(t) for t in textos) and not eh_nenhuma(q["alternativas"][q["resposta_correta"]])
    return {"removida": removida, "motivo": motivo, "restantes": restantes, "monotonica": monotonica,
            "nenhuma_no_fim": nenhuma_no_fim}


def letras_permitidas(plano):
    """Letras de 4 alternativas onde a chave pode ficar, dada a transformação planejada."""
    if plano["monotonica"]:
        return [LETRAS4[plano["restantes"].index(plano["chave"])]]
    return list(LETRAS4[:3] if plano["nenhuma_no_fim"] else LETRAS4)


def balancear(planos, rng):
    """Atribui a letra final da chave a cada item, por ano, igualando as contagens com as restrições."""
    por_ano = defaultdict(list)
    for item_id, p in planos.items():
        por_ano[p["ano"]].append(item_id)
    for ano, ids in por_ano.items():
        contagem = Counter()
        fixos = [i for i in ids if len(letras_permitidas(planos[i])) == 1]
        for i in fixos:
            planos[i]["chave_nova"] = letras_permitidas(planos[i])[0]
            contagem[planos[i]["chave_nova"]] += 1
        livres = [i for i in ids if i not in fixos]
        rng.shuffle(livres)
        for i in sorted(livres, key=lambda i: len(letras_permitidas(planos[i]))):
            opcoes = letras_permitidas(planos[i])
            menor = min(contagem[l] for l in opcoes)
            escolhida = rng.choice([l for l in opcoes if contagem[l] == menor])
            planos[i]["chave_nova"] = escolhida
            contagem[escolhida] += 1


def montar_questao(q, plano, rng):
    """Aplica o plano: devolve (nova questão, mapa antigo→novo, resolução reescrita?, revisar?)."""
    chave_texto_antes = q["alternativas"][q["resposta_correta"]]
    outros = [l for l in plano["restantes"] if l != plano["chave"]]
    if plano["monotonica"]:
        ordem = list(plano["restantes"])
    else:
        rng.shuffle(outros)
        posicoes = list(LETRAS4)
        fixada = None
        if plano["nenhuma_no_fim"]:
            fixada = next(l for l in outros if eh_nenhuma(q["alternativas"][l]))
            outros.remove(fixada)
            posicoes.remove("D")
        posicoes.remove(plano["chave_nova"])
        ordem = [None] * 4
        ordem[LETRAS4.index(plano["chave_nova"])] = plano["chave"]
        for pos, letra in zip(posicoes, outros):
            ordem[LETRAS4.index(pos)] = letra
        if fixada:
            ordem[3] = fixada
    mapa = {antiga: LETRAS4[k] for k, antiga in enumerate(ordem)}
    nova = {mapa[l]: q["alternativas"][l] for l in ordem}
    resolucao, reescrita, revisar = q["resolucao_passo_a_passo"], False, False

    def trocar(m):
        nonlocal reescrita, revisar
        antiga = m.group(3)
        if antiga in mapa:
            reescrita = reescrita or mapa[antiga] != antiga
            return f"{m.group(1)}{m.group(2)}{mapa[antiga]}"
        revisar = True
        return m.group(0)

    resolucao = REFERENCIA_LETRA.sub(trocar, resolucao)
    nova_questao = {**q, "alternativas": dict(sorted(nova.items())), "resposta_correta": mapa[q["resposta_correta"]],
                    "resolucao_passo_a_passo": resolucao}
    assert nova_questao["alternativas"][nova_questao["resposta_correta"]] == chave_texto_antes
    return nova_questao, mapa, reescrita, revisar


def derivar_todos(registros, verificacao, semente):
    """Deriva todos os `registros` (5 alternativas) para 4. `verificacao[item_id]` traz `alternativas_com_resultado`."""
    planos = {}
    for r in registros:
        rng = random.Random(f"{semente}-{r['item_id']}-remocao")
        q = r["questao"]
        protegidas = {q["resposta_correta"], *verificacao[r["item_id"]]["alternativas_com_resultado"]}
        plano = derivar(r, protegidas, rng)
        plano |= {"ano": r["ano"], "chave": q["resposta_correta"]}
        planos[r["item_id"]] = plano
    balancear(planos, random.Random(f"{semente}-balanceamento"))

    derivados, auditoria = [], []
    for r in registros:
        p = planos[r["item_id"]]
        nova, mapa, reescrita, revisar = montar_questao(r["questao"], p, random.Random(f"{semente}-{r['item_id']}-ordem"))
        texto_removido = r["questao"]["alternativas"][p["removida"]]
        r2 = {**r, "questao": nova, "transformacao": {
            "versao": "saeb4", "alternativa_removida": p["removida"], "texto_removido": texto_removido, "motivo": p["motivo"],
            "mapa_letras": mapa, "chave_original": r["questao"]["resposta_correta"], "chave_nova": nova["resposta_correta"],
            "ordem_monotonica_preservada": p["monotonica"], "nenhuma_fixada_no_fim": p["nenhuma_no_fim"],
            "resolucao_reescrita": reescrita, "revisar": revisar}}
        derivados.append(r2)
        assert set(nova["alternativas"].values()) <= set(r["questao"]["alternativas"].values()) and len(nova["alternativas"]) == 4
        assert all(r["questao"]["alternativas"][l] in nova["alternativas"].values() for l in verificacao[r["item_id"]]["alternativas_com_resultado"])
        auditoria.append((r, r2))
    return derivados, auditoria


def main():
    registros = ler_jsonl(ORIGEM)
    verificacao = {r["item_id"]: r for r in ler_jsonl(DADOS / "avaliacao_auto" / "aritmetica.jsonl")}
    if len(verificacao) != len(registros):
        raise SystemExit("rode `make aritmetica` antes: o verificador protege as alternativas que contêm o resultado")
    derivados, auditoria = derivar_todos(registros, verificacao, CONFIG["derivacao_4_alternativas"]["seed"])
    SAIDA.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in derivados), encoding="utf-8")

    mudou = []
    for r, r2 in auditoria:
        antes, depois = verificacao[r["item_id"]]["veredito"], aritmetica.verificar(r2["questao"])["veredito"]
        if antes != depois:
            mudou.append((r["item_id"], antes, depois, r2["transformacao"]["motivo"]))
    escrever_relatorio(auditoria, mudou)
    print(RELATORIO.read_text(encoding="utf-8"))


def escrever_relatorio(auditoria, mudou):
    n = len(auditoria)
    antes, depois = defaultdict(Counter), defaultdict(Counter)
    for r, r2 in auditoria:
        antes[r["ano"]][r["questao"]["resposta_correta"]] += 1
        depois[r["ano"]][r2["questao"]["resposta_correta"]] += 1
    L = ["# Derivação para 4 alternativas (A–D)", "",
         f"{n} questões geradas com 5 alternativas viraram 4, **sem descartar nenhuma**. A geração original "
         "(`questoes.jsonl`) não é alterada; as questões avaliadas são as de `questoes_saeb4.jsonl`, cada uma com o registro "
         "da transformação (`transformacao`).", "",
         "## Alternativa removida", "", "| Motivo | Questões |", "|---|---|"]
    for motivo, k in Counter(r2["transformacao"]["motivo"] for _, r2 in auditoria).most_common():
        L.append(f"| {motivo} | {k} |")
    L += ["", "## Gabarito por letra, antes e depois", "", "| Ano | Antes A/B/C/D/E | Depois A/B/C/D |", "|---|---|---|"]
    for ano in sorted(antes):
        L.append(f"| {ano} | {'/'.join(str(antes[ano][l]) for l in LETRAS5)} | {'/'.join(str(depois[ano][l]) for l in LETRAS4)} |")
    total = Counter(r2["questao"]["resposta_correta"] for _, r2 in auditoria)
    L.append(f"| Todos | {'/'.join(str(sum(antes[a][l] for a in antes)) for l in LETRAS5)} | {'/'.join(str(total[l]) for l in LETRAS4)} |")
    t = [r2["transformacao"] for _, r2 in auditoria]
    L += ["", "## Restrições e salvaguardas", "",
          f"- Ordem monotônica preservada (a chave não pôde ser movida): {sum(x['ordem_monotonica_preservada'] for x in t)}.",
          f"- \"Nenhuma das alternativas\" mantida e fixada em D: {sum(x['nenhuma_fixada_no_fim'] for x in t)}.",
          f"- Resoluções com letra reescrita: {sum(x['resolucao_reescrita'] for x in t)}; a revisar manualmente: {sum(x['revisar'] for x in t)}.",
          f"- Texto da chave inalterado e alternativas protegidas (chave e resultado da resolução) mantidas: verificado em todas as {n}.",
          f"- Veredito da verificação aritmética antes e depois: mudou em {len(mudou)} de {n}."]
    for item_id, a, d, motivo in mudou:
        L.append(f"  - {item_id}: {a} → {d} (remoção: {motivo})")
    RELATORIO.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
