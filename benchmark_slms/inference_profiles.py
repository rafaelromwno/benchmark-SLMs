"""Perfis de inferência reutilizáveis oferecidos pelo fluxo interativo."""

from benchmark_slms.core.contracts import InferenceProfile


DEFAULT_INFERENCE_PROFILES = (
    InferenceProfile(name="deterministico", temperature=0.0, top_p=1.0, repeat_penalty=1.1),
    InferenceProfile(name="balanceado", temperature=0.7, top_p=0.9, repeat_penalty=1.1),
    InferenceProfile(name="criativo", temperature=1.0, top_p=0.95, repeat_penalty=1.1),
)
