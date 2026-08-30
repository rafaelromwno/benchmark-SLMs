"""Ground truth e checagem estrutural de gabarito (proxy até M8)."""

from __future__ import annotations

from benchmark_slms.core.contracts import GeneratedQuestionsResponse, Questao, Sample


def tem_ground_truth(sample: Sample) -> bool:
    return sample.golden is not None


def obter_ground_truth(sample: Sample) -> GeneratedQuestionsResponse | None:
    if not sample.golden:
        return None
    return GeneratedQuestionsResponse.model_validate(sample.golden)


def questao_gabarito_consistente(q: Questao) -> bool:
    """Alternativa correta existe, textos A–E distintos e resolução não vazia."""
    alts = q.alternativas.model_dump()
    if q.resposta_correta not in alts:
        return False
    if not str(alts[q.resposta_correta]).strip():
        return False
    if not str(q.resolucao_passo_a_passo).strip():
        return False
    textos = [str(alts[k]).strip() for k in ("A", "B", "C", "D", "E")]
    if any(not t for t in textos):
        return False
    return len(set(textos)) == 5


def gabarito_estrutural_ok(parsed: GeneratedQuestionsResponse | None) -> bool | None:
    """Proxy de gabarito até GT curado (M8). None se não há JSON parseado."""
    if parsed is None or not parsed.questoes:
        return None
    return all(questao_gabarito_consistente(q) for q in parsed.questoes)


def exact_match(
    predicao: GeneratedQuestionsResponse,
    gabarito: GeneratedQuestionsResponse,
) -> bool:
    raise NotImplementedError("Exact Match será implementado em M8")


def pass_at_k(
    predicoes: list[GeneratedQuestionsResponse],
    gabarito: GeneratedQuestionsResponse,
    k: int = 1,
) -> bool:
    raise NotImplementedError("Pass@k será implementado em M8")
