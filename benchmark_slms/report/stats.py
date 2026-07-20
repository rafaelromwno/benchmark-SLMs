"""Validação estatística — stub para M8 (Kappa de Fleiss, McNemar)."""

from __future__ import annotations

from typing import Any


def fleiss_kappa(matriz: list[list[int]]) -> float:
    """Stub — Kappa de Fleiss para concordância inter-anotador.

    Args:
        matriz: matriz N subjects × k categorias com contagens de raters.

    Returns:
        Coeficiente kappa (implementação real em M8).
    """
    raise NotImplementedError(
        "Kappa de Fleiss será implementado em M8 com avaliação humana (Cenário E)."
    )


def mcnemar_test(
    tabela: tuple[int, int, int, int],
) -> dict[str, Any]:
    """Stub — teste de McNemar para comparação pareada de modelos.

    Args:
        tabela: (a, b, c, d) onde a=ambos certos, b=modelo1 certo/modelo2 errado,
                c=modelo1 errado/modelo2 certo, d=ambos errados.

    Returns:
        dict com estatística e p-valor (implementação real em M8).
    """
    raise NotImplementedError(
        "McNemar será implementado em M8 para comparação estatística entre modelos."
    )


def comparar_vereditos_automatico_vs_humano(
    automaticos: list[bool],
    humanos: list[bool],
) -> dict[str, Any]:
    """Stub — concordância apto_mathia_automatico vs apto_mathia_final."""
    if len(automaticos) != len(humanos):
        raise ValueError("Listas devem ter o mesmo tamanho")
    concordantes = sum(a == h for a, h in zip(automaticos, humanos))
    return {
        "n": len(automaticos),
        "concordantes": concordantes,
        "taxa_concordancia": concordantes / len(automaticos) if automaticos else 0,
        "nota": "Métricas estatísticas completas (Kappa, McNemar) em M8",
    }
