# benchmark-SLMs

Benchmark de Small Language Models (SLMs) para geração de questões de matemática alinhadas à BNCC.

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Uso

```bash
benchmark-slms
```

Menu interativo: catálogo, download (Hugging Face), benchmark, leaderboard e checagem de ambiente.

**Primeira vez:** 11 (ambiente) → 7 (login HF, se precisar) → 9 ou 10 (baixar + testar) → 5 (leaderboard).

Modelos em `modelos_local_gguf/` · resultados em `resultados/` · logs em `logs/`.

Relatórios e paper em `docs/`.

## Critério `apto_mathia`

RAM < 2 GB · TPS ≥ 5 · sem crash/OOM · offline · ≥ 60% JSON válido · tempo médio ≤ 90 s.
