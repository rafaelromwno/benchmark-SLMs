"""Snapshot do ambiente de execução (reproduzibilidade do benchmark)."""

from __future__ import annotations

import platform
import subprocess
import sys
from typing import Any

import psutil


def _cpu_modelo_macos() -> str | None:
    try:
        out = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).strip()
        return out or None
    except Exception:
        return None


def _cpu_modelo_linux() -> str | None:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("model name") or line.startswith("Hardware"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return None


def _cpu_modelo_windows() -> str | None:
    # Preferência: registro (stdlib, sem processo externo)
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
        ) as key:
            name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            if isinstance(name, str) and name.strip():
                return name.strip()
    except Exception:
        pass

    # Fallback: wmic (ainda comum; CREATE_NO_WINDOW evita flash de console)
    try:
        kwargs: dict[str, Any] = {
            "text": True,
            "stderr": subprocess.DEVNULL,
            "timeout": 5,
        }
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        out = subprocess.check_output(["wmic", "cpu", "get", "name"], **kwargs)
        linhas = [
            ln.strip()
            for ln in out.splitlines()
            if ln.strip() and ln.strip().lower() != "name"
        ]
        if linhas:
            return linhas[0]
    except Exception:
        pass

    # Fallback: PowerShell CIM
    try:
        kwargs = {
            "text": True,
            "stderr": subprocess.DEVNULL,
            "timeout": 5,
        }
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Processor).Name",
            ],
            **kwargs,
        )
        name = out.strip()
        return name or None
    except Exception:
        return None


def _cpu_modelo() -> str:
    """Identifica o processador em macOS, Linux e Windows (melhor esforço)."""
    sistema = platform.system()
    if sistema == "Darwin":
        nome = _cpu_modelo_macos()
    elif sistema == "Linux":
        nome = _cpu_modelo_linux()
    elif sistema == "Windows":
        nome = _cpu_modelo_windows()
    else:
        nome = None

    if nome:
        return nome

    proc = (platform.processor() or "").strip()
    if proc and proc.lower() not in {"i386", "x86_64", "amd64", "arm", "arm64", "aarch64"}:
        return proc

    return platform.machine() or "desconhecido"


def coletar_ambiente() -> dict[str, Any]:
    """Coleta informações relevantes da máquina que executa o teste."""
    vm = psutil.virtual_memory()
    return {
        "hostname": platform.node(),
        "sistema": platform.system(),
        "versao_sistema": platform.version(),
        "release": platform.release(),
        "arquitetura": platform.machine(),
        "cpu_modelo": _cpu_modelo(),
        "cpu_fisicos": psutil.cpu_count(logical=False),
        "cpu_logicos": psutil.cpu_count(logical=True),
        "ram_total_gb": round(vm.total / (1024**3), 2),
        "ram_disponivel_gb": round(vm.available / (1024**3), 2),
        "python": sys.version.split()[0],
        "plataforma_python": platform.platform(),
    }
