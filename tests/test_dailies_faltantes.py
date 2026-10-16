"""Dias uteis sem transcricao da daily: a funcao e o comando `dailies`."""

import json
from datetime import date

from soteria_pmo import cli, daily


def _nota(pasta, nome, titulo, falas=True):
    corpo = f'---\ntitle: "{titulo}"\n---\n\n## Resumo\nreuniao\n\n'
    if falas:
        corpo += "## Transcricao\n[0:10] Ana Silva: bom dia pessoal\n[0:30] Beto Souza: bom dia\n"
    (pasta / nome).write_text(corpo, encoding="utf-8")


def _pasta(tmp_path):
    pasta = tmp_path / "dailies"
    pasta.mkdir()
    # quinta 15/10 e sexta 16/10 tem transcricao; a de quarta 14/10 foi escrita em 16/10
    _nota(pasta, "2026-10-16-Daily Equipe Dev 2026-10-14 transcricao.md", "Daily Equipe Dev 2026-10-14 transcricao")
    _nota(pasta, "2026-10-16-Daily Equipe Dev 2026-10-15 transcricao.md", "Daily Equipe Dev 2026-10-15 transcricao")
    _nota(pasta, "2026-10-16-Daily Equipe Dev 2026-10-16 transcricao.md", "Daily Equipe Dev 2026-10-16 transcricao")
    return pasta


def test_dia_sem_nota_aparece_como_faltante(tmp_path):
    pasta = _pasta(tmp_path)
    faltam = daily.dias_sem_daily(pasta, date(2026, 10, 13), date(2026, 10, 16))
    assert faltam == [date(2026, 10, 13)]


def test_nota_que_so_resume_a_reuniao_nao_conta(tmp_path):
    """O resumo de 13/10 existia, sem falas, e o dia seguia sem transcricao."""
    pasta = _pasta(tmp_path)
    _nota(pasta, "2026-10-13-Daily Equipe Dev 2026-10-13_ resumo da transcricao.md",
          "Daily Equipe Dev 2026-10-13: resumo da transcricao", falas=False)
    assert daily.dias_sem_daily(pasta, date(2026, 10, 13), date(2026, 10, 13)) == [date(2026, 10, 13)]


def test_a_data_da_reuniao_vale_e_nao_a_data_em_que_a_nota_foi_escrita(tmp_path):
    pasta = _pasta(tmp_path)
    # as tres notas foram escritas em 16/10; so 16/10 tem a daily de 16/10
    assert daily.dias_sem_daily(pasta, date(2026, 10, 14), date(2026, 10, 14)) == []


def test_fim_de_semana_e_feriado_nao_contam(tmp_path):
    pasta = _pasta(tmp_path)
    # 10/10 e 11/10 sao fim de semana, 12/10 foi feriado
    faltam = daily.dias_sem_daily(pasta, date(2026, 10, 10), date(2026, 10, 12),
                                  frozenset({date(2026, 10, 12)}))
    assert faltam == []
    assert daily.dias_sem_daily(pasta, date(2026, 10, 12), date(2026, 10, 12)) == [date(2026, 10, 12)]


def test_transcricao_de_outra_reuniao_nao_vale_como_daily(tmp_path):
    pasta = _pasta(tmp_path)
    _nota(pasta, "2026-10-13-Alinhamento 2026-10-13.md", "Alinhamento de prioridades")
    assert daily.dias_sem_daily(pasta, date(2026, 10, 13), date(2026, 10, 13)) == [date(2026, 10, 13)]


def test_pasta_inexistente_deixa_todos_os_dias_uteis_faltando(tmp_path):
    faltam = daily.dias_sem_daily(tmp_path / "nao-existe", date(2026, 10, 15), date(2026, 10, 16))
    assert faltam == [date(2026, 10, 15), date(2026, 10, 16)]


def _config(tmp_path, pasta, feriados=()):
    cfg = tmp_path / "pmo.json"
    cfg.write_text(json.dumps({
        "token": "x", "team_id": "1", "projetos": [{"nome": "A", "list_id": "L"}],
        "feriados": list(feriados), "evidencia": {"dailies": str(pasta)}}), encoding="utf-8")
    return cfg


def test_comando_sai_com_2_e_lista_o_dia_que_falta(tmp_path, capsys):
    cfg = _config(tmp_path, _pasta(tmp_path))
    codigo = cli.main(["dailies", "--config", str(cfg), "--ate", "2026-10-16", "--dias", "4"])
    saida = capsys.readouterr().out
    assert codigo == 2
    assert "FALTA    ter 13/10" in saida and "ok       sex 16/10" in saida
    assert "Faltam 1 dia(s): 13/10" in saida and "docs/CAPTURA-DA-DAILY.md" in saida


def test_comando_sai_com_0_quando_esta_em_dia_e_mostra_o_feriado(tmp_path, capsys):
    cfg = _config(tmp_path, _pasta(tmp_path), feriados=["2026-10-12", "2026-10-13"])
    codigo = cli.main(["dailies", "--config", str(cfg), "--ate", "2026-10-16", "--dias", "5"])
    saida = capsys.readouterr().out
    assert codigo == 0
    assert "feriado  seg 12/10" in saida and "Todos os dias uteis" in saida


def test_comando_nao_escreve_nada_na_pasta(tmp_path):
    pasta = _pasta(tmp_path)
    antes = sorted(p.name for p in pasta.iterdir())
    cli.main(["dailies", "--config", str(_config(tmp_path, pasta)), "--ate", "2026-10-16"])
    assert sorted(p.name for p in pasta.iterdir()) == antes
