import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
APP = RAIZ / "modelo"
CONFIG = json.loads((RAIZ / "config" / "protocolo.json").read_text(encoding="utf-8"))
CRITERIOS = json.loads((RAIZ / "config" / "criterios.json").read_text(encoding="utf-8"))["criterios"]
CELULAS = json.loads((RAIZ / "config" / "celulas.json").read_text(encoding="utf-8"))["celulas"]
DADOS = RAIZ / "dados"
LETRAS = "ABCDE"


def ler_jsonl(caminho):
    caminho = Path(caminho)
    if not caminho.exists():
        return []
    with caminho.open(encoding="utf-8") as f:
        return [json.loads(linha) for linha in f if linha.strip()]


def anexar_jsonl(caminho, registro):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def texto_item(q):
    alternativas = "\n".join(f"{l}) {q['alternativas'][l]}" for l in LETRAS)
    return (f"Enunciado: {q['enunciado']}\n{alternativas}\n"
            f"Resolução: {q['resolucao_passo_a_passo']}\nGabarito: {q['resposta_correta']}")


def entrada_item(r):
    return (f"Ano: {r['ano']} ano. Habilidade: {r['habilidade']} — {r['descricao_habilidade']}")


def nota_1a5(score_0a10):
    for baixo, alto, nota in CONFIG["avaliacao_automatica"]["faixas_nota_1a5"]:
        if score_0a10 <= alto:
            return nota
    return 5
