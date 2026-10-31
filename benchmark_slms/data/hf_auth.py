"""Autenticação e diagnóstico de erros do Hugging Face Hub."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class HFAuthStatus(str, Enum):
    OK = "ok"
    SEM_TOKEN = "sem_token"
    TOKEN_INVALIDO = "token_invalido"
    HF_NAO_INSTALADO = "hf_nao_instalado"


@dataclass
class ErroOperacao:
    titulo: str
    detalhe: str
    dicas: list[str]


def dependencias_ok() -> tuple[bool, list[str]]:
    faltando = []
    for pkg in ("pydantic", "psutil", "huggingface_hub", "llama_cpp"):
        try:
            __import__(pkg)
        except ImportError:
            faltando.append("llama-cpp-python" if pkg == "llama_cpp" else pkg)
    return len(faltando) == 0, faltando


def _token_paths() -> list[Path]:
    home = Path.home()
    return [
        home / ".cache" / "huggingface" / "token",
        home / ".huggingface" / "token",
    ]


def remover_token_local() -> bool:
    removido = False
    for p in _token_paths():
        if p.exists():
            p.unlink()
            removido = True
    return removido


def status_hf() -> tuple[HFAuthStatus, str | None]:
    try:
        from huggingface_hub import HfApi
    except ImportError:
        return HFAuthStatus.HF_NAO_INSTALADO, None

    if not any(p.exists() for p in _token_paths()):
        return HFAuthStatus.SEM_TOKEN, None

    try:
        info = HfApi().whoami()
        nome = info.get("name") or info.get("fullname") or "usuário"
        return HFAuthStatus.OK, nome
    except Exception as exc:
        msg = str(exc).lower()
        if "401" in msg or "signature" in msg or "unauthorized" in msg or "invalid" in msg:
            return HFAuthStatus.TOKEN_INVALIDO, None
        return HFAuthStatus.TOKEN_INVALIDO, None


def classificar_erro_download(exc: Exception) -> ErroOperacao:
    msg = str(exc).lower()

    if "401" in msg or "signature verification failed" in msg or "unauthorized" in msg:
        return ErroOperacao(
            titulo="Token do Hugging Face inválido ou expirado",
            detalhe=str(exc).split("\n")[0],
            dicas=[
                "Use a opção 7 do menu → Login Hugging Face",
                "Ou no terminal: hf auth login",
                "Se persistir: apague ~/.cache/huggingface/token e faça login de novo",
            ],
        )

    if "403" in msg or "gated" in msg or "access" in msg:
        return ErroOperacao(
            titulo="Modelo restrito (gated) no Hugging Face",
            detalhe=str(exc).split("\n")[0],
            dicas=[
                "Abra a página do modelo no huggingface.co e aceite os termos de uso",
                "Depois faça login com a opção 7 do menu",
                "Tente o download novamente",
            ],
        )

    if "404" in msg or "not found" in msg or "repository not found" in msg:
        return ErroOperacao(
            titulo="Repositório ou arquivo não encontrado",
            detalhe=str(exc).split("\n")[0],
            dicas=[
                "Confira se o id do catálogo ainda é válido no Hugging Face",
                "Alguns repos oficiais mudaram de nome — tente outro id do catálogo",
                "Verifique o nome exato do arquivo .gguf na aba Files do repositório",
            ],
        )

    if "connection" in msg or "timeout" in msg or "network" in msg:
        return ErroOperacao(
            titulo="Falha de conexão",
            detalhe=str(exc).split("\n")[0],
            dicas=[
                "Verifique sua conexão com a internet",
                "Tente novamente em alguns instantes",
            ],
        )

    return ErroOperacao(
        titulo="Erro no download",
        detalhe=str(exc).split("\n")[0],
        dicas=[
            "Use a opção 7 do menu para verificar login HF",
            "Consulte logs/ para mais detalhes da execução",
        ],
    )


def classificar_erro_execucao(exc: Exception) -> ErroOperacao:
    if isinstance(exc, ImportError):
        return ErroOperacao(
            titulo="Dependências não instaladas",
            detalhe=str(exc),
            dicas=[
                "pip install pydantic psutil huggingface_hub llama-cpp-python",
                "Use opção 11 do menu para verificar o ambiente",
            ],
        )

    if isinstance(exc, FileNotFoundError):
        return ErroOperacao(
            titulo="Modelo não encontrado localmente",
            detalhe=str(exc),
            dicas=[
                "Use a opção 2 do menu para baixar o modelo antes de testar",
                "Ou escolha um modelo marcado com [✓] na listagem",
            ],
        )

    if isinstance(exc, KeyError):
        return ErroOperacao(
            titulo="ID inválido",
            detalhe=str(exc),
            dicas=["Confira os ids disponíveis na opção 1 do menu"],
        )

    msg = str(exc).lower()
    if "llama" in msg or "gguf" in msg or "model" in msg:
        return ErroOperacao(
            titulo="Erro ao carregar ou executar o modelo",
            detalhe=str(exc).split("\n")[0],
            dicas=[
                "Confira se o arquivo .gguf não está corrompido (baixe de novo)",
                "Modelos muito grandes podem estourar RAM — tente um id menor (ex.: 30)",
            ],
        )

    return ErroOperacao(
        titulo="Erro na execução do benchmark",
        detalhe=str(exc).split("\n")[0],
        dicas=["Veja logs/ para a trilha JSONL da execução"],
    )


def imprimir_erro(erro: ErroOperacao) -> None:
    print(f"\n✗ {erro.titulo}")
    print(f"  {erro.detalhe}")
    print("  O que fazer:")
    for dica in erro.dicas:
        print(f"    • {dica}")


def pausar() -> None:
    input("\nPressione Enter para continuar...")


def executar_login_hf() -> bool:
    """Tenta login interativo via CLI oficial do Hugging Face."""
    hf_bin = shutil.which("hf") or shutil.which("huggingface-cli")
    if not hf_bin:
        print("\n✗ CLI do Hugging Face não encontrada.")
        print("  Instale com: pip install huggingface_hub")
        print("  Depois rode: hf auth login")
        return False

    print(f"\nAbrindo login via: {hf_bin} auth login")
    print("(Siga as instruções no terminal — cole o token se solicitado)\n")
    try:
        result = subprocess.run([hf_bin, "auth", "login"], check=False)
        if result.returncode != 0:
            print("\n✗ Login cancelado ou falhou.")
            return False
    except KeyboardInterrupt:
        print("\n✗ Login cancelado.")
        return False

    status, nome = status_hf()
    if status == HFAuthStatus.OK:
        print(f"\n✓ Login OK — conectado como {nome}")
        return True

    print("\n✗ Login concluído, mas a autenticação ainda não está válida.")
    return False


def preparar_download() -> tuple[bool, ErroOperacao | None]:
    """Verifica deps + HF antes de baixar. Retorna (ok, erro)."""
    ok, faltando = dependencias_ok()
    if not ok:
        return False, ErroOperacao(
            titulo="Dependências não instaladas",
            detalhe=f"Pacotes faltando: {', '.join(faltando)}",
            dicas=[
                "Ative o venv: source .venv/bin/activate",
                "Instale: pip install pydantic psutil huggingface_hub llama-cpp-python",
            ],
        )

    status, _ = status_hf()
    if status == HFAuthStatus.HF_NAO_INSTALADO:
        return False, ErroOperacao(
            titulo="huggingface_hub não instalado",
            detalhe="Necessário para baixar modelos",
            dicas=["pip install huggingface_hub"],
        )

    if status == HFAuthStatus.TOKEN_INVALIDO:
        return False, ErroOperacao(
            titulo="Token Hugging Face inválido",
            detalhe="Há um token salvo localmente, mas ele foi rejeitado pelo servidor",
            dicas=[
                "Use a opção 7 → Login Hugging Face",
                "Ou opção 8 → Remover token inválido, depois login de novo",
            ],
        )

    return True, None


def imprimir_status_ambiente(models_dir: Path) -> None:
    ok, faltando = dependencias_ok()
    print("\n--- Ambiente ---")
    if ok:
        print("  Dependências: ✓ OK")
    else:
        print(f"  Dependências: ✗ faltando {', '.join(faltando)}")

    status, nome = status_hf()
    if status == HFAuthStatus.OK:
        print(f"  Hugging Face: ✓ logado como {nome}")
    elif status == HFAuthStatus.SEM_TOKEN:
        print("  Hugging Face: ○ sem login (ok para modelos públicos)")
    elif status == HFAuthStatus.TOKEN_INVALIDO:
        print("  Hugging Face: ✗ token inválido — use opção 7 ou 8")
    else:
        print("  Hugging Face: ✗ huggingface_hub não instalado")

    baixados = sum(1 for m in _listar_baixados(models_dir))
    print(f"  Modelos locais: {baixados} baixado(s) em {models_dir}/")
    print(f"  Python: {sys.version.split()[0]}")


def _listar_baixados(models_dir: Path) -> list:
    from benchmark_slms.data.models import listar_modelos

    return [m for m in listar_modelos(models_dir) if m["baixado"]]
