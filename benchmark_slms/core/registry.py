"""Registro de plugins: tasks, métricas e pós-processadores."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")

_TASKS: dict[str, Callable[..., Any]] = {}
_METRICS: dict[str, Callable[..., Any]] = {}
_POSTPROCESSORS: dict[str, Callable[..., Any]] = {}


def register_task(task_id: str):
    def decorator(fn: Callable[..., Any]):
        _TASKS[task_id] = fn
        return fn

    return decorator


def register_metric(metric_id: str):
    def decorator(fn: Callable[..., Any]):
        _METRICS[metric_id] = fn
        return fn

    return decorator


def register_postprocessor(processor_id: str):
    def decorator(fn: Callable[..., Any]):
        _POSTPROCESSORS[processor_id] = fn
        return fn

    return decorator


def get_task(task_id: str) -> Callable[..., Any]:
    if task_id not in _TASKS:
        raise KeyError(f"Task '{task_id}' não registrada. Disponíveis: {list_tasks()}")
    return _TASKS[task_id]


def get_metric(metric_id: str) -> Callable[..., Any]:
    if metric_id not in _METRICS:
        raise KeyError(f"Métrica '{metric_id}' não registrada. Disponíveis: {list_metrics()}")
    return _METRICS[metric_id]


def get_postprocessor(processor_id: str) -> Callable[..., Any]:
    if processor_id not in _POSTPROCESSORS:
        raise KeyError(
            f"Pós-processador '{processor_id}' não registrado. "
            f"Disponíveis: {list_postprocessors()}"
        )
    return _POSTPROCESSORS[processor_id]


def list_tasks() -> list[str]:
    return sorted(_TASKS.keys())


def list_metrics() -> list[str]:
    return sorted(_METRICS.keys())


def list_postprocessors() -> list[str]:
    return sorted(_POSTPROCESSORS.keys())
