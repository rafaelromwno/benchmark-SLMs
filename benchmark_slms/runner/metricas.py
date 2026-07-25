"""Métricas de inferência (migrado de metricas.py + TTFT/decode)."""

from __future__ import annotations

import os
import threading
import time

import psutil

from benchmark_slms.core.contracts import InferenceMetrics


class MetricasInferencia:
    """Monitor de RAM e latência com separação prefill (TTFT) vs decode."""

    def __init__(self):
        self.processo = psutil.Process(os.getpid())
        self._monitorando = False
        self._thread: threading.Thread | None = None
        self.tempo_load_inicial = 0.0
        self.tempo_load_final = 0.0
        self.tempo_inicio: float | None = None
        self.tempo_fim: float | None = None
        self.tempo_primeiro_token: float | None = None
        self.ram_pico_mb = 0.0
        self.ram_inicio_mb = 0.0
        self.tokens_entrada = 0
        self.tokens_saida = 0
        self.tempo_total_por_rodada: list[float] = []
        self.TPS_por_rodada: list[float] = []
        self.ram_por_rodada: list[float] = []
        self.ttft_por_rodada: list[float] = []

    def _monitorar_ram(self):
        while self._monitorando:
            ram_atual = self.processo.memory_info().rss / (1024**2)
            if ram_atual > self.ram_pico_mb:
                self.ram_pico_mb = ram_atual
            time.sleep(0.1)

    def _iniciar_monitor(self):
        self.ram_inicio_mb = self.processo.memory_info().rss / (1024**2)
        self.ram_pico_mb = self.ram_inicio_mb
        self._monitorando = True
        self._thread = threading.Thread(target=self._monitorar_ram, daemon=True)
        self._thread.start()

    def _parar_monitor(self):
        self._monitorando = False
        if self._thread:
            self._thread.join()

    def iniciar(self, tokens_entrada: int = 0):
        """Liga monitor de RAM. No fluxo GGUF, chamar ANTES do load."""
        self.tokens_entrada = tokens_entrada
        self.tempo_inicio = time.perf_counter()
        self.tempo_primeiro_token = None
        self._iniciar_monitor()

    def marcar_inicio_resposta(self):
        """Reinicia cronômetro de resposta (exclui tempo de load)."""
        self.tempo_inicio = time.perf_counter()
        self.tempo_primeiro_token = None

    def marcar_primeiro_token(self):
        """Marca TTFT (prefill concluído, decode iniciado)."""
        if self.tempo_inicio is not None and self.tempo_primeiro_token is None:
            self.tempo_primeiro_token = time.perf_counter()

    def finalizar(self, tokens_saida: int = 0):
        self.tempo_fim = time.perf_counter()
        self.tokens_saida = tokens_saida
        self._parar_monitor()

    def iniciar_rodada(self):
        self.tempo_inicio = time.perf_counter()
        self.tempo_primeiro_token = None
        self._iniciar_monitor()

    def finalizar_rodada(self, tokens_saida: int):
        self.tempo_fim = time.perf_counter()
        self.tokens_saida = tokens_saida
        self._parar_monitor()
        self.ram_por_rodada.append(self.ram_pico_mb)
        tempo_resposta = self.tempo_resposta_modelo
        self.TPS_por_rodada.append(tokens_saida / tempo_resposta if tempo_resposta > 0 else 0)
        self.tempo_total_por_rodada.append(tempo_resposta)
        if self.tempo_primeiro_token and self.tempo_inicio:
            self.ttft_por_rodada.append(self.tempo_primeiro_token - self.tempo_inicio)
        else:
            self.ttft_por_rodada.append(0.0)

    def tempo_load_modelo_inicial(self):
        self.tempo_load_inicial = time.perf_counter()

    def tempo_load_modelo_final(self):
        self.tempo_load_final = time.perf_counter()

    @property
    def tempo_carregamento_modelo(self) -> float:
        return self.tempo_load_final - self.tempo_load_inicial

    @property
    def tempo_resposta_modelo(self) -> float:
        if self.tempo_inicio is None or self.tempo_fim is None:
            return 0.0
        return self.tempo_fim - self.tempo_inicio

    @property
    def tempo_prefill(self) -> float:
        if self.tempo_inicio is None or self.tempo_primeiro_token is None:
            return 0.0
        return self.tempo_primeiro_token - self.tempo_inicio

    @property
    def tempo_decode(self) -> float:
        if self.tempo_primeiro_token is None or self.tempo_fim is None:
            return self.tempo_resposta_modelo
        return self.tempo_fim - self.tempo_primeiro_token

    @property
    def tempo_total(self) -> float:
        return self.tempo_resposta_modelo + self.tempo_carregamento_modelo

    @property
    def tokens_por_segundo(self) -> float:
        if self.tempo_resposta_modelo <= 0:
            return 0.0
        return self.tokens_saida / self.tempo_resposta_modelo

    @property
    def ram_usada_mb(self) -> float:
        return self.ram_pico_mb - self.ram_inicio_mb

    @property
    def media_rodadas(self) -> dict:
        n = len(self.TPS_por_rodada)
        if n == 0:
            return {
                "tps_medio": 0.0,
                "ram_media_mb": 0.0,
                "ram_pico_mb": 0.0,
                "tempo_medio_segundos": 0.0,
                "ttft_medio_segundos": 0.0,
            }
        return {
            "tps_medio": sum(self.TPS_por_rodada) / n,
            "ram_media_mb": sum(self.ram_por_rodada) / n,
            "ram_pico_mb": max(self.ram_por_rodada),
            "tempo_medio_segundos": sum(self.tempo_total_por_rodada) / n,
            "ttft_medio_segundos": sum(self.ttft_por_rodada) / n if self.ttft_por_rodada else 0.0,
        }

    def to_inference_metrics(self) -> InferenceMetrics:
        # Carga só entra quando foi cronometrada (cenário A); B–D omitem o campo.
        load_medido = self.tempo_load_final > 0.0
        return InferenceMetrics(
            tempo_carregamento_s=self.tempo_carregamento_modelo if load_medido else None,
            tempo_prefill_s=self.tempo_prefill,
            tempo_decode_s=self.tempo_decode,
            tempo_resposta_s=self.tempo_resposta_modelo,
            tempo_total_s=self.tempo_total,
            tokens_entrada=self.tokens_entrada,
            tokens_saida=self.tokens_saida,
            tps=self.tokens_por_segundo,
            ram_inicio_mb=self.ram_inicio_mb,
            ram_pico_mb=self.ram_pico_mb,
            ram_usada_mb=self.ram_usada_mb,
        )

    def relatorio(self) -> str:
        return (
            f"Tempo de carregamento: {self.tempo_carregamento_modelo:.2f}s\n"
            f"TTFT (prefill):        {self.tempo_prefill:.2f}s\n"
            f"Decode:                {self.tempo_decode:.2f}s\n"
            f"Tempo de resposta:     {self.tempo_resposta_modelo:.2f}s\n"
            f"Tokens entrada:        {self.tokens_entrada}\n"
            f"Tokens gerados:        {self.tokens_saida}\n"
            f"TPS:                   {self.tokens_por_segundo:.2f}\n"
            f"RAM pico:              {self.ram_pico_mb:.1f} MB"
        )
