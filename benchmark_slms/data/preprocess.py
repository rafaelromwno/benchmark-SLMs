"""Pré-processamento: Sample -> Prompt (migrado de prompts.py + cenários)."""

from __future__ import annotations

from benchmark_slms.core.contracts import Prompt, PromptMessage, Sample

_BASE = """Você é um especialista sênior em elaboração de itens avaliativos de Matemática para o Ensino Fundamental (1º ao 9º ano), com domínio profundo da Base Nacional Comum Curricular (BNCC).

Suas responsabilidades:
- Criar questões de múltipla escolha (5 alternativas: A, B, C, D, E) rigorosamente alinhadas à habilidade da BNCC solicitada.
- Garantir que o enunciado seja claro, contextualizado e adequado à faixa etária do estudante.
- Produzir alternativas plausíveis e com distratores pedagogicamente fundamentados (erros comuns dos alunos, não respostas absurdas).
- Redigir a resolução passo a passo de forma didática, como faria um professor explicando para o aluno.
- Calibrar a dificuldade respeitando os pré-requisitos informados: os conceitos listados em pré-requisitos devem ser dominados pelo aluno, e NÃO devem ser o foco central da questão — use-os como base para atingir a habilidade-alvo.
- Manter consistência de estilo, formato e nível de abstração com os exemplos fornecidos (few-shot).

Regras absolutas:
- Retorne SOMENTE o JSON estruturado solicitado, sem texto adicional, markdown ou explicações fora do JSON.
- Todas as questões devem ser inéditas entre si na mesma resposta.
- A resposta correta deve ser distribuída de forma variada entre A, B, C, D e E ao longo das questões.

Retorne SOMENTE um JSON com esta estrutura exata:
{
    "questoes": [
        {
            "enunciado": "...",
            "alternativas": {
                "A": "...",
                "B": "...",
                "C": "...",
                "D": "...",
                "E": "..."
            },
            "resposta_correta": "A",
            "resolucao_passo_a_passo": "..."
        }
    ]
}"""

RESOLUCAO_NUMERADA = (
    'O campo "resolucao_passo_a_passo" é OBRIGATÓRIO. Liste apenas os passos de cálculo '
    'numerados, no formato "expressão = resultado". Sem texto introdutório, sem explicações '
    'teóricas, sem conclusão.'
)

RESOLUCAO_CORRIDA = (
    'O campo "resolucao_passo_a_passo" é OBRIGATÓRIO. Escreva a resolução como texto corrido, '
    'sem lista numerada, sem tópicos, sem marcadores. Apresente os passos de cálculo em '
    'sequência natural, no formato "expressão = resultado", conectados em frases contínuas. '
    'Sem texto introdutório, sem explicações teóricas, sem conclusão.'
)

RESOLUCAO_OBJETIVA = (
    'O campo "resolucao_passo_a_passo" é OBRIGATÓRIO. Mostre apenas os passos de cálculo para '
    'chegar na resposta correta, de forma objetiva.'
)

_MODELOS_THINKING = ("qwen3", "deepseek-r1", "phi-4-mini-reasoning", "phi4-mini-reasoning")

_MODELOS_SEM_SYSTEM = ("google/gemma-2-2b-it", "gemma-2-2b-it", "BafS--gemma-2-2b-it")


def construir_prompt_sistema(sufixo_resolucao: str = RESOLUCAO_NUMERADA) -> str:
    return f"{_BASE}\n\n{sufixo_resolucao}"


def sufixo_no_think(modelo: str) -> str:
    m = modelo.lower()
    return " /no_think" if any(t in m for t in _MODELOS_THINKING) else ""


def _formatar_exemplos(examples: list[dict]) -> str:
    if not examples:
        return "Nenhum exemplo disponível — crie questões seguindo as diretrizes gerais da BNCC."
    return "\n".join(f"Exemplo {i + 1}: {ex['enunciado']}" for i, ex in enumerate(examples))


def _montar_user_content(sample: Sample, modelo: str) -> str:
    prereqs = ", ".join(sample.prerequisites) if sample.prerequisites else "Não especificada."
    exemplos = _formatar_exemplos(sample.examples)
    sufixo = sufixo_no_think(modelo)

    return f"""
Gere exatamente {sample.quantity} questão(ões) de múltipla escolha para a seguinte habilidade da BNCC:

**Habilidade:** {sample.habilidade_id}
**Unidade Temática:** {sample.unidade_tematica}

**Pré-requisitos que o aluno já deve dominar (calibração de dificuldade):**
{prereqs}

**Exemplos de questões existentes para esta habilidade (mantenha consistência de estilo):**
{exemplos}

Gere {sample.quantity} questão(ões) novas, inéditas e alinhadas à habilidade {sample.habilidade_id}.{sufixo}
""".strip()


def sample_to_prompt(
    sample: Sample,
    task_id: str,
    modelo: str,
    *,
    sufixo_resolucao: str = RESOLUCAO_NUMERADA,
    generation: dict | None = None,
) -> Prompt:
    system = construir_prompt_sistema(sufixo_resolucao)
    user = _montar_user_content(sample, modelo)

    sem_system = any(n in modelo for n in _MODELOS_SEM_SYSTEM)
    if sem_system:
        messages = [PromptMessage(role="user", content=f"{system}\n\n{user}")]
    else:
        messages = [
            PromptMessage(role="system", content=system),
            PromptMessage(role="user", content=user),
        ]

    default_gen = {
        "max_tokens": 1024,
        "temperature": 0.7,
        "top_p": 0.9,
        "repeat_penalty": 1.1,
    }
    if generation:
        default_gen.update(generation)

    return Prompt(
        sample_id=sample.id,
        task_id=task_id,
        messages=messages,
        quantidade_esperada=sample.quantity,
        generation=default_gen,
        meta={"habilidade_id": sample.habilidade_id},
    )
