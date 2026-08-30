"""Abstração de backends: GGUF (llama-cpp) vs safetensors (transformers)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from benchmark_slms.core.contracts import Prompt, UsageStats


@dataclass
class GenerationResult:
    text: str
    usage: UsageStats
    raw: dict[str, Any] | None = None


class ModelBackend(ABC):
    @abstractmethod
    def gerar(self, prompt: Prompt) -> GenerationResult:
        """Gera texto a partir de um Prompt."""

    @abstractmethod
    def unload(self) -> None:
        """Libera recursos do modelo."""

    def definir_metricas(self, metricas) -> None:
        """Associa o monitor de métricas da rodada atual (TTFT/RAM)."""
        self._metricas = metricas


class GGUDBackend(ModelBackend):
    def __init__(
        self,
        model_path: str,
        n_ctx: int = 2048,
        n_threads: int = 8,
        n_gpu_layers: int = 0,
        metricas=None,
    ):
        from llama_cpp import Llama

        self._metricas = metricas
        if metricas:
            metricas.tempo_load_modelo_inicial()
            metricas.iniciar()

        self._llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,
            verbose=False,
        )

        if metricas:
            metricas.tempo_load_modelo_final()
            metricas.marcar_inicio_resposta()

    def gerar(self, prompt: Prompt) -> GenerationResult:
        messages = [{"role": m.role, "content": m.content} for m in prompt.messages]
        gen = prompt.generation
        m = self._metricas

        kwargs: dict[str, Any] = {
            "messages": messages,
            "max_tokens": gen.get("max_tokens", 1024),
            "temperature": gen.get("temperature", 0.7),
            "top_p": gen.get("top_p", 0.9),
            "repeat_penalty": gen.get("repeat_penalty", 1.1),
            "top_k": int(gen.get("top_k", 20)),
        }
        if "seed" in gen and gen["seed"] is not None:
            kwargs["seed"] = int(gen["seed"])
        if "min_p" in gen:
            kwargs["min_p"] = float(gen["min_p"])

        if m:
            m.marcar_inicio_resposta()

        try:
            return self._gerar_stream(kwargs, m)
        except Exception as exc_stream:
            # Stream do llama-cpp pode falhar ou voltar vazio sob carga —
            # tenta uma vez em modo bloqueante antes de propagar.
            try:
                if m:
                    m.marcar_inicio_resposta()
                return self._gerar_bloqueante(kwargs, m)
            except Exception as exc_block:
                raise RuntimeError(
                    f"GGUF falhou no stream ({type(exc_stream).__name__}: "
                    f"{str(exc_stream).strip() or repr(exc_stream)}) e no "
                    f"fallback ({type(exc_block).__name__}: "
                    f"{str(exc_block).strip() or repr(exc_block)})"
                ) from exc_block

    def _gerar_stream(self, kwargs: dict[str, Any], m) -> GenerationResult:
        partes: list[str] = []
        usage_data: dict[str, Any] = {}
        primeiro = True
        for chunk in self._llm.create_chat_completion(**kwargs, stream=True):
            if primeiro and m is not None:
                m.marcar_primeiro_token()
                primeiro = False
            choice = (chunk.get("choices") or [{}])[0]
            delta = choice.get("delta") or {}
            conteudo = delta.get("content")
            if conteudo:
                partes.append(conteudo)
            if chunk.get("usage"):
                usage_data = chunk["usage"]

        if primeiro and m is not None:
            m.marcar_primeiro_token()

        texto = "".join(partes)
        if not texto.strip():
            raise RuntimeError(
                "stream_vazio: create_chat_completion(stream=True) sem conteúdo"
            )
        return self._montar_resultado(texto, usage_data)

    def _gerar_bloqueante(self, kwargs: dict[str, Any], m) -> GenerationResult:
        resposta = self._llm.create_chat_completion(**kwargs, stream=False)
        if m is not None:
            m.marcar_primeiro_token()
        texto = (
            ((resposta.get("choices") or [{}])[0].get("message") or {}).get("content")
            or ""
        )
        if not texto.strip():
            raise RuntimeError("resposta_vazia: create_chat_completion sem conteúdo")
        return self._montar_resultado(texto, resposta.get("usage") or {}, raw=resposta)

    def _montar_resultado(
        self,
        texto: str,
        usage_data: dict[str, Any],
        raw: dict[str, Any] | None = None,
    ) -> GenerationResult:
        prompt_tokens = int(usage_data.get("prompt_tokens", 0))
        completion_tokens = int(usage_data.get("completion_tokens", 0))
        if completion_tokens == 0 and texto:
            try:
                completion_tokens = max(
                    1, len(self._llm.tokenize(texto.encode("utf-8"), add_bos=False))
                )
            except Exception:
                completion_tokens = max(1, len(texto) // 4)
        total_tokens = int(usage_data.get("total_tokens", 0)) or (
            prompt_tokens + completion_tokens
        )
        usage = UsageStats(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        return GenerationResult(
            text=texto,
            usage=usage,
            raw=raw if raw is not None else {"streamed": True, "usage": usage_data},
        )

    def unload(self) -> None:
        del self._llm


class SafetensorsBackend(ModelBackend):
    def __init__(self, model_path: str, metricas=None):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._torch = torch
        self._metricas = metricas
        if metricas:
            metricas.tempo_load_modelo_inicial()

        self._tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self._model = AutoModelForCausalLM.from_pretrained(
            model_path, local_files_only=True
        )
        self._model.eval()

        if metricas:
            metricas.tempo_load_modelo_final()

    def gerar(self, prompt: Prompt) -> GenerationResult:
        messages = [{"role": m.role, "content": m.content} for m in prompt.messages]
        gen = prompt.generation

        chat = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(chat, return_tensors="pt")
        n_input = inputs["input_ids"].shape[1]

        if self._metricas:
            self._metricas.iniciar(n_input)

        if "seed" in gen and gen["seed"] is not None:
            self._torch.manual_seed(int(gen["seed"]))

        gen_kwargs: dict[str, Any] = {
            "max_new_tokens": gen.get("max_tokens", 1024),
            "do_sample": gen.get("temperature", 0.7) > 0,
            "temperature": gen.get("temperature") if gen.get("temperature", 0) > 0 else None,
            "top_p": gen.get("top_p"),
            "top_k": int(gen.get("top_k", 20)),
            "repetition_penalty": gen.get("repeat_penalty", 1.1),
        }

        with self._torch.no_grad():
            saida = self._model.generate(**inputs, **gen_kwargs)

        tokens_gerados = saida[0][n_input:]
        n_output = int(len(tokens_gerados))

        if self._metricas:
            self._metricas.marcar_primeiro_token()
            self._metricas.finalizar(n_output)

        text = self._tokenizer.decode(tokens_gerados, skip_special_tokens=True)
        usage = UsageStats(
            prompt_tokens=n_input,
            completion_tokens=n_output,
            total_tokens=n_input + n_output,
        )
        return GenerationResult(text=text, usage=usage)

    def unload(self) -> None:
        del self._model
        del self._tokenizer


def criar_backend(
    backend_tipo: str,
    model_path: str,
    metricas=None,
    **kwargs,
) -> ModelBackend:
    if backend_tipo == "gguf":
        return GGUDBackend(model_path, metricas=metricas, **kwargs)
    if backend_tipo == "safetensors":
        return SafetensorsBackend(model_path, metricas=metricas)
    raise ValueError(f"Backend desconhecido: {backend_tipo}")
