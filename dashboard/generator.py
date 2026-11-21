#!/usr/bin/env python3
"""
OpsGraph — Interactive Visual Dashboard & HTML Report Generator (v0.1)
Generates a standalone, dependency-free, interactive HTML executive dashboard
representing a startup's operational infrastructure readiness, gap matrix,
and active Guardian drift feed.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from gap_engine.analyzer import GapAnalyzer, GapReport
from guardian.guardian import CompanyGuardian, HealthDigest
from inventory.scanner import InventorySnapshot, WorkspaceScanner
from resolver.resolver import ResolutionReport, StateResolver

_TOKENS_PATH = BASE_DIR / "docs" / "design" / "tokens.json"

# Baked CALIBRATION tokens — must mirror docs/design/tokens.json. Used when
# the design assets aren't on disk (e.g. packaged installs).
_FALLBACK_TOKENS: Dict[str, str] = {
    "paper": "#F7F5F0",
    "surface": "#FFFFFF",
    "sunk": "#ECE8DF",
    "ink": "#1B1A17",
    "ink-muted": "#6B6459",
    "hairline": "#DEDACF",
    "grid": "#E7E3D8",
    "spec": "#1F3FA0",
    "spec-text": "#1F3FA0",
    "drift": "#E8490F",
    "drift-text": "#B8370B",
    "pass": "#1B7F4E",
    "pass-text": "#187246",
    "reject": "#C73E1D",
    "reject-text": "#9C2F15",
}

_TOKEN_KEY_MAP = {
    "paper": "paper",
    "surface": "surface",
    "grid": "grid",
    "sunk": "sunk",
    "ink": "ink",
    "muted": "ink-muted",
    "hairline": "hairline",
    "spec": "spec",
    "specText": "spec-text",
    "drift": "drift",
    "driftText": "drift-text",
    "pass": "pass",
    "passText": "pass-text",
    "reject": "reject",
    "rejectText": "reject-text",
}


def _load_tokens() -> Dict[str, str]:
    """Resolve CSS color tokens from docs/design/tokens.json when available."""
    tokens = dict(_FALLBACK_TOKENS)
    try:
        raw = json.loads(_TOKENS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return tokens
    colors = raw.get("color", {})
    for src_key, css_var in _TOKEN_KEY_MAP.items():
        value = colors.get(src_key)
        if isinstance(value, str) and value.startswith("#"):
            tokens[css_var] = value
    return tokens


class DashboardGenerator:
    def __init__(
        self,
        resolver: Optional[StateResolver] = None,
        analyzer: Optional[GapAnalyzer] = None,
        guardian: Optional[CompanyGuardian] = None,
    ):
        self.resolver = resolver or StateResolver()
        self.analyzer = analyzer or GapAnalyzer()
        self.guardian = guardian or CompanyGuardian()

    def generate(
        self,
        profile_data: Dict[str, Any],
        inventory: InventorySnapshot,
        output_path: Optional[Path] = None,
    ) -> str:
        # 1. Execute Resolution, Gap Analysis, and Guardian Audit
        resolution = self.resolver.resolve(profile_data)
        gap_report = self.analyzer.analyze(resolution, inventory)
        guardian_digest = self.guardian.audit(profile_data, inventory)

        # 2. Serialize data for frontend script injection
        gap_data = asdict(gap_report)
        guardian_data = asdict(guardian_digest)
        profile_clean = {
            "company": profile_data.get("company", {}),
            "stage": profile_data.get("stage", {}),
            "triggers": profile_data.get("triggers", []),
            "standards": profile_data.get("standards", []),
        }

        # 3. Render HTML
        html_content = self._render_html(
            profile=profile_clean,
            gap=gap_data,
            guardian=guardian_data,
        )

        if output_path:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                f.write(html_content)

        return html_content

    def _render_html(self, profile: Dict[str, Any], gap: Dict[str, Any], guardian: Dict[str, Any]) -> str:
        comp_name = profile["company"].get("legal_name", "OpsGraph Client")
        stage_str = profile["stage"].get("funding_stage", "Seed").upper()
        emp_count = profile["stage"].get("employee_count", 1)
        triggers_str = ", ".join(profile.get("triggers", []))
        score = gap["infrastructure_score"]
        scanned_date = gap["scanned_at"]

        # Tolerance instrument: band covers the last 25% of the rail (>=75);
        # the marker sits at the measured score.
        marker_left = min(max(score, 0), 100)
        if score < 40:
            state_tag, state_cls = "[CRITICAL DRIFT]", "reject"
        elif score < 75:
            state_tag, state_cls = "[DRIFT]", "drift"
        else:
            state_tag, state_cls = "[IN TOLERANCE]", "pass"

        gap_json_str = json.dumps(gap).replace("</script>", "<\\/script>")
        guardian_json_str = json.dumps(guardian).replace("</script>", "<\\/script>")
        tokens = _load_tokens()

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="OpsGraph readiness instrument — gap matrix, domain readiness, and guardian drift feed for the company operating graph.">
  <title>{comp_name} — OpsGraph Readiness</title>
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 26 26'%3E%3Crect width='26' height='26' fill='%23F7F5F0'/%3E%3Ccircle cx='13' cy='13' r='11' fill='none' stroke='%231B1A17' stroke-width='2'/%3E%3Cline x1='13' y1='13' x2='19' y2='6.5' stroke='%231B1A17' stroke-width='2'/%3E%3Ccircle cx='13' cy='13' r='1.8' fill='%231B1A17'/%3E%3C/svg%3E">
  <link href="https://api.fontshare.com/v2/css?f[]=cabinet-grotesk@700,800&display=swap" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@0,400;0,600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --paper: {tokens["paper"]};
      --surface: {tokens["surface"]};
      --sunk: {tokens["sunk"]};
      --ink: {tokens["ink"]};
      --ink-muted: {tokens["ink-muted"]};
      --hairline: {tokens["hairline"]};
      --grid: {tokens["grid"]};
      --spec: {tokens["spec"]};
      --spec-text: {tokens["spec-text"]};
      --drift: {tokens["drift"]};
      --drift-text: {tokens["drift-text"]};
      --pass: {tokens["pass"]};
      --pass-text: {tokens["pass-text"]};
      --reject: {tokens["reject"]};
      --reject-text: {tokens["reject-text"]};
      --font-display: "Cabinet Grotesk", sans-serif;
      --font-body: "Instrument Sans", sans-serif;
      --font-mono: "JetBrains Mono", monospace;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{ overflow-x: clip; }}
    body {{
      background: var(--paper);
      color: var(--ink);
      font-family: var(--font-body);
      font-size: 15px;
      line-height: 1.55;
      padding: 24px;
      -webkit-font-smoothing: antialiased;
    }}
    .container {{ max-width: 1280px; margin: 0 auto; }}
    .skip {{
      position: absolute; width: 1px; height: 1px; overflow: hidden;
      clip: rect(0 0 0 0); white-space: nowrap;
    }}
    .skip:focus {{
      width: auto; height: auto; clip: auto; z-index: 10;
      background: var(--ink); color: var(--paper); padding: 8px 16px;
      font-family: var(--font-mono); font-size: 12px;
    }}
    strong, b {{ font-weight: 600; }}
    .mono {{ font-family: var(--font-mono); }}
    a:focus-visible, button:focus-visible, input:focus-visible {{
      outline: 2px solid var(--spec); outline-offset: 2px;
    }}

    /* Certificate strip header */
    .cert {{
      display: flex; justify-content: space-between; align-items: baseline;
      gap: 16px; padding: 12px 0; border-bottom: 1px solid var(--hairline);
      font-size: 11px; letter-spacing: .04em; color: var(--ink-muted);
      flex-wrap: wrap; margin-bottom: 24px;
    }}
    .cert .brand {{
      font-family: var(--font-display); font-weight: 800; font-size: 14px;
      color: var(--ink); letter-spacing: .02em;
    }}
    .cert-meta {{ display: flex; gap: 16px; flex-wrap: wrap; }}

    .page-head {{
      display: flex; justify-content: space-between; align-items: flex-end;
      gap: 24px; margin-bottom: 24px; flex-wrap: wrap;
    }}
    h1 {{
      font-family: var(--font-display); font-weight: 800; font-size: 30px;
      letter-spacing: -.01em; text-wrap: balance;
    }}
    .head-sub {{ font-size: 13px; color: var(--ink-muted); margin-top: 8px; }}
    .header-actions {{ display: flex; gap: 12px; }}

    /* Bracketed actions — mono, hairline, square */
    .btn {{
      font-family: var(--font-mono); font-size: 12px; letter-spacing: .04em;
      padding: 12px 16px; border: 1px solid var(--ink); background: transparent;
      color: var(--ink); cursor: pointer; white-space: nowrap;
    }}
    .btn:active {{ transform: translateY(1px); background: var(--sunk); }}
    .btn:disabled {{
      border-style: dashed; color: var(--ink-muted); cursor: not-allowed;
    }}
    .btn-primary {{ background: var(--ink); color: var(--paper); }}
    .btn-primary:active {{ transform: translateY(1px); }}

    /* Readiness numeral rail */
    .hero-grid {{
      display: grid; grid-template-columns: 340px 1fr; gap: 24px;
      margin-bottom: 24px;
    }}
    .card {{
      background: var(--surface); border: 1px solid var(--hairline);
      padding: 24px; position: relative;
    }}
    .numeral-block .num-label {{
      font-family: var(--font-mono); font-size: 11px; letter-spacing: .04em;
      color: var(--ink-muted);
    }}
    .numeral {{
      font-family: var(--font-display); font-weight: 800; font-size: 96px;
      line-height: .95; letter-spacing: -.03em; font-variant-numeric: tabular-nums;
      margin-top: 8px;
    }}
    .tolerance {{
      width: 160px; height: 4px; background: var(--hairline);
      position: relative; margin-top: 16px;
    }}
    .tolerance::after {{
      content: ""; position: absolute; right: 0; top: 0; height: 100%;
      width: 25%; background: var(--pass);
    }}
    .tolerance .marker {{
      position: absolute; top: -3px; width: 2px; height: 10px;
      background: var(--ink);
    }}
    .readout {{ margin-top: 16px; display: flex; gap: 8px; flex-wrap: wrap; }}
    .tag {{
      display: inline-block; padding: 4px 8px; border: 1px solid var(--hairline);
      font-family: var(--font-mono); font-size: 11px; letter-spacing: .04em;
    }}
    .tag.pass {{ color: var(--pass-text); border-color: var(--pass); }}
    .tag.drift {{ color: var(--drift-text); border-color: var(--drift); }}
    .tag.reject {{ color: var(--reject-text); border-color: var(--reject); }}
    .tag.spec {{ color: var(--spec-text); border-color: var(--spec); }}
    .tag.sim {{ border-style: dashed; color: var(--ink-muted); }}
    .numeral-note {{ font-size: 12px; color: var(--ink-muted); margin-top: 16px; }}

    /* Summary stats — ledger cells */
    .stat-grid {{
      display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
      margin-top: 16px;
    }}
    .stat-box {{
      background: var(--sunk); padding: 12px; border: 1px solid var(--hairline);
      text-align: center;
    }}
    .stat-val {{
      font-family: var(--font-mono); font-size: 20px; font-weight: 600;
      font-variant-numeric: tabular-nums;
    }}
    .stat-lbl {{
      font-family: var(--font-mono); font-size: 11px; color: var(--ink-muted);
      letter-spacing: .05em; margin-top: 4px;
    }}

    /* Domain scorecards */
    .domain-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 16px; margin-bottom: 24px;
    }}
    .domain-card {{
      background: var(--surface); border: 1px solid var(--hairline);
      padding: 16px;
    }}
    .domain-header {{
      display: flex; justify-content: space-between; align-items: baseline;
      margin-bottom: 8px;
    }}
    .domain-title {{ font-size: 13px; font-weight: 600; }}
    .domain-score {{
      font-family: var(--font-mono); font-size: 13px; font-weight: 600;
      font-variant-numeric: tabular-nums;
    }}
    .prog-track {{
      background: var(--hairline); height: 4px; margin-bottom: 8px;
    }}
    .prog-fill {{ height: 100%; }}
    .domain-meta {{
      display: flex; justify-content: space-between;
      font-family: var(--font-mono); font-size: 11px; color: var(--ink-muted);
    }}

    /* Blockers — drift-tinted, quiet left rule */
    .blockers-section {{
      background: var(--surface); border: 1px solid var(--hairline);
      padding: 24px; margin-bottom: 24px;
    }}
    .blockers-header {{
      display: flex; align-items: baseline; gap: 12px;
      margin-bottom: 8px;
    }}
    .blockers-header h2 {{
      font-family: var(--font-display); font-size: 18px; font-weight: 800;
      letter-spacing: -.01em;
    }}
    .blocker-cards {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 12px; margin-top: 16px;
    }}
    .blocker-item {{
      background: var(--paper); border: 1px solid var(--hairline);
      border-left: 2px solid var(--reject); padding: 12px 16px;
    }}
    .blocker-title {{
      font-size: 13px; font-weight: 600;
      display: flex; justify-content: space-between; gap: 8px;
    }}
    .blocker-id {{ font-family: var(--font-mono); color: var(--spec-text); }}
    .blocker-reason {{ font-size: 12px; color: var(--ink-muted); margin-top: 4px; }}
    .badge-chip {{
      font-family: var(--font-mono); font-size: 11px; letter-spacing: .04em;
      padding: 4px 8px; border: 1px solid var(--hairline); color: var(--ink-muted);
      white-space: nowrap;
    }}

    /* Gap matrix — ledger rows */
    .matrix-section, .guardian-section {{
      background: var(--surface); border: 1px solid var(--hairline);
      padding: 24px; margin-bottom: 24px;
    }}
    .matrix-toolbar {{
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 16px; gap: 12px; flex-wrap: wrap;
    }}
    .matrix-toolbar h2, .guardian-section h2 {{
      font-family: var(--font-display); font-size: 18px; font-weight: 800;
      letter-spacing: -.01em;
    }}
    .matrix-sub {{ font-size: 12px; color: var(--ink-muted); }}
    .search-input {{
      background: var(--paper); border: 1px solid var(--hairline);
      color: var(--ink); padding: 8px 12px; font-size: 13px; width: 280px;
      font-family: var(--font-body);
    }}
    .search-input:focus {{ border-color: var(--spec); }}
    .search-input::placeholder {{ color: var(--ink-muted); }}
    .filter-pills {{ display: flex; gap: 8px; }}
    .pill {{
      font-family: var(--font-mono); font-size: 11px; letter-spacing: .04em;
      padding: 8px 12px; border: 1px solid var(--hairline);
      color: var(--ink-muted); cursor: pointer; user-select: none;
    }}
    .pill.active {{ background: var(--ink); color: var(--paper); border-color: var(--ink); }}

    table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
    th {{
      font-family: var(--font-mono); font-weight: 600; text-align: left;
      color: var(--ink-muted); padding: 8px 12px;
      border-bottom: 1px solid var(--ink);
      font-size: 11px; letter-spacing: .06em;
    }}
    td {{
      padding: 8px 12px; border-bottom: 1px solid var(--hairline);
      vertical-align: middle;
    }}
    tr:hover td {{ background: var(--sunk); }}
    tr.flagged td {{ background: var(--sunk); }}
    tr.flagged td .artifact-name::before {{
      content: "◆"; color: var(--drift); margin-right: 8px; font-size: 9px;
    }}
    .aid {{ font-family: var(--font-mono); font-size: 11.5px; color: var(--spec-text); }}

    /* Guardian feed */
    .feed-item {{
      display: flex; justify-content: space-between; align-items: center;
      gap: 16px; border: 1px solid var(--hairline); border-left-width: 2px;
      padding: 12px 16px; margin-bottom: 8px; background: var(--paper);
    }}
    .feed-item.sev-high {{ border-left-color: var(--reject); }}
    .feed-item.sev-medium {{ border-left-color: var(--drift); }}
    .feed-item.sev-low {{ border-left-color: var(--hairline); }}
    .feed-title {{ font-size: 13px; font-weight: 600; }}
    .feed-desc {{ font-size: 12px; color: var(--ink-muted); }}
    .feed-meta {{ font-family: var(--font-mono); font-size: 11px; color: var(--ink-muted); margin-top: 4px; }}

    @media (max-width: 900px) {{
      .hero-grid {{ grid-template-columns: 1fr; }}
      .numeral {{ font-size: 72px; }}
      body {{ padding: 16px; }}
    }}
    @media print {{
      .btn, .matrix-toolbar .filter-pills, .search-input, .header-actions {{ display: none !important; }}
      .card, .matrix-section, .guardian-section, .blockers-section {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <!-- gstack-lint-disable absolute-surface-token: white is the approved surface token for cards and ledger sections on the paper ground -->
  <!-- gstack-lint-disable dead-band: app dashboard — the readiness numeral and inventory stats lead the fold; no marketing hero here -->
  <!-- gstack-lint-disable small-section-heads: gap matrix and guardian drift feed sections are app-surface headers at 18px per the component spec -->
  <!-- gstack-lint-disable thin-section: the domain-grid scorecards are the section mass — eight across at component density -->
  <!-- gstack-lint-disable placeholder-brand: Acme Cloud is the supplied example profile fixture, not placeholder copy -->
  <!-- gstack-lint-disable screen-word-budget: the gap matrix and guardian feed run at 36px ledger density per the component spec, not a marketing screen -->
  <a class="skip" href="#main">Skip to content</a>
  <div class="container">
    <div class="cert mono">
      <span class="brand">OpsGraph</span>
      <span class="cert-meta">
        <span>{comp_name}</span>
        <span>STAGE {stage_str} / {emp_count} FTE</span>
        <span>SCAN {scanned_date}</span>
        <span>[OBSERVED]</span>
      </span>
    </div>

    <main id="main">
    <div class="page-head">
      <div>
        <h1>Readiness instrument</h1>
        <p class="head-sub">Triggers: {triggers_str} — gap report and guardian digest for the 31-node operating graph.</p>
      </div>
      <div class="header-actions">
        <button class="btn" onclick="window.print()">[ EXPORT PDF ]</button>
        <button class="btn btn-primary" onclick="document.getElementById('cliHint').hidden=false">[ APPLY VIA CLI ]</button>
      </div>
      <div id="cliHint" hidden class="cli-hint mono">
        Dashboards do not write. Apply via:
        <code>opsgraph apply --credentials creds.json --token token.json --approver "you@co" --execute</code>
      </div>
    </div>

    <!-- Numeral rail + inventory -->
    <div class="hero-grid">
      <div class="card numeral-block">
        <div class="num-label">READINESS</div>
        <div class="numeral">{score}</div>
        <div class="tolerance" role="img" aria-label="Needle at {score}; tolerance band is the top 25 percent">
          <div class="marker" style="left: {marker_left}%;"></div>
        </div>
        <div class="readout">
          <span class="tag {state_cls}">{state_tag}</span>
          <span class="tag drift">[DRIFT +{gap["missing_count"] + gap["present_stale_count"]}]</span>
        </div>
        <p class="numeral-note">Weighted readiness across Governance, Security, Finance, and People.</p>
      </div>

      <div class="card">
        <h2 style="font-family: var(--font-display); font-size: 18px; font-weight: 800; letter-spacing: -.01em; margin-bottom: 8px;">Workspace inventory</h2>
        <p class="matrix-sub">Scanned Google Workspace tenant against the 31-node operating graph ontology.</p>

        <div class="stat-grid">
          <div class="stat-box">
            <div class="stat-val" style="color: var(--pass-text);">{gap["present_current_count"]}</div>
            <div class="stat-lbl">PRESENT / CURRENT</div>
          </div>
          <div class="stat-box">
            <div class="stat-val" style="color: var(--drift-text);">{gap["present_stale_count"]}</div>
            <div class="stat-lbl">PRESENT / STALE</div>
          </div>
          <div class="stat-box">
            <div class="stat-val" style="color: var(--spec-text);">{gap["duplicate_count"]}</div>
            <div class="stat-lbl">DUPLICATE / CONFLICT</div>
          </div>
          <div class="stat-box">
            <div class="stat-val" style="color: var(--reject-text);">{gap["missing_count"]}</div>
            <div class="stat-lbl">MISSING / REQUIRED</div>
          </div>
        </div>

        <div style="margin-top: 16px; font-family: var(--font-mono); font-size: 11px; color: var(--ink-muted); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
          <span>NODES 31</span>
          <span>BLOCKERS <strong style="color: var(--reject-text);">{len(gap["immediate_blockers"])}</strong></span>
          <span>GUARDIAN HEALTH <strong>{guardian["health_score"]}%</strong></span>
        </div>
      </div>
    </div>

    <!-- Domain scorecards -->
    <h2 style="font-family: var(--font-display); font-size: 18px; font-weight: 800; letter-spacing: -.01em; margin-bottom: 12px;">Readiness by domain</h2>
    <div class="domain-grid" id="domainContainer"></div>

    <!-- Blockers -->
    <div class="blockers-section">
      <div class="blockers-header">
        <h2>Immediate blockers</h2>
        <span class="tag reject">[{len(gap["immediate_blockers"])} OPEN]</span>
      </div>
      <p class="matrix-sub">High-criticality items required for active enterprise sales, SOC 2, and investor diligence commitments.</p>
      <div class="blocker-cards" id="blockersContainer"></div>
    </div>

    <!-- Gap matrix -->
    <div class="matrix-section">
      <div class="matrix-toolbar">
        <div>
          <h2>Gap matrix</h2>
          <p class="matrix-sub">Required state vs observed workspace reality</p>
        </div>
        <div style="display: flex; gap: 12px; flex-wrap: wrap;">
          <input type="text" id="searchInput" class="search-input" placeholder="Search name, ID, or owner" aria-label="Search artifacts">
          <div class="filter-pills" role="group" aria-label="Filter by status">
            <div class="pill active" onclick="setFilter('ALL', this)">ALL</div>
            <div class="pill" onclick="setFilter('MISSING', this)">MISSING</div>
            <div class="pill" onclick="setFilter('PRESENT_STALE', this)">STALE</div>
            <div class="pill" onclick="setFilter('PRESENT_CURRENT', this)">CURRENT</div>
          </div>
        </div>
      </div>

      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>ARTIFACT</th>
            <th>DOMAIN</th>
            <th>CRITICALITY</th>
            <th>STATUS</th>
            <th>OWNER</th>
            <th>CADENCE</th>
            <th>FRAMEWORKS</th>
            <th>REMEDIATION</th>
          </tr>
        </thead>
        <tbody id="matrixTableBody"></tbody>
      </table>
    </div>

    <!-- Guardian feed -->
    <div class="guardian-section">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 8px;">
        <div>
          <h2>Guardian drift feed</h2>
          <p class="matrix-sub">Continuous monitoring / {guardian["total_drift_events"]} actionable events detected</p>
        </div>
        <span class="tag">[HEALTH {guardian["health_score"]}%]</span>
      </div>
      <div id="guardianFeedContainer"></div>
    </div>

  </main>
  </div>

  <script>
    const GAP_DATA = {gap_json_str};
    const GUARDIAN_DATA = {guardian_json_str};

    let activeFilter = 'ALL';
    let searchQuery = '';

    function sevClass(sev) {{
      return sev === 'HIGH' ? 'sev-high' : (sev === 'MEDIUM' ? 'sev-medium' : 'sev-low');
    }}
    function sevTag(sev) {{
      return sev === 'HIGH' ? '<span class="tag reject">[HIGH]</span>'
           : (sev === 'MEDIUM' ? '<span class="tag drift">[MEDIUM]</span>' : '<span class="tag">[LOW]</span>');
    }}
    function critColor(c) {{
      return c === 'high' ? 'var(--reject-text)' : (c === 'medium' ? 'var(--drift-text)' : 'var(--ink-muted)');
    }}
    function scoreColor(p) {{
      return p < 40 ? 'var(--reject)' : (p < 75 ? 'var(--drift)' : 'var(--pass)');
    }}

    function renderDomains() {{
      const container = document.getElementById('domainContainer');
      container.innerHTML = GAP_DATA.domain_scores.map(d => {{
        const color = scoreColor(d.percentage);
        const blockerText = d.missing_critical > 0
          ? `<span style="color: var(--reject-text); font-weight: 800;">[${{d.missing_critical}} BLOCKER(S)]</span>`
          : '<span style="color: var(--pass-text);">[CLEAR]</span>';
        return `
          <div class="domain-card">
            <div class="domain-header">
              <span class="domain-title">${{d.root_id}} ${{d.name}}</span>
              <span class="domain-score" style="color: ${{color}}">${{d.percentage}}%</span>
            </div>
            <div class="prog-track">
              <div class="prog-fill" style="width: ${{d.percentage}}%; background: ${{color}};"></div>
            </div>
            <div class="domain-meta">
              <span>${{d.earned_points}} / ${{d.total_points}} PTS</span>
              <span>${{blockerText}}</span>
            </div>
          </div>
        `;
      }}).join('');
    }}

    function renderBlockers() {{
      const container = document.getElementById('blockersContainer');
      container.innerHTML = GAP_DATA.immediate_blockers.map(b => {{
        const fw = b.framework_mappings.length > 0 ? b.framework_mappings.join(', ') : 'GOVERNANCE';
        return `
          <div class="blocker-item">
            <div class="blocker-title">
              <span><span class="blocker-id">${{b.artifact_id}}</span> ${{b.artifact_name}}</span>
              <span class="badge-chip">${{fw}}</span>
            </div>
            <div class="blocker-reason">${{b.remediation_action}}</div>
            <div class="feed-meta" style="margin-top: 8px; display: flex; justify-content: space-between;">
              <span>DOMAIN ${{b.root}} ${{b.root_name}}</span>
              <span>OWNER <strong>${{b.resolved_owner}}</strong></span>
            </div>
          </div>
        `;
      }}).join('');
    }}

    function renderMatrix() {{
      const tbody = document.getElementById('matrixTableBody');
      const filtered = GAP_DATA.items.filter(item => {{
        if (activeFilter !== 'ALL' && item.status !== activeFilter) return false;
        if (searchQuery) {{
          const q = searchQuery.toLowerCase();
          const matchName = item.artifact_name.toLowerCase().includes(q);
          const matchId = item.artifact_id.toLowerCase().includes(q);
          const matchOwner = item.resolved_owner.toLowerCase().includes(q);
          if (!matchName && !matchId && !matchOwner) return false;
        }}
        return true;
      }});

      if (filtered.length === 0) {{
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--ink-muted); padding: 20px;">[NO GAPS] — no artifacts match the current filter.</td></tr>`;
        return;
      }}

      tbody.innerHTML = filtered.map(item => {{
        let statusTag = '', flagged = '';
        if (item.status === 'PRESENT_CURRENT') statusTag = '<span class="tag pass">[CURRENT]</span>';
        else if (item.status === 'PRESENT_STALE') {{ statusTag = `<span class="tag drift">[STALE ${{item.days_stale}}D]</span>`; flagged = 'flagged'; }}
        else if (item.status === 'DUPLICATE_COLLISION') {{ statusTag = '<span class="tag spec">[DUP]</span>'; flagged = 'flagged'; }}
        else if (item.status === 'MISPLACED') {{ statusTag = '<span class="tag drift">[MISPLACED]</span>'; flagged = 'flagged'; }}
        else {{ statusTag = '<span class="tag reject">[MISSING]</span>'; flagged = 'flagged'; }}

        const fwStr = item.framework_mappings.length > 0 ? item.framework_mappings.join(', ') : '—';

        return `
          <tr class="${{flagged}}">
            <td class="aid">${{item.artifact_id}}</td>
            <td class="artifact-name"><strong>${{item.artifact_name}}</strong></td>
            <td>${{item.root}} ${{item.root_name}}</td>
            <td style="color: ${{critColor(item.criticality)}}; font-family: var(--font-mono); font-size: 11px;">${{item.criticality.toUpperCase()}}</td>
            <td>${{statusTag}}</td>
            <td>${{item.resolved_owner}}</td>
            <td style="font-family: var(--font-mono);">${{item.review_cadence_days}}D</td>
            <td><span class="badge-chip">${{fwStr}}</span></td>
            <td style="font-size: 11px; color: var(--ink-muted);">${{item.remediation_action}}</td>
          </tr>
        `;
      }}).join('');
    }}

    function renderGuardian() {{
      const container = document.getElementById('guardianFeedContainer');
      container.innerHTML = GUARDIAN_DATA.events.slice(0, 6).map(e => {{
        return `
          <div class="feed-item ${{sevClass(e.severity)}}">
            <div>
              <div class="feed-title">${{sevTag(e.severity)}} ${{e.title}}</div>
              <div class="feed-desc">${{e.description}}</div>
              <div class="feed-meta">OWNER <strong>${{e.assigned_owner}}</strong> / ACTION ${{e.remediation_proposal}}</div>
            </div>
            <div>
              <button class="btn" onclick="this.nextElementSibling.hidden=!this.nextElementSibling.hidden">[PROPOSE]</button>
              <div class="feed-hint" hidden>[SIMULATION] — approval required before any apply</div>
            </div>
          </div>
        `;
      }}).join('');
    }}

    function setFilter(filter, el) {{
      activeFilter = filter;
      document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
      el.classList.add('active');
      renderMatrix();
    }}

    document.getElementById('searchInput').addEventListener('input', (e) => {{
      searchQuery = e.target.value;
      renderMatrix();
    }});

    renderDomains();
    renderBlockers();
    renderMatrix();
    renderGuardian();
  </script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="OpsGraph HTML Dashboard Generator")
    parser.add_argument("profile", help="Path to company profile JSON")
    parser.add_argument("inventory", help="Path to workspace inventory JSON")
    parser.add_argument("--output", default="dashboard.html", help="Output HTML file path")
    parser.add_argument("--open", action="store_true", help="Open generated dashboard in browser")

    args = parser.parse_args()

    with open(args.profile, "r", encoding="utf-8") as f:
        profile_data = json.load(f)

    scanner = WorkspaceScanner()
    inventory_snapshot = scanner.load_snapshot(Path(args.inventory))

    generator = DashboardGenerator()
    out_path = Path(args.output).resolve()
    generator.generate(profile_data, inventory_snapshot, output_path=out_path)

    print(f"dashboard generated: {out_path}")

    if args.open:
        import webbrowser
        webbrowser.open(f"file://{out_path}")


if __name__ == "__main__":
    main()
