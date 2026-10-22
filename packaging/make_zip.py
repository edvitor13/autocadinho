"""Monta o .zip portátil a partir da pasta gerada pelo PyInstaller.

Uso:  python packaging/make_zip.py dist/Autocadinho dist/Autocadinho-1.0.0-windows-x64.zip

O .zip leva a pasta Autocadinho na raiz: quem baixa extrai e abre o Autocadinho.exe. Se um arquivo
estiver preso (o antivírus conferindo o .exe recém-criado), tenta de novo por alguns segundos.
Só biblioteca padrão: roda no CI e no build.bat.
"""

from __future__ import annotations

import sys
import time
import zipfile
from pathlib import Path


def make_zip(src: Path, dst: Path, attempts: int = 6, wait: float = 3.0) -> int:
    files = sorted(p for p in src.rglob("*") if p.is_file())
    if not any(p.suffix.lower() == ".exe" for p in files):
        raise SystemExit(f"Nenhum .exe em {src}: rode o PyInstaller antes.")
    tmp = dst.with_name(dst.name + ".parcial")
    for attempt in range(1, attempts + 1):
        try:
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
                for f in files:
                    zf.write(f, Path(src.name) / f.relative_to(src))
            tmp.replace(dst)
            return len(files)
        except PermissionError as e:
            tmp.unlink(missing_ok=True)
            if attempt == attempts:
                raise
            print(f"  arquivo em uso ({e.filename}); tentando de novo em {wait:.0f} s...")
            time.sleep(wait)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip())
        return 2
    src, dst = Path(argv[0]), Path(argv[1])
    dst.parent.mkdir(parents=True, exist_ok=True)
    n = make_zip(src, dst)
    print(f"Portátil: {dst} ({n} arquivos, {dst.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
