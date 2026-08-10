# Instalar na máquina do perito

Guia de campo. Tudo o que é preciso, por ordem, com o que verificar antes de
avançar e o que fazer quando falha.

---

## Antes de sair

| | |
|---|---|
| **Onde estão as perícias?** | Pergunta-lhe antes. É a única coisa que não se descobre lá. |
| **Ele tem Claude Desktop?** | A app instalada, não o site. Menu Iniciar → escrever `Claude`. |
| **O Drive está no computador?** | Se ele só vê as perícias no site do Google, vais precisar de instalar o Drive para Computador — e isso demora. |
| **Tempo** | A indexação com OCR leva horas. A máquina fica a trabalhar de noite. |
| **Espaço em disco** | O índice ocupa cerca de 10% do tamanho do acervo. Confirmar que há folga. |

---

## PASSO 0 — Encontrar as perícias

Abre o PowerShell (menu Iniciar → `powershell`). **Normal, não como
administrador** — se o título disser "Administrador", fecha e abre outra vez.

Vê que unidades existem:

```powershell
Get-PSDrive -PSProvider FileSystem | Select-Object Name, Root
```

### Caso A — as perícias estão numa pasta do computador

Pede-lhe para abrir a pasta. Clica na barra de endereço lá em cima, `Ctrl+C`.
É esse o caminho. Segue para o passo 1.

### Caso B — estão no Google Drive, com a app instalada

Aparece uma unidade `G:` (ou outra letra). Duas coisas a confirmar:

```powershell
Get-ChildItem "G:\" -Directory
```

E, no explorador: botão direito na pasta das perícias → **Acesso offline** →
**Disponível offline**.

> Sem isto, o Drive mostra os ficheiros mas não os tem no disco — só os
> descarrega quando alguém os abre. O indexador marca-os como `nuvem` e
> salta-os. Esperar a sincronização acabar (ícone verde) antes de avançar.

### Caso C — o Drive só existe no site

```powershell
winget install Google.GoogleDrive
```

Depois abrir o Google Drive pelo menu Iniciar, iniciar sessão com a conta
dele, e voltar ao caso B. **Isto demora** — sincronizar milhares de ficheiros
não é coisa de minutos.

Alternativa mais rápida se ele tiver pressa: descarregar a pasta do site
(botão direito → Transferir), que sai em ZIP. O programa aceita a pasta dos
ZIP directamente e extrai um de cada vez, sem encher o disco.

### Caso D — as perícias estão em ficheiros ZIP

Indicar a pasta dos ZIP no passo 2. O programa reconhece e trata do resto.

---

## PASSO 1 — Instalar

```powershell
irm https://raw.githubusercontent.com/dudumendonca84/pericias/claude/diagnostico-laudos-periciais-9wrgvl/instalar.ps1 | iex
```

Instala o Python, o programa, os pacotes, o Tesseract com o português, e liga
ao Claude Desktop.

**Se disser "FECHA esta janela, abre outra":** instalou o Python e o Windows
só o reconhece em janelas novas. Fechar, abrir outra, colar o mesmo comando.
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

| Pergunta | Resposta |
|---|---|
| Instalar pacotes? | Enter |
| Usar OCR? | Enter |
| **Pasta** | o caminho do passo 0 |
| Criar atalho? | Enter |
| Agendar actualização automática? | Enter |
| Começar agora? | Enter |

**Confirmar o número.** Logo a seguir à pasta, ele diz o que encontrou:

```
  3412 documentos, 0 ficheiros ZIP
  Modo: pasta de documentos
```

Se disser `0 documentos`, a pasta está errada — voltar a correr
`python configurar.py` e escrever outra.

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

Muitos `?` significa parar e voltar ao passo 0, caso B.

Pode ser interrompido com `Ctrl+C` e retomado — não perde o que já fez.

---

## PASSO 4 — Verificar

```powershell
python consultar_acervo.py --resumo
```

Mostra quantos documentos, quantos com texto legível, os tipos de peça e as
varas. Se o número de documentos fizer sentido e a maioria tiver texto
legível, correu bem.

```powershell
python agendar.py --estado
```

Confirma que a actualização automática ficou registada.

---

## PASSO 5 — Ligar ao Claude Desktop

Fechar o Claude Desktop **por completo** — não minimizar. Verificar no ícone
junto ao relógio: botão direito → Quit.

Abrir outra vez. Nas definições, em Connectors, deve aparecer **pericias**.

Testar:

```
que laudos tenho sobre infiltração?
```

Ele deve devolver peças reais do acervo, com nome e número de processo.

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

As perícias novas entram sozinhas, de madrugada. Ele nunca corre comandos.

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
| `0 documentos` no passo 2 | Pasta errada; voltar ao passo 0 |
| Muitos `?` na indexação | Ficheiros só na nuvem; marcar a pasta disponível offline |
| Muitos `O` e OCR a 0 | Tesseract não encontrado; ver passo 1 |
| `database is locked` | Duas indexações ao mesmo tempo; fechar as outras janelas |
| `no space left` | Disco cheio; apagar ZIPs já processados |
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
python configurar.py                         # mudar a pasta do acervo
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

Com o Google Drive para Computador montado, os caminhos ficam:

```
G:\My Drive\eletranabc2
G:\My Drive\perícias judiciais
```

> A letra pode não ser `G:` e a pasta pode chamar-se `Meu Drive` se a conta
> estiver em português. Confirmar com `Get-PSDrive` e `Get-ChildItem` antes de
> escrever os caminhos — o acento em `perícias` também conta.

## Sequência completa

```powershell
# 1. Ver se o Drive está montado
Get-PSDrive -PSProvider FileSystem | Select-Object Name, Root

# 2. Se só houver C:, instalar o Google Drive para Computador
winget install Google.GoogleDrive
#    Abrir o Google Drive pelo menu Iniciar e iniciar sessão com a conta dele.
#    Depois, no explorador: botão direito em cada uma das duas pastas
#    -> Acesso offline -> Disponível offline. ESPERAR sincronizar.

# 3. Confirmar os nomes exactos
Get-ChildItem "G:\" -Directory
Get-ChildItem "G:\My Drive" -Directory

# 4. Instalar o programa
irm https://raw.githubusercontent.com/dudumendonca84/pericias/claude/diagnostico-laudos-periciais-9wrgvl/instalar.ps1 | iex

# 5. Configurar e indexar
cd $HOME\Documents\pericias
python configurar.py
#    Enter em tudo, excepto nas pastas:
#      Pasta 1: G:\My Drive\eletranabc2
#      Pasta 2: G:\My Drive\perícias judiciais
#      Pasta 3: Enter (termina)

# 6. No dia seguinte, verificar
python consultar_acervo.py --resumo
python agendar.py --estado
```

Depois fechar e reabrir o Claude Desktop, e perguntar lá:
*que laudos tenho sobre infiltração?*

## O que pode demorar mais do que se espera

**A sincronização offline do Drive.** Milhares de ficheiros descarregados do
zero levam horas e ocupam o mesmo espaço que ocupam na nuvem. É o passo que
convém começar primeiro e deixar a correr enquanto se faz o resto.

**A indexação com OCR.** Também horas. Pode ser interrompida com `Ctrl+C` e
retomada — não perde o que já fez.

Se a sincronização não tiver acabado quando a indexação começar, aparecem
muitos `?` no ecrã. Nesse caso: `Ctrl+C`, esperar, e correr
`python atualizar.py` mais tarde.
