#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io, os, json, time, uuid, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_URL = "http://localhost:8765"
TEXT = "\u0414\u044F\u043A\u0443\u0454\u043C\u043E \u0437\u0430 \u0434\u0437\u0432\u0456\u043D\u043E\u043A \u0434\u043E \u043A\u043E\u043C\u043F\u0430\u043D\u0456\u0457 \u041E\u043A\u0456-\u0422\u043E\u043A\u0456. \u0411\u0443\u0434\u044C \u043B\u0430\u0441\u043A\u0430, \u0437\u0430\u0447\u0435\u043A\u0430\u0439\u0442\u0435."
VOICE = "Leda"
CONCURRENCY_LEVELS = [1, 5, 10, 20, 50, 70]
TIMEOUT = 120
HEADERS = {'Content-Type': 'application/json; charset=utf-8'}

OUTPUT_DIR = os.path.join("C:\\", "Users", "izeak", "OneDrive", "Work.Oki-toki",
    "TTS для Оки-Токи", "Lira TTS", "stress_test_output")


def http_post(url, data_dict, timeout=TIMEOUT):
    body = json.dumps(data_dict).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers=HEADERS, method='POST')
    resp = urllib.request.urlopen(req, timeout=timeout)
    return resp.read(), resp.headers, resp.status


def start_session(call_id):
    data = {"call_id": call_id}
    body, headers, status = http_post(f"{BASE_URL}/start", data)
    result = json.loads(body.decode('utf-8'))
    return result.get("session_id")


def stop_session(session_id):
    try:
        data = {"session_id": session_id}
        http_post(f"{BASE_URL}/stop", data, timeout=10)
    except Exception:
        pass


def tts_request(session_id, index):
    result = {"index": index, "session_id": session_id, "success": False,
        "error": None, "server_total_ms": None, "server_gen_ms": None,
        "server_parts": None, "server_cps": None, "server_audio_sec": None,
        "wav_data": None, "client_start": None, "client_end": None}
    data = {"session_id": session_id, "text": TEXT, "voice": VOICE}
    t0 = time.perf_counter()
    result["client_start"] = t0
    try:
        wav_data, headers, status = http_post(f"{BASE_URL}/tts", data)
        t1 = time.perf_counter()
        result["client_end"] = t1
        result["success"] = True
        result["wav_data"] = wav_data
        result["server_total_ms"] = float(headers.get("X-TTS-Total-Ms", 0))
        result["server_gen_ms"] = float(headers.get("X-TTS-Gen-Ms", 0))
        result["server_parts"] = headers.get("X-TTS-Parts", "")
        result["server_cps"] = headers.get("X-TTS-CPS", "")
        result["server_audio_sec"] = headers.get("X-TTS-Audio-Sec", "")
    except Exception as e:
        t1 = time.perf_counter()
        result["client_end"] = t1
        result["error"] = str(e)
    return result


def run_concurrency_level(n):
    sep = '=' * 70
    print(f"\n{sep}")
    print(f"  CONCURRENCY LEVEL: {n} requests")
    print(f"{sep}")
    print(f"  Creating {n} sessions...")
    sessions = []
    for i in range(n):
        call_id = f"stress_{n}c_{i}_{uuid.uuid4().hex[:8]}"
        try:
            sid = start_session(call_id)
            sessions.append(sid)
        except Exception as e:
            print(f"  [ERROR] Failed to start session {i}: {e}")
            sessions.append(None)
    valid_sessions = [s for s in sessions if s is not None]
    print(f"  Sessions created: {len(valid_sessions)}/{n}")
    if not valid_sessions:
        print("  [SKIP] No valid sessions, skipping this level.")
        return {"concurrency": n, "sessions_created": 0, "requests_sent": 0,
            "successes": 0, "errors": n, "wall_time_ms": 0, "avg_server_ms": 0,
            "min_server_ms": 0, "max_server_ms": 0, "avg_client_ms": 0,
            "error_details": ["No sessions created"]}
    print(f"  Sending {len(valid_sessions)} TTS requests concurrently...")
    wall_start = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=len(valid_sessions)) as executor:
        futures = {executor.submit(tts_request, sid, i): i
                   for i, sid in enumerate(valid_sessions)}
        for future in as_completed(futures):
            results.append(future.result())
    wall_end = time.perf_counter()
    wall_time_ms = (wall_end - wall_start) * 1000
    successes = [r for r in results if r["success"]]
    errors_list = [r for r in results if not r["success"]]
    server_times = [r["server_total_ms"] for r in successes if r["server_total_ms"]]
    client_times = [(r["client_end"] - r["client_start"]) * 1000 for r in results
                    if r["client_end"] and r["client_start"]]
    avg_server = sum(server_times) / len(server_times) if server_times else 0
    min_server = min(server_times) if server_times else 0
    max_server = max(server_times) if server_times else 0
    avg_client = sum(client_times) / len(client_times) if client_times else 0
    print(f"  Results: {len(successes)} OK, {len(errors_list)} errors, wall={wall_time_ms:.0f}ms")
    if server_times:
        print(f"  Server time: avg={avg_server:.0f}ms, min={min_server:.0f}ms, max={max_server:.0f}ms")
    if errors_list:
        for e in errors_list[:5]:
            idx = e["index"]
            err = e["error"]
            print(f"  [ERROR] req#{idx}: {err}")
        if len(errors_list) > 5:
            print(f"  ... and {len(errors_list) - 5} more errors")
    saved_wav = None
    if successes:
        first = successes[0]
        srv_ms = int(first["server_total_ms"]) if first["server_total_ms"] else 0
        fname = f"stress_{n}concurrent_Chirp3HD_Leda_{srv_ms}ms.wav"
        fpath = os.path.join(OUTPUT_DIR, fname)
        with open(fpath, 'wb') as f:
            f.write(first['wav_data'])
        saved_wav = fname
        wavsize = len(first['wav_data'])
        print(f"  Saved WAV: {fname} ({wavsize} bytes)")
    print(f"  Stopping {len(valid_sessions)} sessions...")
    for sid in valid_sessions:
        stop_session(sid)
    return {"concurrency": n, "sessions_created": len(valid_sessions),
        "requests_sent": len(valid_sessions), "successes": len(successes),
        "errors": len(errors_list), "wall_time_ms": round(wall_time_ms, 1),
        "avg_server_ms": round(avg_server, 1), "min_server_ms": round(min_server, 1),
        "max_server_ms": round(max_server, 1), "avg_client_ms": round(avg_client, 1),
        "saved_wav": saved_wav, "error_details": [e["error"] for e in errors_list]}


def print_summary_table(all_results):
    sep = '=' * 120
    print(f"\n\n{sep}")
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"  STRESS TEST SUMMARY  --  {ts}")
    print(f"  Text: \\\"{TEXT}\\\" ({len(TEXT)} chars)")
    print(f"  Voice: {VOICE}")
    print(sep)
    hdr = ' Concur |  Sent |   OK |  Err |  Wall ms |  Avg Srv |  Min Srv |  Max Srv | Avg Client | WAV file'
    print(hdr)
    print('-' * 120)
    for r in all_results:
        wav_name = r.get("saved_wav", "-") or "-"
        c = r["concurrency"]
        s = r["requests_sent"]
        ok = r["successes"]
        er = r["errors"]
        wt = r["wall_time_ms"]
        avs = r["avg_server_ms"]
        mis = r["min_server_ms"]
        mas = r["max_server_ms"]
        avc = r["avg_client_ms"]
        line = f"{c:>6} | {s:>5} | {ok:>4} | {er:>4} | {wt:>8.0f} | {avs:>8.0f} | {mis:>8.0f} | {mas:>8.0f} | {avc:>10.0f} | {wav_name}"
        print(line)
    print(sep)


def main():
    print('=' * 70)
    print('  TTS Stress Test - Concurrent Requests')
    print(f"  Server: {BASE_URL}")
    print(f"  Text: \\\"{TEXT}\\\"")
    print(f"  Voice: {VOICE}")
    print(f"  Concurrency levels: {CONCURRENCY_LEVELS}")
    print(f"  Output: {OUTPUT_DIR}")
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"  Started: {ts}")
    print('=' * 70)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print()
    print('Health check...')
    try:
        req = urllib.request.Request(f'{BASE_URL}/health', method='GET')
        resp = urllib.request.urlopen(req, timeout=5)
        print(f"  Server is up (status={resp.status})")
    except Exception as e:
        print(f"  [WARNING] Health check failed: {e}")
        print('  Trying /start as alternative check...')
        try:
            sid = start_session('health_check_probe')
            stop_session(sid)
            print('  Server responds to /start, proceeding.')
        except Exception as e2:
            print(f"  [FATAL] Server not reachable: {e2}")
            sys.exit(1)
    all_results = []
    for n in CONCURRENCY_LEVELS:
        result = run_concurrency_level(n)
        all_results.append(result)
        if n < CONCURRENCY_LEVELS[-1]:
            time.sleep(2)
    print_summary_table(all_results)
    results_path = os.path.join(OUTPUT_DIR, 'results.json')
    save_results = {"test_date": datetime.now().isoformat(), "server": BASE_URL,
        "text": TEXT, "text_chars": len(TEXT), "voice": VOICE,
        "concurrency_levels": CONCURRENCY_LEVELS, "results": all_results}
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(save_results, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {results_path}")
    print('Done.')


if __name__ == "__main__":
    main()
