"""Preflight: confere tudo que os passos seguintes precisam, sem gerar nem avaliar nada.

  python 00_verificar_ambiente.py [--gguf Qwen3-4B-Q4_K_M.gguf] [--lora lora_4b_v7b_s44.f16.gguf]
                                  [--juiz-url http://localhost:11434] [--juiz-modelo gpt-oss:20b]
Sai com código 1 se algum item obrigatório falhar. Itens "aviso" não reprovam.
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
import urllib.request
from pathlib import Path

from comum import APP, CELULAS, CRITERIOS, RAIZ

SHA_BASE = "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5"
SHA_LORA = "dd9abbddb2ecceab92cd1b281a671b3c289d621e2bebfca542bce73e1f2b05cb"
resultados = []


def item(nome, ok, detalhe="", obrigatorio=True):
    resultados.append((nome, ok, detalhe, obrigatorio))


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def checar_arquivo(nome, caminho, esperado):
    if not caminho or not Path(caminho).is_file():
        return item(nome, False, f"não encontrado: {caminho}")
    got = sha256(caminho)
    item(nome, got == esperado, "sha256 confere" if got == esperado else f"sha256 diferente ({got[:12]})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gguf")
    ap.add_argument("--lora")
    ap.add_argument("--juiz-url", default="http://localhost:11434")
    ap.add_argument("--juiz-modelo", default="gpt-oss:20b")
    a = ap.parse_args()

    v = sys.version_info
    item("python >= 3.10 (deepeval)", v >= (3, 10), f"{v.major}.{v.minor}.{v.micro}")
    try:
        import deepeval
        item("deepeval importável", True, getattr(deepeval, "__version__", "?"))
    except Exception as e:
        item("deepeval importável", False, repr(e))

    tax = json.loads((APP / "taxonomia_subtemas.json").read_text(encoding="utf-8"))
    faltam = [f"{c['ano']}|{c['habilidade']}" for c in CELULAS if f"{c['ano']}|{c['habilidade']}" not in tax["habilidades"]]
    item("células existem na taxonomia", not faltam, ", ".join(faltam) or f"{len(CELULAS)} células")
    item("5 critérios definidos", len(CRITERIOS) == 5, str(len(CRITERIOS)))

    origem = (RAIZ / "modelo" / "ORIGEM.md").read_text(encoding="utf-8")
    for arq in ("cliente_llama_server.py", "questao.gbnf", "taxonomia_subtemas.json"):
        esperado = re.search(re.escape(arq) + r"`\s*\|\s*`([0-9a-f]{64})`", origem).group(1)
        item(f"modelo/{arq} íntegro", sha256(APP / arq) == esperado)

    item("llama-server no PATH", shutil.which("llama-server") is not None, "instale o llama.cpp: https://github.com/ggml-org/llama.cpp", obrigatorio=False)
    if a.gguf or a.lora:
        checar_arquivo("GGUF base", a.gguf, SHA_BASE)
        checar_arquivo("LoRA GGUF", a.lora, SHA_LORA)
    else:
        item("GGUF base / LoRA", False, "passe --gguf e --lora para conferir hashes", obrigatorio=False)

    try:
        with urllib.request.urlopen(a.juiz_url.rstrip("/") + "/api/tags", timeout=5) as r:
            nomes = [m["name"] for m in json.loads(r.read().decode())["models"]]
        item("Ollama no ar", True, a.juiz_url)
        item(f"modelo {a.juiz_modelo} baixado", a.juiz_modelo in nomes, ", ".join(nomes) or "nenhum modelo")
    except Exception as e:
        item("Ollama no ar", False, f"{a.juiz_url} ({e.__class__.__name__}); rode `ollama serve`", obrigatorio=False)

    for nome, ok, detalhe, obrig in resultados:
        marca = "OK   " if ok else ("FALHA" if obrig else "aviso")
        print(f"[{marca}] {nome}" + (f" — {detalhe}" if detalhe else ""))
    sys.exit(1 if any(not ok and obrig for _, ok, _, obrig in resultados) else 0)


if __name__ == "__main__":
    main()
