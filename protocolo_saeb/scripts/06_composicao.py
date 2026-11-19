"""Gera dados/geracoes/COMPOSICAO.md: proporção de questões por ano, habilidade, operação, dificuldade e gabarito."""
from collections import Counter

from comum import CELULAS, CONFIG, DADOS, LETRAS, ler_jsonl


def main():
    rs = ler_jsonl(DADOS / "geracoes" / "questoes.jsonl")
    est = {e["item_id"]: e for e in ler_jsonl(DADOS / "avaliacao_auto" / "estrutura.jsonl")}
    n = len(rs)
    L = ["# Composição das questões geradas", "",
         f"Total: {n} questões, 40 por ano. Estruturalmente válidas: {sum(e['estrutura_ok'] for e in est.values())}.", "",
         "## Por ano", "", "| Ano | Questões | % do total |", "|---|---|---|"]
    for ano in CONFIG["geracao"]["anos"]:
        k = sum(r["ano"] == ano for r in rs)
        L.append(f"| {ano} | {k} | {100 * k / n:.1f}% |")
    L += ["", "## Por ano e habilidade", "",
          "| Ano | Habilidade | Código Matriz Saeb | Operação | Questões | % do ano | % do total | Fácil/Mod./Difícil | Gabarito A/B/C/D/E | Alt. E \"Nenhuma\" | 2+ tentativas |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in CELULAS:
        g = [r for r in rs if r["ano"] == c["ano"] and r["habilidade"] == c["habilidade"]]
        ano_n = sum(r["ano"] == c["ano"] for r in rs)
        d = Counter(r["dificuldade_pedida"] for r in g)
        a = Counter(r["questao"]["resposta_correta"] for r in g)
        L.append(f"| {c['ano']} | {c['habilidade']} | {c.get('codigo_matriz_saeb') or '-'} | {c['operacao']} | {len(g)} | {100 * len(g) / ano_n:.1f}% | "
                 f"{100 * len(g) / n:.1f}% | {d['Fácil']}/{d['Moderado']}/{d['Difícil']} | "
                 f"{'/'.join(str(a[l]) for l in LETRAS)} | {sum(est[r['item_id']]['alternativa_e_nenhuma'] for r in g)} | "
                 f"{sum(r['tentativas'] > 1 for r in g)} |")
    L += ["", "## Por grupo de operação", "", "| Operação | Questões | % |", "|---|---|---|"]
    for o, k in sorted(Counter(r["operacao"] for r in rs).items()):
        L.append(f"| {o} | {k} | {100 * k / n:.1f}% |")
    L += ["", "## Indicadores de formato (todas as questões)", "",
          f"Número de alternativas por questão: {dict(Counter(len(r['questao']['alternativas']) for r in rs))}. "
          f"Esperado por letra com 5 alternativas: 20%.", "",
          "| Ano | Gabarito A | B | C | D | E | \"Nenhuma das alternativas\" (alt. E) | Questões com alternativas repetidas |",
          "|---|---|---|---|---|---|---|---|"]
    for ano in [*CONFIG["geracao"]["anos"], "Todos"]:
        g = [r for r in rs if ano == "Todos" or r["ano"] == ano]
        a = Counter(r["questao"]["resposta_correta"] for r in g)
        nenhuma = sum("nenhuma d" in r["questao"]["alternativas"]["E"].lower() for r in g)
        rep = sum(len({str(v).lower() for v in r["questao"]["alternativas"].values()}) < 5 for r in g)
        L.append(f"| {ano} | " + " | ".join(f"{100 * a[l] / len(g):.1f}%" for l in LETRAS)
                 + f" | {nenhuma} ({100 * nenhuma / len(g):.1f}%) | {rep} |")
    (DADOS / "geracoes" / "COMPOSICAO.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
