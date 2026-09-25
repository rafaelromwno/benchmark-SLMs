"""Auditoria de conteúdo da chave (alternativa marcada resolve o enunciado)."""

from __future__ import annotations

import argparse
import json
import math
import re
from fractions import Fraction as Fr
from pathlib import Path
from typing import Any

from benchmark_slms.core.contracts import Questao
from benchmark_slms.data.ground_truth import questao_gabarito_consistente
from benchmark_slms.postprocess.json_task import extrair_e_validar, validar_quantidade
from benchmark_slms.report.stats import wilson_ic95

NUM = r"[-+]?\d+(?:[.,]\d+)?"


def _f(s: object) -> float | None:
    m = re.search(NUM, str(s).replace(" ", ""))
    if not m:
        return None
    try:
        return float(m.group().replace(",", "."))
    except ValueError:
        return None


def _norm(s: object) -> str:
    return re.sub(r"\s+", " ", str(s).lower()).strip()


def grade_conteudo(q: Questao) -> bool | None:
    if not questao_gabarito_consistente(q):
        return False
    en_l = _norm(q.enunciado or "")
    alts = q.alternativas.model_dump()
    mark = q.resposta_correta
    marked_val = _f(alts[mark])
    resol = q.resolucao_passo_a_passo or ""

    m = re.search(r"entre\s+(" + NUM + r")\s+e\s+(" + NUM + r")", en_l)
    if m:
        a, b = float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))
        lo, hi = min(a, b), max(a, b)
        correct = [k for k, v in alts.items() if (val := _f(v)) is not None and lo < val < hi]
        return (mark in correct) if correct else False

    eq = re.search(
        r"(\d+)\s*\(\s*[a-z]\s*([+-])\s*(" + NUM + r")\s*\)\s*=\s*(" + NUM + r")",
        en_l,
    )
    if eq:
        a = float(eq.group(1))
        op = eq.group(2)
        b = float(eq.group(3).replace(",", "."))
        c = float(eq.group(4).replace(",", "."))
        inner = c / a
        x = inner - b if op == "+" else inner + b
        return marked_val is not None and abs(marked_val - x) < 1e-6

    eq = re.search(
        r"\(\s*[a-z]\s*([+-])\s*(" + NUM + r")\s*\)\s*\^\s*2\s*=\s*(" + NUM + r")",
        en_l,
    )
    if eq:
        op = eq.group(1)
        b = float(eq.group(2).replace(",", "."))
        c = float(eq.group(3).replace(",", "."))
        if c < 0:
            return False
        roots = {s - b if op == "+" else s + b for s in (math.sqrt(c), -math.sqrt(c))}
        return marked_val is not None and any(abs(marked_val - r) < 1e-6 for r in roots)

    eq = re.search(
        r"(\d+)\s*[a-z]\s*([+-])\s*(" + NUM + r")\s*=\s*(" + NUM + r")",
        en_l,
    )
    if eq:
        a = float(eq.group(1))
        op = eq.group(2)
        b = float(eq.group(3).replace(",", "."))
        c = float(eq.group(4).replace(",", "."))
        x = (c - b) / a if op == "+" else (c + b) / a
        return marked_val is not None and abs(marked_val - x) < 1e-6

    eq = re.search(r"(\d+)\s*[a-z]\s*=\s*(" + NUM + r")", en_l)
    if eq:
        a = float(eq.group(1))
        c = float(eq.group(2).replace(",", "."))
        return marked_val is not None and abs(marked_val - c / a) < 1e-6

    eq = re.search(
        r"(?<!\d)[a-z]\s*([+-])\s*(" + NUM + r")\s*=\s*(" + NUM + r")",
        en_l,
    )
    if eq:
        op = eq.group(1)
        b = float(eq.group(2).replace(",", "."))
        c = float(eq.group(3).replace(",", "."))
        x = c - b if op == "+" else c + b
        return marked_val is not None and abs(marked_val - x) < 1e-6

    m = re.search(
        r"se\s+a\s*=\s*("
        + NUM
        + r")(?:\s+e\s+b\s*=\s*("
        + NUM
        + r"))?.*?valor de\s+a\s*\+\s*(?:b|("
        + NUM
        + r"))",
        en_l,
    )
    if m:
        a = float(m.group(1).replace(",", "."))
        b = float((m.group(2) or m.group(3)).replace(",", "."))
        x = a + b
        return marked_val is not None and abs(marked_val - x) < 1e-6

    m = re.search(r"soma dos n.meros\s+(" + NUM + r")\s+e\s+(" + NUM + r")", en_l)
    if m:
        x = float(m.group(1).replace(",", ".")) + float(m.group(2).replace(",", "."))
        return marked_val is not None and abs(marked_val - x) < 1e-6

    m = re.search(r"divis.o de\s+(" + NUM + r")\s+por\s+(" + NUM + r")", en_l)
    if m:
        x = float(m.group(1).replace(",", ".")) / float(m.group(2).replace(",", "."))
        return marked_val is not None and abs(marked_val - x) < 1e-6

    if "menor" in en_l and all(_f(v) is not None for v in alts.values()):
        vals = {k: _f(v) for k, v in alts.items()}
        return mark == min(vals, key=lambda k: vals[k])  # type: ignore[arg-type, return-value]

    m = re.search(r"m.ltiplo de\s+(\d+)", en_l)
    if m and "par" not in en_l:
        n = int(m.group(1))
        correct = [
            k
            for k, v in alts.items()
            if (val := _f(v)) is not None and abs(val - int(val)) < 1e-9 and int(val) % n == 0
        ]
        return mark in correct if correct else False

    m = re.search(r"m.ltiplo de\s+(\d+).*par|par.*m.ltiplo de\s+(\d+)", en_l)
    if m:
        n = int(m.group(1) or m.group(2))
        correct = [
            k
            for k, v in alts.items()
            if (val := _f(v)) is not None
            and abs(val - int(val)) < 1e-9
            and int(val) % n == 0
            and int(val) % 2 == 0
        ]
        return mark in correct if correct else False

    m = re.search(r"soma dos primeiros\s+(\d+)\s+n.meros.*m.ltiplos de\s+(\d+)", en_l)
    if m:
        k = int(m.group(1))
        n = int(m.group(2))
        s = n * k * (k + 1) / 2
        return marked_val is not None and abs(marked_val - s) < 1e-6

    if "afirma" in en_l and "fals" in en_l:

        def is_false_stmt(txt: object) -> bool | None:
            t = _norm(txt).replace(" ", "")
            if "x/y=y/x" in t:
                return True
            if "x^2+y^2=(x+y)^2" in t:
                return True
            if "x^2-y^2=y^2-x^2" in t:
                return True
            if "√x=√y" in t or "sqrtx=sqrty" in t:
                return True
            if "x+y=y+x" in t or "x*y=y*x" in t or "x×y=y×x" in t:
                return False
            if "x^2+y^2=y^2+x^2" in t or "x^2-y^2=(x-y)(x+y)" in t:
                return False
            return None

        falses = [k for k, v in alts.items() if is_false_stmt(v) is True]
        return mark in falses if falses else None

    if "não representa um número real" in en_l or "nao representa um numero real" in en_l:
        return False

    if (
        ("não pode" in en_l or "nao pode" in en_l or "pode não" in en_l or "pode nao" in en_l)
        and ("fra" in en_l or "a/b" in en_l)
    ):

        def is_rat(txt: object) -> bool | None:
            t = str(txt).strip().lower().replace(" ", "")
            if t in {"...", "…", ""}:
                return None
            if re.fullmatch(r"-?\d+/\d+", t) or re.fullmatch(r"-?\d+", t) or re.fullmatch(r"-?\d+[.,]\d+", t):
                return True
            m2 = re.fullmatch(r"(?:√|sqrt\()(\d+)\)?", t)
            if m2:
                n = int(m2.group(1))
                r = int(math.isqrt(n))
                return r * r == n
            if any(sym in t for sym in ["π", "pi", "√", "∛", "sqrt"]):
                m3 = re.fullmatch(r"√(\d+)", t)
                if m3:
                    n = int(m3.group(1))
                    r = int(math.isqrt(n))
                    return r * r == n
                return False
            return None

        labels = {k: is_rat(v) for k, v in alts.items()}
        cannot = [k for k, v in labels.items() if v is False]
        if len(cannot) == 1:
            return mark == cannot[0]
        if len(cannot) == 0:
            return False
        return mark in cannot

    m = re.search(r"equivalente a\s+(\d+)\s*/\s*(\d+)", en_l)
    if m:
        target = Fr(int(m.group(1)), int(m.group(2)))

        def as_fr(txt: object) -> Fr | None:
            t = str(txt).strip()
            if re.fullmatch(r"-?\d+/\d+", t):
                a, b = t.split("/")
                return Fr(int(a), int(b))
            return None

        matches = [k for k, v in alts.items() if (fr := as_fr(v)) is not None and fr == target]
        return mark in matches if matches else False

    m = re.search(r"converta a fra..o\s+(\d+)\s*/\s*(\d+).*porcent", en_l)
    if m:
        val = float(Fr(int(m.group(1)), int(m.group(2)))) * 100
        nums = [float(x.replace(",", ".")) for x in re.findall(NUM, str(alts[mark]))]
        return any(abs(c - val) < 1e-3 for c in nums)

    m = re.search(r"(\d+)\s+(?:casas|unidades).*?por\s+dia.*?(\d+)\s+dias", en_l)
    if m and marked_val is not None:
        return abs(marked_val - int(m.group(1)) * int(m.group(2))) < 1e-6

    finals = re.findall(r"x\s*=\s*(" + NUM + r")", resol, flags=re.I)
    if finals and marked_val is not None:
        if abs(float(finals[-1].replace(",", ".")) - marked_val) > 1e-6:
            return False
    return None


def auditar_celula_cenario_b(cell_dir: Path) -> tuple[int, int]:
    q_ok = q_tot = 0
    for path in sorted(cell_dir.glob("execucao_*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        preds = ((d.get("tasks") or {}).get("cenario_b") or {}).get("predictions") or []
        for pred in preds:
            if (pred.get("metrics") or {}).get("crash"):
                continue
            ext = extrair_e_validar(pred.get("raw_output") or "")
            if not ext.ok or not ext.parsed:
                continue
            qtd_ok, _ = validar_quantidade(ext.parsed, 3)
            if not qtd_ok:
                continue
            for q in ext.parsed.questoes:
                q_tot += 1
                if grade_conteudo(q) is True:
                    q_ok += 1
    return q_ok, q_tot


def auditar_resultados(resultados: Path) -> list[dict[str, Any]]:
    qp_path = resultados / "quadro_principal.json"
    qp = json.loads(qp_path.read_text(encoding="utf-8"))["quadro_principal"]
    dirs: dict[tuple[str, str], Path] = {}
    for resumo in resultados.rglob("resumo.json"):
        if "quadro" in str(resumo) or "desconhecido" in str(resumo):
            continue
        d = json.loads(resumo.read_text(encoding="utf-8"))
        dirs[(d["modelo"], d["perfil"])] = resumo.parent

    rows: list[dict[str, Any]] = []
    for row in qp:
        modelo, perfil = row.get("modelo"), row.get("perfil")
        if modelo == "desconhecido" or not perfil:
            continue
        cell_dir = dirs.get((modelo, perfil))
        q_ok, q_tot = auditar_celula_cenario_b(cell_dir) if cell_dir else (0, 0)
        if q_tot == 0:
            wilson = None
        else:
            wilson = wilson_ic95(q_ok, q_tot)
        rows.append(
            {
                "modelo": modelo,
                "perfil": perfil,
                "ok": q_ok,
                "total": q_tot,
                "wilson": wilson,
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Auditoria de corretude da chave no cenário B.",
    )
    parser.add_argument(
        "--resultados",
        type=Path,
        default=Path("resultados"),
        help="Pasta com quadro_principal.json e execucao_*.json",
    )
    args = parser.parse_args(argv)
    for row in auditar_resultados(args.resultados):
        w = row["wilson"]
        if w is None:
            gab = "---"
        else:
            gab = (
                f"{100 * w['ponto']:.1f}% "
                f"[{100 * w['ic95'][0]:.1f}--{100 * w['ic95'][1]:.1f}] "
                f"({row['ok']}/{row['total']})"
            )
        print(f"{row['modelo']} {row['perfil']}: {gab}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
