#!/bin/bash
# ai_translation_monitor.sh
# Usage: ./ai_translation_monitor.sh /path/to/file.json

FILE="$1"
API_URL="https://py-services.oki-toki.net/api/translation-checker/check"
API_TOKEN="tm_i3RHCK7frKXXtvR8ietmVl0JHdxCv_GfkOeLG8l4kwI"

# Лог в той же папке где файл
LOG_DIR=$(dirname "$FILE")
LOG_FILE="$LOG_DIR/translation_checker.log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Проверяем что файл передан
if [ -z "$FILE" ]; then
  log "ERROR: Не указан файл. Использование: $0 /path/to/file.json"
  exit 0
fi

# Проверяем что файл существует
if [ ! -f "$FILE" ]; then
  log "ERROR: Файл не найден: $FILE"
  exit 0
fi

# Оборачиваем массив в {"items": [...]}
PAYLOAD=$(jq '{"items": .}' "$FILE" 2>/dev/null)

if [ $? -ne 0 ]; then
  log "ERROR: Не удалось распарсить JSON файл: $FILE"
  exit 0
fi

ITEMS_COUNT=$(echo "$PAYLOAD" | jq '.items | length')
log "INFO: Отправляем файл: $FILE (элементов: $ITEMS_COUNT)"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -1)

if [ "$HTTP_CODE" != "200" ]; then
  log "ERROR: Сервер вернул код $HTTP_CODE для файла: $FILE. Ответ: $BODY"
  exit 0
fi

log "OK: Файл обработан успешно: $FILE. Ответ: $BODY"
exit 0
