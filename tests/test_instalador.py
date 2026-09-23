"""De onde o instalador le as skills, e por que a pergunta importa.

Este arquivo nasceu de um defeito que passou pela entrega de 10/09/2026. O
`soteria-pmo-instalar` resolvia a raiz como `parents[2]` do proprio modulo, o
que da a raiz do checkout e so funciona em checkout. Instalado por wheel,
`parents[2]` cai dentro de `site-packages`, onde nao ha `skills/` nem
`agents/`, e o comando respondia "nada empacotado neste repo" para quem tinha
instalado o pacote exatamente como mandava a instrucao.

Nenhum teste cobria o instalador, e foi por isso que o defeito viajou: a suite
ficava verde porque em checkout o caminho unico era o certo. O que segue mede
as tres situacoes reais, com `HOME` desviado para um diretorio temporario.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from soteria_pmo import instalador as I


@pytest.fixture
def entrega(tmp_path: Path) -> Path:
    """Uma pasta de entrega com a forma da que vai para o cliente."""
    raiz = tmp_path / "Agentes-PMO"
    for nome in ("pmo-reporte", "pmo-bolsao"):
        (raiz / "skills" / nome).mkdir(parents=True)
        (raiz / "skills" / nome / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    (raiz / "agents").mkdir(parents=True)
    (raiz / "agents" / "pmo-horas.md").write_text("# agente\n", encoding="utf-8")
    return raiz


@pytest.fixture
def casa(tmp_path: Path, monkeypatch) -> Path:
    """`~` desviado: nenhum teste toca o ~/.claude real da maquina."""
    lar = tmp_path / "casa"
    lar.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: lar))
    return lar


def test_caminho_explicito_vence(entrega, casa):
    """Quem aponta a pasta nao depende de adivinhacao nenhuma."""
    assert I.raiz_provavel(entrega) == entrega
    r = I.instalar(entrega)
    assert sorted(r["skills"]["installed"]) == ["pmo-bolsao", "pmo-reporte"]
    assert r["agents"]["installed"] == ["pmo-horas"]
    assert (casa / ".claude" / "skills" / "pmo-reporte" / "SKILL.md").is_file()
    assert (casa / ".claude" / "agents" / "pmo-horas.md").is_file()


def test_sem_argumento_encontra_o_diretorio_atual(entrega, casa, monkeypatch):
    """O caso da wheel: `parents[2]` nao serve, e a pessoa esta dentro da pasta.

    E o modo de uso que a instrucao de instalacao descreve, entao e o que
    precisa funcionar sem nenhum argumento.
    """
    monkeypatch.chdir(entrega)
    assert I.raiz_provavel() == entrega
    r = I.instalar()
    assert r["skills"]["available"] and r["agents"]["available"]
    assert len(r["skills"]["installed"]) == 2


def test_sem_pasta_em_lugar_nenhum_nao_inventa_raiz(tmp_path, casa, monkeypatch):
    """Sem `skills/` nem `agents/` em parte alguma, o comando declara ausencia.

    As candidatas sao substituidas porque a suite roda dentro do checkout,
    onde a segunda candidata real existe e tem as pastas. E a situacao de quem
    instalou por wheel e rodou de um diretorio qualquer.
    """
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    monkeypatch.setattr(I, "_candidatas", lambda: (vazio, site_packages))

    r = I.instalar()
    assert r["skills"]["available"] is False
    assert r["agents"]["available"] is False
    assert r["skills"]["installed"] == []


def test_diretorio_atual_vence_a_raiz_do_pacote(entrega, tmp_path, casa, monkeypatch):
    """Estar dentro da pasta de entrega decide qual material e instalado.

    Um checkout do repo aberto ao lado nao pode sequestrar a instalacao: a
    segunda candidata aqui tem `skills/` e ainda assim perde.
    """
    outro = tmp_path / "checkout"
    (outro / "skills" / "pmo-outra").mkdir(parents=True)
    monkeypatch.setattr(I, "_candidatas", lambda: (entrega, outro))

    assert I.raiz_provavel() == entrega
    assert sorted(I.instalar()["skills"]["installed"]) == ["pmo-bolsao", "pmo-reporte"]


def test_nunca_sobrescreve_o_que_a_pessoa_ja_tem(entrega, casa):
    """A regra que o modulo inteiro existe para garantir, medida duas vezes."""
    I.instalar(entrega)
    marca = casa / ".claude" / "skills" / "pmo-reporte" / "SKILL.md"
    marca.write_text("# ajustada pela pessoa\n", encoding="utf-8")

    r = I.instalar(entrega)
    assert r["skills"]["installed"] == []
    assert sorted(r["skills"]["kept_yours"]) == ["pmo-bolsao", "pmo-reporte"]
    assert r["agents"]["kept_yours"] == ["pmo-horas"]
    assert marca.read_text(encoding="utf-8") == "# ajustada pela pessoa\n"


def test_main_com_pasta_inexistente_falha_em_vez_de_adivinhar(tmp_path, casa, capsys):
    """Um caminho errado e erro, nao um desvio silencioso para outra raiz."""
    codigo = I.main([str(tmp_path / "nao-existe")])
    assert codigo == 1
    assert "pasta nao encontrada" in capsys.readouterr().out


def test_main_instala_e_diz_de_onde_leu(entrega, casa, capsys):
    """A saida nomeia a raiz: sem isso, diagnosticar a ausencia e adivinhacao."""
    assert I.main([str(entrega)]) == 0
    saida = capsys.readouterr().out
    assert str(entrega) in saida
    assert "pmo-reporte" in saida
