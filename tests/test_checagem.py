"""A fronteira entre o que este pacote exige e o que ele so aproveita."""

from __future__ import annotations

import json
from datetime import date, timedelta

from soteria_pmo import checagem as C


def cfg_minimo(**extra):
    base = {"token": "pk_x", "team_id": "9007",
            "projetos": [{"nome": "Cliente", "space_id": "1", "horas_contratadas": 100}]}
    base.update(extra)
    return base


def test_so_o_clickup_e_obrigatorio():
    """Seis dos sete itens leem campo do ClickUp e fazem conta. Nada que venha
    da maquina pode ser requisito, e o delegation-core e tudo maquina."""
    c = C.checar(cfg_minimo(), modelo="http://127.0.0.1:1")
    obrigatorios = {i.nome for i in c.itens if i.obrigatorio}
    assert obrigatorios == {"ClickUp: token", "ClickUp: team_id", "Projetos configurados"}
    assert c.pronto, "sem nenhuma fonte de maquina, o pacote ainda esta pronto"


def test_sem_token_nada_roda():
    c = C.checar({"team_id": "9007", "projetos": [{"nome": "x"}]})
    assert not c.pronto
    assert "Nenhum item roda" in C.relatorio(c)


def test_cada_ausencia_vem_com_o_preco_dela():
    """Uma checagem que so lista verde e vermelho transfere para quem le o
    trabalho de saber o que cada vermelho custa."""
    c = C.checar(cfg_minimo(), modelo="http://127.0.0.1:1")
    for item in c.faltando_opcional:
        assert item.custo, f"{item.nome} sem custo declarado"
    texto = C.relatorio(c)
    assert "Nada disso e requisito" in texto


def test_o_vault_ausente_e_ausencia_e_nao_falha(tmp_path):
    c = C.checar(cfg_minimo(evidencia={"vault": str(tmp_path / "nao-existe")}),
                 modelo="http://127.0.0.1:1")
    (vault,) = [i for i in c.itens if i.nome == "Vault com as dailies"]
    assert not vault.presente and not vault.obrigatorio
    assert c.pronto


def test_conta_as_dailies_da_janela_e_diz_a_mais_recente(tmp_path):
    sessoes = tmp_path / "Sessions"
    sessoes.mkdir()
    hoje = date.today()
    for delta in (1, 3, 40):
        d = hoje - timedelta(days=delta)
        (sessoes / f"{d.isoformat()}-Daily-Equipe-Dev-transcricao.md").write_text("x")
    (sessoes / "2026-01-01-Outra-coisa.md").write_text("x")
    c = C.checar(cfg_minimo(evidencia={"vault": str(tmp_path)}), modelo="http://127.0.0.1:1")
    (vault,) = [i for i in c.itens if i.nome == "Vault com as dailies"]
    assert vault.presente
    assert "2 daily" in vault.detalhe, "a de 40 dias esta fora da janela"
    assert f"{hoje - timedelta(days=1):%d/%m}" in vault.detalhe


def test_roster_ausente_desliga_o_item_de_rh_sem_derrubar_o_resto():
    c = C.checar(cfg_minimo(), modelo="http://127.0.0.1:1")
    (roster,) = [i for i in c.itens if i.nome == "Roster de RH"]
    assert not roster.presente
    assert "nao roda" in roster.custo
    assert c.pronto


def test_contagem_de_teto_bate_com_o_que_o_vigia_realmente_vigia():
    """A checagem contava so `horas_contratadas` e ignorava os tetos do codigo.

    Dizia "4 com teto" num config onde o bolsao vigiava 8, porque o vigia cai
    para `TETOS_DE_REFERENCIA` e a checagem nao caia. Uma ferramenta que existe
    para dizer o que falta nao pode inventar uma falta. O teste compara as duas
    leituras em vez de fixar um numero, que e o que impede a dupla contagem de
    voltar.
    """
    from soteria_pmo import bolsao as B

    projetos = [
        {"nome": "China Gate", "space_id": "1"},        # teto so no codigo
        {"nome": "Grupo Angelus", "space_id": "2"},     # teto so no codigo
        {"nome": "Soteria", "space_id": "3", "horas_contratadas": 1800},
        {"nome": "Concessionaria Reviver", "space_id": "4"},  # sem teto
    ]
    c = C.checar(cfg_minimo(projetos=projetos), modelo="http://127.0.0.1:1")
    item = next(i for i in c.itens if i.nome == "Projetos configurados")

    vigiados, sem_teto = B.carregar_bolsoes(projetos)
    assert len(vigiados) == 3, "duas do codigo mais uma do config"
    assert f"{len(vigiados)} com teto" in item.detalhe
    assert f"{len(sem_teto)} sem" in item.detalhe
    assert "4 cliente(s)" in item.detalhe


def test_sem_nenhum_projeto_sem_teto_a_linha_nao_ganha_sufixo():
    """Nao anunciar "0 sem": ruido que faz o leitor procurar o que nao existe."""
    c = C.checar(cfg_minimo(projetos=[{"nome": "China Gate", "space_id": "1"}]),
                 modelo="http://127.0.0.1:1")
    item = next(i for i in c.itens if i.nome == "Projetos configurados")
    assert item.detalhe == "1 cliente(s), 1 com teto"
