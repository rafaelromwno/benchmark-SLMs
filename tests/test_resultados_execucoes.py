"""Testes da organização resultados/<modelo>/execucao_N.json."""

from __future__ import annotations

from pathlib import Path

from benchmark_slms.core.contracts import ModelRunResult, RunConfig
from benchmark_slms.report.aggregate import carregar_resultados
from benchmark_slms.runner.calling import (
    _carregar_resultado,
    _pasta_modelo,
    _salvar_resultado,
    contar_execucoes,
    migrar_resultados_legados,
)


def _result(modelo: str = "org/phi-2", formato: str = "gguf") -> ModelRunResult:
    return ModelRunResult(
        modelo=modelo,
        formato=formato,
        data="28/07/2026",
        run_config=RunConfig(modelos=[modelo]),
    )


def test_pasta_modelo_criada_e_execucoes_sequenciais(tmp_path: Path) -> None:
    resultados = tmp_path / "resultados"
    r = _result()

    assert contar_execucoes(_pasta_modelo(resultados, r.modelo, r.formato)) == 0

    p1 = _salvar_resultado(r, resultados)
    p2 = _salvar_resultado(r, resultados)
    p3 = _salvar_resultado(r, resultados)

    pasta = resultados / "org--phi-2-gguf"
    assert pasta.is_dir()
    assert p1 == pasta / "execucao_1.json"
    assert p2 == pasta / "execucao_2.json"
    assert p3 == pasta / "execucao_3.json"
    assert contar_execucoes(pasta) == 3
    assert all(p.exists() for p in (p1, p2, p3))


def test_modelos_diferentes_tem_pastas_separadas(tmp_path: Path) -> None:
    resultados = tmp_path / "resultados"
    _salvar_resultado(_result("a/modelo-x"), resultados)
    _salvar_resultado(_result("b/modelo-y"), resultados)

    assert (resultados / "a--modelo-x-gguf" / "execucao_1.json").exists()
    assert (resultados / "b--modelo-y-gguf" / "execucao_1.json").exists()
    assert contar_execucoes(resultados / "a--modelo-x-gguf") == 1
    assert contar_execucoes(resultados / "b--modelo-y-gguf") == 1


def test_nao_sobrescreve_execucao_anterior(tmp_path: Path) -> None:
    resultados = tmp_path / "resultados"
    p1 = _salvar_resultado(_result(), resultados)
    conteudo_1 = p1.read_text(encoding="utf-8")

    p2 = _salvar_resultado(_result(), resultados)
    assert p1 != p2
    assert p1.read_text(encoding="utf-8") == conteudo_1
    assert p2.exists()


def test_carregar_resultado_pega_ultima_execucao(tmp_path: Path) -> None:
    resultados = tmp_path / "resultados"
    modelo = "org/phi-2"
    _salvar_resultado(_result(modelo), resultados)
    _salvar_resultado(_result(modelo), resultados)

    loaded = _carregar_resultado(resultados, modelo, "gguf")
    assert loaded is not None
    assert loaded.modelo == modelo


def test_carregar_resultados_le_pastas_por_modelo(tmp_path: Path) -> None:
    resultados = tmp_path / "resultados"
    _salvar_resultado(_result("a/x"), resultados)
    _salvar_resultado(_result("a/x"), resultados)
    _salvar_resultado(_result("b/y"), resultados)

    dados = carregar_resultados(resultados)
    assert len(dados) == 3


def test_migrar_resultado_legado_para_pasta(tmp_path: Path) -> None:
    resultados = tmp_path / "resultados"
    resultados.mkdir()
    legado = resultados / "org--phi-2-gguf.json"
    legado.write_text('{"modelo": "org/phi-2", "formato": "gguf"}', encoding="utf-8")

    movidos = migrar_resultados_legados(resultados)

    destino = resultados / "org--phi-2-gguf" / "execucao_1.json"
    assert movidos == [destino]
    assert destino.exists()
    assert not legado.exists()
    assert '"org/phi-2"' in destino.read_text(encoding="utf-8")


def test_migrar_legado_nao_sobrescreve_execucao_existente(tmp_path: Path) -> None:
    resultados = tmp_path / "resultados"
    pasta = resultados / "org--phi-2-gguf"
    pasta.mkdir(parents=True)
    (pasta / "execucao_1.json").write_text('{"n": 1}', encoding="utf-8")
    legado = resultados / "org--phi-2-gguf.json"
    legado.write_text('{"n": "legado"}', encoding="utf-8")

    migrar_resultados_legados(resultados)

    assert (pasta / "execucao_1.json").read_text(encoding="utf-8") == '{"n": 1}'
    assert (pasta / "execucao_2.json").exists()
    assert not legado.exists()


def test_carregar_resultados_migra_legado_automaticamente(tmp_path: Path) -> None:
    resultados = tmp_path / "resultados"
    resultados.mkdir()
    (resultados / "a--x-gguf.json").write_text(
        '{"modelo": "a/x", "formato": "gguf"}', encoding="utf-8"
    )

    dados = carregar_resultados(resultados)
    assert len(dados) == 1
    assert dados[0]["modelo"] == "a/x"
    assert (resultados / "a--x-gguf" / "execucao_1.json").exists()
