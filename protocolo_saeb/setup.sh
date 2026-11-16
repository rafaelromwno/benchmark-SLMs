#!/usr/bin/env bash
# Cria .venv com Python >= 3.10 (deepeval exige) e instala as dependências. Não baixa modelos.
set -euo pipefail
cd "$(dirname "$0")"

for cand in python3.12 python3.11 python3.13 python3.10 python3; do
  if command -v "$cand" >/dev/null && "$cand" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    PY="$cand"; break
  fi
done
[ -n "${PY:-}" ] || { echo "Python >= 3.10 não encontrado. Instale uma versão 3.10-3.13 (pyenv, gerenciador de pacotes do sistema ou python.org)." >&2; exit 1; }

echo "usando $($PY --version) ($(command -v $PY))"
"$PY" -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt pytest
.venv/bin/pip freeze > requirements.lock
echo "ok. versões fixadas em requirements.lock (commitar depois da primeira instalação)"
