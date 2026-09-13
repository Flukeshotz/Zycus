#!/usr/bin/env python3
"""Live verification of Gemini fallback model against real pipeline schemas."""
import json
import sys

from core.config import get_settings
from core.llm import GroqLLM
from core.models import BusinessInputs, ClauseAssessment, NormalizedInputs
from core.schema import strict_schema

def main():
    settings = get_settings()
    print(f"Gemini API Key configured: {settings.gemini_key_configured}")
    print(f"Fallback model: {settings.model_fallback}")
    print(f"Fallback enabled: {settings.enable_fallback}")

    if not settings.gemini_key_configured:
        print("ERROR: GEMINI_API_KEY is not configured in settings!")
        return 1

    llm = GroqLLM(settings=settings)

    # 1. Direct test of _call_gemini_fallback with NormalizedInputs schema
    print("\n[Test 1] Testing Gemini fallback directly with NormalizedInputs schema...")
    system_prompt = "You are a legal intake normalizer. Parse the following inputs into structured JSON."
    user_prompt = json.dumps({
        "contract_type": "mutual_nda",
        "disclosing_party": "Zycus Inc.",
        "receiving_party": "Northwind Vendor Solutions Pvt. Ltd.",
        "effective_date": "To be filled — use today's date",
        "term": "2 years from effective date",
        "survival_period": "3 years after termination",
        "governing_law": "State of Delaware, USA",
        "purpose": "Evaluating vendor relationship",
        "special_clause": "Affiliate carve-out",
        "payment_terms": "Not applicable",
        "contract_value": ""
    })

    try:
        norm_result = llm._call_gemini_fallback(
            system=system_prompt,
            user=user_prompt,
            schema_model=NormalizedInputs,
            schema_name="normalized_inputs",
            temperature=0.2,
        )
        print("✅ [Test 1] Gemini succeeded with NormalizedInputs!")
        print(f"   Model used: {llm.last_call.model}")
        print(f"   Served by: {llm.last_call.served_by}")
        print(f"   Tokens: total={llm.last_call.total_tokens}, prompt={llm.last_call.prompt_tokens}, completion={llm.last_call.completion_tokens}")
        print(f"   Fields parsed: {len(norm_result.fields)}")
        for f in norm_result.fields[:3]:
            print(f"   - {f.field}: {f.raw_value!r} -> {f.normalized_value!r} (interp: {f.interpretation}, conf: {f.confidence})")
    except Exception as e:
        print(f"❌ [Test 1] Gemini failed on NormalizedInputs: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # 2. Direct test of _call_gemini_fallback with ClauseAssessment schema
    print("\n[Test 2] Testing Gemini fallback directly with ClauseAssessment schema...")
    ca_system = "You are a contract analyst. Return a ClauseAssessment strict JSON object."
    ca_user = "Analyze this special clause: 'The Receiving Party may disclose Confidential Information to its Affiliates.' Matched library clause: affiliate_disclosure."

    try:
        ca_result = llm._call_gemini_fallback(
            system=ca_system,
            user=ca_user,
            schema_model=ClauseAssessment,
            schema_name="clause_assessment",
            temperature=0.3,
        )
        print("✅ [Test 2] Gemini succeeded with ClauseAssessment!")
        print(f"   Deviation: {ca_result.deviation}")
        print(f"   Library match: {ca_result.library_match}")
        print(f"   Proposed text present: {bool(ca_result.proposed_text)}")
        print(f"   Tokens: total={llm.last_call.total_tokens}")
    except Exception as e:
        print(f"❌ [Test 2] Gemini failed on ClauseAssessment: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print("\n🎉 ALL GEMINI LIVE TESTS PASSED! The Gemini model is fully functional and ready as a fallback.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
