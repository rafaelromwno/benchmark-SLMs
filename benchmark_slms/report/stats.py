"""Estatísticas do protocolo: resumos contínuos + IC95% (Wilson / bootstrap)."""

from __future__ import annotations

import math
import random
from typing import Any, Sequence


def _finite(xs: Sequence[float]) -> list[float]:
    out: list[float] = []
    for x in xs:
        try:
            v = float(x)
        except (TypeError, ValueError):
            continue
        if math.isfinite(v):
            out.append(v)
    return out


def _percentile(sorted_xs: list[float], p: float) -> float:
    """Percentil linear (p em 0–100) sobre lista já ordenada."""
    if not sorted_xs:
        return float("nan")
    if len(sorted_xs) == 1:
        return sorted_xs[0]
    k = (p / 100.0) * (len(sorted_xs) - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_xs[int(k)]
    return sorted_xs[f] * (c - k) + sorted_xs[c] * (k - f)


def resumo_continuo(valores: Sequence[float]) -> dict[str, Any]:
    """Mediana, IQR, p95, p99, max e média auxiliar (pareceres v3/v4)."""
    xs = sorted(_finite(valores))
    n = len(xs)
    if n == 0:
        return {
            "n": 0,
            "mediana": None,
            "iqr": None,
            "p25": None,
            "p75": None,
            "p95": None,
            "p99": None,
            "max": None,
            "media": None,
        }
    p25 = _percentile(xs, 25)
    p75 = _percentile(xs, 75)
    return {
        "n": n,
        "mediana": round(_percentile(xs, 50), 6),
        "iqr": round(p75 - p25, 6),
        "p25": round(p25, 6),
        "p75": round(p75, 6),
        "p95": round(_percentile(xs, 95), 6),
        "p99": round(_percentile(xs, 99), 6),
        "max": round(xs[-1], 6),
        "media": round(sum(xs) / n, 6),
    }


def wilson_ic95(sucessos: int, n: int) -> dict[str, Any]:
    """Proporção com IC95% de Wilson; numerador/denominador explícitos."""
    if n <= 0:
        return {
            "numerador": 0,
            "denominador": 0,
            "ponto": None,
            "ic95": [None, None],
            "formato": None,
            "unidade_analise": "execucao",
        }
    z = 1.959963984540054  # N(0,1) 97.5%
    phat = sucessos / n
    denom = 1 + z**2 / n
    centre = phat + z**2 / (2 * n)
    spread = z * math.sqrt(phat * (1 - phat) / n + z**2 / (4 * n**2))
    lo = max(0.0, (centre - spread) / denom)
    hi = min(1.0, (centre + spread) / denom)
    pct = phat * 100
    return {
        "numerador": sucessos,
        "denominador": n,
        "ponto": round(phat, 6),
        "ic95": [round(lo, 6), round(hi, 6)],
        "formato": f"{pct:.1f}% [{lo*100:.1f}–{hi*100:.1f}]",
        "unidade_analise": "execucao",
    }


def bootstrap_ic_mediana(
    valores: Sequence[float],
    *,
    n_boot: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    """IC95% da mediana via bootstrap percentil (requer n≥5)."""
    xs = _finite(valores)
    n = len(xs)
    if n < 5:
        med = _percentile(sorted(xs), 50) if xs else None
        return {
            "n": n,
            "mediana": None if med is None or math.isnan(med) else round(med, 6),
            "ic95": [None, None],
            "formato": None,
            "nota": "n<5 — IC da mediana omitido",
        }
    rng = random.Random(seed)
    meds: list[float] = []
    for _ in range(n_boot):
        amostra = [xs[rng.randrange(n)] for _ in range(n)]
        meds.append(_percentile(sorted(amostra), 50))
    meds.sort()
    lo = _percentile(meds, 2.5)
    hi = _percentile(meds, 97.5)
    med = _percentile(sorted(xs), 50)
    return {
        "n": n,
        "mediana": round(med, 6),
        "ic95": [round(lo, 6), round(hi, 6)],
        "formato": f"{med:.4g} [{lo:.4g}–{hi:.4g}]",
        "unidade_analise": "execucao",
    }


def fleiss_kappa(matriz: list[list[int]]) -> float:
    """Stub — concordância inter-anotador (Cenário E / M8)."""
    raise NotImplementedError(
        "Kappa de Fleiss será implementado em M8 com avaliação humana (Cenário E)."
    )


def mcnemar_test(tabela: tuple[int, int, int, int]) -> dict[str, Any]:
    """Stub — McNemar pareado (M8)."""
    raise NotImplementedError(
        "McNemar será implementado em M8 para comparação estatística entre modelos."
    )


def comparar_vereditos_automatico_vs_humano(
    automaticos: list[bool],
    humanos: list[bool],
) -> dict[str, Any]:
    """Stub — concordância apto_mathia automático vs humano."""
    if len(automaticos) != len(humanos):
        raise ValueError("Listas devem ter o mesmo tamanho")
    concordantes = sum(a == h for a, h in zip(automaticos, humanos))
    return {
        "n": len(automaticos),
        "concordantes": concordantes,
        "taxa_concordancia": concordantes / len(automaticos) if automaticos else 0,
        "nota": "Métricas estatísticas completas (Kappa, McNemar) em M8",
    }
