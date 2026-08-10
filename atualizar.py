#!/usr/bin/env python3
"""
Acrescenta ao acervo as pericias novas desde a ultima vez.

Nao pede argumentos: usa a pasta guardada pelo configurar.py. E este comando
que faz o acervo crescer -- correr depois de entregar uma peca nova.

    python atualizar.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from configurar import CONFIG, INDICE, RAIZ, comando_para, ler_config


def main() -> int:
    if not CONFIG.exists():
        print("Ainda nao esta configurado. Corre primeiro: python configurar.py")
        return 1

    config = ler_config()
    pastas = [p for p in config["pastas"] if Path(p["caminho"]).is_dir()]
    em_falta = [
        p["caminho"] for p in config["pastas"] if not Path(p["caminho"]).is_dir()
    ]
    for caminho in em_falta:
        # Uma pasta que desapareceu -- Drive por montar, disco externo fora --
        # nao pode fazer perder as outras em silencio.
        print(f"AVISO: pasta nao encontrada, saltada: {caminho}")
    if not pastas:
        print("Nenhuma das pastas configuradas existe.")
        print("Corre: python configurar.py")
        return 1

    antes = 0
    if INDICE.exists():
        import sqlite3

        from indexar_pericias import abrir_indice

        conexao = abrir_indice(INDICE)
        antes = conexao.execute("SELECT COUNT(*) FROM documentos").fetchone()[0]
        conexao.close()

    print(f"Pastas   : {len(pastas)}")
    print(f"No indice: {antes} documentos")

    falhou = False
    for i, pasta in enumerate(pastas, 1):
        print()
        print(f"--- pasta {i}/{len(pastas)}: {pasta['caminho']}")
        resultado = subprocess.run(comando_para(pasta, config), cwd=RAIZ)
        # Uma pasta que falha nao pode impedir as outras de serem indexadas.
        falhou = falhou or resultado.returncode != 0

    # As regras de extracao de vara e tipo evoluem; aplica-las ao que ja estava
    # indexado e barato e evita que o acervo fique com metade dos documentos
    # classificados por regras antigas.
    print()
    subprocess.run(
        [sys.executable, str(RAIZ / "indexar_pericias.py"), "--renormalizar"],
        cwd=RAIZ,
    )
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
