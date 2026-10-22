import re
import sys
from pathlib import Path

from autocadinho import i18n

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import i18n_extract  # noqa: E402

PLACEHOLDER = re.compile(r"\{[a-z_]+\}")
TAG = re.compile(r"</?[a-z]+>")


def test_catalog_has_every_text_translated():
    found = i18n_extract.extract()
    catalog = i18n_extract.load()
    missing = [s for s in found if not catalog.get(s)]
    assert not missing, f"sem tradução para o inglês: {missing[:5]}"
    unused = [k for k in catalog if not k.startswith("@") and k not in found]
    assert not unused, f"traduções que sobraram: {unused[:5]}"


def test_placeholders_tags_and_line_breaks_match():
    catalog = i18n_extract.load()
    for src, dst in catalog.items():
        if src.startswith("@"):
            continue
        assert sorted(PLACEHOLDER.findall(src)) == sorted(PLACEHOLDER.findall(dst)), src
        assert sorted(TAG.findall(src)) == sorted(TAG.findall(dst)), src
        assert src.count("\n") == dst.count("\n") or src == "Mover\nfolha", src


def test_set_language_and_fallback():
    assert i18n.set_language("en") == "en"
    assert i18n._("Viga") == "Beam"
    assert i18n._("texto que não existe") == "texto que não existe"
    assert i18n.decimal_sep() == "."
    assert i18n.fmt_decimal(3.5) == "3.50"
    assert i18n.set_language("xx") == "en"
    assert i18n.set_language("pt_BR") == "pt_BR"
    assert i18n._("Viga") == "Viga"
    assert i18n.decimal_sep() == ","
    assert i18n.N_("Viga") == "Viga"


def test_dates_follow_language(qapp):
    from PySide6.QtCore import QDate, QLocale
    day = QDate(2026, 10, 22)
    i18n.set_language("pt_BR")
    assert QLocale().toString(day, QLocale.FormatType.ShortFormat) == "22/10/2026"
    i18n.set_language("en")
    assert QLocale().toString(day, QLocale.FormatType.ShortFormat).startswith("10/22/")


def test_system_language_is_supported():
    assert i18n.system_language() in i18n.LANGUAGES
