# Protocolo de avaliação de questões geradas (SAEB, 1º/5º/9º ano)

Gera **20 questões por célula (ano × habilidade de operação; 8 células = 160 questões)** com o modelo do repositório `qwen3-4b-questoes-matematica`, avalia com **G-Eval (DeepEval)**
e prepara a **revisão por professores**. Desenho e justificativas: [PROTOCOLO.md](PROTOCOLO.md).

```
config/celulas.json      as 8 células (ano, habilidade, operação)
config/protocolo.json    parâmetros fixos (seeds, N por célula, limiar, tamanho da amostra humana)
config/criterios.json    os 5 critérios, com a mesma redação para G-Eval e professores
scripts/01_gerar.py          questões → dados/geracoes/questoes.jsonl
scripts/02_checar_estrutura.py   checagens determinísticas (sem LLM)
scripts/03_geval.py          G-Eval, um metric por critério → dados/avaliacao_auto/geval.jsonl
scripts/04_amostra_humana.py amostra cega + planilhas dos professores → dados/humana/
scripts/05_analisar.py       estatísticas → resultados/resumo.{json,md}
modelo/                  cópia fixa de prompt, gramática e taxonomia do app (ver ORIGEM.md)
```

## Infraestrutura

Pré-requisitos (nada é instalado nem baixado automaticamente, exceto `make setup` e `make baixar-qwen`):

| Item | Para quê | Como |
|---|---|---|
| Python 3.10–3.13 | `deepeval` (3.12 recomendado) | `make setup` cria `.venv` e `requirements.lock` |
| `llama-server` | gerar com Qwen3-4B + LoRA | compilar ou instalar o [llama.cpp](https://github.com/ggml-org/llama.cpp) |
| `Qwen3-4B-Q4_K_M.gguf` (~2,5 GB) | modelo base | `make baixar-qwen` |
| LoRA `lora_4b_v7b_s44.f16.gguf` | adaptador | copiar do repositório do modelo (`gguf/`) para `modelos/` (`LORA`) |
| Ollama + `gpt-oss:20b` (~13 GB) | juiz do G-Eval | instalar o [Ollama](https://ollama.com), depois `ollama pull gpt-oss:20b` |

Com ~16 GB de RAM, gerador e juiz rodam em **momentos separados**.

## Ordem de execução

```bash
cd protocolo_saeb
make setup test verificar          # prepara e confere; não gera nada

# fase 1 — geração (terminal 1: make servidor-gerador)
make gerar estrutura               # encerre o servidor com Ctrl+C

# fase 2 — juiz
make juiz-iniciar                  # terminal 1
make juiz-testar                   # confirma que o juiz distingue questão boa de ruim
make geval

# fase 3 — professores
make amostra PROFESSORES="P1 P2 P3"   # entregar só dados/humana/folha_*.csv
make analisar                          # depois que as folhas voltarem preenchidas
```

Todos os passos retomam de onde pararam. `dados/humana/chave.csv` liga o código da planilha ao item e **não vai
para os professores**. `00_verificar_ambiente.py` e `00_testar_juiz.py` não geram nem avaliam as 160 questões.
