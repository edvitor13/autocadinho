r"""Confere e atualiza o catálogo de tradução (autocadinho/locales/en.json).

Lê o código com `ast` e junta todo texto passado a `_("...")` ou `N_("...")`.

    .venv\Scripts\python tools\i18n_extract.py          # confere: faltando, vazios e sobrando
    .venv\Scripts\python tools\i18n_extract.py --write  # acrescenta os novos (vazios) e tira os que sobram

Sai com código 1 se faltar tradução, para servir de verificação no CI. A ordem do arquivo segue a
ordem em que os textos aparecem no código, para quem traduz ler cada tela em sequência.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "autocadinho"
CATALOG = PACKAGE / "locales" / "en.json"
FUNCS = {"_", "N_"}


def extract(package: Path = PACKAGE) -> dict[str, list[str]]:
    """Texto-fonte → lugares onde aparece ("arquivo:linha"), na ordem do código."""
    found: dict[str, list[str]] = {}
    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(ROOT).as_posix()
        nodes = sorted((n for n in ast.walk(tree) if isinstance(n, ast.Call)), key=lambda n: (n.lineno, n.col_offset))
        for node in nodes:
            if not (isinstance(node.func, ast.Name) and node.func.id in FUNCS and node.args):
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value:
                found.setdefault(arg.value, []).append(f"{rel}:{node.lineno}")
    return found


def load(path: Path = CATALOG) -> dict[str, str]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    write = "--write" in argv
    found = extract()
    catalog = load()
    meta = {k: v for k, v in catalog.items() if k.startswith("@")}
    missing = [s for s in found if s not in catalog]
    empty = [s for s in found if s in catalog and not catalog[s]]
    unused = [k for k in catalog if not k.startswith("@") and k not in found]
    if write:
        out = dict(meta)
        for s in found:
            out[s] = catalog.get(s, "")
        CATALOG.parent.mkdir(parents=True, exist_ok=True)
        CATALOG.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"{CATALOG.relative_to(ROOT)}: {len(found)} textos ({len(missing)} novos, {len(unused)} removidos)")
        return 0
    for title, items in (("Faltando no catálogo", missing), ("Sem tradução", empty), ("Sobrando no catálogo", unused)):
        if items:
            print(f"{title} ({len(items)}):")
            for s in items:
                where = ", ".join(found.get(s, [])[:2])
                print(f"  {s!r}  {where}")
    print(f"{len(found)} textos; {len(missing)} faltando, {len(empty)} sem tradução, {len(unused)} sobrando")
    return 1 if missing or empty else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
