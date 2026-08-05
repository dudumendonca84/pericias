#!/usr/bin/env python3
"""
Constroi e mantem um indice local pesquisavel do acervo de pericias.

O indice e um SQLite com FTS5 que vive na maquina onde os laudos estao.
Nada sai daqui. Correr de novo depois de acrescentar pericias novas so
processa o que mudou -- e assim que o acervo "aprende".

    python indexar_pericias.py --pasta "G:/Meu Drive/pericias"
    python indexar_pericias.py --pasta "G:/Meu Drive/pericias" --colecao publico
    python indexar_pericias.py --procurar "infiltracao laje"
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
import unicodedata
from pathlib import Path

from diagnostico_pericias import (
    EXTENSOES_DOCUMENTO,
    EXTENSOES_RUIDO,
    analisar,
    recolher_ficheiros,
)

INDICE_PREDEFINIDO = Path("acervo_pericias.sqlite")

# Numeracao unica CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO
PADRAO_PROCESSO = re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b")
PADRAO_VARA = re.compile(
    r"\b(\d{1,2}\s*[ªa]?\s*VARA[^\n,.]{0,60})", re.IGNORECASE
)

# Tipo de peca inferido do nome do ficheiro. A ordem importa: a primeira
# regra que casar ganha, por isso as mais especificas vem primeiro.
REGRAS_TIPO = [
    ("esclarecimentos", r"esclarecimento"),
    ("laudo", r"\blaudo\b"),
    ("quesitos", r"quesito"),
    # "honorar" e nao "honorari": ha gralhas no acervo ("honoraros") que a
    # forma mais estrita deixava passar para o balde generico "carta".
    ("honorarios", r"honorar"),
    ("proposta", r"proposta"),
    ("escusa", r"escusa|foro\s+intimo"),
    ("peticao", r"peti[cç]"),
    ("carta", r"\bcarta\b"),
    ("fotos", r"\bfotos?\b|registro\s+fotografico"),
]

ESQUEMA = """
CREATE TABLE IF NOT EXISTS documentos (
    id           INTEGER PRIMARY KEY,
    caminho      TEXT NOT NULL UNIQUE,
    nome         TEXT NOT NULL,
    colecao      TEXT NOT NULL DEFAULT 'pericias',
    extensao     TEXT,
    bytes        INTEGER,
    mtime        REAL,
    estado       TEXT,
    processo     TEXT,
    vara         TEXT,
    tipo         TEXT,
    caracteres   INTEGER,
    paginas      INTEGER,
    indexado_em  REAL
);
CREATE INDEX IF NOT EXISTS idx_processo ON documentos(processo);
CREATE INDEX IF NOT EXISTS idx_tipo     ON documentos(tipo);
CREATE INDEX IF NOT EXISTS idx_colecao  ON documentos(colecao);

-- FTS5 guarda aqui uma copia do texto. Em modo contentless o snippet()
-- nao consegue devolver excertos, e sao os excertos que tornam a pesquisa
-- util para quem esta a redigir uma pericia.
CREATE VIRTUAL TABLE IF NOT EXISTS textos USING fts5(
    texto,
    tokenize="unicode61 remove_diacritics 2"
);
"""


def abrir_indice(caminho: Path) -> sqlite3.Connection:
    conexao = sqlite3.connect(caminho)
    conexao.executescript(ESQUEMA)
    return conexao


def extrair_texto(caminho: Path) -> tuple[str, str, int, int]:
    """Devolve (estado, texto, caracteres, paginas).

    Reaproveita o classificador do diagnostico para decidir o estado e so
    depois volta a ler o texto -- o custo extra e aceitavel e evita duas
    implementacoes da mesma logica a divergirem com o tempo.
    """
    resultado = analisar(caminho)
    if resultado.estado != "ok":
        return resultado.estado, "", resultado.caracteres, resultado.paginas

    extensao = caminho.suffix.lower()
    if extensao == ".pdf":
        import fitz

        with fitz.open(caminho) as doc:
            texto = "".join(p.get_text() for p in doc)
    elif extensao == ".docx":
        import docx

        documento = docx.Document(str(caminho))
        partes = [p.text for p in documento.paragraphs]
        for tabela in documento.tables:
            for linha in tabela.rows:
                partes.extend(c.text for c in linha.cells)
        texto = "\n".join(partes)
    else:
        dados = caminho.read_bytes()
        for codificacao in ("utf-8", "cp1252", "latin-1"):
            try:
                texto = dados.decode(codificacao)
                break
            except UnicodeDecodeError:
                continue
        else:
            texto = ""

    return "ok", texto, resultado.caracteres, resultado.paginas


def sem_acentos(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def inferir_tipo(nome: str) -> str:
    # Underscores e pontos sao separadores de palavra para um humano mas nao
    # para \b, que trata '_' como letra. Tirar acentos primeiro, senao o
    # proprio filtro [^a-z0-9] comia o 'i' de "intimo".
    normalizado = re.sub(r"[^a-z0-9]+", " ", sem_acentos(nome).lower())
    for etiqueta, padrao in REGRAS_TIPO:
        if re.search(padrao, normalizado):
            return etiqueta
    return "outro"


def inferir_processo(nome: str, texto: str) -> str | None:
    # O numero costuma aparecer no cabecalho; procurar so no inicio evita
    # apanhar processos citados de passagem no corpo do laudo.
    for fonte in (nome, texto[:4000]):
        encontrado = PADRAO_PROCESSO.search(fonte)
        if encontrado:
            return encontrado.group(0)
    return None


def inferir_vara(nome: str, texto: str) -> str | None:
    for fonte in (nome, texto[:4000]):
        encontrado = PADRAO_VARA.search(fonte)
        if encontrado:
            return " ".join(encontrado.group(1).split())[:80]
    return None


def indexar(pasta: Path, indice: Path, colecao: str, limite: int | None) -> int:
    conexao = abrir_indice(indice)

    ja_indexados = {
        linha[0]: (linha[1], linha[2])
        for linha in conexao.execute("SELECT caminho, mtime, bytes FROM documentos")
    }

    ficheiros = [
        f
        for f in recolher_ficheiros(pasta)
        if f.suffix.lower() in EXTENSOES_DOCUMENTO
        and f.suffix.lower() not in EXTENSOES_RUIDO
        and not f.name.startswith("~$")
    ]
    if limite:
        ficheiros = ficheiros[:limite]

    print(f"Colecao : {colecao}")
    print(f"Indice  : {indice.resolve()}")
    print(f"Candidatos: {len(ficheiros)}")

    novos = atualizados = inalterados = falhados = 0
    inicio = time.monotonic()

    for i, caminho in enumerate(ficheiros, 1):
        chave = str(caminho)
        try:
            estatisticas = caminho.stat()
        except OSError:
            falhados += 1
            continue

        anterior = ja_indexados.get(chave)
        if anterior and abs(anterior[0] - estatisticas.st_mtime) < 1 and anterior[1] == estatisticas.st_size:
            inalterados += 1
            continue

        estado, texto, caracteres, paginas = extrair_texto(caminho)
        if estado != "ok":
            falhados += 1

        processo = inferir_processo(caminho.name, texto)
        vara = inferir_vara(caminho.name, texto)
        tipo = inferir_tipo(caminho.name)

        cursor = conexao.execute("SELECT id FROM documentos WHERE caminho = ?", (chave,))
        linha = cursor.fetchone()
        campos = (
            caminho.name, colecao, caminho.suffix.lower(), estatisticas.st_size,
            estatisticas.st_mtime, estado, processo, vara, tipo,
            caracteres, paginas, time.time(),
        )

        if linha:
            doc_id = linha[0]
            conexao.execute(
                """UPDATE documentos SET nome=?, colecao=?, extensao=?, bytes=?,
                   mtime=?, estado=?, processo=?, vara=?, tipo=?, caracteres=?,
                   paginas=?, indexado_em=? WHERE id=?""",
                (*campos, doc_id),
            )
            conexao.execute("DELETE FROM textos WHERE rowid = ?", (doc_id,))
            atualizados += 1
        else:
            cursor = conexao.execute(
                """INSERT INTO documentos (caminho, nome, colecao, extensao, bytes,
                   mtime, estado, processo, vara, tipo, caracteres, paginas, indexado_em)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (chave, *campos),
            )
            doc_id = cursor.lastrowid
            novos += 1

        if texto.strip():
            conexao.execute(
                "INSERT INTO textos (rowid, texto) VALUES (?, ?)", (doc_id, texto)
            )

        if i % 50 == 0:
            conexao.commit()
            print(f"  {i}/{len(ficheiros)}", flush=True)

    conexao.commit()
    segundos = time.monotonic() - inicio

    print()
    print(f"Novos       : {novos}")
    print(f"Atualizados : {atualizados}")
    print(f"Inalterados : {inalterados}")
    print(f"Sem texto   : {falhados}")
    print(f"Tempo       : {segundos:.1f}s")

    total = conexao.execute("SELECT COUNT(*) FROM documentos").fetchone()[0]
    processos = conexao.execute(
        "SELECT COUNT(DISTINCT processo) FROM documentos WHERE processo IS NOT NULL"
    ).fetchone()[0]
    print(f"Acervo      : {total} documentos, {processos} processos identificados")

    print()
    print("Por tipo de peca:")
    for tipo, n in conexao.execute(
        "SELECT tipo, COUNT(*) FROM documentos GROUP BY tipo ORDER BY 2 DESC"
    ):
        print(f"  {tipo:<18} {n:>6}")

    conexao.close()
    return 0


def procurar(indice: Path, consulta: str, colecao: str | None, quantos: int) -> int:
    if not indice.exists():
        print(f"ERRO: indice nao existe: {indice}", file=sys.stderr)
        print("Corre primeiro: python indexar_pericias.py --pasta <pasta>", file=sys.stderr)
        return 2

    conexao = abrir_indice(indice)
    sql = """
        SELECT d.nome, d.processo, d.tipo, d.caminho,
               snippet(textos, 0, '>>', '<<', ' ... ', 18) AS excerto
        FROM textos
        JOIN documentos d ON d.id = textos.rowid
        WHERE textos MATCH ?
    """
    parametros: list = [consulta]
    if colecao:
        sql += " AND d.colecao = ?"
        parametros.append(colecao)
    sql += " ORDER BY rank LIMIT ?"
    parametros.append(quantos)

    linhas = list(conexao.execute(sql, parametros))
    if not linhas:
        print("Sem resultados.")
        return 0

    for nome, processo, tipo, caminho, excerto in linhas:
        print(f"\n{'-' * 68}")
        print(f"{nome}")
        print(f"  processo: {processo or '(nao identificado)'}   tipo: {tipo}")
        print(f"  {caminho}")
        print(f"  {' '.join(excerto.split())}")
    print()
    print(f"{len(linhas)} resultado(s).")
    conexao.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Indice local pesquisavel do acervo de pericias."
    )
    parser.add_argument("--pasta", help="pasta a indexar (recursivo)")
    parser.add_argument(
        "--colecao",
        default="pericias",
        help="'pericias' para o acervo do perito, 'publico' para fontes publicas",
    )
    parser.add_argument("--indice", default=str(INDICE_PREDEFINIDO))
    parser.add_argument("--limite", type=int)
    parser.add_argument("--procurar", help="pesquisa em texto integral no indice")
    parser.add_argument("--quantos", type=int, default=10)
    args = parser.parse_args()

    indice = Path(args.indice)

    if args.procurar:
        return procurar(indice, args.procurar, None, args.quantos)

    if not args.pasta:
        parser.error("indica --pasta para indexar ou --procurar para pesquisar")

    pasta = Path(args.pasta).expanduser()
    if not pasta.is_dir():
        print(f"ERRO: pasta nao encontrada: {pasta}", file=sys.stderr)
        return 2

    return indexar(pasta, indice, args.colecao, args.limite)


if __name__ == "__main__":
    raise SystemExit(main())
