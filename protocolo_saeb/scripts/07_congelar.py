"""Congela o protocolo antes da coleta humana: grava config/CONGELADO.json com hashes e versões.

Inclui sha256 de config/, modelo/, das questões geradas e do resultado do juiz (o "selo": prova que o juiz foi
fechado antes de qualquer professor ver uma folha), versões do Python, do deepeval e do llama.cpp, o commit do
git, e o modelo/digest do juiz (via `ollama show`, se disponível). Opcionalmente os hashes do GGUF base e do
adaptador. Não cria tag nem faz push: a tag é decisão de quem publica (`git tag protocolo-v2.0`).

  python 07_congelar.py --juiz-modelo gpt-oss:20b [--gguf caminho] [--lora caminho]
"""
import argparse
import hashlib
import json
import platform
import subprocess
import time
from importlib.metadata import PackageNotFoundError, version

from comum import DADOS, RAIZ

SAIDA = RAIZ / "config" / "CONGELADO.json"


def sha256(caminho, bloco=1 << 20):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for parte in iter(lambda: f.read(bloco), b""):
            h.update(parte)
    return h.hexdigest()


def comando(*args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=30).stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def pacote(nome):
    try:
        return version(nome)
    except PackageNotFoundError:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--juiz-modelo", required=True)
    ap.add_argument("--gguf")
    ap.add_argument("--lora")
    a = ap.parse_args()

    arquivos = sorted([*(RAIZ / "config").glob("*.json"), *(RAIZ / "config").glob("*.csv"), *(RAIZ / "modelo").glob("*"),
                       DADOS / "geracoes" / "questoes.jsonl", DADOS / "avaliacao_auto" / "geval.jsonl"])
    arquivos = [f for f in arquivos if f.is_file() and f.name != "CONGELADO.json"]
    geval = DADOS / "avaliacao_auto" / "geval.jsonl"
    registro = {
        "congelado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "commit_git": comando("git", "-C", str(RAIZ), "rev-parse", "HEAD"),
        "arvore_git_limpa": comando("git", "-C", str(RAIZ), "status", "--porcelain") == "",
        "python": platform.python_version(), "deepeval": pacote("deepeval"),
        "llama_cpp": comando("llama-server", "--version"),
        "juiz": {"modelo": a.juiz_modelo, "ollama_show": comando("ollama", "show", a.juiz_modelo)},
        "selo_do_juiz": {"arquivo": "dados/avaliacao_auto/geval.jsonl", "linhas": sum(1 for _ in geval.open(encoding="utf-8")),
                         "sha256": sha256(geval)} if geval.exists() else None,
        "modelos": {nome: {"arquivo": caminho, "sha256": sha256(caminho)} for nome, caminho in
                    (("gguf_base", a.gguf), ("adaptador_lora", a.lora)) if caminho},
        "arquivos": {str(f.relative_to(RAIZ)): sha256(f) for f in arquivos},
    }
    SAIDA.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"gravado {SAIDA.relative_to(RAIZ)} com {len(registro['arquivos'])} arquivos; selo: {registro['selo_do_juiz']}")


if __name__ == "__main__":
    main()
