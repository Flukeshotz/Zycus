# context.md — Zycus Product Intern (AI PM Track) Take-Home

> The single source of truth for this project. It captures **everything** in the two source documents, then checks every requirement against [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) so no scope is missed.
>
> **Sources** (both authored by Chinmaya Behera, created 20 Aug 2026):
> 1. `Zycus_PM_Intern_Assignment_Brief.docx`: the assignment brief
> 2. `Zycus_TrackA_Sample_ContractAuthoring.docx`: the Track A sample input pack
>
> Both files were inspected at the XML level. Neither has headers, footers, comments, footnotes, hidden text, or hyperlinks. Each has exactly one table.
>
> **Track chosen: A — Contract Authoring Agent**

---

## PART 1 — The Assignment Brief

### 1.1 Context
- Zycus builds **procurement software**.
- One of the highest-value, highest-complexity procurement workflows is **contract management**, specifically:
  - **Contract authoring:** drafting a contract from a template + business inputs.
  - **Redlining:** reviewing a counterparty's proposed contract, flagging risky clauses, and suggesting edits.
- The candidate builds a **working AI agent system** for **one** of the two workflows.
- It is explicitly **not a prompt-wrapper exercise**. They want to see the candidate **build, orchestrate, debug, and make real product judgment calls about trust and uncertainty.**

### 1.2 Track A — Contract Authoring Agent (CHOSEN)
**Given:** a contract template (the Track A sample) and a set of business inputs. The brief's generic input list is **counterparty name, contract value, term length, payment terms, and any special clauses requested**.

**Build an agent system that:**
1. **Fills in the template correctly** using the provided inputs.
2. **Flags any input that is missing, ambiguous, or conflicts with a standard clause.** The brief's examples: *payment terms outside a normal range*, *missing indemnification cap*.
3. **Produces a clean, ready-to-review draft contract** as output.

### 1.3 Track B — Redlining Agent (NOT chosen, recorded for completeness)
Given a counterparty-proposed contract and the company's standard playbook (e.g., "liability cap must not exceed 12 months of fees", "termination notice must be ≥30 days"):
- Identify clauses that deviate from the playbook.
- Propose specific redline edits with actual replacement language, not just "this is risky".
- Flag clauses it isn't confident about rather than silently approving or rejecting them.

### 1.4 Required system properties (apply to BOTH tracks, non-negotiable)
| # | Property | Exact bar |
|---|---|---|
| P1 | **Multi-step / multi-tool** | More than one agent, **or** one agent using at least one external tool (examples: playbook/template lookup as a callable tool, a validation step, a scoring step). **A single ChatGPT-style one-shot call does not meet the bar.** |
| P2 | **Explicit uncertainty handling** | Must distinguish **"confident enough to auto-suggest"** from **"not confident, flag for human review"**, and the candidate must be able to **explain how it decides**. |
| P3 | **AI coding tools are mandatory** | Cursor, Claude Code, Windsurf, Copilot, or similar. They're evaluating how the candidate works *with* AI tools to ship, not hand-coding. |
| P4 | **Working code, run live** | **No recorded demos, no slideware.** Demoed running in real time. |

### 1.5 What Zycus provides
- A sample contract template (Track A) or a sample counterparty contract with planted issues (Track B).
- **"A short standard playbook / clause rulebook (both tracks)"**, stated in the brief. ⚠️ *The Track A pack we received contains no rulebook.* See §4, Gap G1.
- These materials are shared at the start of the assignment window.

### 1.6 What the candidate decides
- Tech stack (any language or framework)
- Agent architecture (single agent + tools, or multiple specialized agents)
- **How the system represents and applies "confidence"**
- **Scope.** *"We would rather see a narrow system that works reliably than a broad one that's fragile."*

### 1.7 Deliverables
| # | Deliverable | Details |
|---|---|---|
| D1 | **Working code in a GitHub repo** | Public or invite-only (candidate's choice) |
| D2 | **Live link to the working product** | Deployed somewhere reachable (Vercel, Render, Replit, Streamlit Cloud, ngrok, or similar). **Interviewers will poke at it during the interview.** It must be **up and stable before the interview slot.** |
| D3 | **Slide deck, 5–6 slides max** | Must cover: **(a)** architecture: which agents/tools exist and how they talk (a simple diagram is fine) · **(b)** screenshots of the product in action (working screens, not mockups) · **(c)** one thing that broke while building, and how it was debugged and fixed · **(d)** one deliberate decision about when the agent should flag uncertainty vs. act on its own |
| D4 | *(Optional)* other live public projects | Personal project, hackathon build, freelance work, side tool. Not required, and not held against the candidate |

### 1.8 Timeline
- **Assignment window:** 22 Aug
- **Expected effort:** **3 hours, strictly.** Deliberately small scope. They evaluate *how much you can get working with AI tools in a fixed window*, and they don't reward spending all week. *"Build something narrow that actually works over something broad that's held together with duct tape."*
- **Live demo:** a scheduled slot during **Round 1**.

### 1.9 Evaluation rubric (shared; every candidate is scored the same way)
| Category | Weight | What they look for |
|---|---|---|
| Build & orchestration fluency | **40%** | Did you actually build a multi-step/multi-tool system, and use AI tools well to get there fast? |
| Debugging ability | **25%** | Can you clearly explain a real failure and how you diagnosed and fixed it? |
| Speed & tool leverage | **15%** | How much you shipped in the time given, relative to effort |
| Product judgment (uncertainty/HITL) | **15%** | Is the confidence/flagging logic sensible for a real contract workflow? |
| Communication in demo | **5%** | Can you explain technical decisions clearly, including to a non-engineer? |

**Note on the optional public project:** interviewers *can* factor it in as supporting context under **Build & orchestration** or **Speed & tool leverage**. It is **not a separately scored category**, and not having one **isn't penalized**.

### 1.10 Note on using AI tools
- Using AI coding assistants is **required**, not just allowed.
- They evaluate whether you can **direct it well, catch its mistakes, and ship something that works**.
- **"Come to the demo ready to talk about where the AI got something wrong and what you did about it."** This is a separate talking point from the deck's "one thing that broke".

### 1.11 Submission
- Share the **GitHub repo link, live product link, and slide deck** by **22 Aug** via "[submission method — email/form]". ⚠️ This placeholder was never filled in. See Gap G5.
- Optional: a link to any other live public project.

---

## PART 2 — Track A Sample Input Pack (Contract Authoring)

### 2.1 What the pack is
Two things: **(a)** a blank contract template for the agent to fill, and **(b)** a set of business inputs to fill it with. The system takes the inputs, **populates the template correctly**, and **flags anything missing, ambiguous, or non-standard**.

### 2.2 Business inputs (feed these to the agent)
| Field | Value |
|---|---|
| Contract type | Mutual Non-Disclosure Agreement (NDA) |
| Disclosing party | Zycus Inc. |
| Receiving party | Northwind Vendor Solutions Pvt. Ltd. |
| Effective date | To be filled — use today's date |
| Term | 2 years from effective date |
| Governing law | State of Delaware, USA |
| Confidentiality survival period | 3 years after termination |
| Purpose of disclosure | Evaluating a potential vendor relationship for procurement software integration |
| Special clause requested | Receiving party wants a carve-out allowing disclosure to their affiliates without prior written consent |
| Payment terms | Not applicable — this is an NDA, not a commercial agreement *(the agent should recognize this field doesn't apply and not force it into the template)* |

### 2.3 Output instructions
- Populate the template and **produce a Word document** containing the Mutual Non-Disclosure Agreement.
- Fill bracketed fields such as `[DISCLOSING PARTY]` from the business inputs.
- Treat the template as a realistic but simplified NDA. **Exact legal formatting doesn't need to be preserved**, but the filled output **must be coherent and internally consistent**.

### 2.4 Blank template (verbatim, the system's input)

```
MUTUAL NON-DISCLOSURE AGREEMENT

This Mutual Non-Disclosure Agreement ("Agreement") is entered into as of [EFFECTIVE DATE], by and between [DISCLOSING PARTY], and [RECEIVING PARTY] (each a "Party" and collectively the "Parties").

1. Purpose. The Parties wish to explore [PURPOSE OF DISCLOSURE] (the "Purpose"), and in connection with the Purpose, each Party may disclose certain confidential information to the other.

2. Confidential Information. "Confidential Information" means any non-public information disclosed by one Party to the other, whether orally or in writing, that is designated as confidential or that reasonably should be understood to be confidential given the nature of the information.

3. Term. This Agreement shall remain in effect for [TERM] from the Effective Date. The obligations of confidentiality shall survive termination for a period of [SURVIVAL PERIOD].

4. Restrictions on Use and Disclosure. The Receiving Party shall not disclose Confidential Information to any third party without the prior written consent of the Disclosing Party, except as expressly permitted under Section 5. [SPECIAL CLAUSE, IF ANY]

5. Permitted Disclosures. Confidential Information may be disclosed to the Receiving Party's employees, officers, and professional advisors who need to know such information for the Purpose, provided they are bound by confidentiality obligations no less protective than this Agreement.

6. Governing Law. This Agreement shall be governed by the laws of [GOVERNING LAW], without regard to its conflict of law principles.

7. Signatures. IN WITNESS WHEREOF, the Parties have executed this Agreement as of the Effective Date.
```

**Placeholder → input mapping**
| Placeholder | Section(s) | Input field |
|---|---|---|
| `[EFFECTIVE DATE]` | Preamble | Effective date → resolved to today |
| `[DISCLOSING PARTY]` | Preamble | Disclosing party |
| `[RECEIVING PARTY]` | Preamble | Receiving party |
| `[PURPOSE OF DISCLOSURE]` | §1 | Purpose of disclosure |
| `[TERM]` | §3 | Term |
| `[SURVIVAL PERIOD]` | §3 | Confidentiality survival period |
| `[SPECIAL CLAUSE, IF ANY]` | §4 | Special clause requested (optional: "if any") |
| `[GOVERNING LAW]` | §6 | Governing law |
| *(no placeholder)* | — | Contract type → selects template/title only |
| *(no placeholder)* | — | **Payment terms → N/A, must not appear** |

### 2.5 What the agent should catch (planted by Zycus)
| # | Planted issue | Expected behaviour |
|---|---|---|
| C1 | The requested **affiliate carve-out** in §4 is broader than a standard NDA clause | Flag it as **non-standard**. Do **not** silently insert it as unrestricted language |
| C2 | **Payment terms** don't apply to an NDA | Recognize it as **not applicable**. Don't force it anywhere |
| C3 | **Effective date** is open ("use today's date") | Handle it sensibly. **No literal placeholder** in the output |

### 2.6 Disclaimer
Simplified, non-binding sample for evaluation only. Not a real Zycus contract and not legal guidance.

---

## PART 3 — Scope Traceability Check (every requirement → problem statement)

Legend: ✅ covered · 🔧 was missing or weak, now added to PROBLEM_STATEMENT.md · ℹ️ informational

| ID | Requirement (source) | Status | Where in PROBLEM_STATEMENT.md |
|---|---|---|---|
| R1 | Fill template correctly from inputs (Brief §Track A) | ✅ | §5.1 (2, 6) |
| R2 | Flag missing inputs (Brief) | ✅ | §5.1 (5 ⛔) |
| R3 | Flag ambiguous inputs (Brief) | ✅ | §5.1 (5 ⚠️) |
| R4 | Flag conflicts with a standard clause (Brief) | ✅ | §5.1 (4, 5), §7 |
| R5 | Brief's generic examples: payment terms outside normal range, missing indemnification cap | 🔧 | §7 (rulebook covers generic commercial checks if such fields are supplied) |
| R6 | Brief's generic input list includes **counterparty name** and **contract value** | 🔧 | §4.2 (contract value row + counterparty = Receiving party) |
| R7 | Clean, ready-to-review draft (Brief) | ✅ | §5.1 (6) |
| R8 | Output is a **Word document** (Track A §3) | ✅ | §5.1 (6) |
| R9 | Coherent and internally consistent; exact legal formatting not required (Track A §3) | ✅ | §5.1 (6), §9 |
| R10 | All 8 placeholders filled (Track A §3) | ✅ | §4.1, §10 DoD |
| R11 | Catch C1: affiliate carve-out non-standard | ✅ | §6 #1 |
| R12 | Catch C2: payment terms N/A | ✅ | §6 #2 |
| R13 | Catch C3: effective date = today, no placeholder | ✅ | §6 #3 |
| R14 | P1: multi-step / multi-tool, not one-shot | ✅ | §5.2 |
| R15 | P2: explicit, explainable uncertainty logic | ✅ | §5.2, §8 |
| R16 | P3: AI coding tools mandatory | ✅ | §5.2 |
| R17 | P4: working code live, **no recorded demos, no slideware** | 🔧 | §5.2 |
| R18 | "Not a prompt-wrapper"; judgment on **trust** and uncertainty | 🔧 | §5.2 |
| R19 | Narrow and reliable over broad and fragile | ✅ | §9 |
| R20 | D1: GitHub repo (public or invite-only) | 🔧 | §11 |
| R21 | D2: live link, **interviewers will poke at it**, stable before slot | 🔧 | §5.1 (8), §11 |
| R22 | D3: 5–6 slides with (a) architecture, (b) real screenshots, (c) broke & fixed, (d) flag-vs-act decision | ✅ | §11 |
| R23 | D4: optional public project, not scored separately, not penalized | 🔧 | §11 |
| R24 | 3 hours strictly | ✅ | §12 |
| R25 | Live demo in a **Round 1** slot | 🔧 | §11 |
| R26 | **Be ready to say where the AI coding tool got it wrong and what you did** | 🔧 | §10, §11 |
| R27 | Rubric: 40 / 25 / 15 / 15 / 5 | ✅ | §10 |
| R28 | Submit repo + live link + deck by 22 Aug (method unspecified) | 🔧 | §12 |
| R29 | Non-binding; not legal guidance | ✅ | §9, §12 |
| R30 | `[SPECIAL CLAUSE, IF ANY]` is optional, so the system must handle "no special clause" cleanly | 🔧 | §5.1 (8) |

**Result: all 30 requirements are now covered.** 11 were missing or under-specified in the first draft and have been added.

---

## PART 4 — Gaps, Ambiguities & Implied Scope

### Gaps in the source documents
| ID | Gap | Our working assumption |
|---|---|---|
| G1 | The brief promises a playbook/rulebook for both tracks, but the Track A pack has none | We write a small, explicit NDA rulebook and present it as a product decision |
| G2 | "Mutual" NDA but one-way Disclosing/Receiving roles | Flag as informational; don't restructure the legal text |
| G3 | §5 permitted recipients exclude affiliates, which conflicts with the C1 request | Flag §4 and §5 together; any accepted carve-out must reconcile both sections |
| G4 | The template has no exclusions, return/destruction clause, remedies, indemnity or liability cap, or signatory names/titles | Informational flags only; the template is intentionally simplified |
| G5 | Submission method is an unfilled placeholder "[email/form]" | Confirm with the recruiter |
| G6 | Deadline shows 22 Aug; today is 13 Sep 2026 | Confirm your actual submission and demo dates |
| G7 | Date format and timezone for "today" not specified | Use a long-form date (e.g., "13 September 2026"), generation date in local time, noted as an assumption |

### Implied scope (not written explicitly, but follows from the brief)
- **Changed inputs, not just the sample.** Interviewers "will poke at" the live link. Expect them to change values: remove governing law, set a 10-year term, add payment terms, leave the special clause empty, add contract value. The system must handle this gracefully and not be hardcoded to the sample.
- **Visible orchestration.** 40% of the score is orchestration. The UI or logs should show the steps and tool calls, not only the final document.
- **A debugging diary during the build.** Both D3(c) and R26 require real stories, so log failures and AI mistakes *as they happen*.
- **Explain it to a non-engineer.** The confidence logic needs a plain-English one-liner.
