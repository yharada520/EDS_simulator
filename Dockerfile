# EDS スペクトル・シミュレータ — Miniconda ベース
# xraylib を conda-forge から確実に導入するため conda を採用する。
FROM continuumio/miniconda3:latest

LABEL maintainer="EDS Simulator" \
      description="EDS spectrum simulator (Streamlit + xraylib)"

WORKDIR /app

# HEALTHCHECK 用に curl を導入
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 依存関係を先にコピーしてレイヤキャッシュを効かせる
COPY environment.yml /app/environment.yml
RUN conda env create -f environment.yml && conda clean -afy

# 以降のコマンドを eds-sim 環境で実行
SHELL ["conda", "run", "--no-capture-output", "-n", "eds-sim", "/bin/bash", "-c"]

# アプリ本体
COPY . /app

EXPOSE 8501

# ヘルスチェック（Streamlit の /_stcore/health を利用）
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8501/_stcore/health || exit 1

# Streamlit 起動（0.0.0.0 バインドでコンテナ外から到達可能に）
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "eds-sim", \
            "streamlit", "run", "app.py", \
            "--server.address=0.0.0.0", "--server.port=8501", \
            "--server.headless=true"]
