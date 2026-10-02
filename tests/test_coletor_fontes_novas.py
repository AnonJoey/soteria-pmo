"""As fontes que entraram em 02/10/2026: Antigravity e agenda (por dado)."""

import json
import sys
from datetime import date, datetime

from soteria_pmo import coletor as C
from soteria_pmo.periodo import BRT

DIA = date(2026, 9, 28)


def _ms(h, m):
    return int(datetime(2026, 9, 28, h, m, tzinfo=BRT).timestamp() * 1000)


def test_antigravity_agrupa_os_pedidos_digitados(tmp_path):
    h = tmp_path / "history.jsonl"
    linhas = [
        {"display": "consegue conectar com o google chrome?", "timestamp": _ms(8, 39),
         "workspace": "/home/x"},
        {"display": "adicione a extensao ao fork", "timestamp": _ms(8, 50),
         "workspace": "/home/x"},
        {"display": "fora da janela", "timestamp": _ms(8, 50) + 3 * 86_400_000,
         "workspace": "/home/x"},
        "linha quebrada",
    ]
    h.write_text("\n".join(json.dumps(x) if isinstance(x, dict) else x for x in linhas))
    evs = C.antigravity(h, DIA, DIA)
    assert len(evs) == 1
    assert evs[0].tipo == "sessao_ia"
    assert evs[0].inicio == datetime(2026, 9, 28, 8, 39, tzinfo=BRT)
    assert "chrome" in evs[0].descricao


EVENTOS = [
    {"titulo": "Agentes CX", "inicio": "2026-09-28T09:00:00-03:00",
     "fim": "2026-09-28T09:30:00-03:00", "dia_inteiro": False, "status": "CONFIRMED"},
    {"titulo": "Dreamforce", "inicio": "2026-09-11T00:00:00-03:00",
     "fim": "2026-09-21T00:00:00-03:00", "dia_inteiro": True},
    {"titulo": "Dreamforce 2026 - San Francisco", "inicio": "2026-09-28T14:00:00-03:00",
     "fim": "2026-10-07T15:30:00-03:00", "dia_inteiro": False},
    {"titulo": "Recepcao", "inicio": "2026-09-28T19:00:00-07:00",
     "fim": "2026-09-28T21:30:00-07:00", "dia_inteiro": False},
    {"titulo": "Cancelada", "inicio": "2026-09-28T11:00:00-03:00",
     "fim": "2026-09-28T12:00:00-03:00", "status": "CANCELLED"},
]


def test_agenda_por_arquivo_ignora_dia_inteiro_e_cancelado(tmp_path):
    arq = tmp_path / "agenda.json"
    arq.write_text(json.dumps(EVENTOS))
    evs = C.agenda(str(arq), DIA, DIA)
    assert [e.descricao for e in evs] == ["agenda: Agentes CX", "agenda: Recepcao"]
    assert evs[0].tipo == "agenda" and evs[0].inferida
    assert evs[1].inicio == datetime(2026, 9, 28, 23, 0, tzinfo=BRT)


def test_agenda_por_comando_troca_as_datas(tmp_path):
    """O pacote nao importa o modulo `agenda`: chama um comando e le o JSON.
    Qualquer produtor que imprima o mesmo formato serve."""
    arq = tmp_path / "eventos.json"
    arq.write_text(json.dumps(EVENTOS))
    script = tmp_path / "produtor.py"
    script.write_text("import sys, pathlib\n"
                      "assert sys.argv[1] == '2026-09-28' and sys.argv[2] == '2026-09-28'\n"
                      f"print(pathlib.Path({str(arq)!r}).read_text())\n")
    evs = C.agenda(f"{sys.executable} {script} {{de}} {{ate}}", DIA, DIA)
    assert [e.descricao for e in evs] == ["agenda: Agentes CX", "agenda: Recepcao"]
