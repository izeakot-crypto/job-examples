FROM python:3.11-slim

WORKDIR /app

# Устанавливаем nginx и supervisor
RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx supervisor && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Копируем requirements всех сервисов и устанавливаем зависимости
COPY services/translation-checker/requirements.txt /app/requirements/translation-checker.txt
COPY services/tts-google-chirp3/requirements.txt /app/requirements/tts-google-chirp3.txt
COPY services/lira-assistants-api/requirements.txt /app/requirements/lira-assistants-api.txt
COPY services/quality-check/requirements.txt /app/requirements/quality-check.txt
COPY services/competitor-monitor/requirements.txt /app/requirements/competitor-monitor.txt
COPY services/transcribe/requirements.txt /app/requirements/transcribe.txt
COPY services/gemini-translate/requirements.txt /app/requirements/gemini-translate.txt
# Будущие сервисы:
# COPY services/original-checker/requirements.txt /app/requirements/original-checker.txt
RUN pip install --no-cache-dir \
    -r /app/requirements/translation-checker.txt \
    -r /app/requirements/tts-google-chirp3.txt \
    -r /app/requirements/lira-assistants-api.txt \
    -r /app/requirements/quality-check.txt \
    -r /app/requirements/competitor-monitor.txt \
    -r /app/requirements/transcribe.txt \
    -r /app/requirements/gemini-translate.txt

# Копируем shared-модули
COPY shared/ /app/shared/

# Копируем все сервисы
COPY services/ /app/services/

# Копируем конфигурации
COPY nginx/nginx.conf /etc/nginx/sites-enabled/default
COPY nginx/docs.html /usr/share/nginx/html/docs.html
COPY supervisord.conf /etc/supervisor/conf.d/py-services.conf

# Создаём директорию для логов
RUN mkdir -p /var/log/py-services

ENV PYTHONPATH=/app

# Nginx на 80 (SSL теперь в gateway-контейнере)
EXPOSE 80

# Запускаем supervisor, который поднимает nginx + все сервисы
CMD ["supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
