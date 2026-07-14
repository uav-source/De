FROM python:3.11-slim

ENV MPLBACKEND=Agg \
    PYTHONHASHSEED=0 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /workspace
COPY requirements-lock-py311.txt .
RUN python -m pip install --no-cache-dir -r requirements-lock-py311.txt
COPY . .
RUN python -m pytest -q -p no:cacheprovider

CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
