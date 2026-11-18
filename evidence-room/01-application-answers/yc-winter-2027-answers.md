# YC Winter 2027 Application Answers — OpsGraph

> **Application Status:** Working Draft (Sprint v1.0)  
> **Target Batch:** Y Combinator Winter 2027  
> **Source Documents:** `docs/strategy/OpsGraph_YC_Application_Preparation_Playbook.txt`  
> **Rule of Discipline:** Specific before broad • Evidence before assertion • Plain, factual, numerical answers • No jargon or pitch-deck fluff.

---

## 1. Company Basics

### Company Name
**OpsGraph** *(working name; update upon incorporation/domain lock)*

### One-line Description
> We turn a startup's existing Google Workspace into a complete, AI-maintained company operating system.

*(Alternative 50-character tight version if required: `AI-maintained operating system for Google Workspace.`)*

### Company URL
`https://opsgraph.io` *(or current staging/landing URL)*

---

## 2. Core Application Questions & Draft Answers

### Q1: What is your company going to make?
**Draft Answer:**
We are building OpsGraph, software that turns a startup's existing Google Workspace into an AI-maintained operating infrastructure. 

When a founder connects their Google Workspace and completes a structured onboarding profile, our system:
1. **Inventories** the existing state (files, folders, permissions, document dates, ownership).
2. **Evaluates gaps** against a deterministic "required-state" model tailored to the company's stage, jurisdiction, team size, and commercial triggers.
3. **Compiles missing infrastructure** directly into their drive—generating approved folder hierarchies, master document registers, core governance policies, decision logs, and investor/enterprise readiness packs.
4. **Monitors continuous drift** via an AI "Company Guardian" agent that flags stale policies, missing evidence, duplicated drafts, and unassigned documents.

Our initial wedge is 5–50 person B2B SaaS and AI startups on Google Workspace that face an urgent readiness trigger: enterprise vendor security reviews, fundraising due diligence, SOC 2 preparation, or rapid hiring.

---

### Q2: Why did you pick this idea? / What is your personal connection to the problem?
**Draft Answer:**
I kept running into the exact same operational failure mode across building and scaling companies: engineering builds the product, but internal company infrastructure remains scattered across Google Drive folders, local desktops, and people's heads. 

Inevitably, an external trigger arrives—a Fortune 500 prospect sends a 150-question security review, a lead investor asks for an organized data room in 48 hours, or a compliance audit begins. The founding team is forced to halt product development for two weeks to manually scramble, buy boilerplate templates, and reconstruct basic registers, policies, and evidence. 

During a recent operating system build, I found myself making dozens of repeatable, systematic decisions regarding document taxonomy, canonical numbering, provenance tracking, and required operational evidence. I realized this is not a creative writing task; it is a deterministic compilation and continuous state reconciliation problem that software should solve.

---

### Q3: What do you understand about your business that others do not? (The Secret / Insight)
**Draft Answer:**
Most people believe the product in this space is a collection of document templates or a new workspace tool like Notion. That is completely wrong.

Templates create false confidence because they instantly go stale and lack continuous evidence binding. Migrating to a new workspace is resisted because teams already do their daily work in Google Docs and Sheets.

The actual product is a **required-state model of the company**: given a company's stage, industry, team composition, geography, and commitments, what operational artifacts *must* exist, who owns them, and what evidence validates them? Once you model the company as an operating graph, compliance readiness, investor data rooms, team onboarding, and document hygiene become different compiled views of the same underlying state. We leave users in their existing Google Workspace and use AI to maintain the state continuously.

---

### Q4: How far along are you?
**Draft Answer:**
We have built and verified the complete end-to-end software loop for Google Workspace:
1. **Operating Graph Ontology:** Codified 31 core operational artifacts (`rules/core-artifacts.json` v0.2) with strict criticality ratings, dependency mappings, review cadences, evidence types, and SOC 2 / ISO crosswalks.
2. **Deterministic State Resolver:** Evaluates company stage, headcount, commercial triggers, and regulated activities to output required artifacts, dynamic functional owner assignments, and topological compilation order.
3. **Workspace Inventory Scanner:** Read-only metadata scanner indexing files, folders, timestamps, and owners without reading private payload content.
4. **Gap Analysis Engine:** Evaluates observed files against the required model, categorizing artifacts into 5 states (Present Current, Present Stale, Misplaced, Duplicate Collision, Missing) and calculating an explainable 0–100% Company Infrastructure Score.
5. **Workspace Compiler:** Generates canonical numbered folder hierarchies (`00_Company_Control` through `99_Archive`), instantiates the Master Document Register (CSV/JSON), and stamps governed templates with provenance metadata and marked founder input placeholders.
6. **Company Guardian:** Background monitoring engine detecting unindexed documents, unowned/contractor files, and expired policy review cadences, outputting a weekly Health Digest with 1-click remediation actions.
7. **Test Suite & Demo:** 10 passing unit tests across all engines and an executable 7-moment live demo (`bin/opsgraph demo`). We are currently running concierge pilots with Seed/Series A B2B founders to refine rule edge cases.

---

### Q5: How many active users or customers do you have? What is your revenue?
**Draft Answer:**
- **Paying customers:** `[X]` startups (paying an initial implementation fee between $750–$2,500).
- **Active pilots:** `[Y]` startups currently undergoing onboarding and gap-resolution.
- **Total revenue to date:** `$[Z]` (cash received across paid pilots / setup fees).
- **Customer pipeline:** `[N]` qualified B2B founders with an immediate trigger (fundraise or enterprise pilot) on our waitlist.

*(Application Rule: Distinguish paying customers, pilots, and waitlist numbers with absolute transparency. No vanity metrics.)*

---

### Q6: Who are your competitors and what makes you different?
**Draft Answer:**
We operate at the intersection of three categories:
1. **Compliance Automation (Vanta, Drata, Secureframe):** They automate security audits (SOC 2, ISO 27001). However, compliance is only one specific view of a company's operational state. They don't organize the general company infrastructure, operating registers, board materials, or hiring operations.
2. **Horizontal Workspaces (Google Workspace, Microsoft 365, Notion):** They provide the raw canvas (docs, sheets, pages), but provide zero semantic opinion on what a Series A company actually needs to operate or pass due diligence.
3. **Fractional COOs & Boutique Ops Consultants:** They create custom operational folders and binders for $5,000–$15,000, but deliver static snapshots that rot within 90 days.

**Our Difference:** We install directly inside the customer's existing Google Workspace, compile the general operating system around their specific stage, and provide an automated Guardian to keep it from decaying.

---

### Q7: How do / will you make money?
**Draft Answer:**
We use a two-part monetization model:
1. **Implementation Fee ($750 – $2,500 one-time):** Paid concierge installation, workspace inventory, gap resolution, and initial compilation of approved missing artifacts.
2. **Company Guardian Subscription ($99 – $499/month recurring SaaS):** Automated background monitoring of Google Workspace for drift, stale policies, missing ownership, unfiled contracts, and upcoming regulatory/governance review dates.

As our deterministic compiler matures, implementation becomes self-serve and high-margin, with expansion revenue coming from enterprise add-on packs (e.g., deep SOC 2 / ISO readiness, multi-entity support, and investor portal views).

---

### Q8: How do you acquire customers? (Distribution)
**Draft Answer:**
We acquire customers exclusively through **trigger-based outbound and channel partnerships**:
1. **Urgent Triggers:** We monitor funding announcements (Seed/Pre-seed rounds), enterprise sales pipeline wins, and hiring surges. Founders are highly receptive to solving operational chaos immediately after closing a round or signing an enterprise LOI.
2. **Channel Referrals:** Early-stage corporate lawyers, startup accountants, and fractional CFOs who dread dealing with disorganized client data rooms and unindexed contracts. They refer clients to us to clean up their operations before transactions.
3. **Founder Community / YC Network:** Direct founder-to-founder outreach offering 48-hour workspace readiness audits.

---

### Q9: Where will the company be based? What are the founders' commitments?
**Draft Answer:**
- **Location:** San Francisco, CA / Remote *(fill exact primary location)*.
- **Commitment:** 100% full-time commitment on OpsGraph. We are not treating this as an incubator project or side venture; this is our sole operating company.

---

## 3. Pre-Submission Verification Gate

Before submitting to the YC portal:
- [ ] Re-verify exact numbers in Q4 & Q5 against `evidence-room/02-metrics/weekly-tracker.md`.
- [ ] Record a 1-minute, unedited founder video answering: Who are you, what are you building, who is the user, and what is your traction? (No music, no pitch deck slides).
- [ ] Confirm the 30-second one-liner passes the cold-stranger test.
- [ ] Ensure no claim is made that OpsGraph "guarantees compliance" (we provide readiness and evidence compilation, not legal certification).
