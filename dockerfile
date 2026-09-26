FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
# setuptools ships with the base image (not our requirements) and the 3.11-slim
# copy lags a security fix (PYSEC-2026-3447, fixed in 83.0.0) — lift it first.
RUN pip install --no-cache-dir -U "setuptools>=83" && \
    pip install --no-cache-dir -r requirements.txt

# Copy everything, including the templates folder
COPY . .

# Ensure the templates folder exists in the container (Safety Check)
RUN ls -R /app/templates

EXPOSE 5000

# --preload: import the app (and build the TimezoneFinder index) once in the
#   master, shared copy-on-write across workers instead of N full copies.
# --threads: serve connections from a thread pool so idle/slow keep-alive probes
#   from the Tailscale-serve proxy don't block the sync workers (the "no URI
#   read" WORKER TIMEOUTs that were recycling workers).
# --timeout 60: absorb slow upstream NWS/Open-Meteo calls (incl. retries).
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "60", "--graceful-timeout", "30", "--preload", "app:app"]