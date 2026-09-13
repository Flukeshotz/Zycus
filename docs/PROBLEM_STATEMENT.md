# Problem Statement — Contract Authoring Agent (Track A)

> Zycus Product Intern (AI PM Track) — Take-Home Assignment
> Track chosen: **A — Contract Authoring**
> Sample contract: **Mutual Non-Disclosure Agreement (NDA)** between Zycus Inc. and Northwind Vendor Solutions Pvt. Ltd.

---

## 1. Context

Zycus builds procurement software. Contract management is one of the most valuable and most complex parts of procurement. **Contract authoring** means turning a standard template plus a set of business inputs into a draft contract. It sounds like mail-merge, but it isn't. The risk is not in the blanks that fill cleanly. The risk is in the inputs that shouldn't be accepted as given:

- A counterparty asks for a clause that is broader than the company's standard position.
- An input field doesn't apply to this contract type (e.g., payment terms on an NDA).
- An input is open-ended ("use today's date") and could leave a literal placeholder in a signed document.
- A required value is missing, vague, or contradicts another value.

A tool that simply fills the blanks produces a document that *looks* finished but may quietly contain risky language. That is worse than no automation, because a reviewer trusts it.

## 2. The Problem

> **Legal and procurement teams need a way to turn a contract template and business inputs into a clean, reviewable draft. Every value must be filled correctly, and anything missing, not applicable, ambiguous, or non-standard must be surfaced for a human decision instead of being silently inserted.**

The system must know the difference between *"I'm confident, so I'll fill this in"* and *"I'm not confident, so a person needs to look at this."* It must also be able to explain why it made each call.

## 3. Primary User

**Contract author / reviewer:** a procurement or legal-ops professional who drafts routine agreements such as NDAs from company templates.

| They need to… | Today's pain |
|---|---|
| Produce a first draft quickly | Manual copy-paste from intake forms into templates |
| Trust that the draft matches the inputs | Typos, inconsistent names or dates across sections, leftover `[PLACEHOLDERS]` |
| Catch non-standard asks before they reach signature | Risky counterparty requests get pasted in verbatim |
| Know exactly where to spend review time | No signal about which parts of the draft are routine and which are risky |

## 4. Inputs

### 4.1 Template (Mutual NDA, 7 sections)
Placeholders: `[EFFECTIVE DATE]`, `[DISCLOSING PARTY]`, `[RECEIVING PARTY]`, `[PURPOSE OF DISCLOSURE]`, `[TERM]`, `[SURVIVAL PERIOD]`, `[SPECIAL CLAUSE, IF ANY]`, `[GOVERNING LAW]`.

### 4.2 Business inputs (sample)

| Field | Value | Expected handling |
|---|---|---|
| Contract type | Mutual NDA | Selects the template and the rules that apply |
| Disclosing party | Zycus Inc. | Direct fill |
| Receiving party | Northwind Vendor Solutions Pvt. Ltd. | Direct fill |
| Effective date | "Use today's date" | **Resolve** to the actual generation date. Never output a literal placeholder |
| Term | 2 years from effective date | Direct fill |
| Governing law | State of Delaware, USA | Direct fill |
| Survival period | 3 years after termination | Fill, then check it against the standard range |
| Purpose | Evaluating a potential vendor relationship for procurement software integration | Direct fill |
| Special clause | Affiliate disclosure carve-out **without prior written consent** | **Flag as non-standard.** Do not insert as unrestricted language |
| Payment terms | Not applicable (NDA) | **Recognize as N/A.** Do not force it into the template |
| Contract value | *Not provided* (listed in the brief's generic Track A inputs) | **Recognize as N/A for an NDA.** If a user supplies one, flag it; don't force it in |

> The brief's generic input "counterparty name" maps to the **Receiving party** (Northwind) in this NDA.

## 5. What the System Must Do

### 5.1 Functional requirements
1. **Parse and normalize** the business inputs into structured fields.
2. **Map inputs to template placeholders.** Detect unmapped inputs (e.g., payment terms) and unfilled placeholders.
3. **Resolve derivable values** such as the effective date, and record how each one was derived.
4. **Validate** every value against a standard clause rulebook: ranges, required fields, allowed language.
5. **Classify every field and clause** into one of these states:
   - ✅ **Auto-filled:** confident, matches standard
   - ⚠️ **Flagged for review:** non-standard, ambiguous, or conflicting, with a reason and a suggested standard alternative
   - ⛔ **Missing / blocked:** required value absent
   - ➖ **Not applicable:** input does not belong in this contract type
6. **Generate a clean draft** as a **Word document (.docx)**. It must contain no leftover brackets and must be internally consistent: the same party names, dates, and terms everywhere.
7. **Produce a review report** alongside the draft that lists every flag, its reason, its confidence, and the recommended action.
8. **Handle changed inputs, not just the sample.** Interviewers will poke at the live link: removing fields, entering out-of-range terms, adding payment terms or contract value, or leaving the optional special clause empty. The system must stay correct and flag sensibly rather than being hardcoded to the sample.

### 5.2 Required system properties (from the brief)
- **Not a prompt-wrapper.** They want to see us build, orchestrate, debug, and make real product judgment calls about **trust and uncertainty**.
- **Multi-step / multi-tool, not a single prompt.** Use either more than one agent, or one agent calling at least one external tool (template lookup, rulebook lookup, validator, scorer). A single one-shot LLM call does not qualify.
- **Explicit uncertainty handling.** There must be a clear, explainable rule that separates *auto-suggest* from *flag for human review*.
- **Built with AI coding tools** (Claude Code / Cursor / etc.).
- **Runs live.** The product must be deployed at a reachable URL and demoed in real time. **No recorded demos, no slideware.**

## 6. Planted Issues the Agent Must Catch (acceptance tests)

| # | Issue | Naive behaviour ❌ | Required behaviour ✅ |
|---|---|---|---|
| 1 | Affiliate carve-out without prior written consent in Section 4 | Pastes the clause in verbatim | Flags it as **non-standard / broader than standard** and explains the risk: confidential info can flow to entities that never signed the NDA. Suggests a standard-conforming version, e.g., affiliates allowed only on a need-to-know basis, bound by equivalent obligations, with the Receiving Party liable for their breaches. The final call stays with a human |
| 2 | Payment terms on an NDA | Inserts a payment clause or a stray "N/A" | Marks the field **Not Applicable** and leaves it out of the document entirely |
| 3 | Effective date = "use today's date" | Leaves `[EFFECTIVE DATE]` or the literal text "today's date" in the draft | Resolves it to the concrete generation date, uses it everywhere, and notes the assumption for the reviewer |

## 7. Additional Risks Worth Surfacing (stretch, shows product judgment)

These aren't planted, but a careful reviewer would notice them:

- **"Mutual" vs. one-way roles.** The template is titled *Mutual* NDA but labels one party "Disclosing" and the other "Receiving". In a mutual NDA both parties disclose and receive. Flag the inconsistency rather than silently rewriting the legal structure.
- **Section 4 ↔ Section 5 conflict.** Section 5 limits permitted disclosure to employees, officers, and advisors. The affiliate request conflicts with that list unless Section 5 is amended too.
- **Survival period (3 yrs) longer than term (2 yrs).** This is common and fine, but it means obligations can last up to 5 years in total. Surface it as informational, not as an error.
- **Standard NDA protections missing from the template**, such as exclusions for public information and return or destruction of information. These are informational flags only; the template is intentionally simplified.
- **Signature block** has no names, titles, or dates. Flag it as to be completed at execution.
- **Generic commercial checks from the brief** (payment terms outside a normal range, missing indemnification cap). They don't apply to this NDA, but the rulebook should handle them if a user supplies commercial fields during the live demo. That shows the rules can be extended beyond NDAs.

## 8. Confidence / Human-in-the-Loop Principle

The core product decision: **the agent should never silently accept a deviation from the standard, and never silently reject a business request.**

- A value is **auto-filled** only when it (a) maps unambiguously to a placeholder, (b) passes deterministic validation against the rulebook, and (c) doesn't change the legal meaning of a standard clause.
- Anything that **changes risk allocation**, such as special clauses or carve-outs, is **always flagged**, however confident the model is. Legal risk decisions belong to humans.
- Confidence is based on **deterministic checks first** (rules, ranges, required fields) and **LLM judgement second** (clause interpretation). Rule-based checks can't be overridden by the model.

## 9. Scope

### In scope
- One contract type: **Mutual NDA** (the provided template)
- Structured business inputs → filled .docx draft + review report
- Rule-based validation + LLM-assisted clause analysis
- Simple web UI: enter/edit inputs → run → view flags → download draft
- Deployed live link

### Out of scope (deliberately)
- Multiple contract types or a template library
- Redlining counterparty paper (that's Track B)
- E-signature, approval workflows, CLM integrations
- Preserving exact legal formatting
- Giving legal advice. The output is a draft for human review.

> Narrow and reliable beats broad and fragile. The brief says so explicitly.

## 10. Success Criteria

| Rubric category (weight) | What "success" looks like for this build |
|---|---|
| Build & orchestration fluency (40%) | A visible multi-step pipeline (parse → map → validate → classify → generate → report), with tool calls that can be shown and explained |
| Debugging ability (25%) | One real failure hit during the build, with a clear story of how it was diagnosed and fixed (e.g., placeholder leakage, the model pasting the carve-out verbatim) |
| Speed & tool leverage (15%) | Working end-to-end in the ~3-hour window, built with Claude Code |
| Product judgment — uncertainty/HITL (15%) | All 3 planted issues caught, with a defensible rule for flag vs. act |
| Communication (5%) | Architecture and confidence logic can be explained to a non-engineer in under 2 minutes |

**Definition of done**
- [ ] Sample inputs produce a .docx with zero unresolved `[PLACEHOLDERS]`
- [ ] Party names, dates, term, and governing law are consistent across all sections
- [ ] Affiliate carve-out flagged as non-standard, with reason and suggested alternative
- [ ] Payment terms marked N/A and absent from the document
- [ ] Effective date resolved to the actual date and noted as an assumption
- [ ] Every field has a status (auto / flagged / missing / N/A) with a reason
- [ ] Deployed at a stable public URL
- [ ] GitHub repo + 5–6 slide deck (architecture, real screenshots, one bug & fix, one flag-vs-act decision)
- [ ] Works with edited or missing inputs, not just the sample
- [ ] Running log of **where the AI coding tool got something wrong and what we did about it** (the brief asks for this at the demo)

## 11. Deliverables

1. GitHub repository with working code (public or invite-only)
2. Live deployed product link (Vercel / Render / Replit / Streamlit Cloud / ngrok or similar). Interviewers will use it during the interview, so it must be **up and stable before the interview slot**
3. Slide deck (5–6 slides max): architecture diagram · screenshots of working screens (not mockups) · one thing that broke and how it was debugged and fixed · one deliberate decision on flagging vs. acting alone
4. *(Optional)* links to other live public projects. These can count as supporting context under Build or Speed; they aren't scored separately, and not having one isn't penalized

**Live demo:** a scheduled slot in **Round 1**. Be ready to explain the architecture, the confidence logic, one real bug, and **where the AI coding tool got something wrong and how we caught it**.

## 12. Constraints & Assumptions

- **Time box:** ~3 hours of effort, strictly.
- **Rulebook:** the brief says a "standard playbook / clause rulebook" is provided for both tracks, but the Track A pack contains only the template and inputs. **Assumption:** we write a small, explicit NDA rulebook ourselves (e.g., acceptable term and survival ranges, allowed disclosure recipients, required fields per contract type). The rulebook's contents are documented as a deliberate product decision.
- **Effective date:** "today" means the date the draft is generated.
- **Submission:** repo + live link + deck, due "22 Aug" by "[email/form]". The brief never fills in the submission method, and today is 13 Sep 2026, so confirm the actual deadline and channel with the recruiter.
- Full source capture and requirement-by-requirement traceability: see [context.md](context.md).
- The sample is simplified and non-binding. The system produces drafts, not legal advice.
