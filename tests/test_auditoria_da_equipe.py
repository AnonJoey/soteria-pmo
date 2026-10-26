"""A auditoria de apontamentos para quem gerencia, e nao so para quem lanca.

Retorno do Max em 26/10/2026: a auditoria trazia so os lancamentos dele, que nao
existem porque ele nao lanca hora, e o que ele queria era os devs que nao apontaram
no dia anterior. A causa era `cliente.entradas` sem `assignee`, que a API entende como
"so o usuario autenticado". Estes testes travam as duas coisas: que a equipe e lida
pela equipe inteira, e que a auditoria pessoal so roda para quem tem evidencia de maquina.
"""
from datetime import date, datetime, timezone

import pytest

from soteria_pmo import cli
from soteria_pmo import lancamentos as L

HOJE = date(2026, 10, 26)            # segunda: o dia util anterior e sexta 23/10
SEXTA = date(2026, 10, 23)


def entrada(quem, dia, horas=4.0):
    inicio = datetime(dia.year, dia.month, dia.day, 15, 0, tzinfo=timezone.utc)
    return {"id": f"{quem}{dia}", "user": {"username": quem}, "start": str(int(inicio.timestamp() * 1000)),
            "duration": str(int(horas * 3_600_000)), "task": {"id": "t"}}


class ClienteDaEquipe:
    def __init__(self, entradas, quebra=False):
        self._entradas = entradas
        self.pedidos = []
        self.quebra = quebra

    def membros(self):
        return [{"id": "1"}, {"id": "2"}, {"id": "3"}]

    def entradas(self, ini, fim, assignee=None):
        self.pedidos.append(assignee)
        if self.quebra:
            raise RuntimeError("api fora")
        return self._entradas if assignee else []   # sem assignee: so o autenticado, que aqui nao lancou nada

    def escopo_das_entradas(self, assignee):
        return "somente o usuario autenticado" if not assignee else f"{len(assignee)} pessoa(s) nomeada(s)"

    def tarefas_da_lista(self, *_a, **_k):
        return []


def historico():
    # Ana e Beto lancaram no mes; so a Ana lancou na sexta. Caio nunca lancou.
    return [entrada("Ana", SEXTA), entrada("Ana", date(2026, 10, 22)),
            entrada("Beto", date(2026, 10, 15)), entrada("Beto", date(2026, 10, 22))]


CFG_DO_MAX = {"team_id": "9", "pessoa": "Max", "projetos": [{"nome": "Soteria", "list_id": "L1"}],
              "equipe_lancamento": ["Ana", "Beto", "Caio"]}


def test_ultimos_dias_uteis_terminam_no_dia_util_anterior_e_pulam_feriado():
    assert L.ultimos_dias_uteis(HOJE) == [date(2026, 10, 19), date(2026, 10, 20), date(2026, 10, 21),
                                          date(2026, 10, 22), SEXTA]
    com_feriado = L.ultimos_dias_uteis(HOJE, 5, frozenset({date(2026, 10, 21)}))
    assert date(2026, 10, 21) not in com_feriado and com_feriado[-1] == SEXTA and len(com_feriado) == 5


def test_resumo_diz_quem_nao_lancou_no_dia_anterior_e_quem_nunca_lancou_nao_some():
    es = historico()
    ontem = L.apurar(es, [SEXTA], ["Ana", "Beto", "Caio"], historico=es)
    recentes = L.apurar(es, L.ultimos_dias_uteis(HOJE), ["Ana", "Beto", "Caio"], historico=es)
    texto = L.formatar_resumo(ontem, recentes)
    assert "1 de 3 lancaram" in texto
    assert "Sem lancamento: Beto, Caio." in texto
    assert "- Caio: 5 de 5" in texto           # quem nunca lancou aparece, com os cinco dias
    assert "Esperados: lista informada em equipe_lancamento" in texto


def test_auditor_de_quem_gerencia_traz_a_equipe_e_nao_os_proprios_lancamentos():
    cliente = ClienteDaEquipe(historico())
    saida = cli.montar_tarefas(CFG_DO_MAX, cliente, HOJE)["auditor"]()
    assert "Lancamentos da equipe" in saida and "Sem lancamento: Beto, Caio." in saida
    assert "Auditoria dos lancamentos" not in saida
    # a equipe foi lida pelo nome, nunca pelo usuario autenticado
    assert cliente.pedidos and all(p == ("1", "2", "3") for p in cliente.pedidos)


def test_sem_evidencia_de_maquina_nao_ha_fechamento_pessoal():
    tarefas = cli.montar_tarefas(CFG_DO_MAX, ClienteDaEquipe([]), HOJE)
    assert "auditor" in tarefas and "fechamento" not in tarefas


def test_com_evidencia_a_auditoria_pessoal_continua_e_diz_o_escopo(monkeypatch):
    monkeypatch.setattr(cli, "evidencia_do_periodo", lambda *_a, **_k: [])
    cfg = dict(CFG_DO_MAX, evidencia={"repos": ["x"]})
    cliente = ClienteDaEquipe(historico())
    tarefas = cli.montar_tarefas(cfg, cliente, HOJE)
    saida = tarefas["auditor"]()
    assert "Auditoria dos lancamentos de Max (escopo: somente o usuario autenticado)" in saida
    assert "Lancamentos da equipe" in saida
    assert "fechamento" in tarefas


def test_api_fora_nao_vira_equipe_em_dia():
    """Uma excecao deixa a rotina marcar o item como falho; um quadro vazio seria lido como saude."""
    with pytest.raises(RuntimeError):
        cli.montar_tarefas(CFG_DO_MAX, ClienteDaEquipe([], quebra=True), HOJE)["auditor"]()
