FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    DOUBAO_ASR_HOST=0.0.0.0 \
    DOUBAO_ASR_PORT=8000

RUN apt-get update \
    && apt-get install -y --no-install-recommends libopus0 curl git g++ \
    && rm -rf /var/lib/apt/lists/*

# 预安装所有 Python 依赖到系统环境
RUN uv pip install --system \
    fastapi>=0.109.0 \
    uvicorn[standard]>=0.27.0 \
    python-multipart>=0.0.6 \
    pydantic>=2.5.0 \
    pydantic-settings>=2.1.0 \
    cryptography \
    git+https://github.com/starccy/doubaoime-asr

WORKDIR /app
COPY doubao_asr_api.py ./

EXPOSE 8000

CMD ["python", "doubao_asr_api.py"] 
