# Acervo de perícias

Ferramentas para um perito do juízo trabalhar sobre o seu próprio acervo de
perícias: diagnosticar o corpus, indexá-lo localmente e consultá-lo através
de uma skill do Claude Code ao redigir peças novas.

**Os documentos nunca saem da máquina.** Este repositório contém apenas
código. O acervo, o índice e tudo o que dele deriva estão no `.gitignore`.

## Instalação

Requer Python 3.10+.

```bash
git clone https://github.com/dudumendonca84/pericias
cd pericias
```

Depois, duplo clique em **`Instalar.bat`** — ou, na linha de comandos:

```bash
python configurar.py
```

A configuração verifica as dependências e instala-as (com o contorno de SSL
que as redes com proxy corporativo exigem), deteta o Tesseract para o OCR,
pergunta onde está o acervo, cria o atalho de pesquisa no ambiente de
trabalho, e constrói o índice. A pasta fica guardada em `config.json`, e a
partir daí os comandos deixam de precisar de argumentos.

**Perícias novas:** duplo clique em `Atualizar Acervo.bat`, ou
`python atualizar.py`. Só processa o que mudou, e volta a aplicar as regras
de classificação ao que já estava indexado.

**Procurar sem terminal:** o atalho `Procurar Pericias` abre uma janela onde
se escreve a pergunta em linguagem normal.

## 1. Diagnosticar o corpus

Antes de indexar, perceber o que é legível. Só leitura — não modifica,
move nem renomeia nada.

```bash
python diagnostico_pericias.py --pasta "G:/Meu Drive/pericias" --limite 30
python diagnostico_pericias.py --pasta "G:/Meu Drive/pericias"
```

Estados reportados:

| Estado | Significa |
|---|---|
| `ok` | texto extraído com sucesso |
| `ocr` | PDF digitalizado, sem camada de texto — precisa de OCR para ser útil |
| `vazio` | ficheiro sem texto ou com 0 bytes |
| `falha` | erro de leitura (ficheiro corrompido, PDF protegido) |
| `nuvem` | ainda não sincronizado do Drive para o disco |
| `ignorado` | ruído (`.tmp`, `.lnk`, `~$…`) ou extensão fora do âmbito |

Se mais de 20% dos primeiros ficheiros estiverem só na nuvem, o script
aborta e avisa: a sincronização offline do Drive não terminou. Marcar a
pasta como *Disponível offline*, esperar, e voltar a correr.

Escreve `diagnostico_pericias.csv` com o detalhe por documento.

## 2. Indexar

```bash
python indexar_pericias.py --pasta "G:/Meu Drive/pericias"
```

Cria `acervo_pericias.sqlite` com texto integral pesquisável (FTS5), e
extrai por documento o número de processo CNJ, a vara e o tipo de peça.

Correr de novo depois de acrescentar perícias novas — só processa o que
mudou. **É este passo que faz o acervo crescer.**

### Acervo entregue em ZIPs, sem espaço para o descomprimir

Quando o acervo vem do Google Drive em dezenas de ZIPs e o disco não chega
para os abrir todos:

```bash
python processar_zips.py --zips "C:/zips-pericias"
python processar_zips.py --zips "C:/zips-pericias" --apagar-zip
```

Processa um ZIP de cada vez — extrai, indexa o texto, apaga o que extraiu.
O pico de disco é o maior ZIP descomprimido, não a soma de todos. Com
`--apagar-zip` liberta também o ZIP já processado.

É retomável: se interromperes, ou se um ZIP estiver corrompido por o
download não ter terminado, volta a correr e continua de onde ficou.
Aborta sozinho se o disco livre descer abaixo de 5 GB.

Os documentos indexados por esta via guardam o nome do ZIP de origem, já
que a pasta de extração deixa de existir.

### OCR — recuperar as digitalizações

Num acervo pericial a maior parte dos PDFs costuma ser digitalização: são
fotografias de páginas, sem letras lá dentro. Entram no índice pelo nome mas
nenhuma pesquisa por conteúdo os encontra.

Precisa do [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
instalado, com o pacote de português:

```bash
winget install UB-Mannheim.TesseractOCR
```

Depois basta acrescentar `--ocr`:

```bash
python indexar_pericias.py --pasta "C:/acervo" --ocr
python processar_zips.py --zips "C:/zips-pericias" --ocr
```

Conta com 1 a 3 segundos por página — um acervo de milhares de documentos
leva horas. Deixa-se a correr de noite; é retomável como o resto.

Os documentos lidos por esta via ficam com estado `ocr-lido`, para se
distinguirem dos que já nasceram digitais. A qualidade depende da
digitalização: páginas direitas e limpas dão texto quase perfeito, páginas
tortas ou com carimbos dão texto com erros — ainda assim pesquisável.

Se o Tesseract não estiver instalado, `--ocr` avisa e não faz nada em vez
de indexar em silêncio sem OCR.

## 3. Consultar

```bash
python indexar_pericias.py --procurar "infiltracao laje"
python indexar_pericias.py --procurar "honorarios arbitramento" --quantos 15
```

Ou, dentro do Claude Code, a skill `pericias` faz isto sozinha quando o
pedido envolve redigir ou pesquisar uma peça.

## 4. Fontes públicas

Material público (legislação, normas, jurisprudência) numa colecção
separada, para não se misturar com o acervo do perito:

```bash
python indexar_pericias.py --pasta "C:/pericias/referencias" --colecao publico
```

## Entregar a um perito sem lhe instalar nada

Na máquina de quem desenvolve, com o índice já construído:

```
Construir EXE.bat
```

Produz a pasta `entrega` com dois ficheiros:

```
Procurar Pericias.exe
acervo_pericias.sqlite
```

Copia-se a pasta para a máquina do perito — pen, email, o que for — e ele
faz duplo clique no `.exe`. Não precisa de Python, nem de Tesseract, nem de
ligação à internet. O acervo inteiro vai dentro do `.sqlite`.

Para lhe dar perícias novas, volta-se a correr `Atualizar Acervo.bat` aqui e
entrega-se o `.sqlite` actualizado. O `.exe` não muda.

## Sobre "aprender"

A skill não aprende sozinha e não tem memória entre sessões. O que melhora
as respostas é o índice ter mais material. O ciclo é: entregar uma peça →
reindexar → a peça passa a estar disponível como precedente.

## Actualizar a skill

```bash
git pull
```

A skill é lida do repositório a cada sessão do Claude Code. Não há
publicação nem servidor: basta o `git pull`.
