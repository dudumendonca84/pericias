#!/usr/bin/env python3
"""
Servidor MCP do acervo de pericias.

Expoe o acervo local como ferramentas que o Claude Desktop, o Claude Code ou
qualquer cliente MCP pode usar. E isto que permite perguntar "que laudos tenho
sobre infiltracao?" na app normal do Claude, sem terminal e sem carregar
documento nenhum para a nuvem: o servidor corre na maquina onde o acervo esta
e so devolve o que lhe e perguntado.

Configuracao no cliente (claude_desktop_config.json):

    {
      "mcpServers": {
        "pericias": {
          "command": "python",
          "args": ["C:/Users/.../pericias/mcp_pericias.py"]
        }
      }
    }

O acervo e procurado automaticamente; ACERVO_PERICIAS aponta-o explicitamente.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

from mcp.server import MCPServer

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from indexar_pericias import sem_acentos  # noqa: E402

NOME_ACERVO = "acervo_pericias.sqlite"
TIPOS = (
    "laudo", "esclarecimentos", "quesitos", "honorarios",
    "proposta", "escusa", "peticao", "carta", "fotos", "outro",
)

servidor = MCPServer(
    name="pericias",
    instructions=(
        "Acervo local de pericias judiciais de engenharia. Usar para encontrar "
        "pecas ja entregues pelo perito e reaproveitar a sua estrutura e "
        "fundamentacao ao redigir pecas novas.\n\n"
        "Consultar sempre o acervo antes de redigir. Nunca inventar factos "
        "periciais -- medicoes, datas de vistoria, valores, folhas dos autos, "
        "nomes de partes: ou vem dos autos, ou sao copiados de um precedente "
        "concreto devolvido por estas ferramentas, ou ficam marcados como "
        "[A PREENCHER] e reportados ao perito."
    ),
)


def localizar_acervo() -> Path | None:
    """Encontra o ficheiro do acervo sem obrigar a configurar caminhos."""
    if os.environ.get("ACERVO_PERICIAS"):
        candidato = Path(os.environ["ACERVO_PERICIAS"]).expanduser()
        return candidato if candidato.is_file() else None

    for candidato in (
        RAIZ / NOME_ACERVO,
        RAIZ / "entrega" / NOME_ACERVO,
        Path.home() / "Documents" / "pericias" / NOME_ACERVO,
        Path.home() / "Documentos" / "pericias" / NOME_ACERVO,
        Path.home() / "Desktop" / NOME_ACERVO,
    ):
        if candidato.is_file():
            return candidato
    return None


def ligar() -> sqlite3.Connection:
    acervo = localizar_acervo()
    if acervo is None:
        raise FileNotFoundError(
            f"Acervo nao encontrado. Coloca {NOME_ACERVO} junto a este ficheiro "
            "ou define a variavel de ambiente ACERVO_PERICIAS."
        )
    # So-leitura: um servidor MCP nunca deve poder alterar o acervo, e assim
    # pode ser consultado enquanto uma indexacao decorre.
    return sqlite3.connect(f"file:{acervo}?mode=ro", uri=True)


def preparar_consulta(pergunta: str) -> str:
    """Reduz uma pergunta escrita a maos as palavras que o FTS5 aceita.

    Pontuacao, aspas e hifenes soltos fazem o motor rebentar com erro de
    sintaxe -- e quem escreve a pergunta nao tem de saber disso.
    """
    import re

    palavras = re.findall(r"[0-9a-zA-Z]+", sem_acentos(pergunta))
    uteis = [p for p in palavras if len(p) > 2] or palavras
    return " OR ".join(uteis)


@servidor.tool()
def resumo_acervo() -> str:
    """Panorama do acervo: quantas pecas, de que tipos, de que varas.

    Usar quando ainda nao se conhece o acervo, ou para saber que material
    existe antes de procurar.
    """
    conexao = ligar()
    try:
        total = conexao.execute("SELECT COUNT(*) FROM documentos").fetchone()[0]
        legiveis = conexao.execute(
            "SELECT COUNT(*) FROM documentos WHERE caracteres > 0"
        ).fetchone()[0]
        processos = conexao.execute(
            "SELECT COUNT(DISTINCT processo) FROM documentos "
            "WHERE processo IS NOT NULL"
        ).fetchone()[0]

        linhas = [
            f"{total} documentos, {legiveis} com texto legivel, "
            f"{processos} processos.",
            "",
            "Por tipo de peca:",
        ]
        linhas += [
            f"  {tipo or '(sem tipo)'}: {n}"
            for tipo, n in conexao.execute(
                "SELECT tipo, COUNT(*) FROM documentos GROUP BY tipo ORDER BY 2 DESC"
            )
        ]
        linhas += ["", "Varas mais frequentes:"]
        linhas += [
            f"  {n:>4}  {vara}"
            for vara, n in conexao.execute(
                "SELECT vara, COUNT(*) FROM documentos WHERE vara IS NOT NULL "
                "GROUP BY vara ORDER BY 2 DESC LIMIT 15"
            )
        ]
        return "\n".join(linhas)
    finally:
        conexao.close()


@servidor.tool()
def procurar(assunto: str, quantos: int = 10) -> str:
    """Procura pecas do acervo por assunto, em texto integral.

    Aceita a pergunta em linguagem normal ("infiltracao na laje de cobertura").
    Acentos e pontuacao sao ignorados. Devolve o nome, processo, vara, tipo e
    um excerto com o termo em destaque.
    """
    consulta = preparar_consulta(assunto)
    if not consulta:
        return "Indica pelo menos uma palavra."

    conexao = ligar()
    try:
        linhas = list(
            conexao.execute(
                """SELECT d.nome, d.processo, d.vara, d.tipo,
                          snippet(textos, 0, '>>', '<<', ' ... ', 20)
                   FROM textos JOIN documentos d ON d.id = textos.rowid
                   WHERE textos MATCH ? ORDER BY rank LIMIT ?""",
                (consulta, max(quantos, 1) * 6),
            )
        )
    except sqlite3.Error as erro:
        return f"Erro na pesquisa: {erro}"
    finally:
        conexao.close()

    if not linhas:
        return f"Nada encontrado para '{assunto}'."

    # O acervo tem a mesma peca em .docx e .pdf e replicada por varias pastas.
    # Sem agrupar, metade dos resultados sao a mesma coisa.
    vistos: set[str] = set()
    saida: list[str] = []
    for nome, processo, vara, tipo, excerto in linhas:
        chave = sem_acentos(Path(nome).stem).lower().strip()
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(
            f"[{tipo}] {nome}\n"
            f"  processo: {processo or '(nao identificado)'}\n"
            f"  vara: {vara or '(nao identificada)'}\n"
            f"  {' '.join((excerto or '').split())}"
        )
        if len(saida) >= quantos:
            break

    return f"{len(saida)} peca(s):\n\n" + "\n\n".join(saida)


@servidor.tool()
def pecas_do_processo(numero: str) -> str:
    """Lista todas as pecas de um processo.

    Aceita o numero CNJ completo ou um fragmento. Usar antes de redigir uma
    peca nova para saber o que ja foi dito nesse processo.
    """
    conexao = ligar()
    try:
        linhas = list(
            conexao.execute(
                """SELECT nome, tipo, caracteres, vara FROM documentos
                   WHERE processo = ? OR processo LIKE ?
                   ORDER BY tipo, nome""",
                (numero, f"%{numero}%"),
            )
        )
    finally:
        conexao.close()

    if not linhas:
        return f"Nenhuma peca do processo {numero}."

    vara = next((linha[3] for linha in linhas if linha[3]), None)
    cabecalho = f"Processo {numero}"
    if vara:
        cabecalho += f" — {vara}"
    corpo = [
        f"{'  ' if caracteres else '* '}[{tipo}] {nome}"
        for nome, tipo, caracteres, _ in linhas
    ]
    rodape = (
        "\n\n* sem texto legivel (digitalizacao nao recuperada pelo OCR)"
        if any(not linha[2] for linha in linhas)
        else ""
    )
    return f"{cabecalho}\n{len(linhas)} peca(s):\n\n" + "\n".join(corpo) + rodape


@servidor.tool()
def ler_peca(nome: str, inteiro: bool = False) -> str:
    """Devolve o texto integral de uma peca do acervo.

    O nome pode ser parcial. Usar depois de procurar, para ler o precedente
    por inteiro antes de redigir -- um excerto nao chega para perceber a
    estrutura de uma peca.
    """
    alvo = sem_acentos(nome).lower()
    conexao = ligar()
    try:
        candidatos = [
            linha
            for linha in conexao.execute(
                """SELECT d.nome, d.processo, d.vara, d.tipo, t.texto
                   FROM documentos d JOIN textos t ON t.rowid = d.id"""
            )
            if alvo in sem_acentos(linha[0]).lower()
        ]
    finally:
        conexao.close()

    if not candidatos:
        return f"Nenhuma peca com texto cujo nome contenha '{nome}'."

    escolhido = candidatos[0]
    aviso = ""
    if len(candidatos) > 1:
        outros = "\n".join(f"  [{c[3]}] {c[0]}" for c in candidatos[1:8])
        aviso = (
            f"\n\n({len(candidatos)} pecas correspondem; mostrada a primeira. "
            f"Outras:\n{outros})"
        )

    nome_peca, processo, vara, tipo, texto = escolhido
    texto = (texto or "").strip()
    limite = 60000 if inteiro else 15000
    truncado = ""
    if len(texto) > limite:
        truncado = f"\n\n[... truncado, faltam {len(texto) - limite} caracteres]"
        texto = texto[:limite]

    return (
        f"{nome_peca}\n"
        f"processo: {processo or '(nao identificado)'}\n"
        f"vara: {vara or '(nao identificada)'}\n"
        f"tipo: {tipo}\n"
        f"{'=' * 60}\n\n{texto}{truncado}{aviso}"
    )


@servidor.tool()
def modelos(tipo: str, quantos: int = 2) -> str:
    """Pecas mais completas de um tipo, como referencia estrutural.

    Tipos: laudo, esclarecimentos, quesitos, honorarios, proposta, escusa,
    peticao, carta, fotos. Ordena pelas mais extensas, que sao as que mostram
    a estrutura toda em vez de uma versao abreviada.
    """
    if tipo not in TIPOS:
        return f"Tipo desconhecido. Disponiveis: {', '.join(TIPOS)}"

    conexao = ligar()
    try:
        linhas = list(
            conexao.execute(
                """SELECT d.nome, d.processo, d.vara, t.texto
                   FROM documentos d JOIN textos t ON t.rowid = d.id
                   WHERE d.tipo = ? AND d.caracteres > 0
                   ORDER BY d.caracteres DESC LIMIT ?""",
                (tipo, max(quantos, 1)),
            )
        )
    finally:
        conexao.close()

    if not linhas:
        return f"Nenhuma peca do tipo '{tipo}' com texto legivel."

    partes = [
        f"{nome}\nprocesso: {processo or '(nao identificado)'}\n"
        f"vara: {vara or '(nao identificada)'}\n{'=' * 60}\n\n"
        f"{(texto or '').strip()[:12000]}"
        for nome, processo, vara, texto in linhas
    ]
    return "\n\n\n".join(partes)


@servidor.tool()
def pecas_da_vara(vara: str, quantos: int = 30) -> str:
    """Lista as pecas de uma vara. Aceita o nome parcial ("32ª" ou "Mage")."""
    alvo = sem_acentos(vara).lower()
    conexao = ligar()
    try:
        linhas = [
            linha
            for linha in conexao.execute(
                """SELECT nome, processo, tipo, vara FROM documentos
                   WHERE vara IS NOT NULL ORDER BY processo, tipo"""
            )
            if alvo in sem_acentos(linha[3]).lower()
        ]
    finally:
        conexao.close()

    if not linhas:
        return f"Nenhuma peca da vara '{vara}'."

    processos = {linha[1] for linha in linhas if linha[1]}
    corpo = "\n".join(
        f"[{tipo}] {nome}  ({processo or 'processo nao identificado'})"
        for nome, processo, tipo, _ in linhas[:quantos]
    )
    extra = (
        f"\n\n(mostradas {quantos} de {len(linhas)})"
        if len(linhas) > quantos
        else ""
    )
    return (
        f"{linhas[0][3]}\n{len(linhas)} peca(s), {len(processos)} processo(s):"
        f"\n\n{corpo}{extra}"
    )


if __name__ == "__main__":
    servidor.run()
