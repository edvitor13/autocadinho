# CLAUDE.md

Leia **[AGENTS.md](AGENTS.md)** antes de mudar qualquer coisa: lá estão o mapa dos módulos, as regras que não
podem ser quebradas, os comandos e as receitas. Detalhes técnicos em [docs/ARQUITETURA.md](docs/ARQUITETURA.md);
formato do arquivo em [docs/FORMATO.md](docs/FORMATO.md); testes, build e release em
[docs/DESENVOLVIMENTO.md](docs/DESENVOLVIMENTO.md).

## O essencial

- **Centímetros, y para baixo**; metros só ao escrever uma medida.
- **Mesmo caminho para tela e papel:** tudo passa por `render.paint_document`.
- **Texto para o usuário com `_()`**, em PT-BR com acentos, e tradução em `autocadinho/locales/en.json`
  (`tools/i18n_extract.py --write`).
- **Arquivos antigos sempre abrem**; gravação sempre atômica.
- **Nunca tocar as preferências nem a recuperação do usuário** em testes e automações
  (`AUTOCADINHO_SETTINGS_DIR`, `AUTOCADINHO_DATA_DIR`).
- **Sem dados pessoais** no projeto.

## Comandos

```bat
.venv\Scripts\python -m pytest -q
.venv\Scripts\python tools\i18n_extract.py
build.bat
```
