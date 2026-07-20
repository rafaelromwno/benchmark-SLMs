"""Pós-processamento JSON (migrado de valida_json.py)."""

from __future__ import annotations

import json
import re

from benchmark_slms.core.contracts import GeneratedQuestionsResponse
from benchmark_slms.core.registry import register_postprocessor


def remover_think(texto: str) -> str:
    """Remove blocos de raciocínio antes de procurar o JSON."""
    tag = "redacted_thinking"
    abre = f"<{tag}>"
    fecha = f"</{tag}>"
    sem = re.sub(re.escape(abre) + r".*?" + re.escape(fecha), "", texto, flags=re.DOTALL | re.IGNORECASE)
    sem = re.sub(re.escape(abre) + r".*$", "", sem, flags=re.DOTALL | re.IGNORECASE)
    return sem.strip()


def extrair_e_validar(texto: str) -> tuple[bool, GeneratedQuestionsResponse | None, str | None]:
    texto = remover_think(texto)
    candidatos = []

    matches_markdown = re.findall(r"```json\s*(.*?)\s*```", texto, re.DOTALL)
    candidatos.extend([m.strip() for m in matches_markdown])

    matches_chaves = re.findall(r"\{.*?\}(?=\s*(?:```|$|\{))", texto, re.DOTALL)
    candidatos.extend([m.strip() for m in matches_chaves])

    if not candidatos:
        return False, None, "JSON não encontrado na resposta"

    ultimo_erro = None

    for json_str in candidatos:
        try:
            dados = json.loads(json_str)
            resultado = GeneratedQuestionsResponse.model_validate(dados)
            return True, resultado, None
        except json.JSONDecodeError:
            ultimo_erro = "JSON inválido"
        except Exception:
            ultimo_erro = "Schema inválido"

    return False, None, ultimo_erro or "Nenhum candidato de JSON válido encontrado"


def parsear_json_bruto(texto: str) -> dict | str:
    texto = remover_think(texto)
    match = re.search(r"```json\s*(.*?)\s*```", texto, re.DOTALL)
    json_str = match.group(1).strip() if match else texto.strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return texto


def validar_quantidade(
    resultado: GeneratedQuestionsResponse, quantidade_esperada: int
) -> tuple[bool, str | None]:
    quantidade_real = len(resultado.questoes)
    if quantidade_real != quantidade_esperada:
        return False, f"Esperado {quantidade_esperada} questões, modelo gerou {quantidade_real}"
    return True, None


@register_postprocessor("json_task")
def processar_json_task(texto: str, quantidade_esperada: int = 1) -> dict:
    valido, resultado, erro = extrair_e_validar(texto)
    qtd_ok, qtd_erro = (True, None)
    if valido and resultado:
        qtd_ok, qtd_erro = validar_quantidade(resultado, quantidade_esperada)

    return {
        "json_valido": valido and qtd_ok,
        "json_erro": erro or qtd_erro,
        "quantidade_ok": qtd_ok,
        "quantidade_erro": qtd_erro,
        "parsed": resultado.model_dump() if resultado else None,
    }
