# EDS スペクトル・シミュレータ — pip ベース
# xraylib は PyPI に各 OS・Python 版の wheel があるため conda 不要。軽量な
# python:slim + pip で構成し、ビルドと起動を高速化する。
FROM python:3.12-slim

LABEL maintainer="EDS Simulator" \
      description="EDS spectrum simulator (Streamlit + xraylib)"

WORKDIR /app

# 依存関係を先にインストールしてレイヤキャッシュを効かせる
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# アプリ本体
COPY . /app

EXPOSE 8501

# ヘルスチェック（Streamlit の /_stcore/health を Python から確認。curl 非依存）
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health').getcode()==200 else 1)" || exit 1

# Streamlit 起動（0.0.0.0 バインドでコンテナ外から到達可能に）
ENTRYPOINT ["streamlit", "run", "app.py", \
            "--server.address=0.0.0.0", "--server.port=8501", \
            "--server.headless=true"]
