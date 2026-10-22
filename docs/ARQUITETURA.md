# Arquitetura do Autocadinho

Como o programa é organizado por dentro. Para o dia a dia (comandos, regras e receitas), veja
[AGENTS.md](../AGENTS.md); para o arquivo `.cadinho`, [FORMATO.md](FORMATO.md).

## Visão geral

- **Python 3.12+ e PySide6** (Qt 6, só os módulos Core, Gui, Widgets e PrintSupport). Nenhuma outra dependência.
- Um único processo e uma única thread: os desenhos são pequenos, então tudo (desenho, histórico, gravação,
  impressão) roda direto na thread da interface.
- **O núcleo não depende da interface.** `model`, `geometry`, `history` e `fileio` não importam Qt (o `fileio`
  só usa biblioteca padrão); `render` e `printing` usam o QPainter, mas nenhum widget. A interface (`ui/`) usa
  todos eles.
- **Um caminho só para pintar.** A tela, a prévia da impressão, a impressora, o PDF, a imagem PNG e a
  miniatura dos recentes pintam o desenho com a mesma função, `render.paint_document`. O que se vê é o que sai.

```
autocadinho/
  __init__.py      versão, nome do app, extensão .cadinho, endereço do repositório
  __main__.py      python -m autocadinho
  app.py           ponto de entrada: QApplication, tema, idioma, janela; autoverificação do executável
  i18n.py          _() e N_(), catálogo locales/en.json, formato de datas e traduções do próprio Qt
  locales/en.json  português -> inglês
  model.py         elementos (viga, linha, pilar, retângulo, texto, medida) e o Document; JSON
  geometry.py      contas: distâncias, encaixe, retas a 90°, giro, formato das medidas (sem Qt)
  history.py       desfazer/refazer por fotografias do documento
  fileio.py        ler/gravar .cadinho (gravação atômica), miniatura, cópia de recuperação
  render.py        pintar elementos, nomes e medidas; caixas de seleção, alças, acerto do clique
  printing.py      a folha impressa (cabeçalho, escala, rodapé), PDF, PNG, impressora, miniatura
  samples.py       o desenho de exemplo (mezanino)
  ui/
    main_window.py janela: barra de cima, ferramentas, área de desenho, painel, barra de baixo, menus
    canvas.py      área de desenho: vista (zoom e arraste), ferramentas, encaixe, seleção, edição no lugar
    properties.py  painel da direita (o selecionado ou os ajustes do desenho)
    home.py        tela inicial com os recentes
    print_dialog.py janela de impressão com prévia; exportar PDF e imagem
    help_dialog.py "Como usar" (F1)
    language_dialog.py escolha do idioma na primeira vez
    theme.py       paletas clara e escura, fontes, folha de estilo (QSS)
    icons.py       ícones desenhados com QPainter (nenhum arquivo de imagem) e o logotipo
    prefs.py       QSettings: idioma, tema, recentes, opções de impressão, geometria da janela
```

## O modelo (`model.py`)

- Cada tipo de elemento é uma `dataclass` registrada em `KINDS` pelo seu `kind` (`beam`, `line`, `pillar`,
  `rect`, `text`, `dim`). `Element.to_dict()` usa `asdict`; `Element.from_dict()` lê só os campos que conhece e
  converte cada valor para o tipo do padrão (`_coerce`), então arquivos estranhos ou de outras versões nunca
  quebram a leitura.
- `Segment` (viga e linha) tem `x1, y1, x2, y2, width`; `Labeled` (viga e pilar) acrescenta o nome:
  `label`, `label_visible`, `label_dx/dy` (deslocamento do nome em relação ao centro; `None` = automático) e
  `label_rot`.
- Cada elemento sabe se mover (`move`), girar 90° em torno de um ponto (`rotate90`, que também gira o
  deslocamento do nome), dizer o seu centro e os seus pontos e trechos de encaixe (`key_points`,
  `snap_segments`).
- `Document` guarda o título, os ajustes (`SETTINGS`, com limites em `LIMITS`) e a lista de elementos do fundo
  para a frente. `next_label(prefixo)` acha o próximo número livre (VIGA 3, P4).
- **Unidade: centímetros, com y para baixo**, em todo o núcleo. Metros só aparecem ao escrever uma medida
  (`geometry.format_length`).

## Pintura (`render.py`)

- `paint_document(p, doc, style)` pinta todos os elementos em coordenadas do desenho (cm). Quem chama monta a
  transformação do QPainter: a área de desenho usa `escala = pixels por cm`, a folha impressa usa
  `mm de papel por cm`.
- `Style` diz como pintar: a tinta (cor *automática*), espessura mínima das linhas e se tudo sai em preto.
  `print_style()` é o papel branco; a área de desenho monta um `Style` com as cores do tema.
- Os **nomes** ficam numa `Box` (centro, largura, altura, ângulo) calculada por `label_box`: ao lado da viga,
  do lado de "cima" (`geometry.normal_up`), ou embaixo/ao lado do pilar; com `label_dx/dy`, onde a pessoa
  arrastou. Textos girados são sempre legíveis (`readable_angle`).
- As mesmas caixas servem para **clicar**: `hit` acha o elemento (e a parte, como o nome) sob o mouse, com
  prioridade para o que está por cima; `touching` acha o que encosta num retângulo de seleção; `handles` dá as
  alças de cada tipo.
- `text_font` desliga o ClearType (antialias por subpixel): o texto do desenho é girado e escalado, e o
  subpixel deixaria franjas coloridas na prévia e no PDF.

## Área de desenho (`ui/canvas.py`)

- **Vista:** `x_tela = x * scale + ox`. 100% de zoom = 1 pixel por cm. `fit()` enquadra o desenho; a rodinha
  aproxima em torno do mouse.
- **Ferramentas:** `TOOLS` (`select`, `beam`, `line`, `pillar`, `rect`, `dim`, `text`, `erase`, `pan`). O arraste
  em andamento fica em `self._drag` (um `SimpleNamespace` com o modo: mover, alça, nome, desenhar, seleção por
  área, mover a folha). **Esc** cancela e restaura o estado de antes.
- **Encaixe** (`snap_point` → `geometry.snap`): primeiro os pontos (pontas, meios, cantos, centros), depois os
  trechos (ao longo de uma viga), por fim a grade (`snap_step`). A tolerância é em pixels da tela. As retas a
  90° (`geometry.ortho`) valem enquanto `ortho_on` e Shift invertem; Alt solta o encaixe.
- **Edição no lugar:** nomes e textos de uma linha são editados num `QLineEdit` sobre a folha
  (`_InlineEditor`); textos de várias linhas vão para o painel (`editRequested`).
- **Área de transferência:** copiar grava os elementos como JSON num tipo próprio (`MIME`) e um texto simples
  com os nomes; colar renova os ids e renumera os nomes automáticos.
- A área de desenho **muda o documento direto** e emite `changed(chave)` quando um passo termina (soltar o
  mouse, Enter, uma tecla de seta). Ela não conhece o histórico.

## Histórico, sujeira e recuperação (`main_window.py`, `history.py`)

- Desfazer/refazer guarda **fotografias** do documento inteiro (o JSON de `to_dict`, com chaves ordenadas).
  Desenhos de obra são pequenos, e isso é simples e à prova de erro: não existe "comando" que possa
  desfazer pela metade. Limite de 300 passos.
- `MainWindow.commit(chave, origem)` grava um passo. Passos seguidos com a **mesma chave** em menos de 1,5 s
  viram um só (digitar no painel, apertar a seta várias vezes). Só chaves do painel e `nudge` (setas) se juntam.
- **Sujeira:** o desenho tem mudanças quando a fotografia atual difere da última salva (`_saved_state`).
  Desfazer até o ponto salvo limpa o "•" do título.
- **Recuperação:** 4 s depois de uma mudança não salva, `fileio.write_recovery` grava a cópia em
  `%LOCALAPPDATA%\Autocadinho\recuperacao.cadinho`. Salvar ou fechar normalmente apaga. Na abertura
  (`startup`), se a cópia existir, o app pergunta: **Recuperar** abre o desenho como "não salvo" (com o
  caminho original, se havia); **Descartar** apaga.

## Arquivos (`fileio.py`)

- `save` escreve num temporário na mesma pasta, faz `fsync` e troca com `os.replace` (atômico no Windows e no
  Linux). Uma falha no meio nunca estraga o arquivo anterior.
- O arquivo leva uma miniatura PNG em Base64 (`printing.thumbnail_png`), lida pela tela inicial sem montar o
  desenho inteiro.
- Erros viram `FileError` com uma mensagem pronta (`not-a-drawing` ou a do sistema operacional), mostrada
  pela janela.

## Impressão (`printing.py`, `ui/print_dialog.py`)

- `PageOptions`: papel (`PAPER_MM`, em mm; A4, A3, A2, Carta e Ofício, que não existe pronto no Qt e é
  criado com `QPageSize` personalizado), orientação (automática pela proporção do desenho), escala
  (0 = ajustar à folha; senão 1:N de `SCALES`), cabeçalho e preto e branco. As opções ficam em `QSettings`.
- `compute_layout` calcula, em mm, a área útil (margens de 10 mm, cabeçalho de 15 mm, rodapé de 7 mm) e o
  fator `k` = mm de papel por cm do desenho. Na escala 1:N, `k = 10 / N`; ajustando à folha, `k` é o maior que
  cabe e a escala aproximada vai para o rodapé.
- `best_scale` acha a maior escala "redonda" em que o desenho cabe (o botão *Usar 1:N, que cabe*).
- `render_page(p, doc, opts, alvo)` monta a folha inteira (título, data no formato do idioma, desenho
  centralizado, escala, nome do app) e serve à impressora (`QPrinter` em alta resolução), ao `QPdfWriter`, à
  imagem PNG e à prévia (que pinta numa `QImage` na resolução da tela e depois desenha a imagem).

## Interface

- **Janela** (`MainWindow._build`): uma `QStackedWidget` com a tela inicial (0) e o editor (1). Trocar o idioma
  **reconstrói a janela inteira** mantendo o desenho, o histórico, o caminho e a vista.
- **Ações** (`_build_actions`): todas as ações com atalho são `QAction` da janela; os botões e menus usam as
  mesmas ações. Os ícones das ações são redesenhados ao trocar o tema (`_recolor_actions`).
- **Painel** (`properties.py`): reconstruído a cada mudança de seleção ou de documento (vinda de fora do
  painel). O widget antigo sai com `takeWidget()` antes do `setWidget()` e é apagado depois (`deleteLater`),
  porque a mudança pode ter vindo de um clique dentro dele.
- **Tema** (`theme.py`): `Palette` com as cores de cada tema, `stylesheet()` gera a folha de estilo QSS e
  `apply()` aplica a paleta, a folha de estilo e redesenha os ícones. A barra de título do Windows acompanha o
  tema escuro (`DwmSetWindowAttribute`).
- **Ícones** (`icons.py`): todos desenhados com QPainter em `draw(nome, painter, cor)`, em 24 × 24 unidades. Os
  widgets marcados com `icons.bind` são repintados na cor do tema. O logotipo (`paint_logo`) também gera os
  `.ico` do executável e do instalador (`tools/make_assets.py`).

## Tradução (`i18n.py`)

- O texto-fonte é o **português do Brasil**, escrito direto no código com `_()`. O inglês está em
  `locales/en.json`, um dicionário português → inglês. Texto sem tradução aparece em português.
- Tabelas montadas na importação (nomes das ferramentas, papéis, seções da ajuda) usam `N_()` e são traduzidas
  com `_()` na hora de mostrar.
- `set_language` também ajusta o `QLocale` padrão (datas 22/10/2026 ou 10/22/2026) e instala a tradução do
  próprio Qt (`qtbase_pt_BR.qm`: menu do botão direito dos campos, janela de cores).
- `tools/i18n_extract.py` lê o código (AST), lista todos os `_()`/`N_()` e confere o catálogo; `--write` acrescenta
  os textos novos. O teste `tests/test_i18n.py` falha se faltar tradução, se sobrar alguma, ou se `{marcadores}`,
  `<tags>` e quebras de linha não baterem.

## Preferências (`ui/prefs.py`)

`QSettings` nativo: no Windows, o registro em `HKCU\Software\Autocadinho\Autocadinho`. Chaves: `language`,
`theme`, `geometry`, `grid`, `snap`, `ortho`, `print_options`, `last_dir`, `recent`. Com a variável
`AUTOCADINHO_SETTINGS_DIR`, tudo vai para um `.ini` nessa pasta (testes e automações nunca tocam as
preferências de quem usa o app). Do mesmo jeito, `AUTOCADINHO_DATA_DIR` troca a pasta da cópia de recuperação.

## Empacotamento

- `Autocadinho.spec` (PyInstaller, pasta única): leva só Qt6Core, Qt6Gui, Qt6Widgets e Qt6PrintSupport, os
  plugins da janela do Windows, dos formatos de imagem e do estilo, a tradução `qtbase_pt_BR.qm` e o catálogo
  `locales/`. Ficam de fora o OpenGL por software, o OpenSSL e os plugins que puxariam Quick, Qml, Pdf, Svg e
  Network. Resultado: uns 60 MB em disco, 25 MB no `.zip`.
- `packaging/windows/Autocadinho.wxs` (WiX v5): instalação por usuário, sem administrador, em
  `%LOCALAPPDATA%\Programs\Autocadinho`, com atalhos e associação dos `.cadinho`. O `UpgradeCode` nunca muda.
- `AUTOCADINHO_SELFTEST=relatorio.json` faz o executável abrir o exemplo, gerar PDF e imagem, conferir as duas
  traduções, gravar um relatório e fechar (`app.self_test`). O CI usa isso para conferir o executável e o app
  instalado pelo `.msi`. Detalhes em [DESENVOLVIMENTO.md](DESENVOLVIMENTO.md).
