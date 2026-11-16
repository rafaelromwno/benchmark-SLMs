# benchmark-SLMs

Benchmark de Small Language Models (SLMs) para geração de questões de matemática alinhadas à BNCC.

## Estrutura do repositório

| Caminho | O que é |
|---|---|
| `benchmark_slms/` | pacote do benchmark (CLI, runner, avaliação, relatórios) |
| `tests/` | testes do pacote (`pytest`) |
| `resultados/` | resultados por modelo e `quadro_principal` |
| `logs/` | logs de execução (não versionados) |
| `protocolo_saeb/` | projeto independente: geração de questões SAEB/BNCC com um modelo ajustado e avaliação com G-Eval + professores. Tem README, ambiente e testes próprios |

O pacote `benchmark_slms` e o `protocolo_saeb` não dependem um do outro: cada um tem seus testes (`pytest` na raiz roda só `tests/`; o protocolo usa `make test` dentro de `protocolo_saeb/`).

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

Relatórios e paper em `docs/` (pasta local, ignorada pelo git).

## Critério `apto_mathia`

RAM < 2 GB · TPS ≥ 5 · sem crash/OOM · offline · ≥ 60% JSON válido · tempo médio ≤ 90 s.
