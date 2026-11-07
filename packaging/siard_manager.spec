# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller recipe for SIARD Workflow Manager (Windows one-folder bundle).

python -m PyInstaller --noconfirm packaging/siard_manager.spec
"""
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(ROOT))
from version import VERSION  # noqa: E402

datas = [
    (str(ROOT / "siard_workflow" / "sources"), "siard_workflow/sources"),
    (str(ROOT / "siard_workflow" / "models"), "siard_workflow/models"),
    (str(ROOT / "config_example.json"), "."),
]
binaries = []
hiddenimports = (collect_submodules("siard_workflow") + collect_submodules("gui")
                 + ["app_paths", "dependencies", "settings", "version",
                    "disk_selector", "selftest"])

for pkg in ("customtkinter", "tkinterdnd2", "reportlab", "pymupdf", "fitz", "lxml",
            "olefile", "msoffcrypto", "docx", "mailmerge", "psutil",
            "py7zr", "rarfile", "magic"):
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue
    datas += [x for x in d if "isoschematron" not in x[0]]
    binaries += b
    hiddenimports += [m for m in h if "isoschematron" not in m]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tests", "testsiard", "weasyprint", "PyInstaller", "pytest",
              "lxml.isoschematron", "matplotlib", "IPython", "gui.app_backup",
              "siard_workflow.examples"],
    noarchive=False,
)
pyz = PYZ(a.pure)

_v = tuple(int(x) for x in (VERSION.split(".") + ["0"] * 4)[:4])
try:
    from PyInstaller.utils.win32.versioninfo import (
        VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct,
        VarFileInfo, VarStruct)
    version_info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=_v, prodvers=_v),
        kids=[StringFileInfo([StringTable("041404B0", [
            StringStruct("CompanyName", "KDRS"),
            StringStruct("FileDescription", "SIARD Workflow Manager"),
            StringStruct("FileVersion", VERSION),
            StringStruct("ProductName", "SIARD Workflow Manager"),
            StringStruct("ProductVersion", VERSION),
            StringStruct("OriginalFilename", "SIARDManager.exe")])]),
            VarFileInfo([VarStruct("Translation", [0x0414, 1200])])])
except Exception:
    version_info = None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SIARDManager",
    console=False,
    upx=False,
    version=version_info,
)
coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="SIARDManager")
