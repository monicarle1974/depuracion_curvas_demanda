FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src \
    MPLBACKEND=Agg \
    OMP_NUM_THREADS=1

WORKDIR /app

# Dependencias (capa cacheada): se leen de pyproject.toml, única fuente de verdad.
COPY pyproject.toml .
RUN python -c "import tomllib; p = tomllib.load(open('pyproject.toml', 'rb'))['project']; \
print('\n'.join(p['dependencies'] + p['optional-dependencies']['test']))" > /tmp/requisitos.txt \
 && pip install -r /tmp/requisitos.txt

# Código y pruebas (en desarrollo se sobrescriben con el volumen de docker-compose).
COPY . .

CMD ["pytest"]
