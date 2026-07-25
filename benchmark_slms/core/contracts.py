"""Contratos de dados entre fases do pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_serializer


# --- Schema JSON (migrado de schema_json.py) ---


class Alternativas(BaseModel):
    A: str
    B: str
    C: str
    D: str
    E: str


class Questao(BaseModel):
    enunciado: str = Field(min_length=1)
    alternativas: Alternativas
    resposta_correta: Literal["A", "B", "C", "D", "E"]
    resolucao_passo_a_passo: str = Field(min_length=1)

    @field_validator("resolucao_passo_a_passo", mode="before")
    @classmethod
    def juntar_lista_em_string(cls, valor: Any) -> Any:
        if isinstance(valor, list):
            itens_validos = [str(item) for item in valor if item is not None and str(item).strip()]
            return "\n".join(itens_validos)
        return valor


class GeneratedQuestionsResponse(BaseModel):
    questoes: list[Questao] = Field(min_length=1)


# --- Contratos inter-fases ---


class Sample(BaseModel):
    """Unidade de dado bruto do dataset (habilidade BNCC + contexto)."""

    id: str
    habilidade_id: str
    unidade_tematica: str
    prerequisites: list[str] = Field(default_factory=list)
    examples: list[dict[str, Any]] = Field(default_factory=list)
    quantity: int = 1
    meta: dict[str, Any] = Field(default_factory=dict)
    golden: dict[str, Any] | None = None


class PromptMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class Prompt(BaseModel):
    """Prompt montado pronto para inferência."""

    sample_id: str
    task_id: str
    messages: list[PromptMessage]
    quantidade_esperada: int = 1
    generation: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)


class UsageStats(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class InferenceMetrics(BaseModel):
    """Métricas de uma inferência.

    ``tempo_carregamento_s`` só é preenchido quando a carga do GGUF foi
    medida (cenário A / cold start). Em B–D o campo fica ``None`` e é
    omitido na serialização — o modelo já está em memória.
    """

    tempo_carregamento_s: float | None = None
    tempo_prefill_s: float = 0.0
    tempo_decode_s: float = 0.0
    tempo_resposta_s: float = 0.0
    tempo_total_s: float = 0.0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    tps: float = 0.0
    ram_inicio_mb: float = 0.0
    ram_pico_mb: float = 0.0
    ram_usada_mb: float = 0.0
    crash: bool = False
    crash_motivo: str | None = None

    @model_serializer(mode="wrap")
    def _omitir_carregamento_nao_medido(self, handler):
        data = handler(self)
        carga = data.get("tempo_carregamento_s")
        # Omitir se não medido (None) ou irrelevante (0.0 em B–D)
        if carga is None or carga == 0 or carga == 0.0:
            data.pop("tempo_carregamento_s", None)
        return data


class Prediction(BaseModel):
    """Saída bruta do modelo + métricas de inferência."""

    sample_id: str
    task_id: str
    modelo: str
    raw_output: str
    usage: UsageStats = Field(default_factory=UsageStats)
    metrics: InferenceMetrics = Field(default_factory=InferenceMetrics)
    rodada: int | None = None


class EvalResult(BaseModel):
    """Resultado de avaliação de uma predição ou agregado de task."""

    task_id: str
    modelo: str
    json_valido: bool = False
    json_erro: str | None = None
    quantidade_ok: bool = True
    quantidade_erro: str | None = None
    parsed: GeneratedQuestionsResponse | None = None
    viabilidade: dict[str, Any] = Field(default_factory=dict)
    agregado: dict[str, Any] = Field(default_factory=dict)
    predictions: list[Prediction] = Field(default_factory=list)


class ModoExecucao(str, Enum):
    SELECTION = "selection"
    BENCHMARK = "benchmark"


class BackendTipo(str, Enum):
    GGUF = "gguf"
    SAFETENSORS = "safetensors"


class RunConfig(BaseModel):
    """Configuração de uma execução matriz N modelos × M tasks."""

    modelos: list[str]
    tasks: list[str] = Field(default_factory=lambda: ["cenario_a", "cenario_b", "cenario_c", "cenario_d"])
    modo: ModoExecucao = ModoExecucao.SELECTION
    backend: BackendTipo = BackendTipo.GGUF
    modelo_paths: dict[str, str] = Field(default_factory=dict)
    seed: int = 42
    n_ctx: int = 2048
    n_threads: int = 8
    n_gpu_layers: int = 0
    resultados_dir: str = "resultados"
    logs_dir: str = "logs"
    offline: bool = True
    quantizacao: str | None = None
    versao_protocolo: str = "0.1.0"


class CriterioTipo(str, Enum):
    HARD = "hard"
    SOFT = "soft"


class CategoriaFalha(str, Enum):
    HARDWARE = "hardware"
    FORMATO = "formato"
    PERFORMANCE = "performance"
    QUALIDADE_CONTEUDO = "qualidade_conteudo"
    NENHUMA = "nenhuma"


class Criterio(BaseModel):
    nome: str
    tipo: CriterioTipo
    passou: bool
    valor: float | int | bool | None = None
    limite: float | int | bool | None = None
    motivo: str | None = None
    categoria_falha: CategoriaFalha = CategoriaFalha.NENHUMA


class Veredito(BaseModel):
    apto_mathia: bool
    criterios: list[Criterio] = Field(default_factory=list)
    motivos_reprovacao: list[str] = Field(default_factory=list)
    categoria_falha: CategoriaFalha = CategoriaFalha.NENHUMA
    modelo: str
    gerado_em: datetime = Field(default_factory=datetime.now)


class ModelRunResult(BaseModel):
    """Resultado bruto padronizado persistido em resultados/."""

    modelo: str
    formato: str
    data: str
    run_config: RunConfig
    tasks: dict[str, EvalResult] = Field(default_factory=dict)
    veredito: Veredito | None = None
    eliminado: bool = False
    motivo_eliminacao: str | None = None
