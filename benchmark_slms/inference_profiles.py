"""Perfis de inferência reutilizáveis oferecidos pelo fluxo interativo."""

from benchmark_slms.core.contracts import InferenceProfile

# Protocolo principal (parecer v4): só T varia; top_p/top_k/RP congelados.
DEFAULT_INFERENCE_PROFILES = (
    InferenceProfile(
        name="balanceado",
        temperature=0.7,
        top_p=0.80,
        top_k=20,
        repeat_penalty=1.00,
    ),
    InferenceProfile(
        name="criativo",
        temperature=1.3,
        top_p=0.80,
        top_k=20,
        repeat_penalty=1.00,
    ),
)

# Fora do ranking principal — disponível só se pedido explicitamente.
EXPLORATORY_INFERENCE_PROFILES = (
    InferenceProfile(
        name="deterministico",
        temperature=0.0,
        top_p=1.0,
        top_k=20,
        repeat_penalty=1.00,
        exploratory=True,
    ),
)
