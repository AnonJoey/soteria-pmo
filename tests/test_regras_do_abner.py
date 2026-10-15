"""Regras confirmadas em 14/10/2026: quem lanca horas e o nascimento do cadastro do ClickUp.

Os dados abaixo sao sinteticos. O cadastro real tem, ao lado da data de nascimento, contato de
emergencia, e-mail e telefone pessoais, endereco e respostas sobre saude: o teste de privacidade
garante que so nome e nascimento atravessam.
"""

import csv
import os
import stat
from datetime import date, datetime, timezone

import pytest

from soteria_pmo import lancamentos as L
from soteria_pmo import rh

H = 3_600_000


def ms(ano, mes, dia, hora=12):
    return int(datetime(ano, mes, dia, hora, tzinfo=timezone.utc).timestamp() * 1000)


def entrada(quem, dia, horas, faturavel):
    return {"user": {"username": quem}, "start": str(ms(2026, 10, dia)), "duration": str(int(horas * H)),
            "billable": faturavel}


# ── faturavel de quem so lanca nao faturavel ─────────────────────────────────

DIAS = [date(2026, 10, 13), date(2026, 10, 14)]


def test_soma_so_o_faturavel_de_quem_esta_em_nao_faturam_dentro_dos_dias():
    entradas = [
        entrada("Pessoa Gestora", 13, 2, True),
        entrada("Pessoa Gestora", 14, 1.5, True),
        entrada("Pessoa Gestora", 14, 4, False),     # nao faturavel: e o esperado
        entrada("Pessoa Gestora", 12, 9, True),      # fora dos dias pedidos
        entrada("Outra Pessoa", 13, 8, True),             # faturavel, mas ela nao esta na regra
    ]
    assert L.faturaveis_de_quem_nao_fatura(entradas, ["Pessoa Gestora"], DIAS) == {"Pessoa Gestora": 3.5}


def test_nome_casa_sem_acento_e_sem_caixa_e_por_e_mail_quando_nao_ha_username():
    entradas = [entrada("Andre Aguiar", 13, 1, True),
                {"user": {"username": None, "email": "gestor.dois@exemplo.com"}, "start": str(ms(2026, 10, 13)),
                 "duration": str(2 * H), "billable": True}]
    achado = L.faturaveis_de_quem_nao_fatura(entradas, ["ANDRÉ AGUIAR", "gestor.dois@exemplo.com"], DIAS)
    assert achado == {"Andre Aguiar": 1.0, "gestor.dois@exemplo.com": 2.0}


def test_sem_nada_faturavel_o_texto_diz_que_nao_ha():
    assert "Nenhuma entrada faturavel" in L.formatar_faturaveis_indevidos({}, ["Pessoa Gestora"])


def test_o_texto_lista_a_pessoa_e_as_horas():
    texto = L.formatar_faturaveis_indevidos({"Pessoa Gestora": 3.5}, ["Pessoa Gestora"])
    assert "Pessoa Gestora: 3,5 h faturaveis" in texto


def test_quem_esta_em_nao_faturam_continua_sendo_cobrado_de_lancar():
    """A regra e sobre faturavel, nao isencao: `esperados` manda, e a pessoa aparece no quadro."""
    entradas = [entrada("Pessoa Gestora", 13, 1, False)]
    q = L.apurar(entradas, [date(2026, 10, 14)], ["Pessoa Gestora", "Outra Pessoa"])
    assert q.sem_lancamento(date(2026, 10, 14)) == ["Outra Pessoa", "Pessoa Gestora"]


# ── nascimento do cadastro do ClickUp ────────────────────────────────────────

SEGREDOS = ["Rua Exemplo 123", "maria.pessoal@exemplo.com", "+55 41 99999-0000", "Contato Emergencia Sigiloso",
            "faco terapia toda semana"]


def tarefa(nome, nascimento_ms):
    """Como o cadastro real: o nome da tarefa e a pessoa; o responsavel e quem cuida do cadastro."""
    return {
        "id": nome, "name": nome, "assignees": [{"username": "Quem Cuida Do Cadastro"}],
        "custom_fields": [
            {"name": "Contato de emergência", "type": "text", "value": SEGREDOS[3]},
            {"name": "Data de nascimento", "type": "date", "value": str(nascimento_ms) if nascimento_ms else None},
            {"name": "E-mail pessoal", "type": "email", "value": SEGREDOS[1]},
            {"name": "Endereço", "type": "location", "value": {"formatted_address": SEGREDOS[0]}},
            {"name": "Telefone pessoal", "type": "phone", "value": SEGREDOS[2]},
            {"name": "Acompanho minha saúde mental com profissional", "type": "drop_down", "value": SEGREDOS[4]},
        ],
    }


def test_le_so_nome_e_nascimento():
    pessoas, sem_data = rh.pessoas_do_clickup([tarefa("Maria Exemplo", ms(1994, 9, 5, 7)), tarefa("Joao Teste", None)])
    assert [(p.nome, p.nascimento) for p in pessoas] == [("Maria Exemplo", date(1994, 9, 5)), ("Joao Teste", None)]
    assert sem_data == ["Joao Teste"]


def test_a_data_e_a_do_dia_em_utc_mesmo_quando_a_meia_noite_foi_em_outro_fuso():
    """03:00, 06:00 e 07:00 UTC, os tres horarios vistos no cadastro real, caem no mesmo dia."""
    for hora in (3, 6, 7):
        pessoas, _ = rh.pessoas_do_clickup([tarefa("Maria Exemplo", ms(1990, 1, 20, hora))])
        assert pessoas[0].nascimento == date(1990, 1, 20)


def test_a_pessoa_e_o_nome_da_tarefa_e_nao_o_responsavel():
    """No cadastro real as 17 tarefas tem o MESMO responsavel (quem cuida do cadastro); usar o
    responsavel colapsava a equipe inteira numa pessoa so."""
    pessoas, _ = rh.pessoas_do_clickup([tarefa("Maria Exemplo", ms(1994, 9, 5)), tarefa("Joao Teste", ms(1990, 1, 20))])
    assert [p.nome for p in pessoas] == ["Maria Exemplo", "Joao Teste"]
    assert "Quem Cuida Do Cadastro" not in repr(pessoas)


def test_valor_ilegivel_vira_sem_data_e_nao_derruba():
    t = tarefa("Maria Exemplo", None)
    t["custom_fields"][1]["value"] = "nao e numero"
    pessoas, sem_data = rh.pessoas_do_clickup([t])
    assert pessoas[0].nascimento is None and sem_data == ["Maria Exemplo"]


def test_nenhum_dado_pessoal_alem_de_nome_e_nascimento_chega_ao_arquivo(tmp_path):
    pessoas, _ = rh.pessoas_do_clickup([tarefa("Maria Exemplo", ms(1994, 9, 5, 7))])
    destino = rh.escrever_roster(pessoas, tmp_path / "rh.csv")
    conteudo = destino.read_text(encoding="utf-8")
    for segredo in SEGREDOS:
        assert segredo not in conteudo and segredo not in repr(pessoas)
    assert conteudo.splitlines()[0] == ",".join(rh.COLUNAS_ROSTER)


def test_o_arquivo_sai_com_permissao_600_e_volta_pelo_carregador(tmp_path):
    destino = rh.escrever_roster([rh.Pessoa("Maria Exemplo", nascimento=date(1994, 9, 5))], tmp_path / "x" / "rh.csv")
    assert stat.S_IMODE(os.stat(destino).st_mode) == 0o600
    assert [(p.nome, p.nascimento) for p in rh.carregar(destino)] == [("Maria Exemplo", date(1994, 9, 5))]
    assert list(destino.parent.glob(".rh-*")) == [], "nao deixa arquivo temporario"


def test_mesclar_poe_o_nascimento_do_clickup_e_guarda_as_outras_datas():
    antigo = [rh.Pessoa("Maria Exemplo", nascimento=date(1990, 1, 1), inicio_contrato=date(2026, 3, 2), fim_contrato=date(2027, 3, 1)),
              rh.Pessoa("Saiu Do Cadastro", nascimento=date(1980, 2, 2))]
    lidas = [rh.Pessoa("MARIA EXEMPLO", nascimento=date(1994, 9, 5)), rh.Pessoa("Nova Pessoa", nascimento=date(2000, 5, 5)),
             rh.Pessoa("Sem Data", nascimento=None)]
    final = {p.nome: p for p in rh.mesclar(antigo, lidas)}
    maria = final["Maria Exemplo"]
    assert maria.nascimento == date(1994, 9, 5) and maria.inicio_contrato == date(2026, 3, 2) and maria.fim_contrato == date(2027, 3, 1)
    assert "Saiu Do Cadastro" in final, "sair do cadastro do ClickUp nao diz que saiu do time"
    assert final["Nova Pessoa"].nascimento == date(2000, 5, 5) and final["Sem Data"].nascimento is None


def test_mesclar_sem_data_na_lista_nao_apaga_o_nascimento_que_ja_estava():
    final = rh.mesclar([rh.Pessoa("Maria Exemplo", nascimento=date(1994, 9, 5))], [rh.Pessoa("Maria Exemplo", nascimento=None)])
    assert final[0].nascimento == date(1994, 9, 5)


def test_o_roster_so_com_nascimento_alimenta_o_aviso_de_aniversario():
    pessoas = [rh.Pessoa("Maria Exemplo", nascimento=date(1994, 10, 18))]
    texto = rh.digest(pessoas, date(2026, 10, 15))
    assert "Maria Exemplo: aniversario em 3d" in texto


def test_erro_no_meio_da_escrita_nao_deixa_temporario_nem_roster_pela_metade(tmp_path):
    destino = tmp_path / "rh.csv"
    rh.escrever_roster([rh.Pessoa("Maria Exemplo", nascimento=date(1994, 9, 5))], destino)
    antes = destino.read_text(encoding="utf-8")
    quebrada = rh.Pessoa("Joao Teste", nascimento="isto nao e uma data")   # sem isoformat: falha na escrita
    with pytest.raises(AttributeError):
        rh.escrever_roster([quebrada], destino)
    assert destino.read_text(encoding="utf-8") == antes, "o roster que ja existia fica como estava"
    assert list(tmp_path.glob(".rh-*")) == []
