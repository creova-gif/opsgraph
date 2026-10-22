# Concierge Pilot Delivery Checklist

> **Source:** Viability Strategy Brief (Appendix B)  
> **Target:** 48-hour repeatable execution per customer with complete decision logging.

---

## Pre-Installation Phase (Hours 0 – 12)

- [ ] **Step 01:** Founder completes structured onboarding profile (`schema/company-profile.schema.json`) and signs off.
- [ ] **Step 02:** Brand assets (SVG logo, primary/secondary hex colors, font guidelines, tone of voice) received and validated.
- [ ] **Step 03:** Google Workspace OAuth scope boundaries documented and authorized (metadata read + dedicated OS folder create).
- [ ] **Step 04:** Existing workspace inventory scan captured (file count, folder hierarchy, dangling unowned documents).
- [ ] **Step 05:** Current taxonomy and historical file-naming conventions mapped into the inventory database.
- [ ] **Step 06:** Sample of duplicate, orphaned, or stale artifacts reviewed with founder/COO.

---

## State Resolution & Gap Mapping Phase (Hours 12 – 24)

- [ ] **Step 07:** Required-State graph generated via State Resolver (`python3 resolver/resolver.py`).
- [ ] **Step 08:** Applicability exceptions, jurisdiction overrides, and custom company rules approved by founder.
- [ ] **Step 09:** Interactive Gap Map and proposed folder taxonomy preview shared with founder for signoff.
- [ ] **Step 10:** Core missing artifacts (up to 31 nodes) drafted with specific company facts and provenance metadata tags.
- [ ] **Step 11:** Master Document Register (`00_Master_Document_Register`) sheet initialized with canonical numbering (`CO-001`, `ES-001`, etc.).
- [ ] **Step 12:** Accountable policy owners assigned based on company's verified functional leadership (CTO, COO, CFO, Head of People).
- [ ] **Step 13:** High-risk legal and compliance claims marked with explicit human-verification flags (never auto-asserted).

---

## Compilation & Handover Phase (Hours 24 – 48)

- [ ] **Step 14:** Installation executed idempotently into Google Workspace with complete audit change log.
- [ ] **Step 15:** Baseline Company Infrastructure Score (0–100%) calculated and generated as an executive summary.
- [ ] **Step 16:** Top 10 immediate remediation priorities (e.g., missing signatures, unindexed vendor agreements) presented to founder.
- [ ] **Step 17:** 30-day Company Guardian drift monitoring configured (weekly scan cadence & Slack alert webhook).
- [ ] **Step 18:** Total implementation hours, API quota usage, and LLM inference costs recorded in the internal unit-economics ledger.
- [ ] **Step 19:** Every non-standard judgment call, edge case, or manual fix appended to the product decision log.
- [ ] **Step 20:** Founder post-delivery verification interview completed (NPS, before/after hours saved, referral request).
