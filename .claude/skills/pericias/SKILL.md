---
name: pericias
description: Apoia a elaboração de peças de perícia judicial de engenharia — laudos, esclarecimentos, quesitos, propostas de honorários, petições ao juízo. Consulta o acervo local de perícias anteriores do perito para encontrar casos análogos e reaproveitar estrutura e fundamentação. Usar sempre que o pedido envolva redigir, rever ou pesquisar uma peça pericial, quando o utilizador mencionar laudo, quesito, vistoria, nomeação, escusa, honorários periciais, ou citar um número de processo CNJ.
---

# Perícias judiciais de engenharia

Esta skill apoia um perito do juízo na elaboração de peças. O material de
referência é o acervo de perícias já entregues, indexado localmente.

## Antes de escrever, consultar o acervo

Nunca redigir uma peça do zero sem primeiro procurar precedentes no acervo.
O valor está em reaproveitar a estrutura, a linguagem e a fundamentação
técnica que o perito já usou e que os juízos já aceitaram.

```bash
python indexar_pericias.py --procurar "infiltracao laje cobertura"
python indexar_pericias.py --procurar "honorarios arbitramento" --quantos 15
```

A pesquisa é em texto integral, ignora acentos e devolve excertos com o
termo em destaque, o número do processo e o caminho do ficheiro. Ler os
ficheiros mais relevantes na íntegra antes de redigir.

Para consultar o acervo por metadados em vez de texto:

```bash
sqlite3 acervo_pericias.sqlite \
  "SELECT nome, processo, vara FROM documentos WHERE tipo='laudo' LIMIT 20;"
```

Tipos disponíveis: `laudo`, `esclarecimentos`, `quesitos`, `honorarios`,
`proposta`, `escusa`, `peticao`, `carta`, `fotos`, `outro`.

## Manter o acervo actualizado

Depois de entregar uma peça nova, reindexar. Só processa o que mudou:

```bash
python indexar_pericias.py --pasta "G:/Meu Drive/pericias"
```

É este passo — e só este — que faz o acervo crescer. Não existe aprendizagem
automática: o que melhora as respostas é haver mais material indexado.

## Fontes públicas

Material público (legislação, normas técnicas, jurisprudência, manuais)
vive numa colecção separada, para não se misturar com o acervo do perito:

```bash
python indexar_pericias.py --pasta "C:/pericias/referencias" --colecao publico
```

Guardar aqui apenas documentos de acesso público. Ao citar legislação,
norma técnica ou jurisprudência numa peça, **verificar sempre a fonte no
documento indexado** — nunca citar artigo, número de norma ou acórdão de
memória. Uma citação errada numa peça pericial é um problema sério.

## Ao redigir

- Seguir a estrutura das peças análogas encontradas no acervo, não um
  modelo genérico.
- Responder a cada quesito individualmente, na ordem em que foi formulado,
  repetindo o enunciado antes da resposta.
- Distinguir com clareza o que foi constatado em vistoria do que é
  inferência técnica do perito.
- Não inventar medições, datas de vistoria, valores ou conclusões. Se um
  dado não está nos autos nem no material fornecido, assinalar a lacuna
  em vez de a preencher.
- Manter o tratamento e a formatação que o perito já usa — está no acervo.

## Confidencialidade

O acervo contém dados de partes identificadas em processos reais. Não copiar
conteúdo de um processo para peça de outro, para além de estrutura e
fundamentação técnica genérica. Não enviar conteúdo do acervo para
serviços externos.
