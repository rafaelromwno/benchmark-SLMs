"""Ground Truth — stub para M8 (Exact Match / Pass@1).

Interface pronta; implementação de gabaritos curados fica para milestone posterior.
"""

from __future__ import annotations

from benchmark_slms.core.contracts import GeneratedQuestionsResponse, Sample


def tem_ground_truth(sample: Sample) -> bool:
    """Indica se o sample possui gabarito curado disponível."""
    return sample.golden is not None


def obter_ground_truth(sample: Sample) -> GeneratedQuestionsResponse | None:
    """Retorna o gabarito esperado, se existir."""
    if not sample.golden:
        return None
    return GeneratedQuestionsResponse.model_validate(sample.golden)


def exact_match(
    predicao: GeneratedQuestionsResponse,
    gabarito: GeneratedQuestionsResponse,
) -> bool:
    """Stub — implementação real em M8."""
    raise NotImplementedError("Exact Match será implementado em M8")


def pass_at_k(
    predicoes: list[GeneratedQuestionsResponse],
    gabarito: GeneratedQuestionsResponse,
    k: int = 1,
) -> bool:
    """Stub — implementação real em M8."""
    raise NotImplementedError("Pass@k será implementado em M8")
