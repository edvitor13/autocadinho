# AGENTS.md

Guia rápido para quem mexe no código do Autocadinho (pessoas ou agentes de IA). Leia antes de mudar
qualquer coisa. Detalhes em [docs/ARQUITETURA.md](docs/ARQUITETURA.md), formato do arquivo em
[docs/FORMATO.md](docs/FORMATO.md), testes, build e release em [docs/DESENVOLVIMENTO.md](docs/DESENVOLVIMENTO.md).

## O que é

App de desktop (Python + PySide6) para desenhos simples de obra: vigas, pilares, linhas, formas (retângulo,
círculo, triângulo, polígono), símbolos (portas, janelas, escada, louças, norte), medidas e textos, em
centímetros de verdade, salvos em `.cadinho` (JSON) e impressos em escala. Público:
gente que não é de informática. Simplicidade e clareza vêm antes de recursos.

## Mapa

| Arquivo | Papel |
|---|---|
| `autocadinho/model.py` | Elementos (`KINDS`) e `Document`; JSON tolerante (`to_dict`/`from_dict`) |
| `autocadinho/geometry.py` | Contas puras: encaixe, 90°, giro, formato das medidas |
| `autocadinho/render.py` | Pinta o desenho (`paint_document`), símbolos, fontes, caixas dos nomes e das áreas, clique, alças, `wall_at` |
| `autocadinho/printing.py` | Folha impressa, escalas, papéis, PDF, PNG, miniatura |
| `autocadinho/fileio.py` | Gravação atômica, leitura, miniatura, cópia de recuperação |
| `autocadinho/history.py` | Desfazer/refazer por fotografias JSON |
| `autocadinho/i18n.py`, `locales/en.json` | `_()`/`N_()`, catálogo inglês, datas, traduções do Qt |
| `autocadinho/updater.py` | Atualização automática: release do GitHub, download, SHA-256, script de instalação |
| `autocadinho/ui/main_window.py` | Janela, ações e atalhos, arquivos, histórico, recuperação, idioma e tema |
| `autocadinho/ui/canvas.py` | Área de desenho: vista, ferramentas, encaixe, seleção, edição no lugar |
| `autocadinho/ui/properties.py` | Painel da direita |
| `autocadinho/ui/home.py`, `print_dialog.py`, `help_dialog.py`, `language_dialog.py`, `update_dialog.py` | Telas e janelas |
| `autocadinho/ui/flyout.py` | Menu flutuante dos grupos Formas e Símbolos |
| `autocadinho/ui/theme.py`, `icons.py`, `prefs.py` | Cores e QSS, ícones em QPainter, QSettings |
| `autocadinho/app.py` | Ponto de entrada e autoverificação do executável |
| `tools/` | `i18n_extract.py`, `screenshots.py`, `make_assets.py`, `make_site.py` (página do app) |
| `packaging/` | `make_zip.py`, `install_marker.py` e `windows/` (WiX, scripts de build e de verificação) |

## Regras que não podem ser quebradas

- **Centímetros e y para baixo** em todo o modelo e no arquivo. Metros só na hora de escrever uma medida.
- **Um caminho só para pintar:** tela, prévia, impressora, PDF, PNG e miniatura passam por
  `render.paint_document`. Não crie um desenho "só para a impressão".
- **O núcleo não importa widgets.** `model`, `geometry`, `history` e `fileio` não usam Qt; `render` e
  `printing` usam o QPainter, sem widgets.
- **Todo texto para o usuário com `_()`**, escrito em português do Brasil com acentos, e com a tradução em
  `locales/en.json` (`python tools/i18n_extract.py --write` e preencha). Tabelas montadas na importação usam
  `N_()`. Os testes falham se faltar tradução.
- **Arquivos antigos sempre abrem.** Não renomeie nem mude o sentido de campos do `.cadinho`; campos novos têm
  padrão neutro; `kind` desconhecido é ignorado. Mudou o formato? Atualize o `docs/FORMATO.md`.
- **Gravação sempre atômica** (`fileio.atomic_write`). Nunca escreva direto por cima de um desenho.
- **Testes e automações nunca tocam as preferências nem a recuperação de quem usa o app:** use
  `AUTOCADINHO_SETTINGS_DIR` e `AUTOCADINHO_DATA_DIR` (o `tests/conftest.py` já faz isso). Testes não acessam a
  internet: `AUTOCADINHO_NO_UPDATE_CHECK` e a rede simulada por monkeypatch. Janelas de teste com
  `WA_DontShowOnScreen`; caixas de pergunta respondidas por monkeypatch, nunca esperando um clique.
- **Uma mudança = um passo no histórico.** A área de desenho emite `changed(chave)` quando o passo termina; a
  janela grava. Não grave o histórico no meio de um arraste.
- **Só Windows nos pacotes** (por enquanto). O código evita coisas exclusivas do Windows fora de `try` e de
  `sys.platform == "win32"`.
- **Sem dependências novas** além do `PySide6-Essentials` sem um bom motivo; o executável corta os módulos do Qt
  que não são usados (`Autocadinho.spec`).
- **Nunca mude o `UpgradeCode`** do instalador (`packaging/windows/Autocadinho.wxs`).
- **Não quebre o atualizador de quem já instalou:** os nomes `Autocadinho-X.Y.Z-windows-x64.msi`/`.zip`, o
  `SHA256SUMS.txt` na release e o marcador `autocadinho-install.json` são um contrato com as versões antigas.
- **Sem dados pessoais** no projeto (nomes, e-mails, caminhos de máquina).

## Comandos

```bat
instalar.bat                                   :: .venv + requirements.txt
.venv\Scripts\python -m pip install -r requirements-dev.txt
executar.bat                                   :: abre o app
.venv\Scripts\python -m pytest -q              :: todos os testes
.venv\Scripts\python tools\i18n_extract.py     :: confere as traduções (--write acrescenta os novos)
.venv\Scripts\python tools\screenshots.py      :: capturas da documentação
.venv\Scripts\python tools\make_site.py        :: página do app (docs/site/index.html)
build.bat                                      :: executável conferido, .zip e (com o WiX) .msi
```

## Receitas

**Um campo novo num elemento** (por exemplo, `dashed` na viga): acrescente na `dataclass` com padrão neutro;
pinte em `render.py`; mostre no painel (`properties.py`) com `_()`; teste o JSON de ida e volta e a leitura de
um arquivo sem o campo; documente no `docs/FORMATO.md`.

**Um tipo novo de elemento:** `dataclass` com `@_register` e `kind` único em `model.py`, com `move`, `rotate90`,
`center`, `key_points`, `snap_segments` (e `sane()` se algum valor do arquivo puder ser impossível); pintura,
limites, clique e alças em `render.py`; ferramenta em
`canvas.py` (`TOOLS`, `_make`/clique) e no trilho da janela (`TOOLS` em `main_window.py`, com tecla e ícone em
`icons.py`); painel; ajuda (`help_dialog.py`); testes; `docs/FORMATO.md`.

**Um símbolo novo** (por exemplo, uma banheira): acrescente em `SYMBOLS` (`model.py`) com o nome e o tamanho
padrão; desenhe no sistema do símbolo em `render._paint_symbol` (origem no centro, ou no meio do vão se for de
parede, com y para dentro do cômodo) e ajuste `Symbol.local_bounds`; se for de parede, ponha em `WALL_SYMBOLS`.
O menu de Símbolos e o ícone (`sym:<nome>`) saem sozinhos; confira o ícone em `icons.SYMBOL_ICON`. Atualize o
`docs/FORMATO.md`.

**Um papel novo:** `PAPER_MM` (mm, em pé), `PAPER_LABELS` (com `N_()` se o nome traduz) e, se o Qt tiver o
tamanho pronto, `PAPER_IDS`. Teste em `tests/test_render_printing.py`.

**Uma escala nova:** acrescente em `printing.SCALES` (em ordem). `best_scale` passa a considerá-la.

**Um texto novo na interface:** `_("...")` no código, `tools\i18n_extract.py --write`, preencha o inglês.

**Um atalho novo:** uma `QAction` em `MainWindow._build_actions` e a linha na tabela `SHORTCUTS` de
`help_dialog.py` (e no `docs/GUIA.md` / `docs/GUIDE.md`).

**Uma versão nova:** siga "Publicar uma versão" em [docs/DESENVOLVIMENTO.md](docs/DESENVOLVIMENTO.md)
(versão em dois lugares, CHANGELOG, `docs/releases/vX.Y.Z.md`, tag).

## Antes de dar por pronto

- `pytest -q` passando e `tools\i18n_extract.py` sem faltas.
- Mudou algo visível? Abra o app (`executar.bat`) e confira nos dois temas e nos dois idiomas; atualize as
  capturas com `tools\screenshots.py` se a tela mudou.
- Mudou o empacotamento? `build.bat` (a autoverificação do executável tem que passar).
- Documentação e CHANGELOG atualizados.
