#!/usr/bin/env python3
"""
Liga o acervo ao Claude Desktop, sem ninguem editar ficheiros de configuracao.

Escreve a entrada do servidor MCP no claude_desktop_config.json, preservando o
que la estiver. Depois disto, o Claude Desktop passa a poder consultar o
acervo -- que continua a viver so nesta maquina.

    python instalar_mcp.py
    python instalar_mcp.py --remover
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
SERVIDOR = RAIZ / "mcp_pericias.py"
NOME = "pericias"


def caminho_config() -> Path | None:
    """Onde o Claude Desktop guarda a configuracao, por sistema."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        return Path(base) / "Claude" / "claude_desktop_config.json" if base else None
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json"
        )
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def ler(config: Path) -> dict:
    if not config.exists():
        return {}
    try:
        return json.loads(config.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"AVISO: {config.name} tem JSON invalido; sera substituido.")
        return {}


def instalar(config: Path) -> int:
    if not SERVIDOR.exists():
        print(f"ERRO: {SERVIDOR.name} nao encontrado.")
        return 1

    try:
        import mcp  # noqa: F401
    except ImportError:
        print("O pacote 'mcp' nao esta instalado. A instalar...")
        import subprocess

        resultado = subprocess.run(
            [
                sys.executable, "-m", "pip", "install",
                "--trusted-host", "pypi.org",
                "--trusted-host", "files.pythonhosted.org",
                "mcp",
            ],
            capture_output=True,
            text=True,
        )
        if resultado.returncode != 0:
            print("FALHOU a instalacao do pacote 'mcp':")
            print((resultado.stderr or "").strip()[-500:])
            return 1
        print("  instalado")

    dados = ler(config)
    servidores = dados.setdefault("mcpServers", {})
    ja_existia = NOME in servidores

    servidores[NOME] = {
        "command": sys.executable,
        "args": [str(SERVIDOR)],
    }

    config.parent.mkdir(parents=True, exist_ok=True)
    # Guardar a versao anterior: este ficheiro pode ter outros servidores
    # configurados por outra pessoa, e perde-los seria um estrago silencioso.
    if config.exists():
        shutil.copy(config, config.with_suffix(".json.bak"))
    config.write_text(
        json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"{'Actualizado' if ja_existia else 'Instalado'} em {config}")
    if len(servidores) > 1:
        outros = [n for n in servidores if n != NOME]
        print(f"  (mantidos os outros servidores: {', '.join(outros)})")
    print()
    print("Fecha e volta a abrir o Claude Desktop.")
    print("Depois pergunta, por exemplo:")
    print('  "que laudos tenho sobre infiltracao?"')
    return 0


def remover(config: Path) -> int:
    dados = ler(config)
    if NOME not in dados.get("mcpServers", {}):
        print("Nao estava instalado.")
        return 0
    del dados["mcpServers"][NOME]
    config.write_text(
        json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Removido de {config}")
    print("Fecha e volta a abrir o Claude Desktop.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Liga o acervo de pericias ao Claude Desktop."
    )
    parser.add_argument("--remover", action="store_true")
    args = parser.parse_args()

    config = caminho_config()
    if config is None:
        print("ERRO: nao consegui determinar a pasta do Claude Desktop.")
        return 1

    return remover(config) if args.remover else instalar(config)


if __name__ == "__main__":
    raise SystemExit(main())
