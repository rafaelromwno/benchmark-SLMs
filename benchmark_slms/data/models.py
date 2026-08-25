"""Catálogo e download de modelos GGUF via Hugging Face Hub."""

from __future__ import annotations

import json
from pathlib import Path

_CATALOG = Path(__file__).parent / "model_catalog.json"
DEFAULT_MODELS_DIR = Path("modelos_local_gguf")


def _repo_root() -> Path:
    return Path.cwd()


def catalog_path() -> Path:
    return _CATALOG


def load_catalog() -> dict[str, dict]:
    """Carrega apenas entradas ativas (ignora chaves `_…`, ex. exclusões documentadas)."""
    with open(_CATALOG, encoding="utf-8") as f:
        raw = json.load(f)
    return {
        mid: entrada
        for mid, entrada in raw.items()
        if not str(mid).startswith("_")
        and isinstance(entrada, dict)
        and "Modelo" in entrada
    }


def pasta_modelo(repo_id: str, base_dir: Path | None = None) -> Path:
    base = base_dir or (_repo_root() / DEFAULT_MODELS_DIR)
    return base / repo_id.replace("/", "--")


def caminho_gguf_local(
    repo_id: str,
    filename: str,
    base_dir: Path | None = None,
) -> Path | None:
    """Retorna o caminho do .gguf se já baixado, senão None."""
    pasta = pasta_modelo(repo_id, base_dir)
    candidatos = [
        pasta / filename,
        pasta / filename.lower(),
    ]
    for c in candidatos:
        if c.exists():
            return c.resolve()
    if pasta.exists():
        ggufs = list(pasta.glob("*.gguf"))
        if len(ggufs) == 1:
            return ggufs[0].resolve()
        for g in ggufs:
            if g.name.lower() == filename.lower():
                return g.resolve()
    return None


def esta_baixado(entrada: dict, base_dir: Path | None = None) -> bool:
    return caminho_gguf_local(entrada["Modelo"], entrada["Arquivo"], base_dir) is not None


def listar_modelos(base_dir: Path | None = None) -> list[dict]:
    catalogo = load_catalog()
    itens = []
    for mid, entrada in catalogo.items():
        local = caminho_gguf_local(entrada["Modelo"], entrada["Arquivo"], base_dir)
        itens.append(
            {
                "id": mid,
                "repo_id": entrada["Modelo"],
                "arquivo": entrada["Arquivo"],
                "quantizacao": entrada.get("Quantizacao", "?"),
                "baixado": local is not None,
                "caminho": str(local) if local else None,
            }
        )
    return itens


def baixar_gguf(
    repo_id: str,
    filename: str,
    base_dir: Path | None = None,
) -> Path:
    """Baixa um arquivo GGUF do Hugging Face Hub."""
    from huggingface_hub import hf_hub_download

    destino = pasta_modelo(repo_id, base_dir)
    destino.mkdir(parents=True, exist_ok=True)

    caminho = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=destino,
    )
    return Path(caminho).resolve()


def baixar_por_id(model_id: str, base_dir: Path | None = None) -> Path:
    catalogo = load_catalog()
    if model_id not in catalogo:
        raise KeyError(f"ID '{model_id}' não encontrado no catálogo.")
    entrada = catalogo[model_id]
    return baixar_gguf(entrada["Modelo"], entrada["Arquivo"], base_dir)


def resolver_modelo(
    model_id: str | None = None,
    repo_id: str | None = None,
    gguf_path: str | None = None,
    base_dir: Path | None = None,
) -> tuple[str, Path]:
    """Resolve (nome_modelo, caminho_gguf) a partir de id, repo ou caminho direto."""
    if gguf_path:
        path = Path(gguf_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")
        nome = repo_id or path.stem
        return nome, path

    if model_id:
        catalogo = load_catalog()
        if model_id not in catalogo:
            raise KeyError(f"ID '{model_id}' inválido.")
        entrada = catalogo[model_id]
        repo_id = entrada["Modelo"]
        local = caminho_gguf_local(repo_id, entrada["Arquivo"], base_dir)
        if not local:
            raise FileNotFoundError(
                f"Modelo id={model_id} ({repo_id}) não baixado. "
                "Use a opção 2 do menu interativo para baixar."
            )
        return repo_id, local

    if repo_id:
        catalogo = load_catalog()
        entrada = next((e for e in catalogo.values() if e["Modelo"] == repo_id), None)
        if entrada:
            local = caminho_gguf_local(repo_id, entrada["Arquivo"], base_dir)
            if local:
                return repo_id, local
        raise FileNotFoundError(
            f"Modelo {repo_id} não encontrado localmente. "
            "Use a opção 2 do menu interativo para baixar."
        )

    raise ValueError("Informe --id, --modelo+--gguf ou --repo+--file.")
