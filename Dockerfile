FROM python:3.11-slim

ENV MPLBACKEND=Agg \
    PYTHONHASHSEED=0 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /workspace
COPY requirements-lock-py311.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir -r requirements-lock-py311.txt
COPY . .
RUN git init \
    && git add . \
    && git -c user.name=container -c user.email=container@invalid commit -m snapshot \
    && python -c "import platform, pytest; platform.platform(); raise SystemExit(pytest.main(['-q', '-p', 'no:cacheprovider']))"

CMD ["python", "-c", "import platform, pytest; platform.platform(); raise SystemExit(pytest.main(['-q', '-p', 'no:cacheprovider']))"]
