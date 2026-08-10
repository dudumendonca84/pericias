#!/usr/bin/env python3
"""
Instalacao e configuracao do acervo, sem exigir conhecimentos de terminal.

Faz as perguntas todas de uma vez, guarda as respostas, e a partir dai os
outros comandos deixam de precisar de argumentos. Correr de novo serve para
mudar a pasta do acervo ou reinstalar dependencias.

    python configurar.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import string
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CONFIG = RAIZ / "config.json"
INDICE = RAIZ / "acervo_pericias.sqlite"

PADRAO = {
    # Lista, nao um caminho: um perito costuma ter o acervo repartido por
    # varias pastas -- laudos numa, peticoes noutra -- e indexar so uma
    # deixava metade do trabalho dele invisivel.
    "pastas": [],
    "ocr": True,
    "lingua": "por",
}


def ler_config() -> dict:
    config = dict(PADRAO)
    if CONFIG.exists():
        try:
            config.update(json.loads(CONFIG.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass

    # Configuracoes escritas pela versao de pasta unica continuam a abrir.
    for antigo in ("pasta_acervo", "pasta_zips"):
        caminho = config.pop(antigo, "")
        if caminho and caminho not in [p["caminho"] for p in config["pastas"]]:
            config["pastas"].append(
                {"caminho": caminho, "zips": antigo == "pasta_zips"}
            )
    return config


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
        print("  https://raw.githubusercontent.com/tesseract-ocr/tessdata/main/por.traineddata")
        print("  para a pasta tessdata da instalacao.")
        return False

    print(f"  Tesseract: {pasta}")
    if (Path(pasta) / "por.traineddata").exists():
        print("  portugues: instalado")
        return True
    print("  portugues: EM FALTA -- o OCR vai ler em ingles e errar acentos")
    return False


# Nomes que valem a pena procurar sozinho antes de perguntar. O Drive chama-se
# "My Drive" ou "Meu Drive" conforme a lingua da conta, e os nomes das pastas
# levam acentos que ninguem acerta a escrever a primeira.
NOMES_ACERVO = ("eletranabc2", "pericias judiciais", "pericia", "laudo")


def sem_acentos_simples(texto: str) -> str:
    import unicodedata

    return "".join(
        c
        for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    ).lower()


def procurar_pastas() -> list[Path]:
    """Procura pastas de pericias nas unidades e nas raizes habituais.

    Poupa escrever caminhos a mao, que e onde se erra: a letra da unidade
    muda, "My Drive" pode ser "Meu Drive", e os acentos raramente sobrevivem
    a ser escritos de cabeca.
    """
    raizes: list[Path] = []
    for letra in string.ascii_uppercase:
        unidade = Path(f"{letra}:\\")
        if not unidade.is_dir():
            continue
        raizes.append(unidade)
        for nome in ("My Drive", "Meu Drive", "Meu disco"):
            if (unidade / nome).is_dir():
                raizes.append(unidade / nome)
    raizes += [Path.home(), Path.home() / "Documents", Path.home() / "Documentos"]

    encontradas: list[Path] = []
    for raiz in raizes:
        try:
            for candidata in raiz.iterdir():
                if not candidata.is_dir():
                    continue
                nome = sem_acentos_simples(candidata.name)
                if any(alvo in nome for alvo in NOMES_ACERVO):
                    if candidata not in encontradas:
                        encontradas.append(candidata)
        except (OSError, PermissionError):
            continue
    return encontradas


def examinar(caminho: str) -> dict | None:
    pasta = Path(caminho).expanduser()
    if not pasta.is_dir():
        print(f"  Nao existe: {pasta}")
        return None

    zips = list(pasta.glob("*.zip"))
    documentos = [
        p for p in pasta.rglob("*")
        if p.is_file() and p.suffix.lower() in {".pdf", ".docx", ".doc", ".rtf"}
    ]
    print(f"  {len(documentos)} documentos, {len(zips)} ficheiros ZIP")

    if not documentos and not zips:
        print("  Nada para indexar aqui -- confirma o caminho.")
        return None

    so_zips = bool(zips) and not documentos
    print(
        "  Modo: acervo em ZIP (extraidos um de cada vez, sem encher o disco)"
        if so_zips
        else "  Modo: pasta de documentos"
    )
    return {"caminho": str(pasta), "zips": so_zips}


def escolher_pastas(config: dict) -> bool:
    titulo("3. Onde estao as pericias")

    if not config["pastas"]:
        sugestoes = procurar_pastas()
        if sugestoes:
            print("  Encontrei estas pastas:")
            for i, s in enumerate(sugestoes, 1):
                print(f"    {i}. {s}")
            print()
            if sim_nao("Usar estas?"):
                for candidata in sugestoes:
                    registo = examinar(str(candidata))
                    if registo:
                        config["pastas"].append(registo)
                if config["pastas"]:
                    print()
                    print(f"  {len(config['pastas'])} pasta(s) a indexar.")
                    return True

    print("  As pastas com os documentos. Podem ser varias -- laudos numa,")
    print("  peticoes noutra. Se o acervo estiver em ZIP, indica a pasta dos ZIP.")
    print("  Enter numa linha vazia termina.")

    if config["pastas"]:
        print()
        print("  Ja configuradas:")
        for p in config["pastas"]:
            print(f"    {p['caminho']}")
        print()
        if not sim_nao("Manter estas e acrescentar mais?", True):
            config["pastas"] = []

    conhecidas = {p["caminho"] for p in config["pastas"]}
    while True:
        print()
        caminho = perguntar(f"Pasta {len(config['pastas']) + 1} (Enter para terminar)")
        if not caminho:
            break
        registo = examinar(caminho)
        if registo and registo["caminho"] not in conhecidas:
            config["pastas"].append(registo)
            conhecidas.add(registo["caminho"])

    if not config["pastas"]:
        print("  Sem pastas nao ha nada a indexar.")
        return False

    print()
    print(f"  {len(config['pastas'])} pasta(s) a indexar.")
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


def agendar_atualizacao() -> None:
    """Oferece correr a actualizacao sozinha.

    Sem isto, alguem tem de se lembrar de correr o atualizar.py depois de cada
    peca entregue. Quem nao se lembra fica com um acervo a envelhecer em
    silencio -- devolve menos do que devia e nao da sinal nenhum.
    """
    titulo("5. Actualizacao automatica")
    if sys.platform != "win32":
        print("  (so disponivel no Windows; noutros sistemas usa o cron)")
        return

    print("  As pericias novas podem ser indexadas sozinhas, de madrugada.")
    if not sim_nao("Agendar?"):
        print("  Podes agendar depois com:  python agendar.py")
        return

    subprocess.run([sys.executable, str(RAIZ / "agendar.py")], cwd=RAIZ)


def comando_para(pasta: dict, config: dict) -> list[str]:
    guiao = "processar_zips.py" if pasta["zips"] else "indexar_pericias.py"
    bandeira = "--zips" if pasta["zips"] else "--pasta"
    comando = [sys.executable, str(RAIZ / guiao), bandeira, pasta["caminho"]]
    if config.get("ocr"):
        comando += ["--ocr", "--lingua", config.get("lingua", "por")]
    return comando


def indexar_agora(config: dict) -> None:
    titulo("6. Construir o acervo")
    if not config["pastas"]:
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

    for i, pasta in enumerate(config["pastas"], 1):
        print()
        print(f"--- pasta {i}/{len(config['pastas'])}: {pasta['caminho']}")
        subprocess.run(comando_para(pasta, config), cwd=RAIZ)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configura o acervo de pericias."
    )
    parser.add_argument(
        "--pastas", nargs="+", metavar="PASTA",
        help="caminhos do acervo, sem perguntar",
    )
    args = parser.parse_args()

    if args.pastas:
        config = ler_config()
        config["pastas"] = []
        for caminho in args.pastas:
            print(f"{caminho}")
            registo = examinar(caminho)
            if registo:
                config["pastas"].append(registo)
        if not config["pastas"]:
            print("Nenhuma pasta valida.")
            return 1
        gravar_config(config)
        print(f"\nGuardado em {CONFIG.name}. Para indexar:  python atualizar.py")
        return 0

    print("=" * 60)
    print("  ACERVO DE PERICIAS -- configuracao")
    print("=" * 60)

    config = ler_config()

    if not verificar_dependencias():
        return 1

    tem_ocr = verificar_ocr()
    config["ocr"] = tem_ocr and sim_nao("Usar OCR nas digitalizacoes?", tem_ocr)

    if not escolher_pastas(config):
        return 1

    gravar_config(config)
    print(f"\n  Configuracao guardada em {CONFIG.name}")

    criar_atalho()
    agendar_atualizacao()
    indexar_agora(config)

    titulo("Pronto")
    print("  Procurar        : abre o atalho 'Procurar Pericias'")
    print("  Pericias novas  : sozinho, ou python atualizar.py")
    print("  Ver agendamento : python agendar.py --estado")
    print("  Reconfigurar    : python configurar.py")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrompido.")
        raise SystemExit(1) from None
