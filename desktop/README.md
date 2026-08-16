# デスクトップ版のビルド / Desktop build

Streamlit アプリを **単体実行ファイル**（Windows: `.exe` / macOS: `.app`）に固めます。
利用者に Python は不要です。中身は「ローカルで Streamlit を起動し、デスクトップ窓
（pywebview）で表示」する構成です。

## 仕組み

- `run_desktop.py` — ローカルで Streamlit を起動し、pywebview のウィンドウで開くランチャ。
- `eds_sim_app.spec` — PyInstaller 設定。Streamlit / xraylib のデータ・メタデータを収集。

## ビルド手順

**重要: ビルドは配布したい OS 上で行います（クロスコンパイル不可）。**
Windows の `.exe` は Windows で、macOS の `.app` は Mac でビルドしてください。

### Windows

```bat
REM リポジトリのルートで
desktop\build_windows.bat
```
→ `dist\EDS-Simulator\EDS-Simulator.exe`（**フォルダごと**配布）

### macOS

```bash
bash desktop/build_macos.sh
```
→ `dist/EDS-Simulator.app`

## 既知の注意点

- **サイズ**: numpy/scipy/streamlit/plotly/pandas/xraylib を含むため、200〜400 MB 程度に
  なります（科学計算系バンドルでは普通）。
- **未署名の警告**: コード署名をしていない場合、初回起動時に
  Windows は SmartScreen（「詳細情報→実行」）、macOS は Gatekeeper（右クリック→開く）の
  警告が出ます。広く配るなら署名（有償）を検討してください。
- **Windows の onefile**: 起動が遅く一部環境で不安定なため、本設定は onedir（フォルダ）
  出力です。`.exe` 単体では動かず、`EDS-Simulator` フォルダごと配布します。
- **xraylib**: `.spec` の `collect_all("xraylib")` でデータを取り込みます。もし起動時に
  xraylib のデータが見つからないエラーが出たら、`.spec` に `collect_data("xraylib")` の
  明示追加が必要な場合があります。

## より簡単な代替

`streamlit-desktop-app`（PyPI）は PyInstaller + pywebview を自動化するヘルパです。
手軽ですが、xraylib のデータ同梱は上記 `.spec` の方が確実です。
