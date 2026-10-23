"""O briefing do dia e o painel em HTML, nunca o .md convertido (pedido do Max, 23/10/2026)."""
from datetime import date
from pathlib import Path

from soteria_pmo import cli, painel

HOJE = date(2026, 10, 23)
HTML = "<html>painel de marca</html>"


def _casa(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    monkeypatch.chdir(tmp_path)


def test_briefing_grava_o_nome_que_a_rotina_do_max_abre(tmp_path, monkeypatch):
    _casa(tmp_path, monkeypatch)
    escritos = painel.gravar_briefing(HTML, HOJE, {})
    rel = tmp_path / "home" / ".soteria-pmo" / "relatorios"
    assert escritos[0] == tmp_path / "home" / ".soteria-pmo" / "reportes" / "painel-2026-10-23.html"
    for nome in ("2026-10-23.html", "2026-10-23-painel.html", "painel-2026-10-23.html"):
        assert (rel / nome).read_text(encoding="utf-8") == HTML


def test_briefing_respeita_diretorio_do_config_e_relatorios_do_cwd(tmp_path, monkeypatch):
    _casa(tmp_path, monkeypatch)
    (tmp_path / "relatorios").mkdir()
    alvo = tmp_path / "outro"
    painel.gravar_briefing(HTML, HOJE, {"diretorio_relatorios": str(alvo)})
    assert (alvo / "2026-10-23.html").read_text(encoding="utf-8") == HTML
    assert (tmp_path / "relatorios" / "2026-10-23.html").read_text(encoding="utf-8") == HTML


def test_briefing_com_saida_explicita_ainda_espelha(tmp_path, monkeypatch):
    _casa(tmp_path, monkeypatch)
    destino = tmp_path / "x" / "meu.html"
    assert painel.gravar_briefing(HTML, HOJE, {}, destino)[0] == destino
    assert destino.read_text(encoding="utf-8") == HTML
    assert (tmp_path / "home" / ".soteria-pmo" / "relatorios" / "2026-10-23.html").exists()


def test_falha_na_copia_nao_derruba_o_painel(tmp_path, monkeypatch):
    _casa(tmp_path, monkeypatch)
    arquivo = tmp_path / "e_um_arquivo"
    arquivo.write_text("x")
    escritos = painel.gravar_briefing(HTML, HOJE, {"diretorio_relatorios": str(arquivo)})
    assert escritos[0].read_text(encoding="utf-8") == HTML


def test_comando_painel_e_o_rodar_usam_o_mesmo_gravador():
    import inspect
    assert "gravar_briefing" in inspect.getsource(cli.cmd_painel)
    assert "gravar_briefing" in inspect.getsource(cli.montar_tarefas)


def test_padrao_do_filtro_vem_da_flag_ou_do_config():
    assert cli._fat_padrao({}) is False
    assert cli._fat_padrao({}, True) is True
    assert cli._fat_padrao({"painel_somente_faturaveis": True}) is True
    assert cli._fat_padrao({"bolsao_somente_faturaveis": True}) is True


def test_painel_leva_o_padrao_no_payload_e_o_modelo_o_usa():

    assert painel.montar_dados(_Nada(), [], HOJE, fat_padrao=True)["filtro_fat_padrao"] is True
    assert painel.montar_dados(_Nada(), [], HOJE)["filtro_fat_padrao"] is False
    modelo = (Path(painel.__file__).parent / "painel_modelo.html").read_text(encoding="utf-8")
    assert "filtroFat=!!D.filtro_fat_padrao" in modelo
    assert "if(fSalvo!==null)" in modelo


class _Nada:
    """Cliente sem projeto nenhum: montar_dados nao deve precisar ler o ClickUp."""
    def __getattr__(self, nome):
        return lambda *a, **k: []
