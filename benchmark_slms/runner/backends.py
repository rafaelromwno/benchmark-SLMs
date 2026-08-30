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

        if self._metricas:
            self._metricas.marcar_inicio_resposta()

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

        resposta = self._llm.create_chat_completion(**kwargs)

        if self._metricas:
            self._metricas.marcar_primeiro_token()

        usage_data = resposta.get("usage", {})
        usage = UsageStats(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )
        text = resposta["choices"][0]["message"]["content"]
        return GenerationResult(text=text, usage=usage, raw=resposta)

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
        self._model = AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True)
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
