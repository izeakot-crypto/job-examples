import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import whisper
import torch

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Пристрій: {device}")
if device == "cuda":
    print(f"GPU: {torch.cuda.get_device_name(0)}")

# Тестуємо на згенерованому аудіо
audio_file = "test_edge_1.mp3"

models_to_test = ["tiny", "base", "small"]

for model_name in models_to_test:
    print(f"\n--- Модель: {model_name} ---")

    start_load = time.time()
    model = whisper.load_model(model_name, device=device)
    load_time = time.time() - start_load
    print(f"Завантаження моделі: {load_time:.2f} сек")

    for i in range(3):
        start = time.time()
        result = model.transcribe(audio_file, language="uk")
        elapsed = time.time() - start
        text = result["text"].strip()
        print(f"Тест {i+1}: {elapsed:.2f} сек | Текст: {text}")

    del model
    if device == "cuda":
        torch.cuda.empty_cache()

print("\nГотово")
