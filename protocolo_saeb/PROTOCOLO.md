# Protocolo

Versão 1.0. Base metodológica: Monteiro et al., *Quality of Mathematical Question Generation with Lightweight LLMs:
Human-Automated Evaluation of Competency-Based Questions* (AIED 2026, CCIS 3032, pp. 92–106) — chamado aqui de
"artigo-base".

## 1. O que mudou em relação ao artigo-base (e por quê)

| Artigo-base | Este protocolo | Motivo |
|---|---|---|
| 1 avaliador humano | **≥ 3 professores, cada item avaliado por 2** | O artigo lista isso como sua principal limitação (sem confiabilidade entre avaliadores, o r = 0,31 não se interpreta). Aqui o κ entre professores vira o teto de referência para o G-Eval. |
| Só intenção de uso (Likert 1–5) | Intenção de uso **+ 4 critérios binários** (correção, resposta única, dados suficientes, aderência ano/habilidade) | O artigo mostra que o G-Eval erra justamente em correção e alinhamento de competência. Com critérios separados dá para dizer *onde* ele diverge. Intenção de uso continua o desfecho principal, para comparar com o artigo. |
| 160 itens, 20–60 por competência | **160 itens (40 por ano, 4 anos), todos avaliados por professores**; inferência por ano e por grupo de operação, célula só descritiva | Mesmo tamanho do artigo, escopo igual (operações) e dupla avaliação. O artigo pede ≥ 50 por código; com 20 não há poder por célula e isso é declarado. |
| Prompts empíricos escritos à mão | **Prompt de produção do app, sem alteração** (`modelo/cliente_llama_server.py`) | Mede o que o app entrega. Reprodutível por construção. |
| Critério G-Eval diferente do que o professor vê | **Mesmo texto de critério, mesma entrada** para G-Eval e professores | Elimina a explicação "avaliaram coisas diferentes". |
| Juiz em nuvem | Juiz **configurável**, versão registrada em cada linha | Ollama local, vLLM ou nuvem; o que importa é declarar e fixar. |

Mantido do artigo-base: binarização em nota ≥ 4, faixas de discretização do G-Eval (0–10 → 1–5), Pearson +
Spearman, κ de Cohen, matriz de confusão, sensibilidade/especificidade, análise por operação/habilidade.

## 2. Perguntas de pesquisa

- **P1** Que fração das questões geradas, por ano, atinge intenção de uso ≥ 4 segundo professores?
- **P2** Quão bem o G-Eval concorda com professores (r, ρ, κ, sensibilidade/especificidade), comparado ao κ entre os
  próprios professores?
- **P3** A qualidade varia entre anos e entre habilidades? (descritivo por célula)
- **P4** Em quais critérios o G-Eval mais diverge dos professores?

## 3. Unidade e geração

- **Célula** = par (ano, habilidade de operação), lista fixa em `config/celulas.json`, escolhida entre as habilidades de operações cobertas pelo modelo:

  | Ano | Habilidades | Operação |
  |---|---|---|
  | 1º | EF01MA06, EF01MA08 | adição; adição/subtração |
  | 2º | H06, H08 | adição/subtração (cálculo, problemas) |
  | 5º | H03, H05 / H04, H06 | adição/subtração (cálculo, problemas) / multiplicação/divisão (cálculo, problemas) |
  | 9º | H02, H06 | quatro operações com números reais (problemas, cálculo) |

  **40 questões por ano, 160 no total**: 1º, 2º e 9º ano com 2 células × 20, 5º ano com 4 células × 10, para que os quatro anos pesem igual. No 5º ano ficam as 10 primeiras de cada célula (índices 00–09 da rotação), sem escolha; as demais estão em `dados/geracoes/excedente_5ano.jsonl` e não entram na análise. 3º e 4º anos ficam fora do escopo; EF01MA02 (contagem) fica fora por não ser operação.
- Uma chamada = uma questão. Dificuldade rotaciona Fácil → Moderado → Difícil (7/7/6 por célula). Subtema, tipo de
  raciocínio e contexto vêm do sorteio do app, semeado por célula e índice.
- Inferência: `temperature` 0,7, `top_p` 0,8, `max_tokens` 512, gramática `modelo/questao.gbnf`, seed
  `seed_base + célula×1000 + índice` (nova seed por tentativa).
- **Ordem de execução.** As 120 questões de 1º, 5º e 9º ano foram geradas e avaliadas pelo G-Eval primeiro. O 2º ano (H06, H08; 40 questões) foi acrescentado depois, com as células no fim de `config/celulas.json` (seeds das anteriores intactas) e o mesmo gerador, prompt, juiz, passos e esforço. Os critérios e passos do G-Eval não foram alterados após ver as notas das primeiras 120. O G-Eval do 2º ano rodou já com contexto de 8192 tokens, sem nenhuma falha. A escolha do 2º ano veio depois dos resultados do 1º, 5º e 9º; declarar no artigo.
- **Sem seleção pós-geração.** Só se repete a chamada quando a *estrutura* falha (até 3 tentativas). O número de
  tentativas e as falhas ficam registrados; "% estruturalmente válidas" é resultado, não filtro oculto.
- Cada registro guarda prompt, seed, slot, tentativas e `modelo_info` (modelo, adaptador, hashes).

## 4. Critérios (`config/criterios.json`)

| Critério | Tipo | Desfecho |
|---|---|---|
| `intencao_uso` | Likert 1–5 (TAM, como no artigo) | **principal**; aprovação = nota ≥ 4 |
| `correcao_matematica` | binário | gabarito confere com a matemática |
| `resposta_unica` | binário | exatamente uma alternativa correta |
| `dados_suficientes` | binário | resolvível só com o texto |
| `aderencia_ano_habilidade` | binário | exige a habilidade e nível do ano |

Os três primeiros binários reproduzem o "núcleo de validade" já usado nas revisões deste repositório
(`avaliacao/amostra_humana_3bracos_*`), então os números são comparáveis com o histórico.

## 5. Avaliação automática (G-Eval)

- DeepEval `GEval`, um metric por critério, entrada = ano + habilidade + descrição; saída avaliada = enunciado,
  alternativas, resolução e gabarito (o que o professor vê).
- Escala nativa 0–1 → ×10 → faixas do artigo-base: [0,1]→1, (1,3]→2, (3,5]→3, (5,7]→4, (7,10]→5. Binário = nota ≥ 4.
- Os critérios viram **passos de avaliação fixos** (`passos_geval` em `config/criterios.json`, `evaluation_steps` do DeepEval) com tetos explícitos (erro matemático, gabarito errado ou resposta não única → nota ≤ 2).
  Motivo: na primeira versão (critério em texto livre), o gpt-oss:20b apontou o gabarito errado de uma questão-sonda
  mas ainda deu nota 4. Os passos foram ajustados só com **2 questões-sonda sintéticas** (`00_testar_juiz.py`), nunca
  com as 120 primeiras questões geradas, e ficam congelados antes de `make geval`. Com os passos, a sonda ruim recebeu 2 e a boa, 5.
- `reasoning_effort` do juiz = `low` (~22 s por chamada no hardware de referência, ~16 GB de RAM). Declarar no artigo como desvio do juiz
  padrão do artigo-base.
- Temperatura do juiz 0. **Juiz ≠ gerador.** Prefira juiz de família diferente de Qwen e dos modelos que
  produziram a base de treino , para não avaliar o modelo com seus próprios vieses.
- Desvio a declarar: com juiz via API genérica não há ponderação por log-probabilidade do G-Eval original.
- **Janela de contexto do juiz.** A rodada começou com o contexto padrão do Ollama (4096 tokens). Em um item (5º ano, H06, `5-H06-03`) o juiz raciocinou além desse limite, a resposta veio truncada e vazia e a execução abortou com 370 de 600 pares gravados. O contexto foi elevado para 8192 tokens (`OLLAMA_CONTEXT_LENGTH`) e a rodada foi retomada; os 230 pares restantes (incluindo esse item) usaram 8192. Os 370 primeiros foram gerados com 4096 e nenhum deles falhou, mas o contexto não é idêntico ao longo do arquivo: declarar no artigo.
- **Falhas do juiz.** Um par (questão, critério) em que o juiz não devolve JSON válido é registrado como `FALHA` no log e fica sem linha em `geval.jsonl`, para ser refeito ao reexecutar `make geval`. Nesta rodada não houve nenhum.
- Roda nas **160** questões estruturalmente válidas. Checagens determinísticas (`02_`) complementam, não
  substituem.

## 6. Avaliação humana

- Amostra = **todas as 160 questões estruturalmente válidas** (`amostra_por_celula: 20`); reduza em `config/protocolo.json` se faltar tempo dos professores. Seed fixa.
- Só questões estruturalmente válidas entram na amostra (as inválidas já são falha medida em §3).
- **Cego**: planilha sem nota do G-Eval, sem dificuldade pedida, sem subtema, em ordem aleatória, códigos anônimos.
- Cada item vai a 2 professores (rodízio balanceado). Com 3 professores: ~107 itens cada (160 × 2 ÷ 3), ~2 min por item.
- Professores: licenciatura em Matemática + experiência no ano. Registrar formação/experiência (sem nome) no artigo.
- Antes de começar, **calibração**: 10 itens fora da amostra, discutidos juntos. Depois, sem conversa.
- Referência humana por item: média das 2 notas Likert (aprovado se ≥ 4); binário = "s" apenas se ambos disseram "s".

## 7. Análise (`05_analisar.py`)

1. Geração: % estruturalmente válida e tentativas, por ano.
2. Aprovação (IC95 de Wilson) por ano, por grupo de operação, por célula (descritivo) e por critério, para G-Eval e para professores.
3. Professores: κ ponderado quadrático (Likert) e κ de Cohen (aprovação e cada binário) entre os dois avaliadores.
4. G-Eval × professores: Pearson, Spearman, acurácia, κ, sensibilidade, especificidade, matriz, por ano e por critério.
5. Interpretação de κ (Viera & Garrett 2005) e de r (Kotrlik & Williams 2003), como no artigo-base.

**Regra de leitura**: se κ entre professores for baixo, o G-Eval não pode ser julgado contra eles; reportar isso antes
de qualquer conclusão sobre o juiz.

## 8. Ameaças à validade (declarar no artigo)

- Um único modelo, um único treino (seed 44), um único juiz.
- Notas do juiz concentradas nos extremos: nos 600 pares, só 10 notas 3 e 1 nota 4; as outras 589 são 1, 2 ou 5. A escala de 5 pontos se comporta quase como binária, o que limita Pearson, Spearman e κ ponderado contra a escala Likert dos professores.
- Em `intencao_uso`, o juiz foi mais leniente que nos critérios objetivos (ex.: `1-EF01MA06-00` recebeu nota 5 mesmo com a divisão fora da habilidade, que o critério de aderência penalizou com 2). Isso reforça comparar cada critério com os professores separadamente.
- Gerador e juiz podem compartilhar vieses de dados sintéticos.
- 10 a 20 por célula: sem poder estatístico por célula; a inferência é por ano (n = 40).
- Professores avaliam texto; não há teste com alunos nem com figuras (itens são autocontidos).
- A rubrica é própria deste protocolo, não validada psicometricamente além do TAM da escala principal.

## 9. Congelar antes de rodar (reprodutibilidade)

Commit de `config/` e `modelo/` (ver `modelo/ORIGEM.md`), hashes do GGUF base, do adaptador e da base de treino (model card), versão do llama.cpp, do
`deepeval`, nome e versão do juiz. Depois de gerar, não editar `dados/geracoes/`.
