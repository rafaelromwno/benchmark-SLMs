# benchmark-SLMs-INCT

Protocolo experimental de benchmark de Small Language Models (SLMs) para geração de questões de matemática alinhadas à BNCC.

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install pydantic psutil huggingface_hub llama-cpp-python
# ou: pip install -e .
```

## Uso — menu interativo (único fluxo)

```bash
benchmark-slms
# ou:
python -m benchmark_slms.cli
```

```
  1  Listar catálogo de modelos
  2  Baixar modelo GGUF (Hugging Face)
  3  Testar modelo [selection]
  4  Testar modelo [benchmark]
  5  Ver leaderboard
  6  Listar tasks (cenários A–D)
  7  Login Hugging Face
  8  Remover token HF inválido
  9  Fluxo completo: baixar + testar   ← recomendado na 1ª vez
  10 Verificar ambiente
  11 Limpar arquivos temporários
  12 Explicar estrutura dos resultados
  0  Sair
```

### Primeira execução (passo a passo)

1. **Opção 10** — verifica dependências e status do Hugging Face
2. **Opção 7** — login (`hf auth login`) se necessário
3. **Opção 9** — escolhe um id do catálogo, baixa e roda o benchmark
4. **Opção 5** — vê o leaderboard

### Erros comuns (tratados no menu)

| Situação | O que fazer no menu |
|----------|---------------------|
| Token HF inválido/expirado | Opção **8** (remover) → **7** (login) → **2** ou **9** |
| Modelo gated no HF | Aceitar termos em huggingface.co → **7** → **2** |
| Modelo não baixado | Opção **2** ou **9** (fluxo completo) |
| Repo/arquivo não encontrado | Opção **1** — escolher outro id do catálogo |

Modelos ficam em `modelos_local_gguf/` (gitignored).

## Fases do pipeline

1. **Dados** — loader, pré-processamento, ground truth (M8)
2. **Execução** — calling N×M, executor, medição
3. **Avaliação** — JSON válido + viabilidade (RAM/TPS/crash)
4. **Report** — veredito `apto_mathia`, leaderboard

Logging JSONL em `logs/`. Resultados em `resultados/`.

## Perfis de inferência

Nas opções de benchmark, selecione um ou mais modelos e perfis nomeados.
Cada perfil fixa `temperature`, `top_p` e `repeat_penalty`; `max_tokens`
permanece como parâmetro do protocolo. A execução percorre cada perfil para
todos os modelos selecionados, preservando o prompt. Os resultados ficam em
`resultados/<modelo>/<perfil>/execucao_N.json`; execuções legadas, sem perfil,
continuam em `resultados/<modelo>/execucao_N.json`.

## Critérios apto_mathia

RAM < 2 GB · TPS ≥ 5 · crash/OOM = 0 · offline · JSON válido conforme task.

Veredito derivado automaticamente.
