"""`soteria-pmo atualizar`: o que ele faz com um clone de verdade.

Os testes usam repositorios git reais em pasta temporaria (um remoto, o clone de
quem usa e um segundo clone que publica a versao nova). So o `pip` e trocado por
um registro de chamadas: reinstalar o pacote dentro da suite mexeria no ambiente
de quem roda os testes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from soteria_pmo import atualizacao as A
from soteria_pmo import instalador as I


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=cwd, capture_output=True, text=True, check=True)
    return r.stdout.strip()


def _publica(raiz: Path, versao: str, skill: str) -> None:
    (raiz / "pyproject.toml").write_text(
        f'[project]\nname = "soteria-pmo"\nversion = "{versao}"\n', encoding="utf-8")
    (raiz / "skills" / "pmo-bolsao").mkdir(parents=True, exist_ok=True)
    (raiz / "skills" / "pmo-bolsao" / "SKILL.md").write_bytes(skill.encode())
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", f"v{versao}")


@pytest.fixture
def mundo(tmp_path: Path, monkeypatch):
    """Remoto com a 1.0.0, o clone da pessoa e um clone que publica a 1.1.0."""
    casa = tmp_path / "casa"
    casa.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: casa))
    remoto = tmp_path / "remoto.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remoto))
    semente = tmp_path / "semente"
    _git(tmp_path, "clone", "-q", str(remoto), str(semente))
    _git(semente, "checkout", "-q", "-b", "main")
    _publica(semente, "1.0.0", "# skill velha\n")
    _git(semente, "push", "-q", "origin", "main")
    usuario = tmp_path / "usuario"
    _git(tmp_path, "clone", "-q", str(remoto), str(usuario))
    return {"casa": casa, "semente": semente, "usuario": usuario}


def _sem_pip():
    chamadas: list[list[str]] = []

    def rodar(cmd, **kw):
        if "pip" in cmd:
            chamadas.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.run(cmd, **kw)

    return rodar, chamadas


def _publica_nova(mundo) -> None:
    _publica(mundo["semente"], "1.1.0", "# skill nova\n")
    _git(mundo["semente"], "push", "-q", "origin", "main")


def test_verificar_conta_os_commits_e_nao_muda_nada(mundo):
    _publica_nova(mundo)
    rodar, pip = _sem_pip()
    r = A.atualizar(mundo["usuario"], so_verificar=True, rodar=rodar)
    assert r["status"] == "verificado"
    assert r["atras"] == 1
    assert A.versao_em(mundo["usuario"]) == "1.0.0"
    assert pip == []
    assert not (mundo["casa"] / ".claude").exists()


def test_atualizar_baixa_reinstala_e_troca_a_skill_nossa(mundo):
    """O caminho inteiro: pull, pip e a skill velha (versao nossa) trocada."""
    rodar, pip = _sem_pip()
    # A skill velha ja esta instalada e e uma versao entregue por nos.
    I.install_skills(mundo["usuario"])
    antiga = mundo["casa"] / ".claude" / "skills" / "pmo-bolsao" / "SKILL.md"
    assert antiga.read_text(encoding="utf-8") == "# skill velha\n"
    _publica_nova(mundo)
    entregues = {"skills/pmo-bolsao/SKILL.md": {I._hash(antiga)}}
    original = I.versoes_entregues
    I.versoes_entregues = lambda: entregues
    try:
        r = A.atualizar(mundo["usuario"], rodar=rodar)
    finally:
        I.versoes_entregues = original
    assert r["status"] == "atualizado"
    assert (r["versao_antes"], r["versao_depois"]) == ("1.0.0", "1.1.0")
    assert A.versao_em(mundo["usuario"]) == "1.1.0"
    assert len(pip) == 1 and pip[0][-2:] == ["-e", str(mundo["usuario"])]
    assert antiga.read_text(encoding="utf-8") == "# skill nova\n"
    assert r["copiado"]["skills"]["updated"] == ["pmo-bolsao"]


def test_skill_que_a_pessoa_alterou_fica_e_a_nova_vai_ao_lado(mundo):
    rodar, _ = _sem_pip()
    I.install_skills(mundo["usuario"])
    minha = mundo["casa"] / ".claude" / "skills" / "pmo-bolsao" / "SKILL.md"
    minha.write_text("# minha versao\n", encoding="utf-8")
    _publica_nova(mundo)
    r = A.atualizar(mundo["usuario"], rodar=rodar)
    assert r["status"] == "atualizado"
    assert minha.read_text(encoding="utf-8") == "# minha versao\n"
    assert (minha.parent / "SKILL.md.novo").read_text(encoding="utf-8") == "# skill nova\n"
    assert r["copiado"]["skills"]["kept_yours"] == ["pmo-bolsao"]


def test_em_dia_nao_baixa_nem_reinstala_mas_copia_o_que_falta(mundo):
    """Sem commit novo o pip nao roda; a copia das skills roda mesmo assim."""
    rodar, pip = _sem_pip()
    r = A.atualizar(mundo["usuario"], rodar=rodar)
    assert r["status"] == "em_dia"
    assert pip == []
    assert r["copiado"]["skills"]["installed"] == ["pmo-bolsao"]


def test_alteracao_local_recusa_e_nao_toca_em_nada(mundo):
    _publica_nova(mundo)
    (mundo["usuario"] / "pyproject.toml").write_text("# meu ajuste\n", encoding="utf-8")
    rodar, pip = _sem_pip()
    r = A.atualizar(mundo["usuario"], rodar=rodar)
    assert r["status"] == "alteracao_local"
    assert "pyproject.toml" in r["detalhe"]
    assert (mundo["usuario"] / "pyproject.toml").read_text(encoding="utf-8") == "# meu ajuste\n"
    assert pip == []


def test_arquivo_nao_rastreado_nao_bloqueia(mundo):
    """Um arquivo novo qualquer (o .venv, por exemplo) nao e alteracao rastreada."""
    _publica_nova(mundo)
    (mundo["usuario"] / "anotacao.txt").write_text("oi\n", encoding="utf-8")
    rodar, _ = _sem_pip()
    assert A.atualizar(mundo["usuario"], rodar=rodar)["status"] == "atualizado"


def test_historia_que_nao_avanca_em_linha_reta_falha_sem_reinstalar(mundo, monkeypatch):
    """Commit local mais commit remoto: o ff-only nao serve, e quem junta e a pessoa.

    `pull.rebase=false` e a configuracao de quem ja pediu ao git para juntar
    sozinho: sem o `--ff-only` o pull teria feito o merge calado. Fica
    explicito porque, sem config, o git recente recusa por conta propria e o
    teste passaria sem provar nada.
    """
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "pull.rebase")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "false")
    (mundo["usuario"] / "extra.txt").write_text("meu\n", encoding="utf-8")
    _git(mundo["usuario"], "add", "-A")
    _git(mundo["usuario"], "commit", "-q", "-m", "local")
    _publica_nova(mundo)
    rodar, pip = _sem_pip()
    r = A.atualizar(mundo["usuario"], rodar=rodar)
    assert r["status"] == "falhou"
    assert pip == []
    assert A.versao_em(mundo["usuario"]) == "1.0.0"
    assert (mundo["usuario"] / "extra.txt").is_file()


def test_falha_do_pip_para_e_diz(mundo):
    _publica_nova(mundo)

    def rodar(cmd, **kw):
        if "pip" in cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "sem rede")
        return subprocess.run(cmd, **kw)

    r = A.atualizar(mundo["usuario"], rodar=rodar)
    assert r["status"] == "falhou"
    assert "sem rede" in r["detalhe"]
    assert not (mundo["casa"] / ".claude").exists()


def test_sem_rede_diz_que_nao_conseguiu_conferir(mundo):
    _git(mundo["usuario"], "remote", "set-url", "origin", str(mundo["usuario"].parent / "nao-existe.git"))
    rodar, pip = _sem_pip()
    r = A.atualizar(mundo["usuario"], rodar=rodar)
    assert r["status"] == "sem_rede"
    assert pip == []


def test_ramo_sem_remoto_acompanhado(mundo):
    _git(mundo["usuario"], "checkout", "-q", "-b", "solto")
    rodar, _ = _sem_pip()
    assert A.atualizar(mundo["usuario"], rodar=rodar)["status"] == "sem_ramo_acompanhado"


def test_instalado_por_wheel_nao_e_checkout(tmp_path, monkeypatch):
    assert A.raiz_do_checkout(tmp_path) is None
    monkeypatch.setattr(A, "raiz_do_checkout", lambda a_partir_de=None: None)
    assert A.atualizar()["status"] == "sem_checkout"


def test_comando_atualizar_existe_e_so_verifica_com_a_flag(mundo, monkeypatch, capsys):
    from soteria_pmo import cli

    _publica_nova(mundo)
    monkeypatch.setattr(A, "raiz_do_checkout", lambda a_partir_de=None: mundo["usuario"])
    assert cli.main(["atualizar", "--verificar"]) == 0
    assert "1 commit(s) para baixar." in capsys.readouterr().out
    assert A.versao_em(mundo["usuario"]) == "1.0.0"
