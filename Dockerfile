FROM python:3.12-slim

# Ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"

# Dependências do sistema mínimas (ex: curl p/ healthcheck opcional)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl tini tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configurações de sistema para melhor performance de rede/websockets
RUN echo 'net.core.somaxconn = 1024' >> /etc/sysctl.conf && \
    echo 'net.ipv4.tcp_keepalive_time = 600' >> /etc/sysctl.conf && \
    echo 'net.ipv4.tcp_keepalive_intvl = 60' >> /etc/sysctl.conf && \
    echo 'net.ipv4.tcp_keepalive_probes = 3' >> /etc/sysctl.conf && \
    echo 'fs.file-max = 65536' >> /etc/sysctl.conf

# Define o diretório de trabalho no container
WORKDIR /app

# Copia requirements e instala
COPY requirements.txt .

# Instala as dependências
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copia o código
COPY . .

# Cria usuário não-root e ajusta permissões
RUN useradd -u 10001 -ms /bin/bash appuser \
    && chown -R appuser:appuser /app

# Configurar limits para o usuário
RUN echo 'appuser soft nofile 65536' >> /etc/security/limits.conf && \
    echo 'appuser hard nofile 65536' >> /etc/security/limits.conf
    
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
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--lifespan", "on"]