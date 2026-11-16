"""Checagens determinísticas (sem LLM) sobre as questões geradas.

`estrutura_ok` = portão duro (conta como falha de geração). As demais são sinalizadores de estilo para análise.
Saída: dados/avaliacao_auto/estrutura.jsonl
"""
import re

from comum import DADOS, LETRAS, anexar_jsonl, ler_jsonl

SAIDA = DADOS / "avaliacao_auto" / "estrutura.jsonl"


def checar(r):
    q = r["questao"]
    if q is None:
        return {"estrutura_ok": False, "motivo": r["falha"]}
    alts = [str(q["alternativas"].get(l, "")).strip() for l in LETRAS]
    texto = q["enunciado"]
    letras_resolucao = re.findall(r"alternativa\s+([A-E])\b|letra\s+([A-E])\b", q["resolucao_passo_a_passo"])
    ultima = next((x or y for x, y in reversed(letras_resolucao)), None)
    return {
        "estrutura_ok": True,
        "alternativas_distintas": len(set(a.lower() for a in alts)) == 5,
        "alternativas_nao_vazias": all(alts),
        "resolucao_curta": len(q["resolucao_passo_a_passo"]) < 40,
        "enunciado_caixa_alta": texto.isupper(),
        "alternativa_e_nenhuma": "nenhuma das alternativas" in alts[4].lower(),
        "resolucao_cita_outra_letra": bool(ultima and ultima != q["resposta_correta"]),
    }


def main():
    if SAIDA.exists():
        SAIDA.unlink()
    registros = ler_jsonl(DADOS / "geracoes" / "questoes.jsonl")
    for r in registros:
        anexar_jsonl(SAIDA, {"item_id": r["item_id"], **checar(r)})
    ok = sum(1 for r in ler_jsonl(SAIDA) if r["estrutura_ok"])
    print(f"estrutura_ok: {ok}/{len(registros)}")


if __name__ == "__main__":
    main()
