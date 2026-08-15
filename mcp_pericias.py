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

# O pacote mcp mudou de nome de classe entre series: 2.x expoe MCPServer,
# 1.x expoe FastMCP. A interface que usamos aqui -- construtor com name e
# instructions, decorador .tool(), metodo .run() -- e igual nas duas, mas
# importar so uma delas faz o servidor morrer no arranque em metade das
# maquinas. E morre em silencio: o Claude Desktop nao mostra erro nenhum,
# apenas nao apresenta as ferramentas, o que e indistinguivel de nao estar
# instalado.
try:
    from mcp.server import MCPServer
except ImportError:  # pragma: no cover - depende da versao instalada
    try:
        from mcp.server.fastmcp import FastMCP as MCPServer
    except ImportError as erro:
        raise SystemExit(
            "O pacote 'mcp' nao esta instalado ou e demasiado antigo.\n"
            "Instala com:\n"
            f"  {sys.executable} -m pip install --upgrade mcp"
        ) from erro

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from indexar_pericias import sem_acentos  # noqa: E402

NOME_ACERVO = "acervo_pericias.sqlite"
TIPOS = (
    "laudo", "esclarecimentos", "quesitos", "honorarios",
    "proposta", "escusa", "peticao", "carta", "fotos", "outro",
)

# Quem usa isto pelo Claude Desktop nao tem a skill do repositorio -- o
# Desktop nao le ficheiros da pasta. Estas instrucoes sao a unica orientacao
# que chega la, por isso carregam o essencial dela.
INSTRUCOES = """
Acervo local de pericias judiciais de engenharia. O utilizador e um perito do
juizo. Este acervo guarda as pecas que ele ja entregou, com o texto integral
pesquisavel, e e a fonte da verdade: o valor esta em trabalhar a partir do que
ele proprio escreveu, nao de modelos genericos.

REGRA QUE NAO SE QUEBRA
Nunca inventar factos periciais. Medicoes, datas de vistoria, valores de
honorarios, numeros de folhas dos autos, conclusoes tecnicas, numeros de
processo, nomes de partes, dados bancarios e de identificacao -- nada disto se
escreve de memoria nem se deduz por analogia. Ou esta nos autos e no material
fornecido, ou vem copiado de um precedente concreto devolvido por estas
ferramentas, ou fica em branco assinalado assim:

    [A PREENCHER: data da vistoria]

Um laudo com um numero inventado e um problema serio para quem o assina, nao
um detalhe de redaccao. Na duvida, deixar em branco e dizer o que falta.

ANTES DE ESCREVER
Procurar precedentes com `procurar`, `pecas_do_processo` ou `modelos`, e ler
por inteiro com `ler_peca` as pecas relevantes. Um excerto de pesquisa nao
chega para perceber a estrutura de uma peca. Nunca redigir do zero.

ESTRUTURA DAS PECAS
Seguir a forma exacta de um precedente real, nao o resumo abaixo -- que serve
so para saber o que procurar.

- Cabecalho, comum a quase tudo: enderecamento ao juizo em maiusculas
  (EXMO. SR. DR. JUIZ DA Na VARA CIVEL DA COMARCA DE ...), numero do processo,
  Autor e Reu, e a formula de apresentacao do perito seguida de "vem, mui
  respeitosamente, ...".
- Laudo: preambulo, objecto da pericia, metodologia e diligencias, descricao
  do constatado em vistoria, fundamentacao tecnica, respostas aos quesitos,
  conclusao, e encerramento com a contagem de folhas por extenso.
- Esclarecimentos: responde a impugnacoes ou quesitos suplementares,
  remetendo ao que ja foi dito no laudo quando aplicavel.
- Quesitos: cada quesito e repetido na integra antes da resposta, na ordem em
  que foi formulado, e cada um e respondido individualmente -- nunca em bloco.
- Honorarios e peticoes: pedido objectivo, com referencia as folhas dos autos.
  Os dados de identificacao e bancarios do perito copiam-se de uma peca
  recente do acervo, nunca se escrevem de memoria.
- Escusa: peca curta, invocando o motivo sem o detalhar quando e foro intimo.

AO REDIGIR
- Espelhar o precedente encontrado: tratamento, formulas, ordem das seccoes,
  grau de detalhe. A voz e do perito, nao nossa.
- Separar com clareza o constatado em vistoria da inferencia tecnica. Confundir
  as duas coisas e o erro que uma impugnacao explora.
- Assinalar todas as lacunas em vez de as preencher com plausibilidades.
- No fim, dizer explicitamente o que ficou por preencher e porque.

CITACOES
Ao citar artigo de lei, norma tecnica ou acordao, verificar no documento
indexado. Nunca citar de memoria -- nem numero de artigo, nem numero de NBR,
nem acordao. Se a fonte nao estiver no acervo, dizer que nao se conseguiu
verificar em vez de escrever a citacao.

O INDICE PODE ESTAR ERRADO
A vara e o tipo de peca sao inferidos automaticamente do nome do ficheiro e do
texto, e ha casos mal classificados. Se algo nao bater -- uma peca numa vara
que o nome do ficheiro contradiz, um tipo que nao corresponde ao conteudo --
assinalar ao perito em vez de assumir que o indice esta certo.

CONFIDENCIALIDADE
O acervo tem processos reais com partes identificadas. Nao transpor conteudo de
um processo para peca de outro alem de estrutura e fundamentacao tecnica
generica.
"""

servidor = MCPServer(name="pericias", instructions=INSTRUCOES.strip())


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


def verificar() -> int:
    """Diz numa passagem se este servidor consegue servir o acervo.

    Diagnosticar isto pelo Claude Desktop e impossivel: quando o servidor nao
    arranca, a aplicacao nao mostra erro -- as ferramentas simplesmente nao
    aparecem. Esta funcao corre o mesmo caminho que o servidor faz ao arrancar
    e diz em que ponto falha.
    """
    print(f"Python  : {sys.executable}")
    print(f"Servidor: {MCPServer.__module__}.{MCPServer.__name__}")

    acervo = localizar_acervo()
    if acervo is None:
        print("Acervo  : NAO ENCONTRADO")
        print()
        print(f"Coloca {NOME_ACERVO} em {RAIZ}")
        print("ou define a variavel de ambiente ACERVO_PERICIAS.")
        return 1
    print(f"Acervo  : {acervo} ({acervo.stat().st_size / 1024 / 1024:.0f} MB)")

    try:
        conexao = ligar()
    except sqlite3.Error as erro:
        print(f"ERRO ao abrir o acervo: {erro}")
        return 1
    try:
        total, laudos = conexao.execute(
            "SELECT COUNT(*), SUM(tipo = 'laudo') FROM documentos"
        ).fetchone()
    except sqlite3.Error as erro:
        print(f"ERRO ao ler o acervo: {erro}")
        return 1
    finally:
        conexao.close()

    print(f"Conteudo: {total} documentos, {laudos or 0} laudos")
    print()
    print("Tudo pronto. Se o Claude Desktop continua sem ver as ferramentas,")
    print("o problema esta na ligacao: corre `python instalar_mcp.py` e")
    print("encerra o Claude pelo icone junto ao relogio antes de o reabrir.")
    return 0


if __name__ == "__main__":
    if "--verificar" in sys.argv:
        raise SystemExit(verificar())
    servidor.run()
