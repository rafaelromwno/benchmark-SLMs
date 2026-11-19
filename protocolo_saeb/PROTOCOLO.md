# Protocolo

Versão 2.0. Base metodológica: Monteiro et al., *Quality of Mathematical Question Generation with Lightweight LLMs:
Human-Automated Evaluation of Competency-Based Questions* (AIED 2026, CCIS 3032, pp. 92–106) — chamado aqui de
"artigo-base".

## 1. O que mudou em relação ao artigo-base (e por quê)

| Artigo-base | Este protocolo | Motivo |
|---|---|---|
| 1 avaliador humano | **≥ 3 professores, todos avaliando todos os itens**, com itens-âncora repetidos | O artigo lista isso como sua principal limitação. Com todos avaliando tudo, o teto humano (Fleiss κ, α de Krippendorff, AC1) é estimado em todos os itens, e a referência é a maioria (2 de 3). |
| Só intenção de uso (Likert 1–5) | Intenção de uso **+ 5 critérios binários**, quatro deles formando o **núcleo** (resolução correta, gabarito coerente, resposta única, dados suficientes) | O artigo mostra que o G-Eval erra justamente em correção e alinhamento de competência. Com critérios separados dá para dizer *onde* ele diverge. Intenção de uso continua o desfecho principal, para comparar com o artigo. |
| 160 itens, 20–60 por competência | **160 itens (40 por ano, 4 anos), todos avaliados por professores**; inferência por ano e por grupo de operação, célula só descritiva | Mesmo tamanho do artigo e escopo igual (operações). O artigo pede ≥ 50 por código; com 10 a 20 não há poder por célula e isso é declarado. |
| Prompts empíricos escritos à mão | **Prompt de produção do app, sem alteração** (`modelo/cliente_llama_server.py`) | Mede o que o app entrega. Reprodutível por construção. |
| Critério G-Eval diferente do que o professor vê | **Mesmo texto de critério, mesma entrada** para G-Eval e professores | Elimina a explicação "avaliaram coisas diferentes". |
| Sem referência objetiva | **Verificação aritmética determinística** com cobertura reportada | Terceira opinião que não é humana nem LLM. |
| Juiz em nuvem | Juiz **configurável**, versão registrada em cada linha | Ollama local, vLLM ou nuvem; o que importa é declarar e fixar. |

Mantido do artigo-base: binarização em nota ≥ 4, faixas de discretização do G-Eval (0–10 → 1–5), análise por
operação/habilidade. Pearson, Spearman e κ de Cohen continuam sendo reportados, mas como **secundários**
(ver §7).

## 2. Perguntas de pesquisa

- **P1** Que fração das questões geradas, por ano, atinge o núcleo e intenção de uso ≥ 4 segundo professores?
- **P2** Quão bem o G-Eval concorda com professores (AC1, κ, sensibilidade/especificidade), comparado à concordância
  entre os próprios professores?
- **P3** A qualidade varia entre anos e entre habilidades? (descritivo por célula)
- **P4** Em quais critérios o G-Eval mais diverge dos professores?
- **P5** Usado como filtro de pré-revisão, que ganho de precisão o juiz dá sobre a taxa-base e a que custo de itens
  válidos descartados? (triagem, §7)

## 3. Unidade e geração

- **Célula** = par (ano, habilidade de operação), lista fixa em `config/celulas.json`, escolhida entre as habilidades de operações cobertas pelo modelo:

  | Ano | Habilidades | Matriz Saeb | Operação |
  |---|---|---|---|
  | 1º | EF01MA06, EF01MA08 | — (BNCC apenas) | adição; adição/subtração |
  | 2º | H06, H08 | 2N1.7, 2N2.1 | adição/subtração (cálculo, problemas) |
  | 5º | H03, H05 / H04, H06 | 5N1.5, 5N2.1 / 5N1.6, 5N2.2 | adição/subtração (cálculo, problemas) / multiplicação/divisão (cálculo, problemas) |
  | 9º | H02, H06 | 9N2.1, 9N1.5 | quatro operações com números reais (problemas, cálculo) |

  **40 questões por ano, 160 no total**: 1º, 2º e 9º ano com 2 células × 20, 5º ano com 4 células × 10, para que os quatro anos pesem igual. No 5º ano ficam as 10 primeiras de cada célula (índices 00–09 da rotação), sem escolha; as demais estão em `dados/geracoes/excedente_5ano.jsonl` e não entram na análise (10 delas servem de calibração dos professores). 3º e 4º anos ficam fora do escopo; EF01MA02 (contagem) fica fora por não ser operação.
- **Códigos.** Os H** são as habilidades da Matriz Saeb–BNCC numeradas em sequência dentro de cada ano. O campo `codigo_matriz_saeb` está em `config/celulas.json` e em cada registro de `questoes.jsonl`; a tabela com a verificação é `config/equivalencia_habilidades.csv`. Os oito códigos foram **conferidos contra a Matriz de Referência de Matemática do Saeb (Inep, 2022)**: código e texto coincidem. O **Saeb não avalia o 1º ano**: esse bloco é alinhado só à BNCC e, no texto do artigo, deve ser descrito como "questões alinhadas à BNCC e, nas etapas de 2º, 5º e 9º anos, às habilidades da Matriz de Referência de Matemática do Saeb", nunca como "itens do Saeb".
- Uma chamada = uma questão. Dificuldade rotaciona Fácil → Moderado → Difícil (7/7/6 por célula). Subtema, tipo de
  raciocínio e contexto vêm do sorteio do app, semeado por célula e índice.
- Inferência: `temperature` 0,7, `top_p` 0,8, `max_tokens` 512, gramática `modelo/questao.gbnf`, seed
  `seed_base + célula×1000 + índice` (nova seed por tentativa).
- **Ordem de execução.** As 120 questões de 1º, 5º e 9º ano foram geradas e avaliadas pelo G-Eval primeiro. O 2º ano (H06, H08; 40 questões) foi acrescentado depois, com as células no fim de `config/celulas.json` (seeds das anteriores intactas) e o mesmo gerador, prompt, juiz, passos e esforço. Os critérios e passos do G-Eval não foram alterados após ver as notas das primeiras 120. A escolha do 2º ano veio depois dos resultados do 1º, 5º e 9º; declarar no artigo.
- **Sem seleção pós-geração.** Só se repete a chamada quando a *estrutura* falha (até 3 tentativas). O número de
  tentativas e as falhas ficam registrados; "% estruturalmente válidas" é resultado, não filtro oculto.
- Cada registro guarda prompt, seed, slot, tentativas e `modelo_info` (modelo, adaptador, hashes).

### Versão de 4 alternativas (A–D)

O gerador produz **5 alternativas** (o prompt de sistema do treino já as pede) e o Saeb usa 4. A versão avaliada
(`saeb4`) é derivada das questões geradas por uma transformação **determinística e auditável**
(`09_derivar_4_alternativas.py`, relatório em `dados/geracoes/DERIVACAO_4_ALTERNATIVAS.md`), que **não descarta nenhuma
questão** e não é uma seleção: aplica-se às 160.

1. Remove uma alternativa que não seja a chave nem uma que contenha o resultado da resolução (assim a correção da
   questão não muda). Preferência: cópia de outra alternativa, "Nenhuma das alternativas", a letra E e, se E for a
   chave ou o resultado, o distrator numericamente mais distante da chave.
2. Reordena as alternativas para **balancear a letra do gabarito por ano** (10 em cada letra A–D por ano, 40 no total).
   Alternativas numéricas em ordem monotônica mantêm a ordem; "Nenhuma das alternativas" que reste fica por último.
3. Reescreve referências a letras na resolução, se houver (nas 160 não há nenhuma).

Salvaguardas verificadas e testadas: o texto da chave não muda; só se removem textos; a verificação aritmética dá o
mesmo veredito antes e depois em todas as 160. `questoes.jsonl` (geração original) não é alterado; as questões que
juiz e professores veem são as de `questoes_saeb4.jsonl`.

**Diagnóstico do desvio entre taxas.** Antes da derivação, 18,3% das 120 primeiras questões (15,0% das 160) tinham
"Nenhuma das alternativas" na alternativa E e 36,9% o gabarito em A. Isso é **herança do corpus de treino, não uma
falha deste protocolo**: no corpus de treino, 23,7% das questões têm "nenhuma d…" (1º ano 60,3%, 2º 20,6%, 5º 9,0%, 9º 17,4%) e
o gabarito é equilibrado (~20% por letra). O model card reporta 2,2% de "nenhuma" nas saídas **no modo de produção**
(gramática + gerar → checar → corrigir/regenerar) e, ao que indicam os arquivos de avaliação, sobre um conjunto de validação congelado de 30 itens de 2º, 5º e 9º anos; este
protocolo avalia a geração bruta, inclui o 1º ano (o de maior taxa) e não aplica pós-processamento. A letra A em
excesso é o "viés de letra do gabarito" que o próprio model card lista como limitação (40,0% no 4B).

## 4. Critérios (`config/criterios.json`)

Todos avaliam o item como o professor o vê. A ordem abaixo é a da folha do professor (Q1 a Q7).

| Q | Critério | Tipo | Núcleo | Desfecho |
|---|---|---|---|---|
| Q1 | `resolucao_correta` | binário | sim | a matemática da resolução está correta |
| Q2 | `gabarito_coerente` | binário | sim | a letra do gabarito é a da alternativa com o resultado da resolução |
| Q3 | `resposta_unica` | binário | sim | exatamente uma alternativa correta |
| Q4 | `dados_suficientes` | binário | sim | resolvível só com o texto |
| Q5 | `aderencia_ano_habilidade` | binário | não | exige a habilidade e nível do ano |
| Q6 | `intencao_uso` | Likert 1–5 (TAM, como no artigo) | não | **principal**; aprovação = nota ≥ 4 |
| Q7 | motivo (texto livre) | — | — | só nas reprovações; alimenta a taxonomia de falhas |

**Núcleo aprovado** = os quatro critérios do núcleo aprovados. Os dois primeiros vieram do desdobramento de
`correcao_matematica` (que perguntava "a matemática está correta **e** o gabarito confere?"), porque o model card
separa os dois modos de falha e eles pedem correções diferentes: gabarito incoerente é corrigível por
pós-processamento determinístico, erro de conta não é. As notas coletadas de `correcao_matematica` ficam em
`geval.jsonl` como **resultado legado** (a análise o reporta à parte).

**Aderência** é medida com ano e habilidade à vista e fica sujeita à ancoragem: declarar como limitação.

## 5. Avaliação automática (G-Eval)

- DeepEval `GEval`, um metric por critério, entrada = ano + habilidade + descrição; saída avaliada = enunciado,
  alternativas, resolução e gabarito (o que o professor vê).
- Escala nativa 0–1 → ×10 → faixas do artigo-base: [0,1]→1, (1,3]→2, (3,5]→3, (5,7]→4, (7,10]→5. Binário = nota ≥ 4.
- Os critérios viram **passos de avaliação fixos** (`passos_geval` em `config/criterios.json`, `evaluation_steps` do DeepEval) com tetos explícitos de nota nos critérios binários (erro matemático, gabarito errado ou resposta não única → nota ≤ 2); `intencao_uso` não tem tetos nos passos.
  Motivo: na primeira versão (critério em texto livre), o gpt-oss:20b apontou o gabarito errado de uma questão-sonda
  mas ainda deu nota 4. Os passos foram ajustados só com **questões-sonda sintéticas** (`00_testar_juiz.py`), nunca
  com as questões geradas, e ficam congelados antes de `make geval`. As quatro sondas são: boa (alta em resolução e
  gabarito), gabarito errado (baixa em `gabarito_coerente`) e conta errada (baixa em `resolucao_correta`).
- **Teto de `intencao_uso` aplicado em código.** Se qualquer critério do núcleo for reprovado, `intencao_uso` fica em
  no máximo 2 (`comum.intencao_com_teto`); a nota bruta do juiz é guardada. Os passos de `intencao_uso` **não trazem tetos
  duros**: erro, gabarito incoerente e resposta não única "pesam muito" e a escala de 0 a 10 é descrita por faixas.
  Resultado: mesmo sem tetos, as notas continuaram em 1, 2 e 5 (10, 32, 1, 1 e 116 nos 160 itens). A escala estreita é
  comportamento do juiz (`gpt-oss:20b`, esforço `low`), não efeito dos tetos; declarar no artigo e usar a binarização
  (nota ≥ 4) como análise principal, com Spearman apenas descritivo.
- `reasoning_effort` do juiz = `low` (~22 s por chamada no hardware de referência, ~16 GB de RAM). Declarar no artigo como desvio do juiz
  padrão do artigo-base.
- Temperatura do juiz 0. **Juiz ≠ gerador.** Prefira juiz de família diferente de Qwen e dos modelos que
  produziram a base de treino , para não avaliar o modelo com seus próprios vieses.
- Desvio a declarar: com juiz via API genérica não há ponderação por log-probabilidade do G-Eval original.
- **Versões e reaproveitamento de notas.** A primeira rodada do G-Eval (800 pares, 160 questões × 5 critérios, depois
  substituídos por 6) foi feita sobre a versão de 5 alternativas. Como `dados_suficientes` e `aderencia_ano_habilidade`
  não dependem das alternativas, as notas dessa rodada são **reaproveitadas** na versão avaliada (`comum.notas_do_juiz`).
  Os demais critérios (`resolucao_correta`, `gabarito_coerente`, `resposta_unica`, `intencao_uso`) foram recalculados
  sobre a versão de 4 alternativas (640 chamadas), cada linha marcada com `"versao": "saeb4"`; depois, `gabarito_coerente`, `resposta_unica` e `intencao_uso` foram recalculados mais uma vez (480 chamadas) porque seus passos mudaram ("A a E" virou "A a D"; tetos internos de `intencao_uso` removidos), e só a última rodada está em `geval.jsonl`; as notas antigas desses
  critérios e `correcao_matematica` ficam no arquivo como legado e **não entram** na análise.
- **Janela de contexto do juiz.** A primeira rodada começou com o contexto padrão do Ollama (4096 tokens). Em um item (5º ano, H06, `5-H06-03`) o juiz raciocinou além desse limite, a resposta veio truncada e vazia e a execução abortou com 370 de 600 pares gravados. O contexto foi elevado para 8192 tokens (`OLLAMA_CONTEXT_LENGTH`) e a rodada foi retomada. As notas reaproveitadas, portanto, vieram de contextos de 4096 (370 pares) e 8192; as recalculadas usam 8192. Declarar no artigo.
- **Falhas do juiz.** Um par (questão, critério) em que o juiz não devolve JSON válido é registrado como `FALHA` no log e fica sem linha em `geval.jsonl`, para ser refeito ao reexecutar `make geval`.
- Roda nas **160** questões estruturalmente válidas.

### Checagens determinísticas (sem LLM)

- `02_checar_estrutura.py`: portão de estrutura (conta como falha de geração) e sinalizadores de estilo.
- `02b_verificar_aritmetica.py`: confere cada equação escrita na resolução e se o resultado final está entre as
  alternativas e bate com a letra do gabarito. **Não interpreta o enunciado**: uma resolução que calcula
  corretamente a conta errada passa. Por isso a **cobertura** é parte do resultado (nas 160: 81,2% verificáveis;
  17,7% de erro entre os verificáveis, 23 de 130). Veredito: `ok`, `erro` ou `nao_verificavel`.
- `02c_contaminacao.py`: similaridade (Jaccard de trigramas de palavras, exata e "de molde", com os números trocados por `#`) de cada enunciado com os de
  um arquivo de treino e com os demais gerados. **Limiar fixado antes de olhar os resultados**: 0,8
  (`config/protocolo.json`). Contra o treino curado (2.978 enunciados), a maior similaridade foi 0,28 (exata) e 0,41
  (molde); nenhuma questão passou do limiar, nem entre si. Reportar a distribuição, não só a contagem. Não foi possível
  comparar com os 299 itens da avaliação preliminar por falta do arquivo.

## 6. Avaliação humana

- Amostra = **todas as 160 questões** estruturalmente válidas (`amostra_por_celula: 20`), na versão de 4 alternativas. Seed fixa.
- **Cego**: planilha sem nota do G-Eval, sem dificuldade pedida, sem subtema, sem modelo, códigos anônimos e **diferentes por professor**.
- **Todos os professores avaliam todos os itens** (≥ 3), cada um em ordem aleatória própria, em blocos de 40. Em cada
  bloco, 2 itens são repetidos mais adiante, com outro código, como **âncoras** (medem a consistência do professor
  consigo mesmo): 160 itens + 8 âncoras = 168 linhas por professor, ~2 min por item. A ligação (professor, código) → item
  fica só em `dados/humana/chave.csv`, que **não vai para os professores**.
- **Folha** (Q1 a Q7, §4): ano e habilidade à vista; nunca a nota do juiz. Q1 a Q4 formam o núcleo; Q5, aderência;
  Q6, intenção de uso (1–5); Q7, motivo em texto livre, só nas reprovações.
- Professores: licenciatura em Matemática + experiência no ano. Registrar formação/experiência (sem nome) no artigo.
- Antes de começar, **calibração**: 10 itens fora da amostra (`dados/humana/calibracao.csv`, do excedente do 5º ano,
  também em 4 alternativas), discutidos juntos. Depois, sem conversa. O autor do modelo não avalia.
- Referência humana por item: **maioria (2 de 3)**, estrita (empate conta como não); unanimidade e "pelo menos um" como
  sensibilidade. Núcleo aprovado = maioria dos professores com os quatro itens do núcleo "sim".

## 7. Análise (`05_analisar.py`, `08_taxonomia.py`)

Ordem de leitura:

1. Geração: % estruturalmente válida e tentativas, por ano. Distribuição das notas do juiz (reportada como resultado).
2. Aprovação (IC95 de Wilson) por ano, por grupo de operação, por célula (descritivo) e por critério, para G-Eval e
   para professores; núcleo aprovado por ano.
3. **Teto humano**: κ de Fleiss, α de Krippendorff e AC1 entre os professores, por critério, para o núcleo e para a
   intenção de uso (α de intervalo no Likert); κ de Cohen e AC1 por par de professores; consistência de cada professor
   pelas âncoras.
4. **Juiz × humanos**: **AC1 de Gwet** como medida primária (com p0, κ e índices de prevalência e de viés ao lado),
   por critério e para o núcleo, e a **diferença** entre o AC1 do juiz contra um professor e o AC1 entre professores,
   com IC95 por bootstrap pareado por itens (2.000 reamostragens, seed fixa) e correção de Holm entre as dimensões.
5. Spearman entre a média Likert dos professores e a nota do juiz, **descritivo** (restrição de amplitude).
6. **Triagem (RQ3)**: o juiz, a verificação aritmética e a combinação dos dois como classificadores contra o núcleo
   aprovado pela maioria: taxa-base, sensibilidade, especificidade, VPP, VPN, taxa de descarte de itens válidos e
   fração descartada, com IC95 por bootstrap.
7. **Taxonomia de falhas** (`make taxonomia`): cada reprovação em uma de cinco causas (conta ou conceito errado;
   gabarito incoerente; mais de uma alternativa correta; enunciado mal posto ou sem dados; inadequação ao ano ou à
   habilidade), por critério para o juiz e para os professores, mais o motivo livre (Q7) e uma planilha de dupla
   codificação em 30% das reprovações (`dados/taxonomia/codificacao.csv`).

**Por quê**: as notas do juiz ficam quase só nos extremos (a escala de 5 pontos se comporta como quase binária), então
Pearson e Spearman ficam atenuados, o κ ponderado quadrático não se aplica quando um lado ocupa dois níveis, e com
aprovação em torno de 70% dos dois lados o κ de Cohen é deflacionado pelo paradoxo da prevalência. O AC1 não sofre
disso.

**Regra de leitura**: se a concordância entre professores for baixa, ela é o teto e o G-Eval não pode ser julgado contra
eles; reportar isso antes de qualquer conclusão sobre o juiz.

**O que não fazer**: κ de Cohen como único coeficiente, correlação como evidência de concordância, teste de hipótese
por célula, α de Cronbach entre critérios desenhados para serem distintos.

## 8. Ameaças à validade (declarar no artigo)

- Um único modelo, um único treino (seed 44), um único juiz.
- Notas do juiz concentradas nos extremos: na primeira rodada (600 pares), só 10 notas 3 e 1 nota 4; as outras 589 eram 1, 2 ou 5. Limita Pearson, Spearman e κ ponderado; por isso o AC1 é a medida primária.
- `intencao_uso`: o juiz foi mais leniente que nos critérios objetivos (ex.: `1-EF01MA06-00` recebeu nota 5 mesmo com a divisão fora da habilidade, que o critério de aderência penalizou com 2). Reforça comparar cada critério com os professores separadamente.
- As notas de `dados_suficientes` e `aderencia_ano_habilidade` foram reaproveitadas da versão de 5 alternativas (§5), e as notas reaproveitadas vieram de dois tamanhos de contexto.
- A versão de 4 alternativas é uma transformação do que o modelo gerou: a letra do gabarito foi balanceada por código, não é a distribuição natural do modelo (que tem viés para a letra A, como o model card declara).
- **Contaminação**: a checagem de similaridade mostra nenhuma cópia acima do limiar contra o treino curado, mas não cobre os 299 itens da avaliação preliminar. Sem comparar com todos os arquivos de treino, evitar a palavra "inéditas".
- Gerador e juiz podem compartilhar vieses de dados sintéticos (o corpus de treino foi majoritariamente escrito e filtrado por LLMs).
- O 1º ano não é etapa do Saeb (alinhado só à BNCC), e a correspondência código do gerador ↔ Matriz Saeb ainda precisa ser conferida contra o texto oficial.
- A aderência é medida com o rótulo à vista (Q5): sujeita à ancoragem. Não tirar conclusão forte sobre aderência.
- Qualidade pedagógica só pela intenção de uso (Q6); o núcleo mede correção.
- 10 a 20 por célula: sem poder estatístico por célula; a inferência é por ano (n = 40). A estimativa de RQ2 e RQ3 é com IC95, não teste de hipótese.
- Professores avaliam texto; não há teste com alunos nem com figuras (itens são autocontidos). A rubrica é própria deste protocolo, não validada psicometricamente além do TAM da escala principal.
- A verificação aritmética só cobre 81,2% dos itens e não interpreta o enunciado.

## 9. Congelar antes de rodar (reprodutibilidade)

`make congelar` grava `config/CONGELADO.json` com: sha256 de `config/`, `modelo/`, das questões geradas e do
`geval.jsonl` (o **selo do juiz**: prova que o juiz foi fechado antes de qualquer professor ver uma folha); versões
do Python, do `deepeval` e do llama.cpp; commit do git e se a árvore estava limpa; modelo e digest do juiz
(`ollama show`); e, se informados, os hashes do GGUF base e do adaptador. A tag (por exemplo `protocolo-v2.0`) é
criada por quem publica, depois de conferir o arquivo. Depois de gerar, não editar `dados/geracoes/`; depois do selo e
do início da coleta, não mudar critérios, passos nem o modelo do juiz.
