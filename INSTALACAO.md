# Instalar na máquina do perito

Guia de campo. Segue por ordem; cada passo tem o que verificar antes de
avançar.

## Antes de sair

- [ ] Saber **onde estão as perícias** na máquina dele (o caminho da pasta).
      É a única coisa que não se descobre lá no momento.
- [ ] Confirmar que ele tem **Claude Desktop** instalado e com sessão iniciada.
      Sem isso, a parte de redigir não funciona — a pesquisa funciona na mesma.
- [ ] Contar com **algumas horas** de indexação. O OCR é lento; a máquina fica
      a trabalhar de noite.

## Na máquina dele

### 1. Instalar

PowerShell **normal** (não como administrador):

```powershell
irm https://raw.githubusercontent.com/dudumendonca84/pericias/claude/diagnostico-laudos-periciais-9wrgvl/instalar.ps1 | iex
```

Instala o Python, o programa, os pacotes, o Tesseract com o português, e liga
ao Claude Desktop.

> Se disser **"FECHA esta janela, abre outra"** — instalou o Python e o `PATH`
> só actualiza em janelas novas. Fecha, abre outra, cola o mesmo comando.

Verificar antes de avançar:

```
[1] Python            Python 3.12.x
[4] OCR (Tesseract)   portugues instalado
[5] Ligar ao Claude   Instalado em C:\Users\...\claude_desktop_config.json
```

Se o passo 4 disser `NAO INSTALADO`, as digitalizações ficam de fora — que
num acervo pericial costumam ser a maioria. Vale a pena resolver antes de
indexar, senão é preciso repetir tudo.

### 2. Construir o acervo

```powershell
cd $HOME\Documents\pericias
python configurar.py
```

Responder:

| Pergunta | Resposta |
|---|---|
| Instalar pacotes? | Enter |
| Usar OCR? | Enter |
| **Pasta** | o caminho das perícias dele |
| Criar atalho? | Enter |
| Agendar actualização automática? | Enter |
| Começar agora? | Enter |

Deixar correr. Pode ser interrompido com `Ctrl+C` e retomado depois — não
perde o que já fez.

### 3. Verificar

```powershell
python consultar_acervo.py --resumo
```

Deve mostrar o número de documentos, os tipos de peça e as varas. Se o número
for muito abaixo do esperado, algo correu mal — ver o diagnóstico abaixo.

```powershell
python agendar.py --estado
```

Confirma que a actualização automática ficou registada.

### 4. Ligar ao Claude Desktop

Fechar e **reabrir** o Claude Desktop. Nas definições, em Connectors, deve
aparecer **pericias**.

Perguntar lá, para testar:

```
que laudos tenho sobre infiltração?
```

## O que ensinar ao perito

Duas coisas, e mais nada.

**Para procurar uma peça:** duplo clique no ícone **Procurar Perícias** no
ambiente de trabalho. Escrever, Enter, clicar num resultado para o ler.

**Para trabalhar numa peça nova:** abrir o Claude Desktop e perguntar em
português normal — *"como respondi antes a quesitos sobre trinca em
alvenaria?"*, *"redige uma carta de levantamento de honorários para a 32ª
Vara"*.

As perícias novas entram sozinhas, de madrugada. Ele não corre comandos.

## Quando algo falha

| Sintoma | Causa |
|---|---|
| `python` não reconhecido | Instalou agora; fechar e reabrir a janela |
| Abre a Microsoft Store | Python não instalado; ver o passo 1 |
| `NAO INSTALADO` no Tesseract | Instalar de github.com/UB-Mannheim/tesseract/wiki |
| Muitos `?` na indexação | Ficheiros só na nuvem; sincronizar offline primeiro |
| Muitos `O` na indexação | Digitalizações sem OCR; confirmar o Tesseract |
| `pericias` não aparece no Claude | Não reabriu o Claude Desktop |
| A pesquisa não encontra nada | `python consultar_acervo.py --resumo` diz o que há |

## Actualizar o programa mais tarde

O mesmo comando do passo 1. Substitui só o programa — o acervo, a
configuração e o agendamento ficam onde estão.
