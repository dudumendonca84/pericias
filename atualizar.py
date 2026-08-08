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

from configurar import CONFIG, INDICE, RAIZ, ler_config


def main() -> int:
    if not CONFIG.exists():
        print("Ainda nao esta configurado. Corre primeiro: python configurar.py")
        return 1

    config = ler_config()
    alvo = config.get("pasta_acervo") or config.get("pasta_zips")
    if not alvo or not Path(alvo).is_dir():
        print(f"A pasta configurada nao existe: {alvo or '(nenhuma)'}")
        print("Corre: python configurar.py")
        return 1

    antes = 0
    if INDICE.exists():
        import sqlite3

        from indexar_pericias import abrir_indice

        conexao = abrir_indice(INDICE)
        antes = conexao.execute("SELECT COUNT(*) FROM documentos").fetchone()[0]
        conexao.close()

    print(f"Acervo   : {alvo}")
    print(f"No indice: {antes} documentos")
    print()

    guiao = "processar_zips.py" if config.get("pasta_zips") else "indexar_pericias.py"
    bandeira = "--zips" if config.get("pasta_zips") else "--pasta"
    comando = [sys.executable, str(RAIZ / guiao), bandeira, alvo]
    if config.get("ocr"):
        comando += ["--ocr", "--lingua", config.get("lingua", "por")]

    resultado = subprocess.run(comando, cwd=RAIZ)
    if resultado.returncode != 0:
        return resultado.returncode

    # As regras de extracao de vara e tipo evoluem; aplica-las ao que ja estava
    # indexado e barato e evita que o acervo fique com metade dos documentos
    # classificados por regras antigas.
    subprocess.run(
        [sys.executable, str(RAIZ / "indexar_pericias.py"), "--renormalizar"],
        cwd=RAIZ,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
