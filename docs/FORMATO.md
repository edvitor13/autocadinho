# O formato `.cadinho`

Um desenho do Autocadinho é um arquivo de texto **JSON** em UTF-8, com a extensão `.cadinho`. Dá para abrir
num editor de texto, guardar no Git e gerar ou ler com qualquer linguagem. O código que lê e grava está em
`autocadinho/model.py` (`Document.to_dict` / `from_dict`) e `autocadinho/fileio.py`.

## Exemplo

Uma viga de 5 m com um pilar na ponta, a medida e um texto (a miniatura foi cortada):

```json
{
 "app": "Autocadinho",
 "format": 1,
 "title": "Garagem",
 "settings": {
  "unit": "m",
  "label_size": 25.0,
  "beam_width": 15.0,
  "pillar_w": 40.0,
  "pillar_h": 20.0,
  "snap_step": 10.0,
  "beam_prefix": "VIGA",
  "pillar_prefix": "P",
  "font": ""
 },
 "elements": [
  {"kind": "beam", "id": "dfd55aefdfe1", "color": "", "x1": 0, "y1": 0, "x2": 500, "y2": 0,
   "width": 15.0, "show_length": false,
   "label": "VIGA 1", "label_visible": true, "label_dx": null, "label_dy": null, "label_rot": 0},
  {"kind": "pillar", "id": "4f721c07f490", "color": "", "x": 0, "y": 0, "w": 40.0, "h": 20.0,
   "label": "P1", "label_visible": true, "label_dx": null, "label_dy": null, "label_rot": 0},
  {"kind": "dim", "id": "5c518439869b", "color": "", "x1": 0, "y1": 0, "x2": 500, "y2": 0,
   "offset": -60, "text": ""},
  {"kind": "text", "id": "59c27a8da88b", "color": "", "x": 250, "y": 200, "text": "Garagem",
   "size": 25.0, "bold": true, "rot": 0, "font": "", "italic": false}
 ],
 "version": "1.1.0",
 "thumbnail": "iVBORw0KGgoAAAANSUhEUgAAAeAAAAFACAYAAABk…"
}
```

## Convenções

- **Unidade:** todas as coordenadas e tamanhos estão em **centímetros da obra**.
- **Eixos:** `x` cresce para a direita e `y` **para baixo** (como na tela). A origem não tem significado especial.
- **Ordem:** `elements` vai do fundo para a frente: o último é desenhado por cima.
- **Cor:** `""` quer dizer *automática* (preto no papel, claro no tema escuro). Fora isso, `#rrggbb`.
- **`id`:** texto curto e único dentro do desenho (12 caracteres hexadecimais nos arquivos gravados pelo app).
  Ids repetidos são trocados na leitura.

## Raiz

| Campo | Tipo | Descrição |
|---|---|---|
| `app` | texto | Sempre `"Autocadinho"`. |
| `format` | número | Versão do formato. Hoje `1`. |
| `title` | texto | Título do desenho (sai no alto da folha impressa). Pode ser vazio. |
| `settings` | objeto | Ajustes do desenho (tabela abaixo). |
| `elements` | lista | Os elementos, do fundo para a frente. **Obrigatório**: um JSON sem `elements` não é aceito como desenho. |
| `version` | texto | Versão do Autocadinho que gravou (informativo). |
| `thumbnail` | texto | Opcional. Miniatura PNG (480 × 320) em Base64, usada na lista de recentes. |
| `recovery` | objeto | Só na cópia de recuperação: `{"original": caminho ou "", "time": segundos desde 1970}`. |

### `settings`

| Campo | Padrão | Descrição |
|---|---|---|
| `unit` | `"m"` | Unidade das medidas escritas: `"m"` (6,20 m) ou `"cm"` (620 cm). |
| `label_size` | `25.0` | Altura das letras dos nomes e das medidas, em cm (2 a 500). |
| `beam_width` | `15.0` | Largura das vigas novas, em cm (1 a 200). |
| `pillar_w`, `pillar_h` | `40.0`, `20.0` | Tamanho dos pilares novos, em cm (1 a 500). |
| `snap_step` | `10.0` | Passo da grade de encaixe, em cm (0 = sem grade; até 500). |
| `beam_prefix` | `"VIGA"` | Palavra do nome automático das vigas novas (VIGA 1, VIGA 2…). Vazio = sem nome. Até 24 caracteres. |
| `pillar_prefix` | `"P"` | O mesmo para os pilares (P1, P2…). Prefixo de uma letra fica colado ao número. |
| `font` | `""` | Desde a 1.1. Família da fonte dos nomes, das medidas e dos textos sem fonte própria (`"Georgia"`). Vazio = a fonte padrão do app (Segoe UI no Windows). Até 80 caracteres. |

O padrão dos prefixos segue o idioma do app quando o desenho é criado (`BEAM`/`C` em inglês). Um desenho salvo
guarda os seus e não muda ao trocar o idioma.

## Elementos

Todo elemento tem `kind`, `id` e `color`. Os campos de cada tipo:

### `beam` (viga) e `line` (linha)

| Campo | Descrição |
|---|---|
| `x1`, `y1`, `x2`, `y2` | Começo e fim do eixo. |
| `width` | Espessura desenhada, em cm (viga: 15 por padrão; linha: 3). |
| `show_length` | `true` escreve o comprimento ao lado. |
| `dashed` | Só na linha: tracejada. |
| `arrow_start`, `arrow_end` | Só na linha, desde a 1.1: seta na ponta 1 (`x1`, `y1`) e na ponta 2. |

A viga também tem os campos de **nome** (abaixo).

### `pillar` (pilar)

| Campo | Descrição |
|---|---|
| `x`, `y` | Centro. |
| `w`, `h` | Largura (em `x`) e altura (em `y`), em cm. |

Também tem os campos de **nome**.

### Campos de nome (viga, pilar e símbolo)

| Campo | Descrição |
|---|---|
| `label` | O nome (`"VIGA 1"`, `"P3"`, qualquer texto). |
| `label_visible` | `false` esconde o nome. |
| `label_dx`, `label_dy` | Posição do centro do nome em relação ao centro do elemento, em cm. `null` = posição automática (ao lado da viga, embaixo ou ao lado do pilar). |
| `label_rot` | `0` = deitado; `90` = em pé (lido de baixo para cima). |

### `rect` (retângulo)

| Campo | Descrição |
|---|---|
| `x`, `y` | Canto de cima à esquerda. |
| `w`, `h` | Largura e altura, em cm. |
| `width` | Espessura da borda. |
| `dashed`, `fill` | Borda tracejada; preenchido com a própria cor, bem clara (16% de opacidade). |
| `show_dims` | Escreve as medidas dos lados. |
| `show_area` | Desde a 1.1: escreve a área, sempre em m², no centro. |

### `ellipse` (círculo ou elipse, desde a 1.1)

Desenhada dentro de um retângulo, como no Paint. Com `w` igual a `h`, é um círculo.

| Campo | Descrição |
|---|---|
| `x`, `y` | Canto de cima à esquerda do retângulo em volta. |
| `w`, `h` | Largura e altura, em cm (o diâmetro, num círculo). |
| `width`, `dashed`, `fill` | Como no retângulo. |
| `show_dims` | Escreve o diâmetro (`Ø 1,20 m`) num círculo; largura e altura numa elipse. |
| `show_area` | Escreve a área no centro. |

### `poly` (polígono e triângulo, desde a 1.1)

| Campo | Descrição |
|---|---|
| `points` | Lista de pontos `[x, y]`, em ordem. Um triângulo é um polígono de 3 pontos. |
| `closed` | `true` (padrão) liga o último ponto ao primeiro; `false` = uma linha de vários pontos. |
| `width`, `dashed`, `fill` | Como no retângulo (`fill` só vale com `closed`). |
| `show_lengths` | Escreve a medida de cada lado, do lado de fora da forma. |
| `show_area` | Escreve a área no centro (só com `closed`). |

### `symbol` (porta, janela, escada, louças e norte, desde a 1.1)

Cada símbolo é desenhado no próprio sistema: a origem é o ponto `x`, `y`; o eixo x corre ao longo da parede
(ou do comprimento) e o eixo y aponta para dentro do cômodo. Esse sistema é girado `angle` graus (no sentido
do relógio na tela, já que y cresce para baixo) e depois espelhado por `flip_x` e `flip_y`.

| Campo | Descrição |
|---|---|
| `shape` | `"door"` (porta), `"door2"` (porta dupla), `"sliding"` (porta de correr), `"window"` (janela), `"stairs"` (escada), `"toilet"` (vaso sanitário), `"sink"` (pia), `"shower"` (chuveiro) ou `"north"` (norte). |
| `x`, `y` | Meio do vão na parede (portas e janelas) ou centro (os outros). |
| `w`, `h` | Portas e janelas: `w` é a largura do vão (`h` não é usado). Escada: comprimento e largura. Louças: largura e comprimento. Norte: o tamanho. |
| `angle` | Rotação em graus. |
| `flip_x` | Espelha ao longo da parede: a dobradiça do outro lado, ou a escada no outro sentido. |
| `flip_y` | Vira para o outro lado da parede: a porta abre para o outro cômodo. |
| `wall` | Portas e janelas: espessura da parede em que estão, em cm. Com mais de 0, o símbolo abre o vão (pinta a cor do papel por cima da parede, por isso portas e janelas são desenhadas depois de todo o resto). 0 = não abre. |
| `steps` | Escada: número de degraus; 0 = automático, um a cada 28 cm do comprimento. |

O símbolo também tem os campos de **nome** (vazio por padrão).

### `text` (texto)

| Campo | Descrição |
|---|---|
| `x`, `y` | Centro do texto. |
| `text` | O texto (pode ter quebras de linha `\n`). |
| `size` | Altura das letras, em cm da obra. |
| `bold` | Negrito. |
| `rot` | `0` = deitado; `90` = em pé (lido de baixo para cima). |
| `font` | Desde a 1.1. Família da fonte; vazio = a fonte do desenho (`settings.font`). |
| `italic` | Desde a 1.1. Itálico. |

### `dim` (medida)

| Campo | Descrição |
|---|---|
| `x1`, `y1`, `x2`, `y2` | Os dois pontos medidos. |
| `offset` | Distância da linha da medida até os pontos, em cm. Positivo afasta para a esquerda de quem vai de 1 para 2 (numa medida da esquerda para a direita, para cima). |
| `text` | Vazio = escreve o comprimento calculado; senão, este texto. |

## Leitura tolerante

O app nunca recusa um desenho por causa de um detalhe:

- campo ausente fica com o padrão; valor de tipo errado (`"grossa"` numa largura) também;
- números fora dos limites dos ajustes são trazidos para dentro deles; `unit` desconhecida vira `"m"`;
- elemento de um `kind` desconhecido (de uma versão mais nova) é ignorado, e os outros são lidos; o mesmo vale
  para um `symbol` com `shape` desconhecido e para um `poly` com menos de 2 pontos;
- pontos de `points` que não forem um par de números finitos são descartados; tamanhos negativos de um
  símbolo viram 1 cm;
- uma fonte que não está instalada no computador continua gravada no arquivo; na tela e no papel, o sistema usa
  uma parecida;
- campos a mais são ignorados;
- arquivo com BOM do UTF-8 é aceito.

Só não é aceito o que não for um objeto JSON com `elements`: aí o app avisa que o arquivo não é um desenho.

## Gravação e cópia de recuperação

- A gravação é **atômica**: o app escreve num arquivo temporário na mesma pasta (`nome.cadinho.xxxx.tmp`), força a
  ida ao disco e só então troca pelo arquivo final. Se algo falhar no meio, o arquivo anterior continua inteiro.
- A **cópia de recuperação** é um `.cadinho` comum com o campo `recovery`, gravado alguns segundos depois de cada
  mudança não salva em `%LOCALAPPDATA%\Autocadinho\recuperacao.cadinho` (no Linux,
  `~/.local/share/autocadinho`). Ela é apagada ao salvar ou ao fechar o app normalmente; se existir na abertura,
  o app oferece recuperar.

## Mudanças no formato

`format` só sobe quando uma versão antiga do app deixaria de ler o arquivo corretamente. Campos e tipos novos
**não** mudam o `format`: versões antigas ignoram o que não conhecem. Registre qualquer mudança neste documento
e no [CHANGELOG](../CHANGELOG.md).

| Versão | Mudança (`format` continua `1`) |
|---|---|
| 1.1 | Tipos `ellipse`, `poly` e `symbol`; `settings.font`; `font` e `italic` no texto; `arrow_start` e `arrow_end` na linha; `show_area` no retângulo. A 1.0 abre esses arquivos sem os elementos novos e sem as fontes. |
