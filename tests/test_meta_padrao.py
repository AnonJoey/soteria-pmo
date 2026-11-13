"""Meta de dias lancados: 90% por padrao desde 13/11/2026, o config vence."""
from __future__ import annotations

from pathlib import Path

from soteria_pmo import cli, painel


def test_padrao_e_90_e_as_duas_chamadas_do_painel_o_usam():
    assert painel.META_DIAS_LANCADOS_PADRAO == 0.9
    texto = Path(cli.__file__).read_text(encoding="utf-8")
    assert texto.count('cfg.get("meta_dias_lancados", painel.META_DIAS_LANCADOS_PADRAO)') == 2
