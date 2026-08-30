"""Testes da organização resultados/<modelo>/execucao_N.json."""

from __future__ import annotations

from pathlib import Path

from benchmark_slms.core.contracts import InferenceProfile, ModelRunResult, RunConfig
from benchmark_slms.report.aggregate import carregar_resultados, gerar_leaderboard
import benchmark_slms.runner.calling as calling
from benchmark_slms.tasks import snapshot_inferencia
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


def test_perfis_sao_persistidos_em_subpastas_e_exibidos_no_leaderboard(tmp_path: Path) -> None:
    resultados = tmp_path / "resultados"
    deterministico = InferenceProfile(
        name="deterministico", temperature=0, top_p=1, repeat_penalty=1.1
    )
    balanceado = InferenceProfile(
        name="balanceado", temperature=0.7, top_p=0.9, repeat_penalty=1.1
    )
    for perfil in (deterministico, balanceado):
        result = _result()
        result.run_config.inference_profile = perfil
        result.inferencia = snapshot_inferencia(profile=perfil)
        _salvar_resultado(result, resultados)

    assert (resultados / "org--phi-2-gguf" / "deterministico" / "execucao_1.json").exists()
    assert (resultados / "org--phi-2-gguf" / "balanceado" / "execucao_1.json").exists()
    assert len(carregar_resultados(resultados)) == 2
    assert {row["profile"] for row in gerar_leaderboard(resultados)["leaderboard"]} == {
        "deterministico",
        "balanceado",
    }


def test_resultado_persiste_perfil_autocontido_sem_campos_de_orquestracao(tmp_path: Path) -> None:
    perfil = InferenceProfile(
        name="balanceado", temperature=0.7, top_p=0.9, repeat_penalty=1.1
    )
    result = _result()
    result.run_config.inference_profiles = [perfil]
    result.run_config.inference_profile = perfil
    result.inferencia = snapshot_inferencia(profile=perfil)

    path = _salvar_resultado(result, tmp_path / "resultados")
    data = __import__("json").loads(path.read_text(encoding="utf-8"))

    assert "inference_profiles" not in data["run_config"]
    assert "inference_profile" not in data["run_config"]
    assert "profile" not in data["inferencia"]
    assert "overrides" not in data["inferencia"]
    assert data["inferencia"]["perfil"] == perfil.model_dump()


def test_leaderboard_prefere_perfil_novo_e_aceita_layouts_anteriores(tmp_path: Path) -> None:
    resultados = tmp_path / "resultados"
    novo = _result("novo/modelo")
    novo.inferencia = {"perfil": {"name": "novo"}}
    _salvar_resultado(novo, resultados)

    legado = resultados / "legado--modelo-gguf" / "execucao_1.json"
    legado.parent.mkdir(parents=True)
    legado.write_text(
        '{"modelo":"legado/modelo","formato":"gguf",'
        '"run_config":{"inference_profile":{"name":"intermediario"}},'
        '"inferencia":{"profile":"antigo"},"tasks":{}}',
        encoding="utf-8",
    )
    antigo = resultados / "antigo--modelo-gguf" / "execucao_1.json"
    antigo.parent.mkdir(parents=True)
    antigo.write_text(
        '{"modelo":"antigo/modelo","formato":"gguf",'
        '"run_config":{},"inferencia":{"profile":"legado"},"tasks":{}}',
        encoding="utf-8",
    )

    perfis = {row["modelo"]: row["profile"] for row in gerar_leaderboard(resultados)["leaderboard"]}
    assert perfis == {
        "novo/modelo": "novo",
        "legado/modelo": "intermediario",
        "antigo/modelo": "legado",
    }


def test_matriz_executa_cada_modelo_para_cada_perfil(monkeypatch, tmp_path: Path) -> None:
    perfis = [
        InferenceProfile(name="p1", temperature=0, top_p=1, repeat_penalty=1.1),
        InferenceProfile(name="p2", temperature=0.8, top_p=0.9, repeat_penalty=1.2),
    ]
    config = RunConfig(
        modelos=["a/x", "b/y"],
        inference_profiles=perfis,
        generation_overrides={"max_tokens": 64},
        logs_dir=str(tmp_path / "logs"),
        multi_seed=False,
    )
    chamadas: list[tuple[str, str | None, dict]] = []

    def fake_executar_modelo(config_atual, modelo, logger=None):
        profile = config_atual.inference_profile
        chamadas.append((modelo, profile.name if profile else None, config_atual.generation_overrides))
        return _result(modelo)

    monkeypatch.setattr(calling, "executar_modelo", fake_executar_modelo)
    calling.executar_matriz(config)

    assert [(modelo, perfil) for modelo, perfil, _ in chamadas] == [
        ("a/x", "p1"), ("b/y", "p1"), ("a/x", "p2"), ("b/y", "p2"),
    ]
    assert chamadas[0][2]["max_tokens"] == 64
    assert chamadas[0][2]["temperature"] == 0
    assert chamadas[0][2]["top_p"] == 1
    assert chamadas[0][2]["repeat_penalty"] == 1.1
    assert chamadas[0][2]["top_k"] == 20
    assert chamadas[0][2]["seed"] == config.seed


def test_matriz_protocolo_gera_10_seeds_por_celula(monkeypatch, tmp_path: Path) -> None:
    from benchmark_slms.protocol import PROTOCOL_SEEDS

    perfil = InferenceProfile(
        name="balanceado", temperature=0.7, top_p=0.8, top_k=20, repeat_penalty=1.0
    )
    config = RunConfig(
        modelos=["a/x"],
        inference_profiles=[perfil],
        logs_dir=str(tmp_path / "logs"),
        multi_seed=True,
    )
    seeds_vistas: list[int] = []

    def fake_executar_modelo(config_atual, modelo, logger=None):
        seeds_vistas.append(config_atual.seed)
        assert config_atual.generation_overrides.get("seed") == config_atual.seed
        return _result(modelo)

    monkeypatch.setattr(calling, "executar_modelo", fake_executar_modelo)
    resultados = calling.executar_matriz(config)

    assert len(resultados) == 10
    assert seeds_vistas == list(PROTOCOL_SEEDS)


def test_perfis_protocolo_balanceado_e_criativo() -> None:
    from benchmark_slms.inference_profiles import DEFAULT_INFERENCE_PROFILES

    assert [p.name for p in DEFAULT_INFERENCE_PROFILES] == ["balanceado", "criativo"]
    bal, cri = DEFAULT_INFERENCE_PROFILES
    assert (bal.temperature, bal.top_p, bal.top_k, bal.repeat_penalty) == (0.7, 0.8, 20, 1.0)
    assert (cri.temperature, cri.top_p, cri.top_k, cri.repeat_penalty) == (1.3, 0.8, 20, 1.0)


def test_catalogo_corte_leve_tem_17_ativos() -> None:
    import json
    from pathlib import Path

    from benchmark_slms.data.models import load_catalog

    ativos = load_catalog()
    assert len(ativos) == 17
    nomes = {e["Modelo"] for e in ativos.values()}
    assert any("SmolLM2-135M" in n for n in nomes)
    assert any("Qwen1.5" in n for n in nomes)
    assert any("phi-2" in n for n in nomes)

    raw = json.loads(Path("benchmark_slms/data/model_catalog.json").read_text(encoding="utf-8"))
    excl = raw["_excluidos_corte_literatura"]
    corte2 = [
        v for v in excl.values()
        if isinstance(v, dict) and str(v.get("Corte", "")).startswith("C4")
    ]
    assert len(corte2) == 7
    assert all(v["Corte"] == "C4-C6+C8" for v in corte2)
