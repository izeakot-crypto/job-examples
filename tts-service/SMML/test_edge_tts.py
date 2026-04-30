import sys, io, os, time, asyncio, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import edge_tts

SENTENCES = {
    "UA": "Дякуємо за дзвінок до компанії Окі-Токі. На жаль, всі оператори зараз зайняті. Будь ласка, залишайтесь на лінії, вам відповідять найближчим часом.",
    "EN": "Thank you for calling Oki-Toki company. Unfortunately, all operators are currently busy. Please stay on the line, you will be answered as soon as possible.",
    "RU": "Благодарим за звонок в компанию Оки-Токи. К сожалению, все операторы сейчас заняты. Пожалуйста, оставайтесь на линии, вам ответят в ближайшее время.",
    "PL": "Dziękujemy za telefon do firmy Oki-Toki. Niestety wszyscy operatorzy są obecnie zajęci. Prosimy pozostać na linii, odpowiemy najszybciej jak to możliwe.",
    "ES": "Gracias por llamar a la empresa Oki-Toki. Lamentablemente todos los operadores están ocupados. Por favor permanezca en la línea, le atenderemos lo antes posible.",
    "TR": "Oki-Toki şirketini aradığınız için teşekkür ederiz. Maalesef tüm operatörler şu anda meşgul. Lütfen hatta kalın, en kısa sürede size yanıt verilecektir.",
}

EDGE_VOICES = {
    "UA": "uk-UA-PolinaNeural",
    "EN": "en-US-JennyNeural",
    "RU": "ru-RU-SvetlanaNeural",
    "PL": "pl-PL-AgnieszkaNeural",
    "ES": "es-ES-ElviraNeural",
    "TR": "tr-TR-EmelNeural",
}

ATTEMPTS = 3

async def test_edge():
    results = {}
    for lang, text in SENTENCES.items():
        voice = EDGE_VOICES[lang]
        times = []
        for _ in range(ATTEMPTS):
            try:
                t0 = time.time()
                communicate = edge_tts.Communicate(text, voice)
                audio_data = b""
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_data += chunk["data"]
                elapsed = time.time() - t0
                if audio_data:
                    times.append(elapsed)
            except Exception as e:
                print(f"  {lang}: помилка - {type(e).__name__}")
        if times:
            avg = round(sum(times) / len(times), 2)
            cps = int(len(text) / avg)
            results[lang] = {"avg": avg, "cps": cps}
            print(f"  Edge TTS {lang}: {avg}с / {cps} CPS (спроби: {', '.join(f'{t:.2f}' for t in times)})")
    return results

print("EDGE TTS — мультимовний тест")
print("="*50)
results = asyncio.run(test_edge())

# Зберегти
with open(os.path.join(os.path.dirname(__file__), "edge_results.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nЗбережено в edge_results.json")
