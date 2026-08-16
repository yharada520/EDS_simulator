"""デスクトップ版ランチャ。

Streamlit は SIGTERM ハンドラを主スレッドで設定するため、サブスレッドでは
起動できない（signal only works in main thread）。そこで Streamlit を
**子プロセス**（その主スレッド）で起動し、ランチャの主スレッドで pywebview の
ウィンドウを表示する。pywebview が使えない場合は既定ブラウザにフォールバック。

PyInstaller で単体実行ファイル（Windows: .exe / macOS: .app）に固める前提。
"""

from __future__ import annotations

import multiprocessing
import os
import socket
import subprocess
import sys
import time

APP_NAME = "EDS Spectrum Simulator"
PREFERRED_PORT = 8501
WORKER_FLAG = "--run-streamlit-worker"


def _resource(rel: str) -> str:
    """バンドル後も有効なリソースパスを返す（PyInstaller の _MEIPASS 対応）。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def _pick_port(preferred: int = PREFERRED_PORT) -> int:
    """空きポートを選ぶ（優先ポートが埋まっていれば任意の空きポート）。"""
    for port in (preferred, 0):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", port))
            chosen = s.getsockname()[1]
            s.close()
            return chosen
        except OSError:
            continue
    return preferred


def _run_streamlit_worker(port: int) -> None:
    """子プロセスの主スレッドで Streamlit を起動（ブロッキング）。"""
    from streamlit import config as st_config
    from streamlit.web import bootstrap

    st_config.set_option("server.address", "127.0.0.1")
    st_config.set_option("server.port", port)
    st_config.set_option("server.headless", True)
    st_config.set_option("server.enableXsrfProtection", False)
    st_config.set_option("browser.gatherUsageStats", False)
    st_config.set_option("global.developmentMode", False)
    # bootstrap.run(main_script_path, is_hello, args, flag_options)
    bootstrap.run(_resource("app.py"), False, [], {})


def _spawn_worker(port: int) -> subprocess.Popen:
    """自分自身（frozen なら .exe / 開発時は python）を worker として起動。"""
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, WORKER_FLAG, str(port)]
    else:
        cmd = [sys.executable, os.path.abspath(__file__), WORKER_FLAG, str(port)]
    return subprocess.Popen(cmd)


def _wait_until_up(port: int, timeout: float = 120.0) -> bool:
    """Streamlit のヘルスチェックが 200 を返すまで待つ。"""
    import urllib.request

    url = f"http://127.0.0.1:{port}/_stcore/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if urllib.request.urlopen(url, timeout=2).getcode() == 200:
                return True
        except Exception:
            time.sleep(0.4)
    return False


def main() -> None:
    multiprocessing.freeze_support()  # Windows の spawn ループ防止

    # 子プロセス（worker）モード: Streamlit を主スレッドで起動して終了
    if WORKER_FLAG in sys.argv:
        port = int(sys.argv[sys.argv.index(WORKER_FLAG) + 1])
        _run_streamlit_worker(port)
        return

    # ランチャモード: Streamlit を別プロセスで起動し、ウィンドウで表示
    port = _pick_port()
    proc = _spawn_worker(port)
    _wait_until_up(port)
    url = f"http://127.0.0.1:{port}"

    try:
        import webview  # pywebview

        webview.create_window(APP_NAME, url, width=1400, height=900)
        webview.start()
    except Exception:
        import webbrowser

        webbrowser.open(url)
        try:
            while proc.poll() is None:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    finally:
        if proc.poll() is None:
            proc.terminate()


if __name__ == "__main__":
    main()
