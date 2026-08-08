#!/usr/bin/env python3
"""
Instalacao e configuracao do acervo, sem exigir conhecimentos de terminal.

Faz as perguntas todas de uma vez, guarda as respostas, e a partir dai os
outros comandos deixam de precisar de argumentos. Correr de novo serve para
mudar a pasta do acervo ou reinstalar dependencias.

    python configurar.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CONFIG = RAIZ / "config.json"
INDICE = RAIZ / "acervo_pericias.sqlite"

PADRAO = {
    "pasta_acervo": "",
    "pasta_zips": "",
    "ocr": True,
    "lingua": "por",
}


def ler_config() -> dict:
    if CONFIG.exists():
        try:
            return {**PADRAO, **json.loads(CONFIG.read_text(encoding="utf-8"))}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(PADRAO)


def gravar_config(config: dict) -> None:
    CONFIG.write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def titulo(texto: str) -> None:
    print()
    print(texto)
    print("-" * len(texto))


def perguntar(pergunta: str, predefinido: str = "") -> str:
    sufixo = f" [{predefinido}]" if predefinido else ""
    resposta = input(f"{pergunta}{sufixo}: ").strip().strip('"')
    return resposta or predefinido


def sim_nao(pergunta: str, predefinido: bool = True) -> bool:
    marca = "S/n" if predefinido else "s/N"
    resposta = input(f"{pergunta} [{marca}]: ").strip().lower()
    if not resposta:
        return predefinido
    return resposta.startswith("s")


def verificar_dependencias() -> bool:
    titulo("1. Dependencias")
    em_falta = []
    for modulo, pacote in (("fitz", "pymupdf"), ("docx", "python-docx")):
        try:
            __import__(modulo)
            print(f"  {pacote}: instalado")
        except ImportError:
            print(f"  {pacote}: EM FALTA")
            em_falta.append(pacote)

    if not em_falta:
        return True

    if not sim_nao(f"Instalar {' e '.join(em_falta)} agora?"):
        print("  Sem estes pacotes o acervo nao pode ser lido.")
        return False

    # --trusted-host: redes com proxy corporativo (Zscaler e afins) quebram a
    # verificacao TLS do pip, e sem isto a instalacao falha sem razao aparente.
    comando = [
        sys.executable, "-m", "pip", "install",
        "--trusted-host", "pypi.org",
        "--trusted-host", "files.pythonhosted.org",
        *em_falta,
    ]
    print(f"  a instalar...")
    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode != 0:
        print("  FALHOU:")
        print("  " + (resultado.stderr or "").strip()[-600:])
        return False
    print("  instalado")
    return True


def verificar_ocr() -> bool:
    titulo("2. OCR (opcional)")
    sys.path.insert(0, str(RAIZ))
    from indexar_pericias import localizar_tessdata

    pasta = localizar_tessdata()
    if not pasta:
        print("  Tesseract: NAO ENCONTRADO")
        print("  Sem OCR, as pericias digitalizadas ficam fora da pesquisa.")
        print("  Para instalar:  winget install UB-Mannheim.TesseractOCR")
        print("  E depois o portugues, de")
        print("  https://github.com/tesseract-ocr/tessdata/raw/main/por.traineddata")
        print("  para a pasta tessdata da instalacao.")
        return False

    print(f"  Tesseract: {pasta}")
    if (Path(pasta) / "por.traineddata").exists():
        print("  portugues: instalado")
        return True
    print("  portugues: EM FALTA -- o OCR vai ler em ingles e errar acentos")
    return False


def escolher_pasta(config: dict) -> bool:
    titulo("3. Onde esta o acervo")
    print("  A pasta com os PDFs e documentos das pericias.")
    print("  Se o acervo ainda esta em ficheiros ZIP, indica a pasta dos ZIP.")
    print()

    caminho = perguntar("Pasta", config.get("pasta_acervo", ""))
    if not caminho:
        print("  Sem pasta nao ha nada a indexar.")
        return False

    pasta = Path(caminho).expanduser()
    if not pasta.is_dir():
        print(f"  Nao existe: {pasta}")
        return False

    zips = list(pasta.glob("*.zip"))
    documentos = [
        p for p in pasta.rglob("*")
        if p.is_file() and p.suffix.lower() in {".pdf", ".docx", ".doc", ".rtf"}
    ]
    print(f"  {len(documentos)} documentos, {len(zips)} ficheiros ZIP")

    if zips and not documentos:
        config["pasta_zips"] = str(pasta)
        config["pasta_acervo"] = ""
        print("  Modo: acervo em ZIP (extraidos um de cada vez, sem encher o disco)")
    else:
        config["pasta_acervo"] = str(pasta)
        config["pasta_zips"] = ""
        print("  Modo: pasta de documentos")
    return True


def criar_atalho() -> None:
    titulo("4. Atalho no ambiente de trabalho")
    origem = RAIZ / "Procurar Pericias.bat"
    if not origem.exists():
        print("  (ficheiro de atalho nao encontrado, saltado)")
        return

    ambiente = Path.home() / "Desktop"
    if not ambiente.is_dir():
        ambiente = Path.home() / "Ambiente de Trabalho"
    if not ambiente.is_dir():
        print("  (ambiente de trabalho nao encontrado, saltado)")
        return

    if not sim_nao("Criar atalho para a janela de pesquisa?"):
        return
    try:
        shutil.copy(origem, ambiente / "Procurar Pericias.bat")
        print(f"  criado em {ambiente}")
    except OSError as erro:
        print(f"  nao foi possivel criar: {erro}")


def indexar_agora(config: dict, com_ocr: bool) -> None:
    titulo("5. Construir o acervo")
    alvo = config.get("pasta_acervo") or config.get("pasta_zips")
    if not alvo:
        return

    if INDICE.exists():
        print(f"  Ja existe um acervo em {INDICE.name}.")
        if not sim_nao("Acrescentar o que houver de novo?"):
            return

    print("  Isto demora: com OCR, horas para um acervo grande.")
    print("  Pode ser interrompido e retomado a qualquer momento.")
    if not sim_nao("Comecar agora?"):
        print("  Podes correr depois com:  python atualizar.py")
        return

    guiao = "processar_zips.py" if config.get("pasta_zips") else "indexar_pericias.py"
    bandeira = "--zips" if config.get("pasta_zips") else "--pasta"
    comando = [sys.executable, str(RAIZ / guiao), bandeira, alvo]
    if com_ocr and config.get("ocr"):
        comando += ["--ocr", "--lingua", config.get("lingua", "por")]

    print()
    subprocess.run(comando, cwd=RAIZ)


def main() -> int:
    print("=" * 60)
    print("  ACERVO DE PERICIAS -- configuracao")
    print("=" * 60)

    config = ler_config()

    if not verificar_dependencias():
        return 1

    tem_ocr = verificar_ocr()
    config["ocr"] = tem_ocr and sim_nao("Usar OCR nas digitalizacoes?", tem_ocr)

    if not escolher_pasta(config):
        return 1

    gravar_config(config)
    print(f"\n  Configuracao guardada em {CONFIG.name}")

    criar_atalho()
    indexar_agora(config, config["ocr"])

    titulo("Pronto")
    print("  Procurar        : abre o atalho 'Procurar Pericias'")
    print("  Pericias novas  : python atualizar.py")
    print("  Reconfigurar    : python configurar.py")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrompido.")
        raise SystemExit(1) from None
