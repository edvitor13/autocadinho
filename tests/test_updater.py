"""Atualizador: versões, escolha do pacote, conferência do SHA-256, consulta ao GitHub (simulada) e o
script que instala depois que o app fecha. Nada aqui acessa a internet."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import time
import urllib.error
from pathlib import Path

import pytest

from autocadinho import __version__, updater

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packaging"))
import install_marker  # noqa: E402

NAMES = ["Autocadinho-9.0.0-windows-x64.msi", "Autocadinho-9.0.0-windows-x64.zip", "SHA256SUMS.txt"]


def release(names, tag="v9.0.0"):
    assets = {n: (f"https://example.invalid/{n}", 10) for n in names}
    return updater.Release(tag=tag, version=updater.parse_version(tag), name=tag, body="", url="u",
                           published="2026-10-22", assets=assets)


@pytest.mark.parametrize("text, expected", [("v1.2.3", (1, 2, 3)), ("1.10", (1, 10)), ("v2.0.0-beta", (2, 0, 0)),
                                            ("", (0,)), ("abc", (0,))])
def test_parse_version(text, expected):
    assert updater.parse_version(text) == expected


def test_is_newer():
    cur = updater.current_version()
    assert updater.is_newer(release([], f"v{cur[0] + 1}.0.0"))
    assert not updater.is_newer(release([], "v" + __version__))
    assert not updater.is_newer(release([], "v0.0.1"))


@pytest.mark.parametrize("kind, expected", [("msi", NAMES[0]), ("zip", NAMES[1])])
def test_pick_asset(kind, expected):
    assert updater.pick_asset(release(NAMES), kind)[0] == expected


def test_pick_asset_missing_or_source():
    assert updater.pick_asset(release(NAMES[1:]), "msi") is None
    assert updater.pick_asset(release(NAMES), "source") is None


def test_install_info_from_source_and_marker(tmp_path, monkeypatch):
    assert updater.install_info() == {"kind": "source"}
    assert not updater.can_auto_install("source")
    # Executável empacotado: lê o marcador gravado pelo build; sem ele, trata como .zip.
    exe = tmp_path / "Autocadinho.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(updater.sys, "frozen", True, raising=False)
    monkeypatch.setattr(updater.sys, "executable", str(exe))
    assert updater.install_info() == {"kind": "zip"}
    install_marker.write_marker(tmp_path, "msi", "1.2.3")
    assert updater.install_info() == {"kind": "msi", "version": "1.2.3"}


def test_install_marker_tool(tmp_path):
    assert install_marker.read_version() == __version__
    path = install_marker.write_marker(tmp_path, "zip", "1.0.0")
    assert json.loads(path.read_text(encoding="utf-8")) == {"kind": "zip", "version": "1.0.0"}
    with pytest.raises(SystemExit):
        install_marker.write_marker(tmp_path, "deb", "1.0.0")
    with pytest.raises(SystemExit):
        install_marker.write_marker(tmp_path, "zip", "1.0")


class FakeResponse(io.BytesIO):
    def __init__(self, data: bytes):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen(routes):
    def opener(req, timeout=0):
        url = req.full_url if hasattr(req, "full_url") else req
        if url not in routes:
            raise urllib.error.HTTPError(url, 404, "nf", {}, None)
        return FakeResponse(routes[url])
    return opener


def test_check_parses_api(monkeypatch):
    api = {"tag_name": "v9.0.0", "name": "9.0", "body": "notas", "html_url": "https://github.com/x",
           "published_at": "2026-10-22T10:00:00Z",
           "assets": [{"name": NAMES[0], "browser_download_url": "https://d/msi", "size": 5}, "lixo"]}
    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen({updater.API_LATEST: json.dumps(api).encode()}))
    rel = updater.check()
    assert rel.tag == "v9.0.0" and rel.version == (9, 0, 0)
    assert rel.assets == {NAMES[0]: ("https://d/msi", 5)}
    assert rel.published == "2026-10-22" and rel.body == "notas"
    assert updater.API_LATEST == "https://api.github.com/repos/edvitor13/autocadinho/releases/latest"


def test_check_no_release_and_offline(monkeypatch):
    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen({}))
    with pytest.raises(updater.UpdateError, match="no-public-release"):
        updater.check()

    def boom(*a, **k):
        raise OSError("sem rede")
    monkeypatch.setattr(updater.urllib.request, "urlopen", boom)
    with pytest.raises(updater.UpdateError, match="offline"):
        updater.check()


def test_download_verifies_checksum(monkeypatch):
    payload = b"conteudo do instalador" * 100
    rel = release(NAMES)
    name = NAMES[1]
    routes = {rel.assets[name][0]: payload,
              rel.assets["SHA256SUMS.txt"][0]: f"{hashlib.sha256(payload).hexdigest()}  {name}\n".encode()}
    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen(routes))
    seen = []
    path = updater.download(rel, (name, rel.assets[name][0], len(payload)), lambda d, t: seen.append((d, t)))
    assert Path(path).read_bytes() == payload
    assert seen[-1] == (len(payload), len(payload))


def test_download_rejects_bad_or_missing_checksum(monkeypatch):
    rel = release(NAMES)
    name = NAMES[1]
    routes = {rel.assets[name][0]: b"adulterado", rel.assets["SHA256SUMS.txt"][0]: f"{'0' * 64}  {name}\n".encode()}
    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen(routes))
    with pytest.raises(updater.UpdateError, match="checksum-mismatch"):
        updater.download(rel, (name, rel.assets[name][0], 10))
    rel = release(NAMES[:-1])
    with pytest.raises(updater.UpdateError, match="no-checksums"):
        updater.download(rel, (NAMES[1], rel.assets[NAMES[1]][0], 10))


def test_auto_check_is_off_in_tests_and_https_works():
    assert updater.auto_check_disabled()  # o conftest liga AUTOCADINHO_NO_UPDATE_CHECK
    assert updater.https_ok()


# ------------------------------------------------------------------ instalação no Windows
windows_only = pytest.mark.skipif(sys.platform != "win32", reason="instalação por PowerShell só no Windows")

_SPAWN_CHILD = r"""
import sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from autocadinho import updater
updater.spawn_powershell(Path(sys.argv[2]))
"""


@windows_only
def test_spawn_powershell_survives_windowless_parent(tmp_path):
    """O app empacotado não tem console. Com DETACHED_PROCESS o PowerShell morre antes de rodar o
    script. O script tem de rodar mesmo que o processo que o chamou
    (aqui um pythonw, sem console) termine na hora."""
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.is_file():
        pytest.skip("pythonw.exe não encontrado")
    marker = tmp_path / "rodou.txt"
    script = tmp_path / "teste.ps1"
    script.write_text(f"Start-Sleep -Milliseconds 300\nSet-Content -Path {updater._ps(marker)} -Value 'ok'\n",
                      encoding="utf-8-sig")
    child = tmp_path / "filho.py"
    child.write_text(_SPAWN_CHILD, encoding="utf-8")
    root = str(Path(updater.__file__).resolve().parents[1])
    subprocess.run([str(pythonw), str(child), root, str(script)], timeout=60, check=True)
    deadline = time.time() + 45
    while time.time() < deadline and not marker.exists():
        time.sleep(0.25)
    assert marker.exists(), "o PowerShell lançado pelo atualizador não rodou o script"


def _parse_errors(script: Path) -> str:
    check = ("$e = $null; [System.Management.Automation.Language.Parser]::ParseFile("
             f"{updater._ps(script)}, [ref]$null, [ref]$e) | Out-Null; $e.Count")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", check], capture_output=True, text=True, timeout=60)
    return out.stdout.strip() + out.stderr


@windows_only
def test_install_msi_writes_logged_script(tmp_path, monkeypatch):
    work = tmp_path / "pasta d'Ana"  # apóstrofo no caminho precisa ser escapado
    work.mkdir()
    pkg = work / NAMES[0]
    pkg.write_bytes(b"x")
    spawned = []
    monkeypatch.setattr(updater, "spawn_powershell", spawned.append)
    monkeypatch.setattr(updater.sys, "executable", str(tmp_path / "App d'Ana" / "Autocadinho.exe"))
    updater.install(str(pkg), "msi")
    assert spawned == [work / "atualizar.ps1"]
    body = spawned[0].read_text(encoding="utf-8-sig")
    assert body.startswith("Start-Transcript -Path '") and "d''Ana" in body
    assert "msiexec.exe" in body and "'/passive'" in body and "'/l*v'" in body and "instalar.log" in body
    assert body.index("msiexec.exe") < body.index("Process]::Start(") < body.index("Stop-Transcript")
    assert "$psi.UseShellExecute = $false" in body and "App d''Ana" in body
    assert _parse_errors(spawned[0]) == "0"


@windows_only
def test_install_zip_extracts_and_mirrors(tmp_path, monkeypatch):
    import zipfile
    pkg = tmp_path / NAMES[1]
    with zipfile.ZipFile(pkg, "w") as z:
        z.writestr("Autocadinho/Autocadinho.exe", b"exe")
        z.writestr("Autocadinho/_internal/x.dll", b"dll")
    spawned = []
    monkeypatch.setattr(updater, "spawn_powershell", spawned.append)
    monkeypatch.setattr(updater.sys, "executable", str(tmp_path / "app" / "Autocadinho.exe"))
    updater.install(str(pkg), "zip")
    body = spawned[0].read_text(encoding="utf-8-sig")
    assert "robocopy" in body and "/MIR" in body and str(tmp_path / "app") in body
    assert (tmp_path / "novo" / "Autocadinho" / "Autocadinho.exe").exists()
    assert _parse_errors(spawned[0]) == "0"


def test_install_rejects_bad_zip_and_source(tmp_path, monkeypatch):
    with pytest.raises(updater.UpdateError, match="unsupported"):
        updater.install(str(tmp_path / "x.zip"), "source")
    if sys.platform != "win32":
        return
    import zipfile
    pkg = tmp_path / "ruim.zip"
    with zipfile.ZipFile(pkg, "w") as z:
        z.writestr("../fora.txt", b"x")
    monkeypatch.setattr(updater, "spawn_powershell", lambda s: pytest.fail("não devia instalar"))
    with pytest.raises(updater.UpdateError, match="bad-archive"):
        updater.install(str(pkg), "zip")
    pkg.write_bytes(b"nem zip")
    with pytest.raises(updater.UpdateError, match="bad-archive"):
        updater.install(str(pkg), "zip")


def test_spawn_does_not_use_detached_process(monkeypatch):
    calls = []
    monkeypatch.setattr(updater.subprocess, "Popen", lambda *a, **k: calls.append(k))
    updater.spawn_powershell(Path("x.ps1"))
    flags = calls[0]["creationflags"]
    assert not flags & 0x00000008  # DETACHED_PROCESS derruba o PowerShell sem console
    assert calls[0]["stdin"] is subprocess.DEVNULL
