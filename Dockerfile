FROM python:3.11-slim-bookworm

RUN groupadd -r divinemesh && \
    useradd -r -g divinemesh -m -d /home/divinemesh -s /bin/bash divinemesh

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 libopenblas0 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/data /app/logs /home/divinemesh/.divinemesh
COPY client/ /app/client/

RUN chown -R divinemesh:divinemesh /app /home/divinemesh && \
    chmod 700 /app/data /home/divinemesh/.divinemesh && \
    chmod +x /app/client/entrypoint.sh

USER divinemesh
EXPOSE 7474
CMD ["/bin/bash", "/app/client/entrypoint.sh"]
