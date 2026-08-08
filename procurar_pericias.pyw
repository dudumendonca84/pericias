#!/usr/bin/env python3
"""
Janela de pesquisa do acervo de pericias.

Feita para ser usada sem terminal e sem comandos: escreve-se a pergunta em
linguagem normal, carrega-se Enter, e os resultados aparecem. A extensao .pyw
evita que o Windows abra uma janela preta de consola por tras.

Tudo o que aparece aqui vem do indice local. Nada sai da maquina.
"""

from __future__ import annotations

import re
import sqlite3
import tkinter as tk
import unicodedata
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, ttk

INDICE = Path(__file__).resolve().parent / "acervo_pericias.sqlite"

# Tamanhos generosos: quem usa isto tem quase 80 anos e le no ecra o dia todo.
TAMANHO_BASE = 15
TAMANHO_TITULO = 20

# Quantos documentos mostrar de cada vez. Uma lista com centenas de linhas nao
# se percorre; o botao "Mostrar mais" traz o lote seguinte quando faz falta.
POR_PAGINA = 50

FUNDO = "#ffffff"
TEXTO = "#1a1a1a"
DESTAQUE = "#0b4f9e"
SUAVE = "#5a5a5a"


def sem_acentos(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def palavras_uteis(pergunta: str) -> list[str]:
    """Extrai as palavras pesquisáveis de uma pergunta escrita à mão.

    O motor de pesquisa rejeita pontuação, aspas e hífenes soltos com um erro
    de sintaxe. Quem escreve "infiltração na laje — 3ª vara?" não tem de saber
    disso: aqui ficam só as palavras.
    """
    palavras = re.findall(r"[0-9a-zA-Z]+", sem_acentos(pergunta))
    # Palavras muito curtas só acrescentam ruído ("de", "na", "o").
    uteis = [p for p in palavras if len(p) > 2]
    return uteis or palavras


def consultas(pergunta: str) -> list[str]:
    """Consultas a tentar por ordem, da mais exigente para a mais tolerante.

    Exigir todas as palavras dá resultados precisos quando acerta, mas basta
    uma palavra que não esteja no texto -- "32ª", que só aparece no nome do
    ficheiro -- para devolver nada. Quem escreve uma frase inteira ficaria
    convencido de que o acervo não tem o documento. Daí a segunda tentativa,
    que aceita qualquer uma das palavras e deixa o motor ordenar por
    relevância: quem tiver mais palavras aparece primeiro.
    """
    uteis = palavras_uteis(pergunta)
    if not uteis:
        return []
    if len(uteis) == 1:
        return [uteis[0]]
    return [" AND ".join(uteis), " OR ".join(uteis)]


class Aplicacao(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Acervo de Perícias")
        self.geometry("1100x750")
        self.configure(bg=FUNDO)
        self.minsize(900, 600)

        self.fonte = tkfont.Font(family="Segoe UI", size=TAMANHO_BASE)
        self.fonte_titulo = tkfont.Font(
            family="Segoe UI", size=TAMANHO_TITULO, weight="bold"
        )
        self.fonte_lista = tkfont.Font(family="Segoe UI", size=TAMANHO_BASE)

        self.resultados: list[tuple] = []
        self.mostrados = 0
        self.alargou = False
        self._construir()
        self._verificar_indice()

    def _construir(self) -> None:
        topo = tk.Frame(self, bg=FUNDO, padx=24, pady=20)
        topo.pack(fill="x")

        tk.Label(
            topo,
            text="O que procura?",
            font=self.fonte_titulo,
            bg=FUNDO,
            fg=TEXTO,
        ).pack(anchor="w")

        tk.Label(
            topo,
            text="Escreva como fala. Por exemplo: infiltração na laje",
            font=self.fonte,
            bg=FUNDO,
            fg=SUAVE,
        ).pack(anchor="w", pady=(2, 10))

        linha = tk.Frame(topo, bg=FUNDO)
        linha.pack(fill="x")

        self.entrada = tk.Entry(
            linha, font=tkfont.Font(family="Segoe UI", size=TAMANHO_TITULO),
            relief="solid", borderwidth=2, bg="#fbfbfb", fg=TEXTO,
        )
        self.entrada.pack(side="left", fill="x", expand=True, ipady=8)
        self.entrada.bind("<Return>", lambda _: self.procurar())
        self.entrada.focus_set()

        tk.Button(
            linha, text="Procurar", font=self.fonte_titulo,
            bg=DESTAQUE, fg="white", activebackground="#083a75",
            activeforeground="white", relief="flat", cursor="hand2",
            padx=28, command=self.procurar,
        ).pack(side="left", padx=(12, 0))

        self.botao_mais = tk.Button(
            linha, text="Mostrar mais", font=self.fonte,
            bg="#e8e8e8", fg=TEXTO, relief="flat", cursor="hand2",
            padx=18, command=self._mostrar_lote,
        )

        self.estado = tk.Label(
            topo, text="", font=self.fonte, bg=FUNDO, fg=SUAVE, anchor="w"
        )
        self.estado.pack(fill="x", pady=(12, 0))

        corpo = tk.PanedWindow(
            self, orient="vertical", bg=FUNDO, sashwidth=8, sashrelief="flat"
        )
        corpo.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        caixa_lista = tk.Frame(corpo, bg=FUNDO)
        self.lista = tk.Listbox(
            caixa_lista, font=self.fonte_lista, bg="#fbfbfb", fg=TEXTO,
            selectbackground=DESTAQUE, selectforeground="white",
            relief="solid", borderwidth=1, activestyle="none",
        )
        barra_lista = ttk.Scrollbar(caixa_lista, command=self.lista.yview)
        self.lista.configure(yscrollcommand=barra_lista.set)
        barra_lista.pack(side="right", fill="y")
        self.lista.pack(side="left", fill="both", expand=True)
        self.lista.bind("<<ListboxSelect>>", lambda _: self.mostrar())
        corpo.add(caixa_lista, height=280)

        caixa_texto = tk.Frame(corpo, bg=FUNDO)
        self.texto = tk.Text(
            caixa_texto, font=self.fonte, bg="#fbfbfb", fg=TEXTO,
            relief="solid", borderwidth=1, wrap="word",
            padx=16, pady=16, spacing1=3, spacing3=3,
        )
        barra_texto = ttk.Scrollbar(caixa_texto, command=self.texto.yview)
        self.texto.configure(yscrollcommand=barra_texto.set, state="disabled")
        barra_texto.pack(side="right", fill="y")
        self.texto.pack(side="left", fill="both", expand=True)
        corpo.add(caixa_texto)

        self.texto.tag_configure("cabecalho", font=self.fonte_titulo, foreground=DESTAQUE)
        self.texto.tag_configure("etiqueta", foreground=SUAVE)

    def _verificar_indice(self) -> None:
        if INDICE.exists():
            try:
                conexao = sqlite3.connect(INDICE)
                total = conexao.execute(
                    "SELECT COUNT(*) FROM documentos"
                ).fetchone()[0]
                conexao.close()
                self.estado.configure(text=f"{total} documentos no acervo.")
                return
            except sqlite3.Error:
                pass
        messagebox.showwarning(
            "Acervo não encontrado",
            "Não encontrei o ficheiro do acervo nesta pasta.\n\n"
            "Peça a quem instalou para o colocar aqui:\n"
            f"{INDICE}",
        )
        self.estado.configure(text="Acervo não encontrado.")

    def procurar(self) -> None:
        pergunta = self.entrada.get().strip()
        if not pergunta:
            return

        tentativas = consultas(pergunta)
        if not tentativas:
            self.estado.configure(text="Escreva pelo menos uma palavra.")
            return

        self.lista.delete(0, "end")
        self._escrever("")
        self.estado.configure(text="A procurar...")
        self.update_idletasks()

        linhas: list[tuple] = []
        alargou = False
        try:
            conexao = sqlite3.connect(INDICE)
            for i, consulta in enumerate(tentativas):
                linhas = list(
                    conexao.execute(
                        """SELECT d.nome, d.processo, d.vara, d.tipo, d.origem,
                                  t.texto
                           FROM textos t JOIN documentos d ON d.id = t.rowid
                           WHERE t.textos MATCH ? ORDER BY rank LIMIT 2000""",
                        (consulta,),
                    )
                )
                if linhas:
                    alargou = i > 0
                    break
            conexao.close()
        except sqlite3.Error as erro:
            self.estado.configure(text="Não consegui procurar.")
            messagebox.showerror("Erro", str(erro))
            return

        # O acervo tem o mesmo documento em .docx e .pdf e replicado por várias
        # pastas. Mostrar tudo faria a mesma peça aparecer cinco vezes.
        vistos: set[str] = set()
        self.resultados = []
        for linha in linhas:
            chave = sem_acentos(Path(linha[0]).stem).lower().strip()
            if chave in vistos:
                continue
            vistos.add(chave)
            self.resultados.append(linha)

        if not self.resultados:
            self.estado.configure(text="Não encontrei nada com essas palavras.")
            self.botao_mais.pack_forget()
            return

        self.alargou = alargou
        self.mostrados = 0
        self._mostrar_lote()
        self.lista.selection_set(0)
        self.mostrar()

    def _mostrar_lote(self) -> None:
        """Acrescenta o lote seguinte de resultados à lista."""
        fatia = self.resultados[self.mostrados : self.mostrados + POR_PAGINA]
        for nome, processo, _, _, _, _ in fatia:
            rotulo = Path(nome).stem
            if processo:
                rotulo = f"{rotulo}   —   {processo}"
            self.lista.insert("end", f"  {rotulo}")
        self.mostrados += len(fatia)

        total = len(self.resultados)
        faltam = total - self.mostrados
        aviso = (
            "  (não havia nada com todas as palavras, mostro o mais parecido)"
            if self.alargou
            else ""
        )
        if faltam:
            self.estado.configure(
                text=f"A mostrar {self.mostrados} de {total} documentos.{aviso}"
            )
            self.botao_mais.configure(
                text=f"Mostrar mais {min(POR_PAGINA, faltam)}"
            )
            self.botao_mais.pack(side="left", padx=(12, 0))
        else:
            plural = "s" if total > 1 else ""
            self.estado.configure(
                text=f"{total} documento{plural}. Clique num para o ler.{aviso}"
            )
            self.botao_mais.pack_forget()

    def mostrar(self) -> None:
        seleccao = self.lista.curselection()
        if not seleccao:
            return
        nome, processo, vara, tipo, origem, texto = self.resultados[seleccao[0]]

        self._escrever("")
        self.texto.configure(state="normal")
        self.texto.insert("end", f"{nome}\n", "cabecalho")
        detalhes = []
        if processo:
            detalhes.append(f"Processo: {processo}")
        if vara:
            detalhes.append(f"Vara: {vara}")
        if tipo and tipo != "outro":
            detalhes.append(f"Tipo: {tipo}")
        if origem:
            detalhes.append(f"Arquivo: {origem}")
        if detalhes:
            self.texto.insert("end", "\n".join(detalhes) + "\n", "etiqueta")
        self.texto.insert("end", "\n" + (texto or "").strip())
        self.texto.configure(state="disabled")
        self.texto.see("1.0")

    def _escrever(self, conteudo: str) -> None:
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        if conteudo:
            self.texto.insert("end", conteudo)
        self.texto.configure(state="disabled")


if __name__ == "__main__":
    Aplicacao().mainloop()
