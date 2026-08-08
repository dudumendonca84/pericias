#!/usr/bin/env python3
"""
Consultas ao acervo para apoiar a redacao de pecas periciais.

O indexar_pericias.py responde a "onde esta isto?". Este responde as perguntas
que se fazem quando se esta a escrever uma peca nova: quais sao os precedentes
deste tipo, o que ja foi dito neste processo, como e que ele costuma redigir
esta seccao.

    python consultar_acervo.py --processo 0012140-26.2013.8.19.0028
    python consultar_acervo.py --ler "Laudo Pericial 28"
    python consultar_acervo.py --modelos laudo --quantos 3
    python consultar_acervo.py --resumo
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from indexar_pericias import INDICE_PREDEFINIDO, abrir_indice, sem_acentos

TIPOS = (
    "laudo", "esclarecimentos", "quesitos", "honorarios",
    "proposta", "escusa", "peticao", "carta", "fotos", "outro",
)


def resumo(conexao: sqlite3.Connection) -> int:
    total = conexao.execute("SELECT COUNT(*) FROM documentos").fetchone()[0]
    com_texto = conexao.execute(
        "SELECT COUNT(*) FROM documentos WHERE caracteres > 0"
    ).fetchone()[0]
    processos = conexao.execute(
        "SELECT COUNT(DISTINCT processo) FROM documentos WHERE processo IS NOT NULL"
    ).fetchone()[0]

    print(f"Documentos        : {total}")
    print(f"Com texto legivel : {com_texto}")
    print(f"Processos         : {processos}")
    print()
    print("Por tipo de peca:")
    for tipo, n in conexao.execute(
        "SELECT tipo, COUNT(*) FROM documentos GROUP BY tipo ORDER BY 2 DESC"
    ):
        print(f"  {tipo or '(sem tipo)':<18} {n:>6}")
    print()
    print("Varas mais frequentes:")
    for vara, n in conexao.execute(
        """SELECT vara, COUNT(*) FROM documentos
           WHERE vara IS NOT NULL GROUP BY vara ORDER BY 2 DESC LIMIT 12"""
    ):
        print(f"  {n:>4}  {vara}")
    return 0


def por_processo(conexao: sqlite3.Connection, numero: str) -> int:
    linhas = list(
        conexao.execute(
            """SELECT nome, tipo, caracteres, vara, origem FROM documentos
               WHERE processo = ? ORDER BY tipo, nome""",
            (numero,),
        )
    )
    if not linhas:
        # Aceitar um numero parcial: quem escreve de cabeca raramente acerta
        # nos vinte digitos da numeracao CNJ.
        linhas = list(
            conexao.execute(
                """SELECT nome, tipo, caracteres, vara, origem FROM documentos
                   WHERE processo LIKE ? ORDER BY tipo, nome""",
                (f"%{numero}%",),
            )
        )
    if not linhas:
        print(f"Nenhum documento com o processo {numero}.")
        return 1

    vara = next((linha[3] for linha in linhas if linha[3]), None)
    print(f"Processo: {numero}")
    if vara:
        print(f"Vara    : {vara}")
    print(f"Pecas   : {len(linhas)}")
    print()
    for nome, tipo, caracteres, _, origem in linhas:
        marca = " " if caracteres else "*"
        print(f"{marca} [{tipo:<15}] {nome}")
    if any(not linha[2] for linha in linhas):
        print()
        print("* sem texto legivel (digitalizacao que o OCR nao recuperou)")
    return 0


def ler(conexao: sqlite3.Connection, procura: str, inteiro: bool) -> int:
    alvo = sem_acentos(procura).lower()
    candidatos = [
        linha
        for linha in conexao.execute(
            """SELECT d.nome, d.processo, d.vara, d.tipo, t.texto
               FROM documentos d JOIN textos t ON t.rowid = d.id"""
        )
        if alvo in sem_acentos(linha[0]).lower()
    ]
    if not candidatos:
        print(f"Nenhum documento com texto cujo nome contenha '{procura}'.")
        return 1

    if len(candidatos) > 1:
        print(f"{len(candidatos)} documentos correspondem. A mostrar o primeiro.")
        for nome, _, _, tipo, _ in candidatos[:10]:
            print(f"  [{tipo}] {nome}")
        print()

    nome, processo, vara, tipo, texto = candidatos[0]
    print("=" * 72)
    print(nome)
    if processo:
        print(f"Processo: {processo}")
    if vara:
        print(f"Vara: {vara}")
    print(f"Tipo: {tipo}")
    print("=" * 72)
    print()
    texto = (texto or "").strip()
    if inteiro or len(texto) <= 12000:
        print(texto)
    else:
        print(texto[:12000])
        print()
        print(f"[... truncado, {len(texto) - 12000} caracteres. Usa --inteiro.]")
    return 0


def modelos(conexao: sqlite3.Connection, tipo: str, quantos: int) -> int:
    """Peças mais completas de um tipo, para servirem de referência estrutural.

    Ordena por extensão de texto: a peça mais longa de um tipo é geralmente a
    mais completa, e é essa que mostra a estrutura toda -- preâmbulo, quesitos,
    fundamentação, encerramento -- em vez de uma versão abreviada.
    """
    linhas = list(
        conexao.execute(
            """SELECT d.nome, d.processo, d.vara, d.caracteres, t.texto
               FROM documentos d JOIN textos t ON t.rowid = d.id
               WHERE d.tipo = ? AND d.caracteres > 0
               ORDER BY d.caracteres DESC LIMIT ?""",
            (tipo, quantos),
        )
    )
    if not linhas:
        print(f"Nenhuma peca do tipo '{tipo}' com texto legivel.")
        print(f"Tipos disponiveis: {', '.join(TIPOS)}")
        return 1

    for nome, processo, vara, caracteres, texto in linhas:
        print("=" * 72)
        print(nome)
        if processo:
            print(f"Processo: {processo}")
        if vara:
            print(f"Vara: {vara}")
        print(f"{caracteres} caracteres")
        print("=" * 72)
        print((texto or "").strip()[:8000])
        print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Consultas ao acervo para apoiar a redacao de pecas."
    )
    parser.add_argument("--indice", default=str(INDICE_PREDEFINIDO))
    parser.add_argument("--resumo", action="store_true", help="panorama do acervo")
    parser.add_argument("--processo", help="todas as pecas de um processo")
    parser.add_argument("--ler", help="texto integral do documento cujo nome contenha isto")
    parser.add_argument("--inteiro", action="store_true", help="nao truncar o texto")
    parser.add_argument("--modelos", help=f"pecas de referencia ({'|'.join(TIPOS)})")
    parser.add_argument("--quantos", type=int, default=2)
    args = parser.parse_args()

    indice = Path(args.indice)
    if not indice.exists():
        print(f"ERRO: indice nao existe: {indice}", file=sys.stderr)
        print("Corre primeiro: python indexar_pericias.py --pasta <pasta>", file=sys.stderr)
        return 2

    conexao = abrir_indice(indice)
    try:
        if args.resumo:
            return resumo(conexao)
        if args.processo:
            return por_processo(conexao, args.processo)
        if args.ler:
            return ler(conexao, args.ler, args.inteiro)
        if args.modelos:
            return modelos(conexao, args.modelos, args.quantos)
        parser.print_help()
        return 1
    finally:
        conexao.close()


if __name__ == "__main__":
    raise SystemExit(main())
