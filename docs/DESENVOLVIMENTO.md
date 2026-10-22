# Desenvolvimento

Como preparar o ambiente, testar, traduzir, gerar o executável e o instalador e publicar uma versão.
O mapa do código está em [ARQUITETURA.md](ARQUITETURA.md) e as regras do dia a dia em [AGENTS.md](../AGENTS.md).

## Ambiente

Precisa do Python **3.12 ou mais novo** (o CI usa o 3.15). No Windows:

```bat
instalar.bat                                         :: cria o .venv e instala o requirements.txt
.venv\Scripts\python -m pip install -r requirements-dev.txt   :: + pytest e PyInstaller
executar.bat                                         :: abre o app (sem console)
```

Em qualquer sistema:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt    # no Windows: .venv\Scripts\python
.venv/bin/python -m autocadinho [desenho.cadinho]
```

A única dependência de execução é o `PySide6-Essentials` (Qt 6: Core, Gui, Widgets e PrintSupport).

### Variáveis de ambiente

| Variável | Efeito |
|---|---|
| `AUTOCADINHO_SETTINGS_DIR` | Preferências num `.ini` nessa pasta, em vez do registro do Windows. Os testes e as ferramentas usam sempre uma pasta temporária. |
| `AUTOCADINHO_DATA_DIR` | Pasta da cópia de recuperação, em vez de `%LOCALAPPDATA%\Autocadinho`. |
| `AUTOCADINHO_SELFTEST` | Caminho de um `.json`: o app faz a autoverificação, grava o relatório e fecha (veja [Executável](#executável)). |

## Testes

```bat
.venv\Scripts\python -m pytest -q
```

| Arquivo | O que cobre |
|---|---|
| `tests/test_geometry.py` | Distâncias, retas a 90°, encaixe (prioridade de pontos, trechos e grade), giro, formato das medidas |
| `tests/test_model.py` | Elementos e documento: JSON de ida e volta, leitura tolerante, nomes automáticos, prefixos por idioma, giro, ordem |
| `tests/test_history_fileio.py` | Desfazer/refazer e junção de passos; gravar e ler; gravação atômica; cópia de recuperação |
| `tests/test_render_printing.py` | Caixas dos nomes, clique, alças, limites; folha impressa, escalas, papéis, PDF, PNG e miniatura |
| `tests/test_i18n.py` | Catálogo completo (via `tools/i18n_extract.py`), marcadores e tags iguais, datas por idioma |
| `tests/test_ui.py` | A janela de verdade usada com mouse e teclado: desenhar, encaixar, selecionar, mover, painel, arquivos, recuperação depois de "queda de energia", idioma, tema, impressão |

Regras dos testes:

- O `tests/conftest.py` aponta `AUTOCADINHO_SETTINGS_DIR` e `AUTOCADINHO_DATA_DIR` para uma pasta temporária
  **antes** de importar o app: os testes nunca mexem nas preferências nem na cópia de recuperação de quem usa
  o app no mesmo computador.
- No Windows os testes usam a plataforma normal do Qt (a `offscreen` não tem fontes no Windows) e as janelas são
  criadas com `WA_DontShowOnScreen`: existem e recebem eventos, mas não aparecem na tela. Em outros sistemas
  o conftest usa `offscreen`.
- Caixas de pergunta (`QMessageBox.exec`) são respondidas por `answer()` em `test_ui.py`, que clica no botão
  pelo texto; nenhuma janela modal fica esperando.

## Traduções

O texto-fonte é o português, direto no código, sempre com `_()` (ou `N_()` em tabelas montadas na importação).
Para um texto novo:

1. Escreva `_("Texto em português")` no código (com `{marcadores}` para valores: `_("{n} itens").format(n=3)`).
2. Rode `.venv\Scripts\python tools\i18n_extract.py --write`: os textos novos entram vazios em
   `autocadinho/locales/en.json`, na ordem em que aparecem no código, e os que sumiram saem.
3. Preencha o inglês. Mantenha os mesmos `{marcadores}`, `<tags>` e quebras de linha.
4. `tools\i18n_extract.py` (sem `--write`) e `tests/test_i18n.py` falham se faltar alguma tradução.

Os textos do próprio Qt (menu do botão direito nos campos, janela de cores) vêm da tradução `qtbase_pt_BR.qm`
que acompanha o PySide6 e que o executável também leva.

## Capturas de tela e ícones

```bat
.venv\Scripts\python tools\screenshots.py     :: docs/img/*.png (português e -en), com o desenho de exemplo
.venv\Scripts\python tools\make_assets.py     :: assets/logo.ico, documento.ico, logo-256.png, logo-512.png
```

As capturas rodam com preferências temporárias e janelas fora da tela. O logotipo é desenhado em código
(`icons.paint_logo`); o `assets/logo.svg` é o mesmo desenho, mantido à mão para quem precisar de um vetor.

## Executável

```bat
build.bat
```

1. Instala o PyInstaller e o pytest no `.venv`, se faltarem.
2. Gera `dist\Autocadinho\` com o `Autocadinho.exe` (receita em `Autocadinho.spec`).
3. Confere o executável com `packaging\windows\verificar_exe.ps1`: abre o app com `AUTOCADINHO_SELFTEST`, que
   abre o desenho de exemplo, gera um PDF e uma imagem, confere o inglês e os textos do Qt em português, grava
   um relatório e fecha. A janela aparece por alguns segundos. As preferências de quem roda não são tocadas.
4. Se o WiX estiver instalado, gera o instalador `.msi` (abaixo).
5. Gera o `.zip` portátil com `packaging\make_zip.py` (que tenta de novo se o antivírus estiver lendo o `.exe`).

O `Autocadinho.spec` corta o que o app não usa: módulos do Qt além de Core, Gui, Widgets e PrintSupport,
plugins que puxariam Quick, Qml, Pdf, Svg e Network, o OpenGL por software (20 MB), o OpenSSL e as traduções do
Qt que não são o português. Se o app passar a usar outro módulo do Qt, tire-o de `QT_UNUSED` (e, se for o caso,
de `QT_DLLS_UNUSED`) e rode o `build.bat`: a autoverificação mostra se o pacote abre.

## Instalador `.msi`

Feito com o [WiX Toolset](https://wixtoolset.org/) v5, que precisa do .NET SDK:

```bat
dotnet tool install --global wix --version 5.0.2
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\windows\build_msi.ps1 ^
    -SourceDir dist\Autocadinho -Output dist\Autocadinho-1.0.0-windows-x64.msi
```

- Instalação **por usuário**, sem pedir administrador, em `%LOCALAPPDATA%\Programs\Autocadinho`, com atalho no
  Menu Iniciar e na Área de Trabalho e a associação dos `.cadinho` (com o ícone `assets\documento.ico`).
- Interface em português: licença MIT (gerada do `LICENSE` por `license_rtf.py`), instalar e concluir, com a
  opção de abrir o app no fim.
- Uma versão nova instala por cima e substitui a antiga no mesmo lugar (`MajorUpgrade`). **Nunca mude o
  `UpgradeCode`** em `packaging\windows\Autocadinho.wxs`.
- Linha de comando: `msiexec /i Autocadinho.msi /passive ABRIR_APOS_INSTALAR=1`; `INSTALLFOLDER=...` escolhe
  outra pasta; `ADDLOCAL`/`REMOVE` escolhem `AtalhoDesktop` e `AssociacaoCadinho`.
- O instalador grava só em `HKCU\Software\Autocadinho\Instalador`; as preferências do app ficam em
  `HKCU\Software\Autocadinho\Autocadinho` e sobrevivem a atualizações e à desinstalação.

`packaging\windows\verificar_msi.ps1` instala, confere (pasta, atalhos, associação, "Adicionar ou remover
programas", autoverificação do app instalado), atualiza para uma versão maior, desinstala e confere que não
sobrou nada. **Ele roda só no CI**: no seu computador, desinstalaria o seu Autocadinho.

## CI (GitHub Actions)

`.github/workflows/build.yml`:

- **Todo push e pull request:** testes no Windows (inclui a conferência das traduções).
- **Push no `main`, tags `v*` e execução manual:** também gera o executável, roda a autoverificação, monta o
  `.msi`, testa o `.msi` de verdade (instalar, atualizar, desinstalar) e monta o `.zip`. Os pacotes ficam nos
  artefatos da execução.
- **Tags `v*`:** publica a release com o `.msi`, o `.zip` e o `SHA256SUMS.txt`, com o texto de
  `docs/releases/<tag>.md` (ou as notas automáticas do GitHub, se o arquivo não existir). Tags com hífen
  (`v1.1.0-beta`) viram pré-lançamento.

## Publicar uma versão

1. Suba a versão em `autocadinho/__init__.py` (`__version__` e `__date__`) e em `pyproject.toml`. O CI confere
   que as duas batem e que a tag bate com elas. O MSI só aceita números (`x.y.z`).
2. Escreva a seção da versão no [CHANGELOG.md](../CHANGELOG.md) e o texto da página da release em
   `docs/releases/vX.Y.Z.md` (para quem vai baixar: o que mudou, em linguagem simples).
3. Faça o commit no `main`, envie e espere o CI ficar verde (é ele que testa o `.msi`).
4. Crie e envie a tag:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

5. O CI publica a release. Confira a página e baixe o `.msi` para um teste rápido.

## Estilo do código

- Comentários, docstrings, mensagens e nomes de testes em **português do Brasil com acentos**; nomes de
  variáveis, funções e campos do arquivo em inglês, sem acentos.
- Linhas de até 120 caracteres; `from __future__ import annotations`; tipos nas assinaturas.
- Texto para o usuário sempre com `_()`: simples, direto e no vocabulário de obra (viga, pilar, medida, folha),
  sem jargão de informática.
- Mudou o formato do arquivo? Atualize o [FORMATO.md](FORMATO.md) e mantenha a leitura de arquivos antigos.
