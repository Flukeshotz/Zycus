#!/usr/bin/env python3
"""P6 live production smoke test script against Vercel."""
import json
import sys
import httpx

BASE_URL = "https://zycus-blond.vercel.app"

def main() -> int:
    print(f"Running P6 live smoke test against {BASE_URL}...")
    client = httpx.Client(timeout=60.0)

    # 1. Health check
    res = client.get(f"{BASE_URL}/api/health")
    assert res.status_code == 200, f"Health check failed: {res.status_code} {res.text}"
    health = res.json()
    print("1. Health check:", health)
    assert health.get("groq_key_configured") is True

    # 2. S01 end-to-end
    with open("evals/scenarios/S01_sample.json") as f:
        s01_data = json.load(f)
    print("2. Sending S01 to /api/run...")
    res = client.post(f"{BASE_URL}/api/run", json={"inputs": s01_data["inputs"]})
    assert res.status_code == 200, f"S01 failed: {res.status_code} {res.text}"
    envelope = res.json()
    run_result = envelope["run_result"]
    print(f"   S01 readiness: {run_result['readiness']}")
    assert run_result["readiness"] == s01_data["expected"]["readiness"]
    assert "docx_base64" in envelope and len(envelope["docx_base64"]) > 1000

    # 3. S08 prompt injection end-to-end
    with open("evals/scenarios/S08_prompt_injection.json") as f:
        s08_data = json.load(f)
    print("3. Sending S08 (Prompt Injection attempt) to /api/run...")
    res = client.post(f"{BASE_URL}/api/run", json={"inputs": s08_data["inputs"]})
    assert res.status_code == 200, f"S08 failed: {res.status_code} {res.text}"
    s08_envelope = res.json()
    s08_run = s08_envelope["run_result"]
    assert s08_run["readiness"] == s08_data["expected"]["readiness"]
    # Verify injection note present in special_clause decision
    sc_dec = next((d for d in s08_run["decisions"] if d["field"] == "special_clause"), None)
    assert sc_dec is not None, "special_clause decision missing"
    print(f"   S08 special_clause info_notes: {sc_dec.get('info_notes')}")
    assert any("inject" in note.lower() for note in sc_dec.get("info_notes", [])), "Expected injection in info_notes"

    print("\n✅ All P6 live smoke checks passed against production!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
