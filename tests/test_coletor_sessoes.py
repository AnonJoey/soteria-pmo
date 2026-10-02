"""Sessao de IA: o que a pessoa acompanhou e o que o agente fez sozinho."""

import json
from datetime import date, datetime, timedelta, timezone

from soteria_pmo import coletor as C
from soteria_pmo.periodo import BRT


def _z(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _sessao(tmp_path, registros):
    pasta = tmp_path / "projects" / "-home-x"
    pasta.mkdir(parents=True)
    with (pasta / "abc12345.jsonl").open("w") as fh:
        for r in registros:
            fh.write(json.dumps(r) + "\n")
    return tmp_path / "projects"


def digitado(dt, texto="faz o job"):
    return {"type": "user", "timestamp": _z(dt), "cwd": "/home/x/Projects/cliente",
            "message": {"role": "user", "content": texto}}


def agente(dt):
    return {"type": "assistant", "timestamp": _z(dt), "cwd": "/home/x/Projects/cliente",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}}


def resultado_de_ferramenta(dt):
    """Registro `user` que nao foi digitado: e a volta de uma ferramenta."""
    return {"type": "user", "timestamp": _z(dt), "cwd": "/home/x/Projects/cliente",
            "message": {"role": "user", "content": [{"type": "tool_result", "content": "x"}]}}


def test_job_noturno_vira_sessao_autonoma_e_nao_sessao_acompanhada(tmp_path):
    """Medido em setembro de 2026: as noites de 24 para 25 e de 25 para 26/09
    entraram como janelas de 9,5h e 9,9h de sessao de IA, com a mesma forca de
    trabalho acompanhado. Eram o agente rodando sozinho depois de um pedido."""
    t0 = datetime(2026, 9, 24, 23, 0, tzinfo=BRT)
    regs = [digitado(t0)]
    regs += [agente(t0 + timedelta(minutes=m)) for m in range(1, 180, 5)]
    regs += [resultado_de_ferramenta(t0 + timedelta(minutes=m)) for m in range(3, 180, 5)]
    raiz = _sessao(tmp_path, regs)

    evs = C.sessoes_ia(raiz, date(2026, 9, 24), date(2026, 9, 25))
    acompanhadas = [e for e in evs if e.tipo == "sessao_ia"]
    autonomas = [e for e in evs if e.tipo == "sessao_ia_autonoma"]

    limite = C.ATENCAO + timedelta(minutes=5)
    assert sum((e.fim - e.inicio).total_seconds() for e in acompanhadas) <= limite.total_seconds()
    assert autonomas and autonomas[0].inicio >= t0 + C.ATENCAO
    assert autonomas[-1].fim >= t0 + timedelta(hours=2, minutes=50)


def test_conversa_continua_fica_toda_acompanhada(tmp_path):
    t0 = datetime(2026, 9, 29, 10, 0, tzinfo=BRT)
    regs = []
    for m in range(0, 90, 10):
        regs += [digitado(t0 + timedelta(minutes=m)), agente(t0 + timedelta(minutes=m + 2))]
    raiz = _sessao(tmp_path, regs)

    evs = C.sessoes_ia(raiz, date(2026, 9, 29), date(2026, 9, 29))
    assert evs and all(e.tipo == "sessao_ia" for e in evs)


def test_registros_injetados_pelo_harness_nao_contam_como_digitados(tmp_path):
    """Medido na noite de 26 para 27/09/2026: o resumo de compactacao e a
    retomada por limite de uso chegam como `user` e abriam atencao no meio de
    um job autonomo."""
    t0 = datetime(2026, 9, 26, 23, 47, tzinfo=BRT)
    resumo = digitado(t0 + timedelta(hours=4), "This session is being continued")
    resumo["isCompactSummary"] = True
    retomada = digitado(t0 + timedelta(hours=3), "Your usage limit has reset")
    retomada["origin"] = {"kind": "auto-continuation"}
    agendada = digitado(t0 + timedelta(hours=2), "Continue o trabalho do runbook")
    agendada["scheduledTaskId"] = "x"
    humano = digitado(t0)
    humano["origin"] = {"kind": "human"}
    regs = [humano, agendada, retomada, resumo]
    regs += [agente(t0 + timedelta(minutes=m)) for m in range(1, 300, 5)]
    raiz = _sessao(tmp_path, regs)

    evs = C.sessoes_ia(raiz, date(2026, 9, 26), date(2026, 9, 27))
    acompanhado = sum((e.fim - e.inicio).total_seconds() for e in evs if e.tipo == "sessao_ia")
    assert acompanhado <= 50 * 60
