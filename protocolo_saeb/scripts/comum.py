import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
APP = RAIZ / "modelo"
CONFIG = json.loads((RAIZ / "config" / "protocolo.json").read_text(encoding="utf-8"))
_CRITERIOS = json.loads((RAIZ / "config" / "criterios.json").read_text(encoding="utf-8"))
CRITERIOS = _CRITERIOS["criterios"]
LEGADO = _CRITERIOS.get("legado", [])
NUCLEO = [c["id"] for c in CRITERIOS if c.get("nucleo")]
LIMIAR = CONFIG["avaliacao_automatica"]["limiar_aprovacao_nota"]
TETO_INTENCAO = 2
_DERIVACAO = CONFIG["derivacao_4_alternativas"]
VERSAO = _DERIVACAO["versao_avaliada"]
VERSAO_ORIGEM = _DERIVACAO["versao_origem"]
REAPROVEITADOS = set(_DERIVACAO["criterios_reaproveitados_da_origem"])
QUESTOES_ORIGINAIS = RAIZ / "dados" / "geracoes" / "questoes.jsonl"
QUESTOES = RAIZ / "dados" / "geracoes" / ("questoes_saeb4.jsonl" if VERSAO == "saeb4" else "questoes.jsonl")
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
    alternativas = "\n".join(f"{l}) {q['alternativas'][l]}" for l in sorted(q["alternativas"]))
    return (f"Enunciado: {q['enunciado']}\n{alternativas}\n"
            f"Resolução: {q['resolucao_passo_a_passo']}\nGabarito: {q['resposta_correta']}")


def entrada_item(r):
    return (f"Ano: {r['ano']} ano. Habilidade: {r['habilidade']} — {r['descricao_habilidade']}")


def nota_1a5(score_0a10):
    for baixo, alto, nota in CONFIG["avaliacao_automatica"]["faixas_nota_1a5"]:
        if score_0a10 <= alto:
            return nota
    return 5


def nucleo_aprovado(notas):
    """True se todos os critérios do núcleo têm nota >= limiar; None se algum não foi avaliado."""
    if any(c not in notas for c in NUCLEO):
        return None
    return all(notas[c] >= LIMIAR for c in NUCLEO)


def intencao_com_teto(notas):
    """Nota de intencao_uso com o teto aplicado por código: núcleo reprovado => no máximo TETO_INTENCAO."""
    bruta = notas["intencao_uso"]
    return bruta if nucleo_aprovado(notas) is not False else min(bruta, TETO_INTENCAO)


def notas_do_juiz(linhas):
    """Linhas do geval.jsonl válidas para a versão avaliada: {(item_id, criterio): linha}.

    Vale a linha da versão avaliada; na falta dela, vale a da versão de origem só para os critérios que não
    dependem das alternativas (REAPROVEITADOS). Linhas sem `versao` são da versão de origem.
    """
    validas = {}
    for r in linhas:
        versao = r.get("versao", VERSAO_ORIGEM)
        chave = (r["item_id"], r["criterio"])
        if versao == VERSAO:
            validas[chave] = r
        elif r["criterio"] in REAPROVEITADOS and chave not in validas:
            validas[chave] = r
    return validas
