# Acervo de perícias

Ferramentas para um perito do juízo trabalhar sobre o seu próprio acervo de
perícias: diagnosticar o corpus, indexá-lo localmente e consultá-lo através
de uma skill do Claude Code ao redigir peças novas.

**Os documentos nunca saem da máquina.** Este repositório contém apenas
código. O acervo, o índice e tudo o que dele deriva estão no `.gitignore`.

## Instalação

Requer Python 3.10+ e o Claude Code instalado.

```bash
git clone https://github.com/dudumendonca84/pericias
cd pericias
pip install pymupdf python-docx
```

Se o pip falhar por SSL (típico em redes com Zscaler ou proxy corporativo):

```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org pymupdf python-docx
```

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
