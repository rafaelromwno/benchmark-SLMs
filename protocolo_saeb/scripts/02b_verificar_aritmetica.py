"""Verificação aritmética determinística (sem LLM) de cada questão.

Confere (1) cada equação escrita na resolução (`a + b = c`) e (2) se o resultado da resolução (última igualdade ou números da última frase) está entre
as alternativas e se a letra do gabarito é a dessa alternativa. NÃO interpreta o enunciado: uma resolução que
calcula corretamente a conta errada passa na parte (1). Por isso a **cobertura** é parte do resultado: só os
itens `verificavel` entram nas taxas.

Veredito por item: ok | erro | nao_verificavel.
Saídas: dados/avaliacao_auto/aritmetica.jsonl e aritmetica_resumo.json
"""
import ast
import json
import re
from fractions import Fraction

from comum import DADOS, LETRAS, ler_jsonl

SAIDA = DADOS / "avaliacao_auto" / "aritmetica.jsonl"
RESUMO = DADOS / "avaliacao_auto" / "aritmetica_resumo.json"

NUMERO = r"\d+(?:\.\d{3})*(?:,\d+)?|\d+\.\d{1,2}(?!\d)|\d+"
NUMEROS = re.compile(NUMERO)
IGUALDADE = re.compile(rf"=\s*(?P<n>{NUMERO})")
CARACTERES_EXPRESSAO = set("0123456789.,+-−–×x*÷/:() ")
MAX_EXPRESSAO = 80


def numero(texto):
    t = texto.strip()
    if re.fullmatch(r"\d+(?:\.\d{3})+(?:,\d+)?", t):
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", ".")
    return Fraction(t)


def avaliar(expressao):
    """Avalia uma expressão aritmética com + - * / e parênteses, em frações exatas. None se não for válida."""
    e = expressao.replace("×", "*").replace("÷", "/").replace(":", "/").replace("−", "-").replace("–", "-")
    e = re.sub(r"(?<=[\d)])\s*x\s*(?=[\d(])", "*", e)
    e = re.sub(NUMERO, lambda m: f"F('{numero(m.group(0))}')", e)
    try:
        arvore = ast.parse(e, mode="eval")
        for no in ast.walk(arvore):
            if not isinstance(no, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Load, ast.Constant,
                                   ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd)):
                return None
            if isinstance(no, ast.Name) and no.id != "F":
                return None
            if isinstance(no, ast.Call) and not (isinstance(no.func, ast.Name) and no.func.id == "F"):
                return None
        return eval(compile(arvore, "<expr>", "eval"), {"__builtins__": {}}, {"F": Fraction})
    except (SyntaxError, ZeroDivisionError, ValueError, TypeError):
        return None


def _igual(calculado, escrito):
    """Igualdade exata, ou igualdade na precisão escrita (arredondamento ou truncamento: 4,166 para 25/6)."""
    valor = numero(escrito)
    if calculado == valor:
        return True
    casas = len(escrito.split(",")[1]) if "," in escrito else 0
    return casas > 0 and abs(calculado - valor) < Fraction(1, 10 ** casas)


def valor_alternativa(texto):
    achados = NUMEROS.findall(str(texto))
    return numero(achados[0]) if len(achados) == 1 else None


def equacoes(texto):
    """Pares (expressão, resultado_escrito) de cada `expressão = número` com a expressão puramente numérica."""
    achadas = []
    for m in re.finditer("=", texto):
        j = m.start()
        direita = re.match(rf"\s*({NUMERO})", texto[j + 1:])
        if not direita:
            continue
        depois = texto[j + 1 + direita.end():].lstrip()
        if re.match(rf"[+\-−–×x*÷/:^]\s*[\d(]", depois):
            continue  # cadeia "a = b + c": o resultado completo aparece na próxima igualdade
        i = j
        while i > 0 and j - i < MAX_EXPRESSAO and texto[i - 1] in CARACTERES_EXPRESSAO:
            i -= 1
        for k in [i] + [p + 1 for p in range(i, j) if texto[p] == " "]:
            candidato = texto[k:j].strip()
            candidato = candidato.lstrip(".,:;-−–+*×÷/x ")
            antes = texto[:j - len(texto[k:j])].rstrip()
            if (candidato and re.search(r"[+\-−–×x*÷/:]", candidato) and avaliar(candidato) is not None
                    and not (antes and (antes[-1].isalpha() or antes[-1] in "^²³"))):
                achadas.append((candidato, direita.group(1)))
                break
    return achadas


def verificar(q):
    resolucao = q["resolucao_passo_a_passo"]
    conferidas, erradas = 0, []
    for expressao, escrito in equacoes(resolucao):
        esquerda = avaliar(expressao)
        conferidas += 1
        if not _igual(esquerda, escrito):
            erradas.append(f"{expressao} = {escrito} (correto: {float(esquerda):g})")
    finais = IGUALDADE.findall(resolucao)
    final = numero(finais[-1]) if finais else None
    ultima_frase = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", resolucao.strip())[-1]
    candidatos = {numero(n) for n in NUMEROS.findall(ultima_frase)} | ({final} if final is not None else set())
    todas = sorted(q["alternativas"])
    letras = [l for l in todas if valor_alternativa(q["alternativas"][l]) in candidatos]
    numericas = sum(valor_alternativa(q["alternativas"][l]) is not None for l in todas)
    verificavel = conferidas > 0 and bool(candidatos) and numericas >= len(todas) - 1
    fora = verificavel and not letras
    confere = (q["resposta_correta"] in letras) if letras else None
    if not verificavel:
        veredito = "nao_verificavel"
    else:
        veredito = "erro" if erradas or fora or confere is False else "ok"
    return {"equacoes_conferidas": conferidas, "equacoes_erradas": erradas,
            "resultado_final": float(final) if final is not None else None,
            "alternativas_com_resultado": letras, "gabarito_confere": confere,
            "resultado_fora_das_alternativas": bool(fora), "verificavel": verificavel, "veredito": veredito}


def main():
    if SAIDA.exists():
        SAIDA.unlink()
    registros = [r for r in ler_jsonl(DADOS / "geracoes" / "questoes.jsonl") if r["questao"]]
    resultados = []
    for r in registros:
        v = {"item_id": r["item_id"], "ano": r["ano"], **verificar(r["questao"])}
        resultados.append(v)
        with SAIDA.open("a", encoding="utf-8") as f:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")
    n = len(resultados)
    ver = [v for v in resultados if v["verificavel"]]
    erro = [v for v in ver if v["veredito"] == "erro"]
    resumo = {"n_itens": n, "n_verificaveis": len(ver), "cobertura_pct": round(100 * len(ver) / n, 1) if n else None,
              "n_erro": len(erro), "erro_entre_verificaveis_pct": round(100 * len(erro) / len(ver), 1) if ver else None,
              "por_ano": {}}
    for ano in sorted({v["ano"] for v in resultados}):
        g = [v for v in resultados if v["ano"] == ano]
        gv = [v for v in g if v["verificavel"]]
        resumo["por_ano"][ano] = {"n": len(g), "verificaveis": len(gv), "erro": sum(v["veredito"] == "erro" for v in gv)}
    RESUMO.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resumo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
