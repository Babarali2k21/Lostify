FROM python:3.12-slim

WORKDIR /app

COPY notification-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY shared ./shared
COPY notification-service/app ./app

ENV PYTHONPATH=/app

EXPOSE 8003

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
