"""O que este pacote precisa, o que ele so aproveita, e o que falta agora.

Existe porque a fronteira entre obrigatorio e opcional estava so na cabeca de
quem construiu. O pacote nasceu dentro do delegation-core e passou a consumir
coisas que aquele ambiente oferecia: o vault com as transcricoes de daily, as
sessoes de IA em disco, e um modelo local em 127.0.0.1:8181. Nada disso e
requisito, e ate 08/09/2026 nada dizia isso em lugar nenhum.

A regra que este modulo torna visivel:

- **Obrigatorio: o ClickUp.** Token e team. Seis dos sete itens leem campo do
  ClickUp e fazem conta, e funcionam com isso e mais nada.
- **Opcional: tudo que vem da maquina.** Repositorios, sessoes de IA, historico
  do navegador, vault e modelo local. Sem eles o item 4, o motor de horas,
  continua rodando e simplesmente pergunta mais. Faltar fonte nao e erro, e
  menos evidencia, e menos evidencia sai declarado como pergunta.
- **Opcional: o roster de RH.** Sem ele o item 6 nao roda, e diz que nao roda.

Cada ausencia aqui vem com o preco dela em uma frase, porque uma checagem que
so lista verde e vermelho transfere para quem le o trabalho de saber o que cada
vermelho custa.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

from . import bolsao

#: Onde o interprete de daily procura o modelo. Vem do delegation-core quando
#: ele esta de pe, e nada aqui sobe modelo nenhum.
MODELO_PADRAO = "http://127.0.0.1:8181"

#: Planilha de exemplo com as colunas que `rh.carregar` le. Caminho dentro do
#: repositorio, e nao um arquivo gerado: e material para copiar e preencher.
MODELO_DE_ROSTER = "contrib/rh-modelo.csv"


@dataclass
class Item:
    """Uma dependencia, se ela esta la, e o que custa nao estar."""

    nome: str
    obrigatorio: bool
    presente: bool
    detalhe: str = ""
    custo: str = ""

    @property
    def marca(self) -> str:
        if self.presente:
            return "ok"
        return "FALTA" if self.obrigatorio else "ausente"


@dataclass
class Checagem:
    itens: list[Item] = field(default_factory=list)

    @property
    def pronto(self) -> bool:
        """Da para rodar? So o obrigatorio decide isso."""
        return all(i.presente for i in self.itens if i.obrigatorio)

    @property
    def faltando_opcional(self) -> list[Item]:
        return [i for i in self.itens if not i.obrigatorio and not i.presente]


def _porta_responde(url: str, timeout: float = 1.5) -> bool:
    partes = urlparse(url)
    try:
        with socket.create_connection((partes.hostname or "127.0.0.1",
                                       partes.port or 80), timeout=timeout):
            return True
    except OSError:
        return False


def _conta_dailies(vault: Path, dias: int = 30) -> tuple[int, date | None]:
    """Quantas transcricoes de daily existem na janela, e a mais recente."""
    pasta = vault / "Sessions"
    if not pasta.is_dir():
        return 0, None
    limite = date.today() - timedelta(days=dias)
    achadas: list[date] = []
    for p in pasta.glob("*.md"):
        nome = p.name
        if "daily" not in nome.lower():
            continue
        try:
            d = date.fromisoformat(nome[:10])
        except ValueError:
            continue
        if d >= limite:
            achadas.append(d)
    return len(achadas), max(achadas) if achadas else None


def checar(cfg: dict, modelo: str = MODELO_PADRAO) -> Checagem:
    """Monta a checagem a partir do config, sem tocar a rede do ClickUp.

    O token nao e validado com uma chamada de proposito: uma checagem que gasta
    uma ida a API para dizer "existe um token" mistura duas perguntas. Aqui a
    pergunta e o que esta configurado; se o token estiver errado, quem diz e o
    proprio comando que for usa-lo.
    """
    c = Checagem()
    ev = cfg.get("evidencia") or {}
    projetos = cfg.get("projetos") or []

    c.itens.append(Item(
        nome="ClickUp: token", obrigatorio=True, presente=bool(cfg.get("token")),
        detalhe="configurado" if cfg.get("token") else "",
        custo="sem token nenhum item roda"))
    c.itens.append(Item(
        nome="ClickUp: team_id", obrigatorio=True, presente=bool(cfg.get("team_id")),
        detalhe=str(cfg.get("team_id") or ""),
        custo="sem team nao ha de onde ler entrada de tempo"))

    # Quem tem teto e pergunta para o vigia, nao conta refeita aqui. Esta linha
    # contava so `horas_contratadas` do config e ignorava `TETOS_DE_REFERENCIA`,
    # entao dizia "4 com teto" onde o bolsao vigiava 8: a checagem que existe
    # para dizer o que falta inventava uma falta que nao havia. Duas leituras da
    # mesma regra derivam, e a correcao e nao ter duas.
    vigiados, sem_teto = bolsao.carregar_bolsoes(projetos)
    detalhe_projetos = f"{len(projetos)} cliente(s), {len(vigiados)} com teto"
    if sem_teto:
        detalhe_projetos += f", {len(sem_teto)} sem"
    c.itens.append(Item(
        nome="Projetos configurados", obrigatorio=True, presente=bool(projetos),
        detalhe=detalhe_projetos,
        custo="sem projeto o vigia de bolsao e o cronograma nao tem o que ler"))

    # ── daqui para baixo, tudo opcional ──────────────────────────────────────

    vault = Path(ev["vault"]).expanduser() if ev.get("vault") else None
    tem_vault = bool(vault and vault.is_dir())
    detalhe = ""
    if tem_vault:
        n, recente = _conta_dailies(vault)
        detalhe = (f"{n} daily(s) nos ultimos 30 dias"
                   + (f", a mais recente de {recente:%d/%m}" if recente else ""))
    c.itens.append(Item(
        nome="Vault com as dailies", obrigatorio=False, presente=tem_vault,
        detalhe=detalhe,
        custo="sem transcricao o motor de horas nao sabe o QUE foi feito, so "
              "quanto tempo houve, e toda proposta sai como atividade nao "
              "identificada"))

    c.itens.append(Item(
        nome="Modelo local para ler as dailies", obrigatorio=False,
        presente=_porta_responde(modelo), detalhe=modelo,
        custo="sem modelo as transcricoes nao sao interpretadas, com o mesmo "
              "efeito de nao existirem"))

    sessoes = Path(ev["sessoes_ia"]).expanduser() if ev.get("sessoes_ia") else None
    c.itens.append(Item(
        nome="Sessoes de IA em disco", obrigatorio=False,
        presente=bool(sessoes and sessoes.is_dir()),
        detalhe=str(sessoes or ""),
        custo="perde a fonte que mais pesa na apuracao de quem trabalha assim"))

    repos = [Path(r).expanduser() for r in (ev.get("repos") or ())]
    existentes = [r for r in repos if (r / ".git").is_dir()]
    c.itens.append(Item(
        nome="Repositorios git", obrigatorio=False, presente=bool(existentes),
        detalhe=f"{len(existentes)} de {len(repos)} encontrado(s)",
        custo="perde o commit, que e a evidencia mais precisa de todas"))

    hist = Path(ev["historico_navegador"]).expanduser() if ev.get("historico_navegador") else None
    c.itens.append(Item(
        nome="Historico do navegador", obrigatorio=False,
        presente=bool(hist and hist.exists()), detalhe=str(hist or ""),
        custo="perde a fonte que separa trabalho de pessoal por dominio"))

    roster = Path(cfg["roster_rh"]).expanduser() if cfg.get("roster_rh") else None
    c.itens.append(Item(
        nome="Roster de RH", obrigatorio=False,
        presente=bool(roster and roster.exists()), detalhe=str(roster or ""),
        # A ausencia vem com o caminho da saida: as colunas do roster estavam
        # so no codigo, entao quem quisesse ligar o item 6 tinha que ler o
        # `carregar` para descobrir como e a planilha.
        custo="o item 6 nao roda, e diz que nao roda em vez de sair vazio; "
              f"as colunas estao em {MODELO_DE_ROSTER}"))

    return c


def relatorio(c: Checagem) -> str:
    linhas = ["Checagem do ambiente", ""]
    for i in c.itens:
        obrig = "obrigatorio" if i.obrigatorio else "opcional   "
        linhas.append(f"  [{i.marca:7}] {obrig}  {i.nome}"
                      + (f": {i.detalhe}" if i.detalhe else ""))
    linhas.append("")
    if c.pronto:
        linhas.append("  O obrigatorio esta completo: os itens que leem so o "
                      "ClickUp rodam.")
    else:
        faltam = [i.nome for i in c.itens if i.obrigatorio and not i.presente]
        linhas.append(f"  FALTA o obrigatorio: {', '.join(faltam)}. Nenhum item roda.")

    if c.faltando_opcional:
        linhas.append("")
        linhas.append("  O que esta ausente, e o que cada ausencia custa:")
        for i in c.faltando_opcional:
            linhas.append(f"    {i.nome}: {i.custo}")
        linhas.append("")
        linhas.append("  Nada disso e requisito. Sao fontes que enriquecem a "
                      "apuracao de horas e o item de RH; faltar significa mais "
                      "pergunta, nunca numero inventado.")
    return "\n".join(linhas)
