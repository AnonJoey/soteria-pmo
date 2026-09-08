"""Guarda de suite: nenhum teste escreve na config real da maquina.

Isto existe por causa de um estrago real, nao de uma preocupacao teorica.

Em 02/09/2026, na base de onde este pacote saiu, um teste chamou uma funcao
cujo ultimo passo era salvar a configuracao. O objeto de config nao sabe de
onde veio: um construido pelo teste com um caminho temporario grava por cima da
config real exatamente como o carregado dela gravaria. O resultado foi um
daemon apontando para `/tmp/pytest-of-joey/...`, servico fora do ar, e config
reescrita a mao.

A licao que viajou junto com o pacote: o perigo nao e o teste que se sabe
destrutivo, e a funcao que faz mais do que o nome dela cobre. Por isso a rede
abaixo e `autouse`, e nao um opt-in que cada autor de teste precise lembrar de
pedir.

Aqui a superficie e menor que a de origem, e por isso a guarda tambem e: este
pacote tem um arquivo de estado do usuario, `~/.soteria-pmo/pmo.json`, mais o
caminho antigo `~/.delegation_core/pmo.json` que a cli ainda le como segunda
opcao. Os dois carregam o token do ClickUp do workspace real, entao os dois sao
vigiados.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _sem_escrita_na_config_real(tmp_path, monkeypatch):
    """Reaponta o caminho de config do pacote para um diretorio temporario."""
    from soteria_pmo import cli as cli_mod

    raiz = tmp_path / "estado_soteria_pmo"
    raiz.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(cli_mod, "CONFIG_HOME", raiz, raising=False)
    monkeypatch.setattr(cli_mod, "CONFIG_PADRAO", raiz / "pmo.json", raising=False)
    # Tambem o caminho antigo: sem isto, um teste que exercitasse o desvio de
    # compatibilidade leria a config de verdade, com o token de verdade dentro.
    monkeypatch.setattr(cli_mod, "CONFIG_ANTIGO", raiz / "pmo-antigo.json", raising=False)

    yield raiz


@pytest.fixture(autouse=True)
def _config_real_intacta():
    """Rede de seguranca: falha o teste que ainda assim tocar a config real.

    O fixture acima cobre os caminhos conhecidos. Este cobre os que ninguem
    mapeou ainda, e falha o teste culpado em vez de deixar a maquina quebrada
    para quem for rodar a suite depois. O arquivo e devolvido antes da falha: o
    teste ja errou, a maquina de quem roda a suite nao precisa pagar por isso.
    """
    vigiados = [Path.home() / ".soteria-pmo" / "pmo.json",
                Path.home() / ".delegation_core" / "pmo.json"]
    antes = {p: (p.read_bytes() if p.exists() else None) for p in vigiados}

    yield

    for caminho, conteudo in antes.items():
        depois = caminho.read_bytes() if caminho.exists() else None
        if conteudo == depois:
            continue
        if conteudo is None:
            caminho.unlink(missing_ok=True)
        else:
            caminho.write_bytes(conteudo)
        pytest.fail(
            f"o teste escreveu em {caminho}. Nenhum teste toca o estado real da "
            "maquina: use o tmp_path que conftest._sem_escrita_na_config_real ja "
            "instalou. O arquivo foi restaurado."
        )
