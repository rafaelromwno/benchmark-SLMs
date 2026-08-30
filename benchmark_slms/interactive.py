"""Menu interativo — único ponto de entrada para download e benchmark."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from benchmark_slms.core.contracts import BackendTipo, ModoExecucao, RunConfig
from benchmark_slms.data.hf_auth import (
    HFAuthStatus,
    classificar_erro_download,
    classificar_erro_execucao,
    dependencias_ok,
    executar_login_hf,
    imprimir_erro,
    imprimir_status_ambiente,
    pausar,
    preparar_download,
    remover_token_local,
    status_hf,
)
from benchmark_slms.data.models import (
    DEFAULT_MODELS_DIR,
    baixar_por_id,
    caminho_gguf_local,
    listar_modelos,
    load_catalog,
    resolver_modelo,
)
from benchmark_slms.inference_profiles import DEFAULT_INFERENCE_PROFILES


def limpar_tela() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _escolher_id(
    rotulo: str,
    base_dir: Path,
    *,
    apenas_baixados: bool = False,
) -> str | None:
    catalogo = load_catalog()
    status_map = {m["id"]: m["baixado"] for m in listar_modelos(base_dir)}

    print(f"\n{rotulo}:")
    encontrou = False
    for mid, entrada in catalogo.items():
        baixado = status_map.get(mid, False)
        if apenas_baixados and not baixado:
            continue
        encontrou = True
        marca = "✓" if baixado else " "
        print(
            f"  [{marca}] id {mid}: {entrada['Modelo']} "
            f"({entrada.get('Quantizacao', '?')})"
        )

    if apenas_baixados and not encontrou:
        print("  (nenhum modelo baixado — use opção 2 ou 9 primeiro)")
        return None

    escolha = input(f"\nDigite o id (Enter para cancelar): ").strip()
    if not escolha:
        return None
    if escolha not in catalogo:
        print(f"✗ Id '{escolha}' inválido.")
        pausar()
        return None
    if apenas_baixados and not status_map.get(escolha):
        print(f"✗ Modelo id={escolha} ainda não foi baixado.")
        pausar()
        return None
    return escolha


def _escolher_ids(rotulo: str, base_dir: Path, *, apenas_baixados: bool = False) -> list[str]:
    """Seleciona um ou mais modelos por ids separados por vírgula."""
    primeiro = _escolher_id(rotulo, base_dir, apenas_baixados=apenas_baixados)
    if not primeiro:
        return []
    resto = input("Outros ids (separados por vírgula; Enter = nenhum): ").strip()
    if not resto:
        return [primeiro]
    catalogo = load_catalog()
    ids = [primeiro, *[item.strip() for item in resto.split(",") if item.strip()]]
    invalidos = [mid for mid in ids if mid not in catalogo]
    if invalidos:
        print(f"✗ Id(s) inválido(s): {', '.join(invalidos)}.")
        return []
    return list(dict.fromkeys(ids))


def _escolher_perfis() -> list:
    print("\nPerfis de inferência (protocolo):")
    for i, perfil in enumerate(DEFAULT_INFERENCE_PROFILES, 1):
        print(
            f"  {i}. {perfil.name}: temperature={perfil.temperature}, "
            f"top_p={perfil.top_p}, top_k={perfil.top_k}, "
            f"repeat_penalty={perfil.repeat_penalty}"
        )
    raw = input(
        "Perfis (números separados por vírgula; Enter = balanceado+criativo): "
    ).strip()
    if not raw:
        return list(DEFAULT_INFERENCE_PROFILES)
    try:
        indices = [int(item.strip()) for item in raw.split(",")]
        perfis = [DEFAULT_INFERENCE_PROFILES[i - 1] for i in indices]
    except (IndexError, ValueError):
        print("✗ Seleção de perfis inválida.")
        return []
    return list({perfil.name: perfil for perfil in perfis}.values())


def _listar_catalogo(base: Path) -> None:
    modelos = listar_modelos(base)
    print(f"\nCatálogo ({len(modelos)} modelos):")
    for m in modelos:
        status = "baixado" if m["baixado"] else "pendente"
        print(f"  id {m['id']:>2} [{status:8}] {m['repo_id']} ({m['quantizacao']})")
        if m["caminho"]:
            print(f"           → {m['caminho']}")


def _baixar_modelo(mid: str, base: Path) -> bool:
    entrada = load_catalog()[mid]
    local = caminho_gguf_local(entrada["Modelo"], entrada["Arquivo"], base)
    if local:
        print(f"\n✓ Modelo id={mid} já está em:\n  {local}")
        pausar()
        return True

    ok, erro_prep = preparar_download()
    if not ok and erro_prep:
        imprimir_erro(erro_prep)
        pausar()
        return False

    print(f"\nBaixando {entrada['Arquivo']}")
    print(f"  de {entrada['Modelo']}...")
    print("(pode demorar — depende do tamanho e da conexão)\n")

    try:
        caminho = baixar_por_id(mid, base)
        print(f"\n✓ Download concluído:\n  {caminho}")
        pausar()
        return True
    except Exception as exc:
        imprimir_erro(classificar_erro_download(exc))
        status, _ = status_hf()
        if status in (HFAuthStatus.SEM_TOKEN, HFAuthStatus.TOKEN_INVALIDO):
            print("\n  Deseja fazer login agora? [S/n]: ", end="")
            if input().strip().upper() != "N":
                if executar_login_hf():
                    print("\nTentando download novamente...")
                    try:
                        caminho = baixar_por_id(mid, base)
                        print(f"\n✓ Download concluído:\n  {caminho}")
                        pausar()
                        return True
                    except Exception as exc2:
                        imprimir_erro(classificar_erro_download(exc2))
        pausar()
        return False


def _perguntar_generation() -> dict:
    """Pergunta parâmetros de inferência. Enter mantém o default do cenário."""
    print("\nConfigurar parâmetros de inferência? [s/N]: ", end="")
    if input().strip().upper() != "S":
        return {}

    print(
        "\nParâmetros (Enter = default do cenário):\n"
        "  A: temperature=0, top_p=1, max_tokens=1024, repeat_penalty=1.1\n"
        "  B/C/D: temperature=0.7, top_p=0.9, max_tokens=1024, repeat_penalty=1.1"
    )
    campos: list[tuple[str, type]] = [
        ("temperature", float),
        ("top_p", float),
        ("repeat_penalty", float),
        ("max_tokens", int),
    ]
    overrides: dict = {}
    for nome, conv in campos:
        raw = input(f"  {nome}: ").strip()
        if not raw:
            continue
        try:
            overrides[nome] = conv(raw)
        except ValueError:
            print(f"  ✗ Valor inválido para {nome} — ignorado.")
    if overrides:
        print(f"\nOverrides ativos: {overrides}")
    else:
        print("\nNenhum override — usando defaults por cenário.")
    return overrides


def _executar_benchmark(model_ids: list[str], modo: ModoExecucao, models_dir: Path) -> None:
    from benchmark_slms.runner.calling import executar_matriz

    ok, faltando = dependencias_ok()
    if not ok:
        imprimir_erro(
            classificar_erro_execucao(
                ImportError(f"Dependências faltando: {', '.join(faltando)}")
            )
        )
        pausar()
        return

    modelo_paths: dict[str, str] = {}
    modelos: list[str] = []
    for model_id in model_ids:
        try:
            repo_id, gguf_path = resolver_modelo(model_id=model_id, base_dir=models_dir)
        except FileNotFoundError as exc:
            imprimir_erro(classificar_erro_execucao(exc))
            print("\n  Baixar agora? [S/n]: ", end="")
            if input().strip().upper() == "N" or not _baixar_modelo(model_id, models_dir):
                return
            repo_id, gguf_path = resolver_modelo(model_id=model_id, base_dir=models_dir)
        modelos.append(repo_id)
        modelo_paths[repo_id] = str(gguf_path)

    perfis = _escolher_perfis()
    if not perfis:
        pausar()
        return

    config = RunConfig(
        modelos=modelos,
        modo=modo,
        backend=BackendTipo.GGUF,
        modelo_paths=modelo_paths,
        inference_profiles=perfis,
    )

    from benchmark_slms.protocol import PROTOCOL_SEEDS

    n_seeds = len(PROTOCOL_SEEDS)
    print(
        f"\nExecutando {len(modelos)} modelo(s) × {len(perfis)} perfil(is) "
        f"× {n_seeds} seeds [{modo.value}]..."
    )
    print(f"Seeds do protocolo: {list(PROTOCOL_SEEDS)}")
    print("Aguarde — cenário B pode levar vários minutos...\n")

    try:
        resultados = executar_matriz(config)
    except Exception as exc:
        imprimir_erro(classificar_erro_execucao(exc))
        pausar()
        return

    for r in resultados:
        apto = r.veredito.apto_mathia if r.veredito else False
        print(f"\n{'='*50}")
        print(f"Modelo: {r.modelo}")
        print(f"apto_mathia: {'SIM ✓' if apto else 'NÃO ✗'}")
        if r.motivo_eliminacao:
            print(f"Motivo: {r.motivo_eliminacao}")
        slug = r.modelo.replace("/", "--")
        if r.formato == "gguf":
            slug += "-gguf"
        perfil = r.run_config.inference_profile.name if r.run_config.inference_profile else None
        print(f"Resultado: resultados/{slug}/{perfil or ''}")

    print("\n  Ver leaderboard agora? [S/n]: ", end="")
    if input().strip().upper() != "N":
        from benchmark_slms.report.aggregate import imprimir_leaderboard

        imprimir_leaderboard()

    print("  Ver quadro principal (artigo)? [S/n]: ", end="")
    if input().strip().upper() != "N":
        from benchmark_slms.report.aggregate import imprimir_quadro_principal

        imprimir_quadro_principal()

    pausar()


def _fluxo_completo(base: Path, modo: ModoExecucao) -> None:
    """Baixar (se necessário) + testar no modo informado — fluxo guiado."""
    if modo == ModoExecucao.SELECTION:
        print("\n--- Fluxo completo: baixar + testar [selection — para ao reprovar] ---")
    else:
        print("\n--- Fluxo completo: baixar + testar [benchmark — roda tudo] ---")

    mid = _escolher_id("modelo", base)
    if not mid:
        return

    entrada = load_catalog()[mid]
    if not caminho_gguf_local(entrada["Modelo"], entrada["Arquivo"], base):
        print("\n[1/2] Download...")
        if not _baixar_modelo(mid, base):
            return
    else:
        print(f"\n[1/2] Modelo id={mid} já baixado — pulando download.")

    print(f"\n[2/2] Benchmark (modo {modo.value})...")
    _executar_benchmark([mid], modo, base)


def _login_hf_menu() -> None:
    status, nome = status_hf()
    if status == HFAuthStatus.OK:
        print(f"\n✓ Já logado como {nome}.")
        print("  Refazer login? [s/N]: ", end="")
        if input().strip().upper() != "S":
            pausar()
            return

    if status == HFAuthStatus.TOKEN_INVALIDO:
        print("\n⚠ Token local detectado, mas inválido.")
        print("  Remover token antigo antes do login? [S/n]: ", end="")
        if input().strip().upper() != "N":
            remover_token_local()
            print("  Token removido.")

    executar_login_hf()
    pausar()


def _remover_token_menu() -> None:
    if remover_token_local():
        print("\n✓ Token removido de ~/.cache/huggingface/token")
    else:
        print("\n○ Nenhum token local encontrado.")
    pausar()


def _limpar_temporarios_menu(base: Path) -> None:
    from benchmark_slms.cleanup import limpar_temporarios, resumo_limpeza

    print("\n--- Limpar arquivos temporários ---")
    print("  a) Resultados (resultados/<modelo>/execucao_*.json)")
    print("  b) Logs (logs/*.jsonl, *.log)")
    print("  c) Cache Python (__pycache__)")
    print("  d) Cache HF (.cache em modelos_local_gguf/)")
    print("  e) Tudo acima (exceto .gguf)")
    print("  Enter — cancelar")

    escolha = input("\nO que remover? ").strip().lower()
    if not escolha:
        return

    mapa = {
        "a": dict(limpar_resultados=True, limpar_logs=False, limpar_pycache=False, limpar_hf_cache=False),
        "b": dict(limpar_resultados=False, limpar_logs=True, limpar_pycache=False, limpar_hf_cache=False),
        "c": dict(limpar_resultados=False, limpar_logs=False, limpar_pycache=True, limpar_hf_cache=False),
        "d": dict(limpar_resultados=False, limpar_logs=False, limpar_pycache=False, limpar_hf_cache=True),
        "e": dict(limpar_resultados=True, limpar_logs=True, limpar_pycache=True, limpar_hf_cache=True),
    }
    if escolha not in mapa:
        print("✗ Opção inválida.")
        pausar()
        return

    print("\n⚠ Modelos .gguf NÃO serão apagados.")
    confirma = input("Confirmar limpeza? [s/N]: ").strip().lower()
    if confirma != "s":
        print("Cancelado.")
        pausar()
        return

    relatorio = limpar_temporarios(
        models_dir=base,
        **mapa[escolha],
    )
    print("\n" + resumo_limpeza(relatorio))
    pausar()


def _explicar_resultados() -> None:
    print(
        """
--- Estrutura de resultados/ ---

Uma pasta por modelo, com execuções sequenciais:
  resultados/<repo-id-normalizado>-gguf/execucao_1.json
  resultados/<repo-id-normalizado>-gguf/execucao_2.json
  ...

Cada execucao_N.json:
  modelo, formato, data          — identificação da execução
  run_config                     — parâmetros brutos da run (seed, n_ctx, tasks, modo…)
  inferencia                     — params efetivos por cenário + overrides + backend
  ambiente                       — máquina (CPU, RAM, SO, Python)
  tasks                          — resultado bruto por cenário (A–D)
  veredito                       — apto_mathia derivado (nunca manual)
  eliminado, motivo_eliminacao   — espelho do veredito

tasks.<cenario_x>:
  json_valido, json_erro         — passou no schema? (validação por questão)
  agregado.questoes_invalidas    — questões descartadas com motivo
  agregado.questoes_validas      — quantas passaram no schema
  parsed                         — JSON validado (questões BNCC)
  viabilidade                    — RAM, TPS, tempos, crash
  agregado                       — métricas resumidas do cenário
  predictions[]                  — cada inferência (raw_output + metrics)

Cenários:
  A — cold start (1 questão, RAM + tempo de carga)
  B — 10 rodadas em série (TPS, taxa JSON, crashes)
  C — pressão JSON (até 3 tentativas, 5 questões)
  D — habilidades sem exemplo BNCC

veredito:
  apto_mathia                    — boolean final
  criterios[]                    — hard/soft com valor, limite, passou
  motivos_reprovacao[]           — por que reprovou
  categoria_falha                — hardware | formato | performance…

Logs detalhados: logs/<run_id>.jsonl (trilha por fase/task)
"""
    )
    pausar()


def menu_interativo(models_dir: Path | None = None) -> int:
    base = models_dir or Path(DEFAULT_MODELS_DIR)
    base.mkdir(parents=True, exist_ok=True)

    ok, faltando = dependencias_ok()
    if not ok:
        print("\n⚠ Dependências faltando:", ", ".join(faltando))
        print("  Instale antes de continuar:")
        print("    pip install pydantic psutil huggingface_hub llama-cpp-python\n")

    status, _ = status_hf()
    if status == HFAuthStatus.TOKEN_INVALIDO:
        print("\n⚠ Token Hugging Face inválido detectado.")
        print("  Downloads podem falhar — use opção 7 (Login) ou 8 (Remover token).\n")

    while True:
        print("\n" + "=" * 52)
        print("       benchmark-SLMs-INCT")
        print("=" * 52)
        print("  1  Listar catálogo de modelos")
        print("  2  Baixar modelo GGUF (Hugging Face)")
        print("  3  Testar modelo [selection — para ao reprovar]")
        print("  4  Testar modelo [benchmark — roda tudo]")
        print("  5  Ver leaderboard")
        print("  6  Listar tasks (cenários A–D)")
        print("  7  Login Hugging Face (hf auth login)")
        print("  8  Remover token HF inválido")
        print("  9  Fluxo completo: baixar + testar [selection — para ao reprovar]")
        print("  10 Fluxo completo: baixar + testar [benchmark — roda tudo]")
        print("  11 Verificar ambiente")
        print("  12 Limpar arquivos temporários")
        print("  13 Explicar estrutura dos resultados")
        print("  14 Ver quadro principal (tabela do artigo)")
        print("  0  Sair")
        print("-" * 52)

        opcao = input("Escolha: ").strip()

        try:
            if opcao == "0":
                print("\nAté logo!")
                return 0

            elif opcao == "1":
                _listar_catalogo(base)
                pausar()

            elif opcao == "2":
                mid = _escolher_id("modelo para baixar", base)
                if mid:
                    _baixar_modelo(mid, base)

            elif opcao == "3":
                ids = _escolher_ids("modelo para testar", base, apenas_baixados=False)
                if ids:
                    _executar_benchmark(ids, ModoExecucao.SELECTION, base)

            elif opcao == "4":
                ids = _escolher_ids("modelo para testar", base, apenas_baixados=False)
                if ids:
                    _executar_benchmark(ids, ModoExecucao.BENCHMARK, base)

            elif opcao == "5":
                from benchmark_slms.report.aggregate import imprimir_leaderboard

                imprimir_leaderboard()
                pausar()

            elif opcao == "14":
                from benchmark_slms.report.aggregate import imprimir_quadro_principal

                imprimir_quadro_principal()
                pausar()

            elif opcao == "6":
                from benchmark_slms.core.registry import list_tasks

                print("\nTasks registradas:")
                for t in list_tasks():
                    print(f"  - {t}")
                pausar()

            elif opcao == "7":
                _login_hf_menu()

            elif opcao == "8":
                _remover_token_menu()

            elif opcao == "9":
                _fluxo_completo(base, ModoExecucao.SELECTION)

            elif opcao == "10":
                _fluxo_completo(base, ModoExecucao.BENCHMARK)

            elif opcao == "11":
                imprimir_status_ambiente(base)
                pausar()

            elif opcao == "12":
                _limpar_temporarios_menu(base)

            elif opcao == "13":
                _explicar_resultados()

            else:
                print("\n✗ Opção inválida.")
                pausar()

        except KeyboardInterrupt:
            print("\n\nOperação cancelada.")
            pausar()

    return 0
