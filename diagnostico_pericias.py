#!/usr/bin/env python3
"""
Diagnostico de um corpus de laudos periciais.

Percorre uma pasta, tenta extrair texto de cada documento e reporta o que
consegue ler, o que falha e porque. Nao modifica, move nem renomeia nada:
todos os ficheiros sao abertos em modo leitura.

Uso tipico:
    python diagnostico_pericias.py --pasta "G:/Meu Drive/pericias" --limite 30
    python diagnostico_pericias.py --pasta "G:/Meu Drive/pericias"
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# Extensoes que contem texto util. Tudo o resto e ruido de sincronizacao
# (.tmp do Word, .lnk do Windows) e conta como ignorado, nao como falha.
EXTENSOES_DOCUMENTO = {".pdf", ".docx", ".doc", ".rtf", ".odt", ".txt"}
EXTENSOES_RUIDO = {".tmp", ".lnk", ".ini", ".ds_store", ".gdoc", ".gsheet"}

# Abaixo deste numero de caracteres por pagina assume-se que o PDF nao tem
# camada de texto -- e digitalizacao e precisa de OCR para ser aproveitado.
LIMIAR_CARACTERES_POR_PAGINA = 80


@dataclass
class Resultado:
    caminho: Path
    extensao: str
    bytes_ficheiro: int
    estado: str  # ok | vazio | ocr | falha | ignorado | nuvem
    caracteres: int = 0
    paginas: int = 0
    detalhe: str = ""


@dataclass
class Resumo:
    resultados: list[Resultado] = field(default_factory=list)
    segundos: float = 0.0

    def por_estado(self) -> Counter:
        return Counter(r.estado for r in self.resultados)

    def por_extensao(self) -> Counter:
        return Counter(r.extensao for r in self.resultados)


def so_na_nuvem(caminho: Path) -> bool:
    """Deteta ficheiros que o Google Drive/OneDrive ainda nao materializou.

    No Windows estes ficheiros existem na listagem mas o conteudo so e
    descarregado quando alguem os abre. Se a sincronizacao offline nao
    terminou, abri-los em massa e lento e pouco fiavel -- vale mais
    detetar e avisar.
    """
    if os.name != "nt":
        return False
    try:
        atributos = os.stat(caminho, follow_symlinks=False).st_file_attributes
    except (OSError, AttributeError):
        return False
    FILE_ATTRIBUTE_OFFLINE = 0x1000
    FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x40000
    FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000
    mascara = (
        FILE_ATTRIBUTE_OFFLINE
        | FILE_ATTRIBUTE_RECALL_ON_OPEN
        | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
    )
    return bool(atributos & mascara)


def extrair_pdf(caminho: Path) -> tuple[str, int, int, str]:
    import fitz  # pymupdf

    with fitz.open(caminho) as doc:
        if doc.needs_pass:
            return "falha", 0, 0, "PDF protegido por palavra-passe"
        paginas = doc.page_count
        texto = "".join(pagina.get_text() for pagina in doc)

    caracteres = len(texto.strip())
    if paginas == 0:
        return "falha", caracteres, paginas, "PDF sem paginas"
    if caracteres == 0:
        return "ocr", caracteres, paginas, "sem camada de texto (digitalizacao)"
    if caracteres / paginas < LIMIAR_CARACTERES_POR_PAGINA:
        return (
            "ocr",
            caracteres,
            paginas,
            f"camada de texto residual ({caracteres // paginas} car/pag)",
        )
    return "ok", caracteres, paginas, ""


def extrair_docx(caminho: Path) -> tuple[str, int, int, str]:
    import docx

    documento = docx.Document(str(caminho))
    partes = [p.text for p in documento.paragraphs]
    for tabela in documento.tables:
        for linha in tabela.rows:
            partes.extend(celula.text for celula in linha.cells)

    caracteres = len("\n".join(partes).strip())
    if caracteres == 0:
        return "vazio", 0, 0, "documento sem texto"
    return "ok", caracteres, 0, ""


def extrair_texto_simples(caminho: Path) -> tuple[str, int, int, str]:
    dados = caminho.read_bytes()
    for codificacao in ("utf-8", "cp1252", "latin-1"):
        try:
            texto = dados.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    else:
        return "falha", 0, 0, "codificacao nao reconhecida"

    if caminho.suffix.lower() == ".rtf":
        # Heuristica deliberadamente grosseira: conta so o que esta fora das
        # chavetas de controlo. Serve para saber se ha texto, nao para o extrair.
        texto = "".join(c for c in texto if c.isprintable())

    caracteres = len(texto.strip())
    if caracteres == 0:
        return "vazio", 0, 0, "ficheiro sem texto"
    return "ok", caracteres, 0, ""


def analisar(caminho: Path, verificar_nuvem: bool = True) -> Resultado:
    extensao = caminho.suffix.lower()
    try:
        tamanho = caminho.stat().st_size
    except OSError as erro:
        return Resultado(caminho, extensao, 0, "falha", detalhe=f"stat: {erro}")

    base = Resultado(caminho, extensao, tamanho, "ok")

    if extensao in EXTENSOES_RUIDO or caminho.name.startswith("~$"):
        base.estado = "ignorado"
        base.detalhe = "ficheiro temporario ou atalho"
        return base

    if extensao not in EXTENSOES_DOCUMENTO:
        base.estado = "ignorado"
        base.detalhe = f"extensao fora do ambito ({extensao or 'sem extensao'})"
        return base

    # Ficheiros acabados de extrair de um ZIP estao sempre materializados.
    # Confiar no atributo do Windows nesse caso e um erro: ha maquinas onde
    # ele vem marcado indevidamente e documentos bons ficavam por ler.
    if verificar_nuvem and so_na_nuvem(caminho):
        base.estado = "nuvem"
        base.detalhe = "ainda nao sincronizado localmente"
        return base

    if tamanho == 0:
        base.estado = "vazio"
        base.detalhe = "ficheiro com 0 bytes"
        return base

    try:
        if extensao == ".pdf":
            estado, caracteres, paginas, detalhe = extrair_pdf(caminho)
        elif extensao == ".docx":
            estado, caracteres, paginas, detalhe = extrair_docx(caminho)
        elif extensao in {".txt", ".rtf"}:
            estado, caracteres, paginas, detalhe = extrair_texto_simples(caminho)
        else:
            # .doc e .odt precisam de conversores externos (LibreOffice,
            # antiword). Marcar como ignorado e mais honesto do que falhar.
            base.estado = "ignorado"
            base.detalhe = f"{extensao} precisa de conversao previa"
            return base
    except Exception as erro:  # noqa: BLE001 - queremos o diagnostico, nao a stacktrace
        base.estado = "falha"
        base.detalhe = f"{type(erro).__name__}: {erro}"[:160]
        return base

    base.estado = estado
    base.caracteres = caracteres
    base.paginas = paginas
    base.detalhe = detalhe
    return base


def recolher_ficheiros(pasta: Path) -> list[Path]:
    return sorted(p for p in pasta.rglob("*") if p.is_file())


def escrever_csv(resumo: Resumo, destino: Path) -> None:
    with destino.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(
            ["caminho", "extensao", "bytes", "estado", "caracteres", "paginas", "detalhe"]
        )
        for r in resumo.resultados:
            escritor.writerow(
                [r.caminho, r.extensao, r.bytes_ficheiro, r.estado,
                 r.caracteres, r.paginas, r.detalhe]
            )


def imprimir_resumo(resumo: Resumo, total_encontrado: int) -> None:
    estados = resumo.por_estado()
    analisados = len(resumo.resultados)
    documentos = analisados - estados.get("ignorado", 0)

    print()
    print("=" * 68)
    print("RESUMO")
    print("=" * 68)
    print(f"Ficheiros encontrados na pasta : {total_encontrado}")
    print(f"Ficheiros analisados           : {analisados}")
    print(f"Documentos (fora ruido)        : {documentos}")
    print(f"Tempo                          : {resumo.segundos:.1f}s")
    print()

    print("Por extensao:")
    for extensao, n in resumo.por_extensao().most_common():
        print(f"  {extensao or '(sem extensao)':<16} {n:>6}")
    print()

    etiquetas = {
        "ok": "texto extraido",
        "ocr": "digitalizado, precisa de OCR",
        "vazio": "sem texto",
        "falha": "erro de leitura",
        "nuvem": "so na nuvem, nao sincronizado",
        "ignorado": "ignorado (ruido ou fora do ambito)",
    }
    print("Por estado:")
    for estado, n in estados.most_common():
        percentagem = (n / analisados * 100) if analisados else 0
        print(f"  {estado:<10} {n:>6}  {percentagem:5.1f}%  {etiquetas.get(estado, '')}")
    print()

    if documentos:
        legiveis = estados.get("ok", 0)
        print(f"Taxa de extracao sobre documentos: {legiveis / documentos * 100:.1f}%")

    caracteres = sum(r.caracteres for r in resumo.resultados)
    print(f"Total de caracteres extraidos    : {caracteres:,}".replace(",", " "))

    falhas = [r for r in resumo.resultados if r.estado == "falha"]
    if falhas:
        print()
        print(f"Primeiras falhas ({len(falhas)} no total):")
        for r in falhas[:10]:
            print(f"  {r.caminho.name[:58]:<58} {r.detalhe}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnostico read-only de um corpus de laudos periciais."
    )
    parser.add_argument("--pasta", required=True, help="pasta a analisar (recursivo)")
    parser.add_argument("--limite", type=int, help="analisar apenas os N primeiros")
    parser.add_argument(
        "--csv",
        default="diagnostico_pericias.csv",
        help="ficheiro CSV com o detalhe por documento",
    )
    parser.add_argument(
        "--limiar-nuvem",
        type=float,
        default=20.0,
        help="percentagem de ficheiros so-na-nuvem acima da qual aborta",
    )
    args = parser.parse_args()

    pasta = Path(args.pasta).expanduser()
    if not pasta.is_dir():
        print(f"ERRO: pasta nao encontrada: {pasta}", file=sys.stderr)
        return 2

    print(f"Pasta   : {pasta}")
    ficheiros = recolher_ficheiros(pasta)
    total_encontrado = len(ficheiros)
    print(f"Ficheiros encontrados: {total_encontrado}")

    if args.limite:
        ficheiros = ficheiros[: args.limite]
        print(f"Limite aplicado: {len(ficheiros)}")
    print()

    resumo = Resumo()
    inicio = time.monotonic()

    for i, caminho in enumerate(ficheiros, 1):
        resultado = analisar(caminho)
        resumo.resultados.append(resultado)

        marca = {
            "ok": ".", "ocr": "O", "vazio": "_",
            "falha": "X", "nuvem": "?", "ignorado": "-",
        }[resultado.estado]
        print(marca, end="", flush=True)
        if i % 80 == 0:
            print(f"  {i}/{len(ficheiros)}")

        # Se a sincronizacao offline nao terminou, insistir nos 3000 e perder
        # tempo. Aborta cedo, com uma amostra suficiente para ter confianca.
        if i >= 50:
            na_nuvem = resumo.por_estado().get("nuvem", 0)
            if na_nuvem / i * 100 > args.limiar_nuvem:
                print()
                print()
                print(
                    f"ABORTADO: {na_nuvem} dos primeiros {i} ficheiros estao so na "
                    f"nuvem ({na_nuvem / i * 100:.0f}%)."
                )
                print(
                    "A sincronizacao offline do Drive nao terminou. Marca a pasta "
                    'como "Disponivel offline", espera, e volta a correr.'
                )
                resumo.segundos = time.monotonic() - inicio
                imprimir_resumo(resumo, total_encontrado)
                return 3

    resumo.segundos = time.monotonic() - inicio
    print()

    imprimir_resumo(resumo, total_encontrado)

    destino = Path(args.csv)
    escrever_csv(resumo, destino)
    print()
    print(f"Detalhe por documento escrito em: {destino.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
