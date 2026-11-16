import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def carregar(nome_arquivo):
    spec = importlib.util.spec_from_file_location(nome_arquivo.replace(".py", ""), SCRIPTS / nome_arquivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
