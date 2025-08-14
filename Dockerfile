FROM python:3.12-slim

# Ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"

# Dependências do sistema mínimas (ex: curl p/ healthcheck opcional)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl tini\
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho no container
WORKDIR /app

# Copia requirements e instala
COPY requirements.txt .

# Instala as dependências
RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código
COPY . .

# Cria usuário não-root e ajusta permissões
RUN useradd -u 10001 -ms /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expor porta interna
EXPOSE 8000

# Healthcheck simples (opcional se usar no compose)
# HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
#   CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

# Use tini como init (PID 1) para repasse de sinais/graceful shutdown
ENTRYPOINT ["/usr/bin/tini", "--"]

# Execução do servidor ASGI
# --proxy-headers para respeitar X-Forwarded-* vindo do Traefik
# --forwarded-allow-ips="*" se confia apenas no Traefik na mesma rede
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]