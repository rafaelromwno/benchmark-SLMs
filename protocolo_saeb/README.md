# Protocolo de avaliação de questões geradas (SAEB, 1º/2º/5º/9º ano)

Gera **40 questões por ano (1º, 2º, 5º e 9º; 10 células de ano × habilidade de operação = 160 questões)** com o modelo do repositório `qwen3-4b-questoes-matematica`, avalia com **G-Eval (DeepEval)**
e prepara a **revisão por professores**. Desenho e justificativas: [PROTOCOLO.md](PROTOCOLO.md).

```
config/celulas.json      as 10 células (ano, habilidade, operação)
config/protocolo.json    parâmetros fixos (seeds, N por célula, limiar, tamanho da amostra humana)
config/criterios.json    os 6 critérios (núcleo + aderência + intenção de uso), com a mesma redação para G-Eval e professores
scripts/01_gerar.py          questões (5 alternativas, como geradas) → dados/geracoes/questoes.jsonl
scripts/02_checar_estrutura.py   checagens determinísticas (sem LLM)
scripts/02b_verificar_aritmetica.py  confere as contas da resolução e o gabarito, com cobertura → dados/avaliacao_auto/aritmetica.jsonl
scripts/02c_contaminacao.py  similaridade com o treino e entre as questões → dados/avaliacao_auto/contaminacao*.json*
scripts/09_derivar_4_alternativas.py  versão A–D balanceada, sem descartar questões → dados/geracoes/questoes_saeb4.jsonl
scripts/03_geval.py          G-Eval, um metric por critério → dados/avaliacao_auto/geval.jsonl
scripts/04_amostra_humana.py amostra cega + planilhas dos professores → dados/humana/
scripts/05_analisar.py       estatísticas → resultados/resumo.{json,md}
scripts/06_composicao.py     proporção por ano/habilidade → dados/geracoes/COMPOSICAO.md
scripts/07_congelar.py       hashes e versões; sela o resultado do juiz → config/CONGELADO.json
scripts/08_taxonomia.py      causas de reprovação (juiz e professores) → dados/taxonomia/
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
make aritmetica derivar            # verificação aritmética e versão de 4 alternativas (A-D) balanceada
make contaminacao TREINO=arquivo.jsonl   # similaridade com o treino (opcional)

# fase 2 — juiz
make juiz-iniciar                  # terminal 1
make juiz-testar                   # confirma que o juiz distingue as sondas boa, gabarito errado e conta errada
make geval
make congelar                      # sela o resultado do juiz antes da coleta humana

# fase 3 — professores
make amostra PROFESSORES="P1 P2 P3"   # todos avaliam todos os itens; entregar só dados/humana/folha_*.csv
make analisar taxonomia                # depois que as folhas voltarem preenchidas
```

Todos os passos retomam de onde pararam. `dados/humana/chave.csv` liga o código da planilha ao item e **não vai
para os professores**. `00_verificar_ambiente.py` e `00_testar_juiz.py` não geram nem avaliam as 160 questões.
