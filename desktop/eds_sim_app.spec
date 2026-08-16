# PyInstaller spec — EDS Spectrum Simulator デスクトップ版
#
# リポジトリのルートから実行する:
#   pyinstaller desktop/eds_sim_app.spec
#
# Streamlit / xraylib は動的にデータ・メタデータを読むため collect_all と
# copy_metadata でまとめて取り込む。ビルドは各 OS 上で個別に行う
# （クロスコンパイル不可。Windows→.exe, macOS→.app）。

import os

from PyInstaller.utils.hooks import collect_all, copy_metadata

# パスは spec の場所（desktop/）基準で解決されるため、リポジトリのルートを求める
ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = []
binaries = []
hiddenimports = []

# 動的読み込みするパッケージを丸ごと収集
for pkg in ("streamlit", "xraylib", "plotly", "altair", "pandas",
            "scipy", "numpy", "pyarrow"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# Streamlit はバージョン検出に importlib.metadata を使うためメタデータが必要
for pkg in ("streamlit", "numpy", "scipy", "pandas", "plotly", "xraylib"):
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass

# アプリ本体を同梱（_MEIPASS 直下に配置され import 可能になる）
datas += [
    (os.path.join(ROOT, "app.py"), "."),
    (os.path.join(ROOT, "i18n.py"), "."),
    (os.path.join(ROOT, "eds_sim"), "eds_sim"),
    (os.path.join(ROOT, ".streamlit"), ".streamlit"),
]

block_cipher = None

a = Analysis(
    [os.path.join(SPECPATH, "run_desktop.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EDS-Simulator",
    debug=False,
    strip=False,
    upx=False,
    console=False,  # ウィンドウアプリ（コンソール非表示）
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="EDS-Simulator",
)

# macOS の .app バンドル（macOS でビルドしたときのみ生成される）
app = BUNDLE(
    coll,
    name="EDS-Simulator.app",
    icon=None,
    bundle_identifier="com.yharada520.edssimulator",
)
