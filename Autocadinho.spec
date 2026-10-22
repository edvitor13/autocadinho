# -*- mode: python ; coding: utf-8 -*-
# Receita do PyInstaller para o Autocadinho (Windows).
#
# Gera uma pasta única (onedir), que abre mais rápido que um .exe só e é a base do instalador .msi:
#     dist/Autocadinho/Autocadinho.exe     (janela, sem console)
#     dist/Autocadinho/_internal/          (Python, Qt e as traduções)
#
# Uso:  python -m PyInstaller --noconfirm --clean Autocadinho.spec
# (o build.bat faz isso e monta o .zip e o .msi; veja docs/DESENVOLVIMENTO.md)

import os
import re

ROOT = SPECPATH  # noqa: F821  (variável injetada pelo PyInstaller)
NAME = "Autocadinho"

# Versão lida do código (sem importar o pacote), usada nos metadados do executável.
with open(os.path.join(ROOT, "autocadinho", "__init__.py"), encoding="utf-8") as _f:
    VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', _f.read()).group(1)


def version_info():
    """Metadados do .exe (Propriedades > Detalhes)."""
    from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct, StringTable,
                                                     VarFileInfo, VarStruct, VSVersionInfo)
    nums = tuple(int(n) for n in re.findall(r"\d+", VERSION)[:3])
    nums = nums + (0,) * (4 - len(nums))
    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=nums, prodvers=nums, mask=0x3F, flags=0x0, OS=0x40004, fileType=0x1,
                          subtype=0x0, date=(0, 0)),
        kids=[
            StringFileInfo([StringTable("041604B0", [  # pt-BR, Unicode
                StringStruct("CompanyName", NAME),
                StringStruct("FileDescription", "Autocadinho - desenhos simples de obra"),
                StringStruct("FileVersion", VERSION),
                StringStruct("InternalName", NAME),
                StringStruct("LegalCopyright", "Licença MIT. Código aberto."),
                StringStruct("OriginalFilename", f"{NAME}.exe"),
                StringStruct("ProductName", NAME),
                StringStruct("ProductVersion", VERSION),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x0416, 1200])]),
        ],
    )


# O catálogo de tradução é lido com Path(__file__).parent / "locales".
DATAS = [(os.path.join(ROOT, "autocadinho", "locales"), os.path.join("autocadinho", "locales"))]

# Módulos do Qt que o app não usa: ficam de fora mesmo que outra biblioteca tente puxá-los.
QT_UNUSED = ["Qt3DAnimation", "Qt3DCore", "Qt3DExtras", "Qt3DInput", "Qt3DLogic", "Qt3DRender", "QtBluetooth",
             "QtCharts", "QtDataVisualization", "QtGraphs", "QtHttpServer", "QtLocation", "QtMultimedia",
             "QtMultimediaWidgets", "QtNetwork", "QtNetworkAuth", "QtNfc", "QtOpenGL", "QtOpenGLWidgets", "QtPdf",
             "QtPdfWidgets", "QtPositioning", "QtQml", "QtQuick", "QtQuick3D", "QtQuickControls2", "QtQuickWidgets",
             "QtRemoteObjects", "QtScxml", "QtSensors", "QtSerialBus", "QtSerialPort", "QtSpatialAudio", "QtSql",
             "QtStateMachine", "QtSvg", "QtSvgWidgets", "QtTest", "QtTextToSpeech", "QtUiTools", "QtWebChannel",
             "QtWebEngineCore", "QtWebEngineQuick", "QtWebEngineWidgets", "QtWebSockets", "QtWebView", "QtXml"]

a = Analysis(  # noqa: F821
    [os.path.join(ROOT, "Autocadinho.pyw")],
    pathex=[ROOT],
    binaries=[],
    datas=DATAS,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # O ssl (com o OpenSSL) fica: o atualizador consulta o GitHub e baixa as versões novas por HTTPS.
    excludes=["tkinter", "unittest", "pydoc", "pytest",
              *(f"PySide6.{m}" for m in QT_UNUSED)],
    noarchive=False,
    optimize=0,
)

# Plugins do Qt sem uso aqui. O teclado virtual, o PDF como imagem, o SVG e o toque por rede puxariam
# Quick, Qml, Pdf, Svg e Network (uns 25 MB). Sobram a janela do Windows, os formatos de imagem e o estilo.
QT_PLUGINS_UNUSED = ("/platforminputcontexts/", "/generic/", "/iconengines/", "/imageformats/qpdf",
                     "/imageformats/qsvg", "/platforms/qdirect2d", "/platforms/qminimal", "/platforms/qoffscreen")
# Só Qt6Core, Qt6Gui, Qt6Widgets e Qt6PrintSupport são usados de fato (conferido com o pefile).
QT_DLLS_UNUSED = ("qt6network", "qt6opengl", "qt6pdf", "qt6qml", "qt6quick", "qt6svg", "qt6virtualkeyboard")


def _keep(dest):
    d = "/" + dest.replace("\\", "/").lower()
    name = d.rsplit("/", 1)[-1]
    # Traduções do próprio Qt: só a do português (o inglês é o texto original do Qt).
    if "/translations/" in d and d.endswith(".qm"):
        return name == "qtbase_pt_br.qm"
    if "/plugins/" in d and any(p in d for p in QT_PLUGINS_UNUSED):
        return False
    # OpenGL por software (20 MB): o app desenha com o QPainter e não usa OpenGL.
    return not (name.startswith(QT_DLLS_UNUSED) or name == "opengl32sw.dll")


a.datas = [x for x in a.datas if _keep(x[0])]
a.binaries = [x for x in a.binaries if _keep(x[0])]

pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=os.path.join(ROOT, "assets", "logo.ico"),
    version=version_info(),
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=NAME,
)
