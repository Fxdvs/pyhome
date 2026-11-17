# The pyhome server in a container. Run it with docker compose, see docs/docker.md.
FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# the server and what it shares with the clients; .dockerignore keeps configs, databases and keys out
COPY shared/ shared/
COPY server/ server/

# never root: uid 1000 is the first user on a Raspberry Pi and on most Linux machines,
# so a mounted folder that user owns is writable as it is
RUN useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin pyhome \
 && mkdir /data \
 && chown pyhome /data
USER pyhome

# everything the server writes lives in its data folder, mounted at /data
ENV PYHOME_DATA=/data \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
VOLUME /data

# clients, the dashboard, Find servers
EXPOSE 50000 50001 50002/udp

WORKDIR /app/server
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["python", "healthcheck.py"]
CMD ["python", "app.py"]
