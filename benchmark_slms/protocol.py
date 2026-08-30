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
