#!/usr/bin/env python3
"""
Indexa um acervo entregue em ZIPs sem precisar de espaco para o descomprimir todo.

Processa um ZIP de cada vez: extrai para uma pasta temporaria, indexa o texto,
apaga o que extraiu, passa ao seguinte. O pico de disco e o tamanho do maior
ZIP descomprimido, nao a soma de todos.

E retomavel: se interromperes a meio, volta a correr e continua de onde ficou.

    python processar_zips.py --zips C:\\zips-pericias
    python processar_zips.py --zips C:\\zips-pericias --apagar-zip
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
import time
import zipfile
from pathlib import Path

from indexar_pericias import (
    INDICE_PREDEFINIDO,
    abrir_indice,
    indexar,
    localizar_tessdata,
)

TABELA_LOTES = """
CREATE TABLE IF NOT EXISTS lotes (
    ficheiro     TEXT PRIMARY KEY,
    bytes        INTEGER,
    documentos   INTEGER,
    processado_em REAL
);
"""


def ja_processados(indice: Path) -> set[str]:
    conexao = abrir_indice(indice)
    conexao.executescript(TABELA_LOTES)
    nomes = {linha[0] for linha in conexao.execute("SELECT ficheiro FROM lotes")}
    conexao.close()
    return nomes


def registar_lote(indice: Path, nome: str, tamanho: int, documentos: int) -> None:
    conexao = abrir_indice(indice)
    conexao.executescript(TABELA_LOTES)
    conexao.execute(
        "INSERT OR REPLACE INTO lotes VALUES (?, ?, ?, ?)",
        (nome, tamanho, documentos, time.time()),
    )
    conexao.commit()
    conexao.close()


def contar_documentos(indice: Path) -> int:
    conexao = abrir_indice(indice)
    total = conexao.execute("SELECT COUNT(*) FROM documentos").fetchone()[0]
    conexao.close()
    return total


def maior_id(indice: Path) -> int:
    conexao = abrir_indice(indice)
    valor = conexao.execute("SELECT COALESCE(MAX(id), 0) FROM documentos").fetchone()[0]
    conexao.close()
    return valor


def reparar(indice: Path) -> int:
    """Repara indices escritos pela versao que normalizava o caminho tarde demais.

    Essa versao guardava o caminho absoluto da pasta de extracao e so depois o
    convertia para relativo, o que duplicava cada documento a cada corrida e
    rebentava na conversao. Aqui as linhas absolutas ganham o caminho relativo
    e as antigas duplicadas -- que nao passaram por OCR -- sao descartadas.
    """
    conexao = abrir_indice(indice)
    marcadores = ("\\\\?\\", "C:\\_x\\", "/_extracao/", "\\_extracao\\")

    linhas = list(conexao.execute("SELECT id, caminho, caracteres FROM documentos"))
    absolutos = [
        (i, c, n) for i, c, n in linhas if any(m in c for m in marcadores)
    ]
    if not absolutos:
        print("Nada a reparar.")
        conexao.close()
        return 0

    por_relativo = {c: i for i, c, _ in linhas if not any(m in c for m in marcadores)}

    convertidos = descartados = 0
    for doc_id, caminho, _ in absolutos:
        relativo = caminho
        for marcador in ("_x\\", "_extracao\\", "_x/", "_extracao/"):
            if marcador in relativo:
                relativo = relativo.split(marcador, 1)[1]
                break

        antigo = por_relativo.get(relativo)
        if antigo is not None:
            # A linha nova traz o texto do OCR; a antiga nao. Fica a nova.
            conexao.execute("DELETE FROM textos WHERE rowid = ?", (antigo,))
            conexao.execute("DELETE FROM documentos WHERE id = ?", (antigo,))
            descartados += 1
        conexao.execute(
            "UPDATE documentos SET caminho = ? WHERE id = ?", (relativo, doc_id)
        )
        convertidos += 1

    conexao.commit()
    total = conexao.execute("SELECT COUNT(*) FROM documentos").fetchone()[0]
    conexao.close()
    print(f"Caminhos corrigidos : {convertidos}")
    print(f"Duplicados removidos: {descartados}")
    print(f"Total no indice     : {total} documentos")
    return 0


def espaco_livre_gb(caminho: Path) -> float:
    return shutil.disk_usage(caminho).free / 1024**3


def caminho_longo(p: Path) -> str:
    r"""Forma do caminho que ignora o limite de 260 caracteres do Windows.

    Os acervos periciais tem arvores muito fundas (relatorios de
    comissionamento, anexos por disciplina) e estouram MAX_PATH com
    facilidade. O prefixo \\?\ desliga esse limite, mas exige um caminho
    absoluto e so com barras invertidas.
    """
    if os.name != "nt":
        return str(p)
    absoluto = os.path.abspath(str(p))
    if absoluto.startswith("\\\\?\\"):
        return absoluto
    if absoluto.startswith("\\\\"):  # partilha de rede
        return "\\\\?\\UNC\\" + absoluto[2:]
    return "\\\\?\\" + absoluto


def extrair(zip_path: Path, destino: Path) -> tuple[int, int, str | None]:
    """Extrai um ZIP ficheiro a ficheiro.

    Devolve (extraidos, saltados, erro_fatal). Extrair membro a membro em vez
    de chamar extractall e deliberado: um unico caminho problematico fazia
    abortar o lote inteiro e perdiam-se os milhares de ficheiros bons que
    vinham no mesmo ZIP.
    """
    destino.mkdir(parents=True, exist_ok=True)
    alvo = caminho_longo(destino)
    extraidos = saltados = 0
    try:
        with zipfile.ZipFile(zip_path) as z:
            for membro in z.infolist():
                if membro.is_dir():
                    continue
                try:
                    z.extract(membro, alvo)
                    extraidos += 1
                except Exception:  # noqa: BLE001,PERF203
                    saltados += 1
    except zipfile.BadZipFile:
        # Tipicamente um download que nao terminou. Nao vale a pena insistir.
        return extraidos, saltados, "ZIP corrompido ou incompleto"
    except Exception as erro:  # noqa: BLE001
        return extraidos, saltados, f"{type(erro).__name__}: {erro}"
    return extraidos, saltados, None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Indexa um acervo em ZIPs processando um de cada vez."
    )
    parser.add_argument("--zips", help="pasta com os ficheiros .zip")
    parser.add_argument(
        "--reparar",
        action="store_true",
        help="corrige um indice deixado inconsistente por versoes anteriores",
    )
    parser.add_argument(
        "--temp",
        help="pasta de trabalho (por omissao, uma subpasta de --zips)",
    )
    parser.add_argument("--indice", default=str(INDICE_PREDEFINIDO))
    parser.add_argument("--colecao", default="pericias")
    parser.add_argument(
        "--apagar-zip",
        action="store_true",
        help="apagar cada ZIP depois de indexado (liberta disco a meio do processo)",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="ler digitalizacoes por OCR (muito mais lento, recupera-as para a pesquisa)",
    )
    parser.add_argument("--lingua", default="por")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument(
        "--minimo-livre-gb",
        type=float,
        default=5.0,
        help="aborta se o disco livre descer abaixo disto",
    )
    args = parser.parse_args()

    if args.reparar:
        return reparar(Path(args.indice))

    if not args.zips:
        parser.error("indica --zips")

    pasta_zips = Path(args.zips).expanduser()
    if not pasta_zips.is_dir():
        print(f"ERRO: pasta nao encontrada: {pasta_zips}", file=sys.stderr)
        return 2

    if args.temp:
        temp = Path(args.temp).expanduser()
    elif os.name == "nt":
        # Raiz curta de proposito: cada caracter aqui e um caracter a menos
        # disponivel para a arvore que vem dentro do ZIP.
        temp = Path(f"{Path(pasta_zips).drive or 'C:'}\\_x")
    else:
        temp = pasta_zips / "_extracao"
    indice = Path(args.indice)

    if args.ocr and not localizar_tessdata():
        print(
            "ERRO: Tesseract nao encontrado. Instala-o e/ou define TESSDATA_PREFIX.",
            file=sys.stderr,
        )
        return 2

    zips = sorted(pasta_zips.glob("*.zip"))
    if not zips:
        print(f"ERRO: nenhum .zip em {pasta_zips}", file=sys.stderr)
        return 2

    feitos = ja_processados(indice)
    pendentes = [z for z in zips if z.name not in feitos]

    total_gb = sum(z.stat().st_size for z in zips) / 1024**3
    print(f"ZIPs encontrados : {len(zips)} ({total_gb:.1f} GB)")
    print(f"Ja processados   : {len(feitos)}")
    print(f"Por processar    : {len(pendentes)}")
    print(f"Disco livre      : {espaco_livre_gb(pasta_zips):.1f} GB")
    print(f"Pasta de trabalho: {temp}")
    print()

    if not pendentes:
        print("Nada por fazer. O acervo ja esta todo indexado.")
        print(f"Total no indice: {contar_documentos(indice)} documentos")
        return 0

    inicio = time.monotonic()
    falhados: list[tuple[str, str]] = []

    for i, zip_path in enumerate(pendentes, 1):
        livre = espaco_livre_gb(pasta_zips)
        if livre < args.minimo_livre_gb:
            print()
            print(f"ABORTADO: so restam {livre:.1f} GB livres.")
            print("Liberta espaco e volta a correr -- continua de onde ficou.")
            return 3

        tamanho_gb = zip_path.stat().st_size / 1024**3
        print("=" * 68)
        print(f"[{i}/{len(pendentes)}] {zip_path.name}  ({tamanho_gb:.2f} GB)")
        print(f"disco livre: {livre:.1f} GB")

        shutil.rmtree(caminho_longo(temp), ignore_errors=True)

        extraidos, saltados, erro = extrair(zip_path, temp)
        if erro and extraidos == 0:
            print(f"  FALHOU: {erro}")
            falhados.append((zip_path.name, erro))
            shutil.rmtree(caminho_longo(temp), ignore_errors=True)
            continue
        if erro:
            print(f"  AVISO: {erro} -- {extraidos} ficheiros salvos antes disso")
            falhados.append((zip_path.name, f"parcial: {erro}"))
        if saltados:
            # Nunca deixar isto passar em silencio: o acervo tem de ficar
            # completo, e um ficheiro perdido sem aviso e pior que um erro.
            print(f"  ATENCAO: {saltados} ficheiro(s) nao extraidos")
            falhados.append((zip_path.name, f"{saltados} ficheiro(s) nao extraidos"))

        print(f"  extraidos {extraidos} ficheiros, a indexar...")
        antes = contar_documentos(indice)
        try:
            indexar(
                Path(caminho_longo(temp)),
                indice,
                args.colecao,
                None,
                args.ocr,
                args.lingua,
                args.dpi,
                Path(caminho_longo(temp)),
                zip_path.name,
                False,
            )
        except Exception as erro:  # noqa: BLE001
            print(f"  ERRO ao indexar: {type(erro).__name__}: {erro}")
            falhados.append((zip_path.name, str(erro)))
            shutil.rmtree(caminho_longo(temp), ignore_errors=True)
            continue
        novos = contar_documentos(indice) - antes

        # Apagar antes de passar ao proximo -- e isto que mantem o pico baixo.
        shutil.rmtree(caminho_longo(temp), ignore_errors=True)
        registar_lote(indice, zip_path.name, zip_path.stat().st_size, novos)

        if args.apagar_zip:
            zip_path.unlink()
            print(f"  ZIP apagado ({tamanho_gb:.2f} GB libertados)")

        print(f"  +{novos} documentos no indice")
        print()

    segundos = time.monotonic() - inicio
    print("=" * 68)
    print(f"Concluido em {segundos / 60:.1f} min")
    print(f"Total no indice: {contar_documentos(indice)} documentos")
    print(f"Disco livre    : {espaco_livre_gb(pasta_zips):.1f} GB")

    if falhados:
        print()
        print(f"{len(falhados)} ZIP(s) falharam:")
        for nome, erro in falhados:
            print(f"  {nome}: {erro}")
        print("Volta a descarrega-los e corre outra vez -- so estes serao processados.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
