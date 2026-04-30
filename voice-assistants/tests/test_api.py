"""
Comprehensive integration tests for LIRA Voice Assistants API.
Tests all endpoints, all providers, error handling, edge cases.
Validates spec compliance: error format, field names, HTTP codes.
"""

import httpx
import asyncio
import sys

BASE = "http://127.0.0.1:8000"
PASSED = 0
FAILED = 0
RESULTS = []


def report(name: str, ok: bool, detail: str = ""):
    global PASSED, FAILED
    status = "PASS" if ok else "FAIL"
    if ok:
        PASSED += 1
    else:
        FAILED += 1
    line = f"[{status}] {name}"
    if detail and not ok:
        line += f" — {detail}"
    print(line)
    RESULTS.append({"test": name, "status": status, "detail": detail})


async def run_tests():
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as c:

        # ═══════════════════════════════════════════════════
        # 1. HEALTH CHECK
        # ═══════════════════════════════════════════════════
        r = await c.get("/health")
        report("GET /health returns 200", r.status_code == 200)
        report("GET /health body", r.json().get("status") == "ok")

        # ═══════════════════════════════════════════════════
        # 2. CREATE — all providers
        # ═══════════════════════════════════════════════════
        sessions = {}

        # OpenAI (chat mode)
        r = await c.post("/assistant/create", json={
            "session_id": "call-001",
            "comp_id": 1,
            "contact_id": 100,
            "provider": "openai",
            "config": {
                "api_key": "sk-test-key",
                "model": "gpt-4o",
                "system_prompt": "You are a helpful assistant.",
                "temperature": 0.5,
                "max_tokens": 500,
            },
        })
        report("CREATE openai — status 200", r.status_code == 200)
        data = r.json()
        report("CREATE openai — has assistant_session_id", "assistant_session_id" in data)
        sessions["openai"] = data.get("assistant_session_id")

        # OpenAI (assistants mode) — fails because fake key can't create thread
        r = await c.post("/assistant/create", json={
            "session_id": "call-002",
            "comp_id": 1,
            "contact_id": 101,
            "provider": "openai",
            "config": {
                "api_key": "sk-test-key",
                "assistant_id": "asst_abc123",
            },
        })
        report("CREATE openai assistants — returns error with bad key", r.status_code == 500)
        err = r.json()
        report("CREATE openai assistants — error format matches spec",
               "error" in err and "reason" in err.get("error", {}))

        # Claude
        r = await c.post("/assistant/create", json={
            "session_id": "call-003",
            "comp_id": 2,
            "contact_id": 200,
            "provider": "claude",
            "config": {
                "api_key": "sk-ant-test",
                "model": "claude-sonnet-4-20250514",
                "system_prompt": "You are a call center operator.",
            },
        })
        report("CREATE claude — status 200", r.status_code == 200)
        data = r.json()
        report("CREATE claude — has assistant_session_id", "assistant_session_id" in data)
        sessions["claude"] = data.get("assistant_session_id")

        # n8n
        r = await c.post("/assistant/create", json={
            "session_id": "call-004",
            "comp_id": 3,
            "contact_id": 300,
            "provider": "n8n",
            "config": {
                "url": "https://n8n.example.com/webhook/test",
                "api_key": "n8n-token",
                "system_prompt": "Agent workflow",
            },
            "parameters": {
                "response_path": "data.text",
                "timeout": 60,
            },
        })
        report("CREATE n8n — status 200", r.status_code == 200)
        data = r.json()
        report("CREATE n8n — has assistant_session_id", "assistant_session_id" in data)
        sessions["n8n"] = data.get("assistant_session_id")

        # ═══════════════════════════════════════════════════
        # 3. CREATE — error cases
        # ═══════════════════════════════════════════════════

        # Unknown provider
        r = await c.post("/assistant/create", json={
            "session_id": "err-1",
            "comp_id": 1,
            "contact_id": 1,
            "provider": "gemini",
            "config": {"api_key": "x"},
        })
        report("CREATE unknown provider — 422 or 400",
               r.status_code in (400, 422))
        body = r.json()
        report("CREATE unknown provider — has error info",
               "gemini" in str(body) or "provider" in str(body).lower())

        # n8n without url
        r = await c.post("/assistant/create", json={
            "session_id": "err-2",
            "comp_id": 1,
            "contact_id": 1,
            "provider": "n8n",
            "config": {"api_key": "x"},
        })
        report("CREATE n8n without url — 400", r.status_code == 400)
        err = r.json()
        report("CREATE n8n without url — spec error format",
               "error" in err and "url" in err["error"]["reason"].lower())

        # Missing required fields
        r = await c.post("/assistant/create", json={
            "session_id": "err-3",
            "comp_id": 1,
        })
        report("CREATE missing fields — 422", r.status_code == 422)

        # Empty body
        r = await c.post("/assistant/create", json={})
        report("CREATE empty body — 422", r.status_code == 422)

        # Invalid JSON
        r = await c.post("/assistant/create", content=b"not json",
                         headers={"Content-Type": "application/json"})
        report("CREATE invalid JSON — 422", r.status_code == 422)

        # ═══════════════════════════════════════════════════
        # 4. RESUME
        # ═══════════════════════════════════════════════════

        # Valid resume
        sid = sessions["openai"]
        r = await c.post("/assistant/resume", json={
            "comp_id": 1,
            "assistant_session_id": sid,
        })
        report("RESUME valid session — 200", r.status_code == 200)
        report("RESUME returns same session_id",
               r.json().get("assistant_session_id") == sid)

        # Resume non-existent session
        r = await c.post("/assistant/resume", json={
            "comp_id": 1,
            "assistant_session_id": "non-existent-uuid",
        })
        report("RESUME non-existent — 404", r.status_code == 404)
        err = r.json()
        report("RESUME non-existent — spec error format",
               "error" in err and "reason" in err.get("error", {}))

        # Resume with wrong comp_id
        r = await c.post("/assistant/resume", json={
            "comp_id": 999,
            "assistant_session_id": sid,
        })
        report("RESUME wrong comp_id — 403", r.status_code == 403)

        # ═══════════════════════════════════════════════════
        # 5. MESSAGE — error cases (no real API keys)
        # ═══════════════════════════════════════════════════

        # Message to valid openai session (will fail at provider level)
        sid = sessions["openai"]
        r = await c.post("/assistant/message", json={
            "comp_id": 1,
            "assistant_session_id": sid,
            "messages": [{"role": "user", "content": "Hello!"}],
        })
        report("MESSAGE openai with fake key — 500", r.status_code == 500)
        err = r.json()
        report("MESSAGE openai — spec error format",
               "error" in err and "reason" in err.get("error", {}))

        # Message to non-existent session
        r = await c.post("/assistant/message", json={
            "comp_id": 1,
            "assistant_session_id": "non-existent",
            "messages": [{"role": "user", "content": "Hi"}],
        })
        report("MESSAGE non-existent session — 404", r.status_code == 404)

        # Message with wrong comp_id
        sid = sessions["claude"]
        r = await c.post("/assistant/message", json={
            "comp_id": 999,
            "assistant_session_id": sid,
            "messages": [{"role": "user", "content": "Hi"}],
        })
        report("MESSAGE wrong comp_id — 403", r.status_code == 403)

        # Message with empty messages array
        sid = sessions["claude"]
        r = await c.post("/assistant/message", json={
            "comp_id": 2,
            "assistant_session_id": sid,
            "messages": [],
        })
        report("MESSAGE empty messages — 500 (no real key)", r.status_code == 500)

        # ═══════════════════════════════════════════════════
        # 6. CLOSE
        # ═══════════════════════════════════════════════════

        # Close valid session
        sid = sessions["n8n"]
        r = await c.post("/assistant/close", json={
            "comp_id": 3,
            "assistant_session_id": sid,
        })
        report("CLOSE valid session — 200", r.status_code == 200)
        report("CLOSE response has status=closed", r.json().get("status") == "closed")

        # Try to resume closed session
        r = await c.post("/assistant/resume", json={
            "comp_id": 3,
            "assistant_session_id": sid,
        })
        report("RESUME after close — 404", r.status_code == 404)

        # Close non-existent
        r = await c.post("/assistant/close", json={
            "comp_id": 1,
            "assistant_session_id": "non-existent",
        })
        report("CLOSE non-existent — 404", r.status_code == 404)

        # Close with wrong comp_id
        sid = sessions["openai"]
        r = await c.post("/assistant/close", json={
            "comp_id": 999,
            "assistant_session_id": sid,
        })
        report("CLOSE wrong comp_id — 403", r.status_code == 403)

        # ═══════════════════════════════════════════════════
        # 7. CREATE with default/optional params
        # ═══════════════════════════════════════════════════

        # Minimal config
        r = await c.post("/assistant/create", json={
            "session_id": "call-min",
            "comp_id": 10,
            "contact_id": 10,
            "provider": "claude",
            "config": {"api_key": "key"},
        })
        report("CREATE minimal config — 200", r.status_code == 200)

        # Full config with vendor parameters
        r = await c.post("/assistant/create", json={
            "session_id": "call-full",
            "comp_id": 10,
            "contact_id": 10,
            "provider": "openai",
            "config": {
                "url": "https://custom-openai-proxy.com/v1",
                "api_key": "sk-proxy",
                "model": "gpt-4o-mini",
                "assistant_id": None,
                "system_prompt": "Custom prompt",
                "temperature": 0.3,
                "max_tokens": 2000,
            },
            "parameters": {
                "top_p": 0.9,
                "frequency_penalty": 0.5,
            },
        })
        report("CREATE full config with parameters — 200", r.status_code == 200)

        # ═══════════════════════════════════════════════════
        # 8. OpenAPI schema + spec compliance
        # ═══════════════════════════════════════════════════

        r = await c.get("/openapi.json")
        report("GET /openapi.json — 200", r.status_code == 200)
        schema = r.json()
        paths = list(schema.get("paths", {}).keys())
        expected_paths = [
            "/assistant/create", "/assistant/resume",
            "/assistant/message", "/assistant/close", "/health",
        ]
        report("OpenAPI has all 5 paths",
               all(p in paths for p in expected_paths),
               f"Found: {paths}")

        schemas = list(schema.get("components", {}).get("schemas", {}).keys())
        report("OpenAPI has CreateRequest schema", "CreateRequest" in schemas)
        report("OpenAPI has MessageResponse schema", "MessageResponse" in schemas)
        report("OpenAPI has Completion schema", "Completion" in schemas)
        report("OpenAPI has ProviderConfig schema", "ProviderConfig" in schemas)
        report("OpenAPI has ErrorResponse schema", "ErrorResponse" in schemas)

        # ═══════════════════════════════════════════════════
        # 9. Spec field names check (tokens_send, tokens_received)
        # ═══════════════════════════════════════════════════
        completion_schema = schema["components"]["schemas"].get("Completion", {})
        props = list(completion_schema.get("properties", {}).keys())
        report("Completion has 'text' field", "text" in props)
        report("Completion has 'tokens_send' field", "tokens_send" in props)
        report("Completion has 'tokens_received' field", "tokens_received" in props)

        # ═══════════════════════════════════════════════════
        # 10. Response format consistency: successful responses
        # ═══════════════════════════════════════════════════

        # Create returns assistant_session_id at top level
        r = await c.post("/assistant/create", json={
            "session_id": "format-test",
            "comp_id": 99,
            "contact_id": 99,
            "provider": "openai",
            "config": {"api_key": "test"},
        })
        data = r.json()
        report("CREATE response — assistant_session_id at top level (no wrapper)",
               "assistant_session_id" in data and len(data) == 1)

        # Resume returns assistant_session_id at top level
        r = await c.post("/assistant/resume", json={
            "comp_id": 99,
            "assistant_session_id": data["assistant_session_id"],
        })
        rdata = r.json()
        report("RESUME response — assistant_session_id at top level",
               "assistant_session_id" in rdata and len(rdata) == 1)

    # ═══════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print(f"  TOTAL: {PASSED + FAILED} | PASSED: {PASSED} | FAILED: {FAILED}")
    print("=" * 60)

    if FAILED > 0:
        print("\nFailed tests:")
        for r in RESULTS:
            if r["status"] == "FAIL":
                print(f"  - {r['test']}: {r['detail']}")

    return FAILED == 0


if __name__ == "__main__":
    ok = asyncio.run(run_tests())
    sys.exit(0 if ok else 1)
