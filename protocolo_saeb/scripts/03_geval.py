"""Avaliação automática com G-Eval (DeepEval): um metric por critério de config/criterios.json.

Passos de avaliação fixos em config/criterios.json (evaluation_steps), para o juiz não reinventá-los a cada chamada.
Juiz = qualquer endpoint compatível com a API de chat da OpenAI (Ollama /v1, llama-server, vLLM, nuvem).
O juiz NÃO pode ser o modelo gerador. Registre nome/versão do juiz: ele vai em cada linha de saída.

  python 03_geval.py --juiz-url http://localhost:11434/v1 --juiz-modelo gpt-oss:20b

Requer Python >= 3.10 e `pip install deepeval`.
Nota: o G-Eval original pondera a nota pelas log-probabilidades; com juiz via API genérica o DeepEval usa a
nota direta. Isso é um desvio do artigo-base e deve ser declarado no texto.
"""
import argparse
import json
import os
import re
import urllib.request

from deepeval.metrics import GEval
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from comum import (CONFIG, CRITERIOS, DADOS, QUESTOES, VERSAO, anexar_jsonl, entrada_item, ler_jsonl, nota_1a5,  # noqa
                   notas_do_juiz, texto_item)

SAIDA = DADOS / "avaliacao_auto" / "geval.jsonl"


class JuizOpenAICompat(DeepEvalBaseLLM):
    def __init__(self, url, modelo, chave, esforco=None):
        self.url, self.modelo, self.chave, self.esforco = url.rstrip("/"), modelo, chave, esforco

    def load_model(self):
        return self

    def get_model_name(self):
        return self.modelo

    def generate(self, prompt, schema=None):
        if schema is not None:
            prompt += "\n\nResponda somente com JSON válido que siga exatamente o schema pedido."
        corpo = {"model": self.modelo, "temperature": CONFIG["avaliacao_automatica"]["temperatura_juiz"],
                 "messages": [{"role": "user", "content": prompt}]}
        if self.esforco:
            corpo["reasoning_effort"] = self.esforco
        req = urllib.request.Request(
            self.url + "/chat/completions", data=json.dumps(corpo).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.chave}"})
        with urllib.request.urlopen(req, timeout=600) as r:
            texto = json.loads(r.read().decode())["choices"][0]["message"]["content"]
        if schema is None:
            return texto
        achado = re.search(r"\{.*\}", texto, re.DOTALL)
        return schema.model_validate_json(achado.group(0) if achado else texto)

    async def a_generate(self, prompt, schema=None):
        return self.generate(prompt, schema)


def montar_metrica(criterio, juiz):
    return GEval(
        name=criterio["id"], evaluation_steps=criterio["passos_geval"], model=juiz,
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        async_mode=False, verbose_mode=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--juiz-url", required=True)
    ap.add_argument("--juiz-modelo", required=True)
    ap.add_argument("--juiz-chave", default=os.environ.get("JUIZ_API_KEY", "sem-chave"))
    ap.add_argument("--esforco", choices=["low", "medium", "high"], help="reasoning_effort do juiz (gpt-oss)")
    ap.add_argument("--criterios", nargs="*", default=[c["id"] for c in CRITERIOS])
    a = ap.parse_args()

    juiz = JuizOpenAICompat(a.juiz_url, a.juiz_modelo, a.juiz_chave, a.esforco)
    metricas = {c["id"]: montar_metrica(c, juiz) for c in CRITERIOS if c["id"] in a.criterios}
    estrutura = {r["item_id"]: r for r in ler_jsonl(DADOS / "avaliacao_auto" / "estrutura.jsonl")}
    feitos = set(notas_do_juiz(ler_jsonl(SAIDA)))

    for r in ler_jsonl(QUESTOES):
        if not estrutura[r["item_id"]]["estrutura_ok"]:
            continue
        caso = LLMTestCase(input=entrada_item(r), actual_output=texto_item(r["questao"]))
        for cid, metrica in metricas.items():
            if (r["item_id"], cid) in feitos:
                continue
            try:
                metrica.measure(caso)
            except Exception as erro:
                print(f"FALHA {r['item_id']} {cid}: {type(erro).__name__}", flush=True)
                continue
            score10 = round(metrica.score * 10, 2)
            anexar_jsonl(SAIDA, {"item_id": r["item_id"], "criterio": cid, "score_0a10": score10,
                                 "nota_1a5": nota_1a5(score10), "justificativa": metrica.reason,
                                 "juiz": a.juiz_modelo, "versao": VERSAO})
        print(r["item_id"])


if __name__ == "__main__":
    main()
