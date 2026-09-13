# Scenario Evaluation Report

- **Run Date**: 2026-09-13 21:14:55 IST
- **Mode**: `live`
- **Repeats**: 1
- **Overall Pass Rate**: 14/14 (100.0%)
- **Must-Pass Pass Rate**: 6/6 (100.0%)

## Token Usage by Model

| Model | Total Tokens |
|---|---|
| `openai/gpt-oss-120b` | 15,719 |
| `openai/gpt-oss-20b` | 19,871 |

## Scenario Results

| ID | Title | Must-Pass | Expected | Actual | Result | Latency | Tokens | Details |
|---|---|---|---|---|---|---|---|---|
| S01 | Provided sample (Zycus / Northwind Mutual NDA) | **Yes** | `NEEDS_REVIEW` | `NEEDS_REVIEW` | ✅ PASS | 6.9s | gpt-oss-20b: 1489, gpt-oss-120b: 1679 | — |
| S02 | Governing law left empty | **Yes** | `BLOCKED` | `BLOCKED` | ✅ PASS | 8.0s | gpt-oss-20b: 1555, gpt-oss-120b: 1837 | — |
| S03 | Term of 10 years (outside standard range) | No | `NEEDS_REVIEW` | `NEEDS_REVIEW` | ✅ PASS | 7.4s | gpt-oss-20b: 1530, gpt-oss-120b: 1923 | — |
| S04 | Term expressed as an ambiguous condition, not a duration | No | `NEEDS_REVIEW` | `NEEDS_REVIEW` | ✅ PASS | 5.3s | gpt-oss-20b: 1560, gpt-oss-120b: 1819 | — |
| S05 | Payment terms supplied on an NDA | **Yes** | `NEEDS_REVIEW` | `NEEDS_REVIEW` | ✅ PASS | 11.7s | gpt-oss-20b: 1727, gpt-oss-120b: 1777 | — |
| S06 | No special clause requested | **Yes** | `READY_FOR_SIGNATURE_REVIEW` | `READY_FOR_SIGNATURE_REVIEW` | ✅ PASS | 1.3s | gpt-oss-20b: 1480 | — |
| S07 | Special clause with no library match (residual knowledge carve-out) | No | `NEEDS_REVIEW` | `NEEDS_REVIEW` | ✅ PASS | 6.6s | gpt-oss-20b: 1585, gpt-oss-120b: 1591 | — |
| S08 | Special clause attempts a prompt injection | **Yes** | `NEEDS_REVIEW` | `NEEDS_REVIEW` | ✅ PASS | 11.0s | gpt-oss-20b: 1516, gpt-oss-120b: 1557 | — |
| S09 | Receiving party name has no legal entity designator | No | `NEEDS_REVIEW` | `NEEDS_REVIEW` | ✅ PASS | 6.8s | gpt-oss-20b: 1502, gpt-oss-120b: 1658 | — |
| S10 | Both parties identical, and neither is a Zycus entity | No | `BLOCKED` | `BLOCKED` | ✅ PASS | 7.7s | gpt-oss-20b: 1503, gpt-oss-120b: 1878 | — |
| S11 | Effective date given explicitly, not derived | No | `NEEDS_REVIEW` | `NEEDS_REVIEW` | ✅ PASS | 54.1s | gpt-oss-20b: 1496 | — |
| S12 | Survival period stated as perpetual | No | `NEEDS_REVIEW` | `NEEDS_REVIEW` | ✅ PASS | 76.7s | gpt-oss-20b: 1490 | — |
| S13 | Governing law not on the approved list (Singapore) | No | `NEEDS_REVIEW` | `NEEDS_REVIEW` | ✅ PASS | 1.0s | gpt-oss-20b: 1438 | — |
| S14 | AI unavailable — safe degraded draft | **Yes** | `NEEDS_REVIEW` | `NEEDS_REVIEW` | ✅ PASS | 0.0s | — | — |
