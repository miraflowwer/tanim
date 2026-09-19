FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/srv/tanim:/srv/tanim/backend

WORKDIR /srv/tanim

COPY backend/requirements.txt /srv/tanim/backend/requirements.txt
RUN python -m pip install --no-cache-dir -r /srv/tanim/backend/requirements.txt

COPY backend /srv/tanim/backend
COPY scripts /srv/tanim/scripts

RUN useradd --create-home --uid 10001 tanim
USER 10001

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]