"""Pós-processamento JSON (migrado de valida_json.py)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from benchmark_slms.core.contracts import GeneratedQuestionsResponse, Questao
from benchmark_slms.core.registry import register_postprocessor


def remover_think(texto: str) -> str:
    """Remove blocos de raciocínio antes de procurar o JSON."""
    tag = "redacted_thinking"
    abre = f"<{tag}>"
    fecha = f"</{tag}>"
    sem = re.sub(re.escape(abre) + r".*?" + re.escape(fecha), "", texto, flags=re.DOTALL | re.IGNORECASE)
    sem = re.sub(re.escape(abre) + r".*$", "", sem, flags=re.DOTALL | re.IGNORECASE)
    return sem.strip()


def _resumo_erro_pydantic(exc: ValidationError) -> str:
    partes = []
    for err in exc.errors()[:3]:
        loc = ".".join(str(x) for x in err.get("loc", ()))
        msg = err.get("msg", "inválido")
        partes.append(f"{loc}: {msg}" if loc else msg)
    return "; ".join(partes) if partes else "schema inválido"


def validar_questoes_individuais(
    dados: Any,
) -> tuple[GeneratedQuestionsResponse | None, list[dict[str, Any]], str | None]:
    """Valida cada questão isoladamente; mantém as válidas e reporta as inválidas."""
    if not isinstance(dados, dict):
        return None, [], "Raiz do JSON não é um objeto"

    raw_list = dados.get("questoes")
    if raw_list is None:
        return None, [], "Campo 'questoes' ausente"
    if not isinstance(raw_list, list):
        return None, [], "Campo 'questoes' não é uma lista"
    if len(raw_list) == 0:
        return None, [], "Lista 'questoes' vazia"

    validas: list[Questao] = []
    invalidas: list[dict[str, Any]] = []

    for i, item in enumerate(raw_list):
        try:
            validas.append(Questao.model_validate(item))
        except ValidationError as exc:
            invalidas.append({"indice": i, "erro": _resumo_erro_pydantic(exc)})
        except Exception as exc:
            invalidas.append({"indice": i, "erro": str(exc)})

    if not validas:
        return (
            None,
            invalidas,
            f"Nenhuma questão válida ({len(invalidas)} inválida(s))",
        )

    return GeneratedQuestionsResponse(questoes=validas), invalidas, None


@dataclass
class ExtracaoJson:
    """Resultado da extração/validação JSON (questão a questão)."""

    ok: bool
    parsed: GeneratedQuestionsResponse | None
    erro: str | None
    questoes_invalidas: list[dict[str, Any]] = field(default_factory=list)
    questoes_geradas: int = 0

    @property
    def questoes_validas(self) -> int:
        return len(self.parsed.questoes) if self.parsed else 0


def extrair_e_validar(texto: str) -> ExtracaoJson:
    """Extrai JSON da resposta e valida cada questão individualmente.

    Questões com schema inválido são reportadas em ``questoes_invalidas`` e
    descartadas; as válidas permanecem em ``parsed`` (não invalida o conjunto).
    """
    texto = remover_think(texto)
    candidatos: list[str] = []

    matches_markdown = re.findall(r"```json\s*(.*?)\s*```", texto, re.DOTALL)
    candidatos.extend([m.strip() for m in matches_markdown])

    matches_chaves = re.findall(r"\{.*?\}(?=\s*(?:```|$|\{))", texto, re.DOTALL)
    candidatos.extend([m.strip() for m in matches_chaves])

    if not candidatos:
        return ExtracaoJson(ok=False, parsed=None, erro="JSON não encontrado na resposta")

    ultimo_erro = "Nenhum candidato de JSON válido encontrado"
    melhor: ExtracaoJson | None = None

    for json_str in candidatos:
        try:
            dados = json.loads(json_str)
        except json.JSONDecodeError:
            ultimo_erro = "JSON inválido"
            continue

        parsed, invalidas, erro = validar_questoes_individuais(dados)
        geradas = len(dados["questoes"]) if isinstance(dados, dict) and isinstance(dados.get("questoes"), list) else 0

        if parsed is not None:
            resultado = ExtracaoJson(
                ok=True,
                parsed=parsed,
                erro=None,
                questoes_invalidas=invalidas,
                questoes_geradas=geradas,
            )
            # Prefere o candidato com mais questões válidas
            if melhor is None or resultado.questoes_validas > melhor.questoes_validas:
                melhor = resultado
        else:
            ultimo_erro = erro or "Schema inválido"
            if melhor is None and invalidas:
                melhor = ExtracaoJson(
                    ok=False,
                    parsed=None,
                    erro=ultimo_erro,
                    questoes_invalidas=invalidas,
                    questoes_geradas=geradas,
                )

    if melhor and melhor.ok:
        return melhor
    if melhor:
        return melhor
    return ExtracaoJson(ok=False, parsed=None, erro=ultimo_erro)


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
        return (
            False,
            f"Esperado {quantidade_esperada} questões válidas, restaram {quantidade_real}",
        )
    return True, None


@register_postprocessor("json_task")
def processar_json_task(texto: str, quantidade_esperada: int = 1) -> dict:
    extracao = extrair_e_validar(texto)
    qtd_ok, qtd_erro = (True, None)
    if extracao.ok and extracao.parsed:
        qtd_ok, qtd_erro = validar_quantidade(extracao.parsed, quantidade_esperada)

    erro = extracao.erro or qtd_erro
    if extracao.questoes_invalidas and not erro:
        n_inv = len(extracao.questoes_invalidas)
        erro = f"{n_inv} questão(ões) inválida(s) descartada(s)"

    return {
        "json_valido": extracao.ok and qtd_ok,
        "json_erro": erro,
        "quantidade_ok": qtd_ok,
        "quantidade_erro": qtd_erro,
        "parsed": extracao.parsed.model_dump() if extracao.parsed else None,
        "questoes_validas": extracao.questoes_validas,
        "questoes_geradas": extracao.questoes_geradas,
        "questoes_invalidas": extracao.questoes_invalidas,
    }
