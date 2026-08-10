# Instalar na máquina do perito

Guia de campo. Por ordem, com o que verificar antes de avançar e o que fazer
quando falha.

---

## Antes de sair

| | |
|---|---|
| **Ele tem Claude Desktop?** | A app instalada, não o site. Menu Iniciar → escrever `Claude`. |
| **O Drive está no computador?** | Se ele só vê as perícias no site do Google, é preciso instalar o Drive para Computador — e sincronizar demora. |
| **Tempo** | A sincronização e a indexação levam horas cada uma. A máquina fica a trabalhar de noite. |
| **Espaço em disco** | O acervo tem de caber no disco, e o índice ocupa mais cerca de 10%. |

Não é preciso saber os caminhos: a configuração procura as pastas sozinha.

---

## PASSO 0 — O Google Drive

Abre o PowerShell (menu Iniciar → `powershell`). **Normal, não como
administrador** — se o título disser "Administrador", fecha e abre outra vez.

```powershell
Get-PSDrive -PSProvider FileSystem | Select-Object Name, Root
```

**Se aparecer uma unidade além do `C:`** (`G:` ou outra letra), o Drive está
montado. Salta para a sincronização, mais abaixo.

**Se só aparecer `C:`:**

```powershell
winget install Google.GoogleDrive
```

Abrir o Google Drive pelo menu Iniciar e iniciar sessão com a conta dele.

### Sincronizar as pastas

No explorador, em **cada** pasta de perícias: botão direito → **Acesso
offline** → **Disponível offline**.

> Sem isto, o Drive lista os ficheiros mas não os tem no disco — só os
> descarrega quando alguém os abre. O indexador marca-os como `nuvem` e
> salta-os, e o acervo fica pela metade sem se perceber porquê.

**Começa por aqui e deixa a sincronizar** enquanto fazes o resto. É o passo
mais demorado: milhares de ficheiros do zero levam horas.

### Se ele tiver pressa

Em vez de sincronizar, descarregar as pastas do site do Drive (botão direito →
Transferir), que saem em ZIP. O programa aceita a pasta dos ZIP e extrai um de
cada vez, sem encher o disco.

---

## PASSO 1 — Instalar

```powershell
irm https://raw.githubusercontent.com/dudumendonca84/pericias/claude/diagnostico-laudos-periciais-9wrgvl/instalar.ps1 | iex
```

Instala o Python, o programa, os pacotes, o Tesseract com o português, e liga
ao Claude Desktop.

**Se disser "FECHA esta janela, abre outra":** instalou o Python e o Windows só
o reconhece em janelas novas. Fechar, abrir outra, colar o mesmo comando.
Acontece uma vez.

Verificar antes de avançar:

```
[1] Python              Python 3.12.x
[4] OCR (Tesseract)     portugues instalado
[5] Ligar ao Claude     Instalado em C:\Users\...
```

> Se o `[4]` disser `NAO INSTALADO`, resolver **antes** de indexar. As
> digitalizações ficariam de fora, e num acervo pericial costumam ser a
> maioria — descobrir isso depois obriga a repetir horas de trabalho.

---

## PASSO 2 — Construir o acervo

```powershell
cd $HOME\Documents\pericias
python configurar.py
```

Ele procura as pastas sozinho e propõe o que encontrar:

```
3. Onde estao as pericias
-------------------------
  Encontrei estas pastas:
    1. G:\My Drive\eletranabc2
    2. G:\My Drive\perícias judiciais

Usar estas? [S/n]:
```

**Enter.** Depois Enter em tudo o resto.

Confirma os números que aparecem por pasta:

```
  1847 documentos, 0 ficheiros ZIP
  Modo: pasta de documentos
```

**Se não encontrar as pastas**, cai no diálogo de escrever à mão — uma por
linha, Enter vazio para terminar. Ou, se souberes os caminhos:

```powershell
python configurar.py --pastas "G:\My Drive\eletranabc2" "G:\My Drive\perícias judiciais"
python atualizar.py
```

---

## PASSO 3 — Esperar

Aparecem marcas a indicar o que vai encontrando:

| Marca | Significa |
|---|---|
| `.` | texto extraído, tudo bem |
| `O` | digitalização — vai por OCR, é lento |
| `?` | **só na nuvem** — sincronização por acabar |
| `X` | erro de leitura |
| `-` | ignorado (ficheiro temporário, imagem) |

Muitos `?` significa parar (`Ctrl+C`), esperar a sincronização, e correr
`python atualizar.py` mais tarde. Não perde o que já fez.

---

## PASSO 4 — Verificar

```powershell
python consultar_acervo.py --resumo
python agendar.py --estado
```

O primeiro mostra quantos documentos, quantos com texto legível, os tipos de
peça e as varas. O segundo confirma que a actualização automática ficou
registada.

---

## PASSO 5 — Ligar ao Claude Desktop

Fechar o Claude Desktop **por completo** — não minimizar. Verificar no ícone
junto ao relógio: botão direito → Quit.

Abrir outra vez. Nas definições, em Connectors, deve aparecer **pericias**.

Testar:

```
que laudos tenho sobre infiltração?
```

Deve devolver peças reais do acervo, com nome e número de processo.

---

## O que ensinar ao perito

Duas coisas, e mais nada.

**Procurar uma peça antiga:** duplo clique no ícone **Procurar Perícias** no
ambiente de trabalho. Escrever como se fala, Enter, clicar num resultado para
o ler.

**Trabalhar numa peça nova:** abrir o Claude Desktop e perguntar em português
normal:

- *como respondi antes a quesitos sobre trinca em alvenaria?*
- *redige uma carta de levantamento de honorários para a 32ª Vara*
- *mostra-me tudo o que entreguei no processo 0012140-26.2013.8.19.0028*

As perícias novas entram sozinhas, aos domingos de madrugada. Ele nunca corre
comandos.

**O que ele deve saber:** o Claude não se lembra de conversas anteriores. Se o
corrigir hoje, amanhã tem de dizer outra vez. O que fica é o que está escrito
nas peças dele.

---

## Quando algo falha

| Sintoma | Causa e solução |
|---|---|
| `python` não é reconhecido | Instalou agora — fechar e reabrir a janela |
| Abre a Microsoft Store | Python não instalado; repetir o passo 1 |
| `[4] NAO INSTALADO` | Instalar de github.com/UB-Mannheim/tesseract/wiki, e o `por.traineddata` para a pasta `tessdata` |
| Não encontrou as pastas | Escrever à mão, ou usar `--pastas` |
| `0 documentos` numa pasta | Caminho errado, ou sincronização por acabar |
| Muitos `?` na indexação | Ficheiros só na nuvem; marcar disponível offline |
| Muitos `O` e OCR a 0 | Tesseract não encontrado; ver passo 1 |
| `database is locked` | Duas indexações ao mesmo tempo; fechar as outras janelas |
| `no space left` | Disco cheio |
| `pericias` não aparece no Claude | Não fechou o Claude Desktop por completo |
| O Claude não usa o acervo | Dizer-lhe *"procura no meu acervo"* |
| A pesquisa não encontra nada | `python consultar_acervo.py --resumo` diz o que existe |
| Peça arquivada na vara errada | `python indexar_pericias.py --renormalizar` |

---

## Comandos de referência

```powershell
cd $HOME\Documents\pericias

python consultar_acervo.py --resumo          # o que existe no acervo
python atualizar.py                          # apanhar perícias novas agora
python agendar.py --estado                   # ver a actualização automática
python agendar.py --diario                   # passar a diária
python agendar.py --remover                  # desligar
python indexar_pericias.py --renormalizar    # recorrigir varas e tipos
python configurar.py                         # mudar as pastas do acervo
python instalar_mcp.py --remover             # desligar do Claude Desktop
```

Actualizar o programa mais tarde: o mesmo comando do passo 1. Substitui só o
programa — o acervo, a configuração e o agendamento ficam onde estão.

---

# Anexo — a instalação concreta

Acervo repartido por duas pastas do Google Drive pessoal:

| Pasta | Conteúdo |
|---|---|
| `eletranabc2` | laudos e esclarecimentos sobre o laudo |
| `perícias judiciais` | petições de honorários, de esclarecimentos de honorários, de levantamento, e outras |

A configuração reconhece ambos os nomes sozinha, com ou sem acentos, e o Drive
chamado `My Drive` ou `Meu Drive`. Não é preciso escrever caminhos.

## Sequência completa

```powershell
# 1. O Drive
Get-PSDrive -PSProvider FileSystem | Select-Object Name, Root
winget install Google.GoogleDrive          # se só houver C:
#    Iniciar sessão no Google Drive, e marcar AS DUAS pastas como
#    "Disponível offline" no explorador. Deixar a sincronizar.

# 2. O programa
irm https://raw.githubusercontent.com/dudumendonca84/pericias/claude/diagnostico-laudos-periciais-9wrgvl/instalar.ps1 | iex

# 3. O acervo
cd $HOME\Documents\pericias
python configurar.py
#    "Encontrei estas pastas ... Usar estas?" -> Enter
#    Enter em tudo o resto. Deixar indexar de noite.

# 4. No dia seguinte
python consultar_acervo.py --resumo
python agendar.py --estado
```

Depois fechar e reabrir o Claude Desktop, e perguntar lá:
*que laudos tenho sobre infiltração?*
