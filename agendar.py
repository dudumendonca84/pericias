#!/usr/bin/env python3
"""
Agenda a actualizacao do acervo para correr sozinha.

Sem isto, alguem tem de se lembrar de correr o atualizar.py depois de cada
peca entregue -- e quem nao se lembra fica com um acervo que envelhece em
silencio, a devolver menos do que devia sem dar sinal de nada.

    python agendar.py                 semanal, domingo as 03:00
    python agendar.py --hora 22       a hora que preferires
    python agendar.py --diario
    python agendar.py --remover
    python agendar.py --estado
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
TAREFA = "AcervoPericias"


def windows() -> bool:
    return sys.platform == "win32"


def correr(argumentos: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["schtasks", *argumentos], capture_output=True, text=True, shell=False
    )


def agendar(diario: bool, hora: int) -> int:
    alvo = RAIZ / "atualizar.py"
    if not alvo.exists():
        print(f"ERRO: {alvo.name} nao encontrado.")
        return 1

    # pythonw em vez de python: a tarefa corre sem abrir uma janela preta por
    # cima do que a pessoa esta a fazer.
    executavel = Path(sys.executable)
    silencioso = executavel.with_name("pythonw.exe")
    if not silencioso.exists():
        silencioso = executavel

    comando = f'"{silencioso}" "{alvo}"'
    argumentos = [
        "/Create", "/TN", TAREFA, "/TR", comando,
        "/ST", f"{hora:02d}:00", "/F",
    ]
    argumentos += ["/SC", "DAILY"] if diario else ["/SC", "WEEKLY", "/D", "SUN"]

    resultado = correr(argumentos)
    if resultado.returncode != 0:
        print("FALHOU ao criar a tarefa:")
        print((resultado.stderr or resultado.stdout).strip())
        return 1

    quando = "todos os dias" if diario else "todos os domingos"
    print(f"Agendado: {quando} as {hora:02d}:00.")
    print()
    print("O acervo passa a actualizar-se sozinho. Se o computador estiver")
    print("desligado a essa hora, o Windows corre a tarefa no arranque seguinte.")
    print()
    print(f"Para desligar:  python agendar.py --remover")
    return 0


def remover() -> int:
    resultado = correr(["/Delete", "/TN", TAREFA, "/F"])
    if resultado.returncode != 0:
        print("Nao estava agendado.")
        return 0
    print("Agendamento removido.")
    return 0


def estado() -> int:
    resultado = correr(["/Query", "/TN", TAREFA, "/V", "/FO", "LIST"])
    if resultado.returncode != 0:
        print("Nao esta agendado. Para agendar:  python agendar.py")
        return 1

    interessa = (
        "TaskName", "Next Run Time", "Last Run Time", "Last Result",
        "Schedule", "Status", "Nome da Tarefa", "Proxima",
    )
    for linha in resultado.stdout.splitlines():
        if any(linha.strip().startswith(campo) for campo in interessa):
            print(f"  {linha.strip()}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Agenda a actualizacao automatica do acervo."
    )
    parser.add_argument("--diario", action="store_true", help="em vez de semanal")
    parser.add_argument("--hora", type=int, default=3, help="hora do dia (0-23)")
    parser.add_argument("--remover", action="store_true")
    parser.add_argument("--estado", action="store_true")
    args = parser.parse_args()

    if not windows():
        print("O agendamento automatico so esta implementado para Windows.")
        print("Noutros sistemas, usa o cron para correr atualizar.py.")
        return 1

    if not 0 <= args.hora <= 23:
        print("A hora tem de estar entre 0 e 23.")
        return 1

    if args.remover:
        return remover()
    if args.estado:
        return estado()
    return agendar(args.diario, args.hora)


if __name__ == "__main__":
    raise SystemExit(main())
