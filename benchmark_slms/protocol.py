"""Constantes versionadas do protocolo experimental (pareceres v1/v4)."""

from __future__ import annotations

# Réplicas por célula (modelo × perfil × cenário). Lista fixa e auditável.
# Unidade de replicação: uma execução completa com esta seed no RNG de geração
# e na amostragem do cenário B.
PROTOCOL_SEEDS: tuple[int, ...] = (42, 7, 13, 21, 33, 55, 89, 123, 256, 777)

# Congelados no manifesto — só temperature varia entre perfis do protocolo.
PROTOCOL_SAMPLING_FREEZE: dict[str, float | int | bool] = {
    "top_k": 20,
    "min_p": 0.0,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
    "enable_thinking": False,
}

# Timeout wall-clock (s) por cenário — falha vira codigo_falha="timeout".
PROTOCOL_TIMEOUTS_S: dict[str, float] = {
    "cenario_a": 180.0,
    "cenario_b": 120.0,
    "cenario_c": 120.0,
    "cenario_d": 120.0,
}
PROTOCOL_TIMEOUT_DEFAULT_S: float = 120.0

# Unidade de análise do quadro principal (parecer v4).
ANALYSIS_UNIT = "execucao"  # modelo × perfil × seed (= 1 JSON em resultados/)
