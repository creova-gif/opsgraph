#!/usr/bin/env python3
"""
Company OS — Interactive Visual Dashboard & HTML Report Generator (v0.1)
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
        comp_name = profile["company"].get("legal_name", "Company OS Client")
        stage_str = profile["stage"].get("funding_stage", "Seed").upper()
        emp_count = profile["stage"].get("employee_count", 1)
        triggers_str = ", ".join(profile.get("triggers", []))
        score = gap["infrastructure_score"]
        scanned_date = gap["scanned_at"]

        # SVG Circle math: circumference = 2 * pi * r = 2 * 3.14159 * 54 = 339.292
        circumference = 339.292
        offset = circumference - (score / 100.0) * circumference
        score_color = "#ef4444" if score < 40 else ("#f59e0b" if score < 75 else "#10b981")
        badge_text = "CRITICAL DUE DILIGENCE GAPS" if score < 40 else ("PROGRESSING INFRASTRUCTURE" if score < 75 else "ENTERPRISE READY")
        badge_bg = "rgba(239, 68, 68, 0.15)" if score < 40 else ("rgba(245, 158, 11, 0.15)" if score < 75 else "rgba(16, 185, 129, 0.15)")

        gap_json_str = json.dumps(gap).replace("</script>", "<\\/script>")
        guardian_json_str = json.dumps(guardian).replace("</script>", "<\\/script>")

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{comp_name} — Company OS Readiness Dashboard</title>
  <style>
    :root {{
      --bg-base: #0b0f19;
      --bg-surface: #111827;
      --bg-elevated: #1f2937;
      --border: #374151;
      --border-focus: #6366f1;
      --text-main: #f9fafb;
      --text-muted: #9ca3af;
      --text-dim: #6b7280;
      --accent: #6366f1;
      --accent-glow: rgba(99, 102, 241, 0.2);
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg-base);
      color: var(--text-main);
      font-family: var(--font-sans);
      line-height: 1.5;
      padding: 24px;
    }}

    .container {{
      max-width: 1280px;
      margin: 0 auto;
    }}

    /* Header Nav */
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 24px;
    }}
    .brand-title {{
      font-size: 20px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .brand-pill {{
      background: var(--accent-glow);
      color: #818cf8;
      border: 1px solid var(--accent);
      padding: 2px 8px;
      border-radius: 9999px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .header-actions {{
      display: flex;
      gap: 12px;
    }}
    .btn {{
      background: var(--bg-elevated);
      color: var(--text-main);
      border: 1px solid var(--border);
      padding: 8px 16px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s ease;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .btn:hover {{
      background: #283548;
      border-color: #4b5563;
    }}
    .btn-primary {{
      background: #4f46e5;
      border-color: #6366f1;
    }}
    .btn-primary:hover {{
      background: #4338ca;
    }}

    /* Top Grid */
    .hero-grid {{
      display: grid;
      grid-template-columns: 340px 1fr;
      gap: 20px;
      margin-bottom: 24px;
    }}
    .card {{
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      position: relative;
    }}

    /* Score Dial */
    .dial-container {{
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      justify-content: center;
    }}
    .svg-dial {{
      transform: rotate(-90deg);
      width: 140px;
      height: 140px;
    }}
    .dial-bg {{
      fill: none;
      stroke: var(--bg-elevated);
      stroke-width: 12;
    }}
    .dial-val {{
      fill: none;
      stroke: {score_color};
      stroke-width: 12;
      stroke-linecap: round;
      stroke-dasharray: {circumference};
      stroke-dashoffset: {offset};
      transition: stroke-dashoffset 1s ease-out;
    }}
    .dial-text {{
      position: absolute;
      top: 55px;
      font-size: 32px;
      font-weight: 800;
      font-family: var(--font-mono);
      color: var(--text-main);
    }}
    .dial-badge {{
      margin-top: 16px;
      padding: 4px 12px;
      border-radius: 9999px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.05em;
      color: {score_color};
      background: {badge_bg};
      border: 1px solid {score_color};
    }}

    /* Summary Stats */
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin-top: 16px;
    }}
    .stat-box {{
      background: var(--bg-elevated);
      padding: 12px;
      border-radius: 8px;
      border: 1px solid var(--border);
      text-align: center;
    }}
    .stat-val {{
      font-size: 20px;
      font-weight: 700;
      font-family: var(--font-mono);
    }}
    .stat-lbl {{
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-top: 2px;
    }}

    /* Domain Grid */
    .domain-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .domain-card {{
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px 16px;
    }}
    .domain-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }}
    .domain-title {{
      font-size: 13px;
      font-weight: 600;
    }}
    .domain-score {{
      font-family: var(--font-mono);
      font-size: 13px;
      font-weight: 700;
    }}
    .prog-track {{
      background: var(--bg-elevated);
      height: 6px;
      border-radius: 9999px;
      overflow: hidden;
      margin-bottom: 8px;
    }}
    .prog-fill {{
      height: 100%;
      background: var(--accent);
      border-radius: 9999px;
      transition: width 0.5s ease;
    }}
    .domain-meta {{
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      color: var(--text-muted);
    }}

    /* Immediate Blockers Banner */
    .blockers-section {{
      background: rgba(239, 68, 68, 0.05);
      border: 1px solid rgba(239, 68, 68, 0.3);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 24px;
    }}
    .blockers-header {{
      display: flex;
      align-items: center;
      gap: 8px;
      color: #f87171;
      font-size: 15px;
      font-weight: 700;
      margin-bottom: 12px;
    }}
    .blocker-cards {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 12px;
    }}
    .blocker-item {{
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-left: 3px solid var(--danger);
      border-radius: 6px;
      padding: 12px 14px;
    }}
    .blocker-title {{
      font-size: 13px;
      font-weight: 600;
      display: flex;
      justify-content: space-between;
    }}
    .blocker-reason {{
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 4px;
    }}
    .badge-chip {{
      font-size: 10px;
      padding: 2px 6px;
      border-radius: 4px;
      font-family: var(--font-mono);
      background: var(--bg-elevated);
      color: #cbd5e1;
    }}

    /* Controls Bar & Matrix Table */
    .matrix-section {{
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 24px;
    }}
    .matrix-toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .search-input {{
      background: var(--bg-elevated);
      border: 1px solid var(--border);
      color: var(--text-main);
      padding: 8px 14px;
      border-radius: 6px;
      font-size: 13px;
      width: 280px;
    }}
    .search-input:focus {{
      outline: none;
      border-color: var(--border-focus);
    }}
    .filter-pills {{
      display: flex;
      gap: 8px;
    }}
    .pill {{
      background: var(--bg-elevated);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 6px 12px;
      border-radius: 9999px;
      font-size: 12px;
      cursor: pointer;
      user-select: none;
      transition: all 0.2s;
    }}
    .pill.active {{
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      text-align: left;
    }}
    th {{
      background: var(--bg-elevated);
      color: var(--text-muted);
      font-weight: 600;
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      text-transform: uppercase;
      font-size: 10px;
      letter-spacing: 0.05em;
    }}
    td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      color: #e2e8f0;
    }}
    tr:hover td {{
      background: rgba(255, 255, 255, 0.02);
    }}

    .status-tag {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 8px;
      border-radius: 4px;
      font-weight: 600;
      font-size: 11px;
    }}
    .tag-current {{ background: rgba(16, 185, 129, 0.15); color: #34d399; }}
    .tag-stale {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; }}
    .tag-missing {{ background: rgba(239, 68, 68, 0.15); color: #f87171; }}
    .tag-conflict {{ background: rgba(168, 85, 247, 0.15); color: #c084fc; }}
    .tag-misplaced {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; }}

    /* Guardian Feed */
    .guardian-section {{
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 24px;
    }}
    .feed-item {{
      background: var(--bg-elevated);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 16px;
      margin-bottom: 10px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .feed-info {{
      display: flex;
      flex-direction: column;
      gap: 2px;
    }}
    .feed-title {{
      font-size: 13px;
      font-weight: 600;
    }}
    .feed-desc {{
      font-size: 12px;
      color: var(--text-muted);
    }}

    /* Print styles */
    @media print {{
      body {{ background: #fff; color: #000; padding: 0; }}
      .btn, .matrix-toolbar, .header-actions {{ display: none !important; }}
      .card, .matrix-section, .domain-card, .blockers-section {{ border: 1px solid #ccc; background: #fff; color: #000; }}
      th {{ background: #f3f4f6; color: #111; }}
      td {{ color: #111; border-bottom: 1px solid #ddd; }}
      .stat-box {{ background: #f9fafb; border: 1px solid #ccc; }}
      .badge-chip {{ background: #e5e7eb; color: #111; }}
    }}
  </style>
</head>
<body>

  <div class="container">
    <!-- Header -->
    <header>
      <div>
        <div class="brand-title">
          <span>{comp_name}</span>
          <span class="brand-pill">Company OS Beta</span>
        </div>
        <p style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
          Stage: <strong>{stage_str}</strong> ({emp_count} FTE) • Triggers: <strong>{triggers_str}</strong> • Audit Date: <strong>{scanned_date}</strong>
        </p>
      </div>
      <div class="header-actions">
        <button class="btn" onclick="window.print()">
          <span>🖨️</span> Export Executive PDF
        </button>
        <button class="btn btn-primary" onclick="alert('Compiler execution launched directly to Google Drive.')">
          <span>⚡</span> Reconcile in Google Drive
        </button>
      </div>
    </header>

    <!-- Hero / Dial Grid -->
    <div class="hero-grid">
      <!-- Dial Card -->
      <div class="card dial-container">
        <div style="position: relative; width: 140px; height: 140px;">
          <svg class="svg-dial" viewBox="0 0 120 120">
            <circle class="dial-bg" cx="60" cy="60" r="54"></circle>
            <circle class="dial-val" cx="60" cy="60" r="54"></circle>
          </svg>
          <div class="dial-text">{score}%</div>
        </div>
        <div class="dial-badge">{badge_text}</div>
        <p style="font-size: 11px; color: var(--text-muted); margin-top: 12px;">
          Weighted operational readiness across Governance, Security, Finance, and People.
        </p>
      </div>

      <!-- Quick Stats Card -->
      <div class="card">
        <h3 style="font-size: 14px; font-weight: 600; margin-bottom: 8px;">Workspace Inventory Status</h3>
        <p style="font-size: 12px; color: var(--text-muted);">
          Scanned Google Workspace tenant against the 31-node Operating Graph ontology.
        </p>

        <div class="summary-grid">
          <div class="stat-box">
            <div class="stat-val" style="color: var(--success);">{gap["present_current_count"]}</div>
            <div class="stat-lbl">Present & Current</div>
          </div>
          <div class="stat-box">
            <div class="stat-val" style="color: var(--warning);">{gap["present_stale_count"]}</div>
            <div class="stat-lbl">Present but Stale</div>
          </div>
          <div class="stat-box">
            <div class="stat-val" style="color: #c084fc;">{gap["duplicate_count"]}</div>
            <div class="stat-lbl">Duplicate Conflicts</div>
          </div>
          <div class="stat-box">
            <div class="stat-val" style="color: var(--danger);">{gap["missing_count"]}</div>
            <div class="stat-lbl">Missing Required</div>
          </div>
        </div>

        <div style="margin-top: 16px; font-size: 12px; color: var(--text-muted); display: flex; justify-content: space-between;">
          <span>Total Operational Nodes: <strong>31</strong></span>
          <span>Immediate Due Diligence Blockers: <strong style="color: var(--danger);">{len(gap["immediate_blockers"])}</strong></span>
          <span>Guardian Health Score: <strong>{guardian["health_score"]}%</strong></span>
        </div>
      </div>
    </div>

    <!-- Domain Readiness Scorecards -->
    <h3 style="font-size: 14px; font-weight: 600; margin-bottom: 12px;">Readiness by Operational Domain</h3>
    <div class="domain-grid" id="domainContainer">
      <!-- Injected via JS -->
    </div>

    <!-- Immediate Blockers Callout -->
    <div class="blockers-section">
      <div class="blockers-header">
        <span>🚨</span>
        <span>Immediate Deal & Due Diligence Blockers ({len(gap["immediate_blockers"])})</span>
      </div>
      <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 12px;">
        These high-criticality items are required for your active enterprise sales, SOC 2, and investor diligence commitments:
      </p>
      <div class="blocker-cards" id="blockersContainer">
        <!-- Injected via JS -->
      </div>
    </div>

    <!-- Interactive Gap Matrix Table -->
    <div class="matrix-section">
      <div class="matrix-toolbar">
        <div>
          <h3 style="font-size: 15px; font-weight: 700;">Operating Graph Gap Matrix</h3>
          <p style="font-size: 12px; color: var(--text-muted);">Required State vs Observed Workspace Reality</p>
        </div>
        <div style="display: flex; gap: 10px;">
          <input type="text" id="searchInput" class="search-input" placeholder="Search by name, ID, or owner...">
          <div class="filter-pills">
            <div class="pill active" onclick="setFilter('ALL', this)">All (31)</div>
            <div class="pill" onclick="setFilter('MISSING', this)">Missing (🔴)</div>
            <div class="pill" onclick="setFilter('PRESENT_STALE', this)">Stale (🟡)</div>
            <div class="pill" onclick="setFilter('PRESENT_CURRENT', this)">Current (🟢)</div>
          </div>
        </div>
      </div>

      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Artifact Title</th>
            <th>Domain</th>
            <th>Criticality</th>
            <th>Status</th>
            <th>Owner</th>
            <th>Cadence</th>
            <th>Frameworks</th>
            <th>Actionable Remediation</th>
          </tr>
        </thead>
        <tbody id="matrixTableBody">
          <!-- Injected via JS -->
        </tbody>
      </table>
    </div>

    <!-- Active Guardian Drift Feed -->
    <div class="guardian-section">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <div>
          <h3 style="font-size: 15px; font-weight: 700;">Active Company Guardian Feed</h3>
          <p style="font-size: 12px; color: var(--text-muted);">
            Continuous drift monitoring • {guardian["total_drift_events"]} actionable events detected
          </p>
        </div>
        <span class="badge-chip" style="background: rgba(99, 102, 241, 0.2); color: #818cf8;">
          Weekly Health Score: {guardian["health_score"]}%
        </span>
      </div>

      <div id="guardianFeedContainer">
        <!-- Injected via JS -->
      </div>
    </div>

  </div>

  <script>
    const GAP_DATA = {gap_json_str};
    const GUARDIAN_DATA = {guardian_json_str};

    let activeFilter = 'ALL';
    let searchQuery = '';

    // Render Domains
    function renderDomains() {{
      const container = document.getElementById('domainContainer');
      container.innerHTML = GAP_DATA.domain_scores.map(d => {{
        const color = d.percentage < 40 ? 'var(--danger)' : (d.percentage < 75 ? 'var(--warning)' : 'var(--success)');
        const blockerText = d.missing_critical > 0 ? `<span style="color: var(--danger); font-weight: 700;">🔴 ${{d.missing_critical}} Blocker(s)</span>` : '<span style="color: var(--success);">🟢 Clear</span>';
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
              <span>${{d.earned_points}} / ${{d.total_points}} pts</span>
              <span>${{blockerText}}</span>
            </div>
          </div>
        `;
      }}).join('');
    }}

    // Render Blockers
    function renderBlockers() {{
      const container = document.getElementById('blockersContainer');
      container.innerHTML = GAP_DATA.immediate_blockers.map(b => {{
        const fw = b.framework_mappings.length > 0 ? b.framework_mappings.join(', ') : 'Governance';
        return `
          <div class="blocker-item">
            <div class="blocker-title">
              <span><strong>${{b.artifact_id}}</strong> — ${{b.artifact_name}}</span>
              <span class="badge-chip">${{fw}}</span>
            </div>
            <div class="blocker-reason">
              ${{b.remediation_action}}
            </div>
            <div style="margin-top: 8px; font-size: 11px; color: var(--text-muted); display: flex; justify-content: space-between;">
              <span>Domain: ${{b.root}} ${{b.root_name}}</span>
              <span>Owner: <strong>${{b.resolved_owner}}</strong></span>
            </div>
          </div>
        `;
      }}).join('');
    }}

    // Render Matrix Table
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
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 20px;">No artifacts match the current filter.</td></tr>`;
        return;
      }}

      tbody.innerHTML = filtered.map(item => {{
        let statusTag = '';
        if (item.status === 'PRESENT_CURRENT') statusTag = '<span class="status-tag tag-current">🟢 Current</span>';
        else if (item.status === 'PRESENT_STALE') statusTag = `<span class="status-tag tag-stale">🟡 Stale (${{item.days_stale}}d)</span>`;
        else if (item.status === 'DUPLICATE_COLLISION') statusTag = '<span class="status-tag tag-conflict">⚠️ Duplicate</span>';
        else if (item.status === 'MISPLACED') statusTag = '<span class="status-tag tag-misplaced">📦 Misplaced</span>';
        else statusTag = '<span class="status-tag tag-missing">🔴 Missing</span>';

        const critColor = item.criticality === 'high' ? 'var(--danger)' : (item.criticality === 'medium' ? 'var(--warning)' : 'var(--text-muted)');
        const fwStr = item.framework_mappings.length > 0 ? item.framework_mappings.join(', ') : '—';

        return `
          <tr>
            <td style="font-family: var(--font-mono); font-weight: 700;">${{item.artifact_id}}</td>
            <td><strong>${{item.artifact_name}}</strong></td>
            <td>${{item.root}} ${{item.root_name}}</td>
            <td style="color: ${{critColor}}; font-weight: 600;">${{item.criticality.toUpperCase()}}</td>
            <td>${{statusTag}}</td>
            <td>${{item.resolved_owner}}</td>
            <td>${{item.review_cadence_days}}d</td>
            <td><span class="badge-chip">${{fwStr}}</span></td>
            <td style="font-size: 11px; color: var(--text-muted);">${{item.remediation_action}}</td>
          </tr>
        `;
      }}).join('');
    }}

    // Render Guardian Feed
    function renderGuardian() {{
      const container = document.getElementById('guardianFeedContainer');
      container.innerHTML = GUARDIAN_DATA.events.slice(0, 6).map(e => {{
        const color = e.severity === 'HIGH' ? 'var(--danger)' : (e.severity === 'MEDIUM' ? 'var(--warning)' : 'var(--text-muted)');
        return `
          <div class="feed-item">
            <div class="feed-info">
              <div class="feed-title">
                <span style="color: ${{color}}; font-weight: 700;">[${{e.severity}}]</span>
                ${{e.title}}
              </div>
              <div class="feed-desc">${{e.description}}</div>
              <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
                Assigned to: <strong>${{e.assigned_owner}}</strong> • Action: ${{e.remediation_proposal}}
              </div>
            </div>
            <button class="btn" onclick="alert('Simulated 1-click fix: ${{e.remediation_proposal}}')">
              ⚡ Fix
            </button>
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

    // Init
    renderDomains();
    renderBlockers();
    renderMatrix();
    renderGuardian();
  </script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="Company OS HTML Dashboard Generator")
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

    print(f"✅ Interactive Dashboard generated: {out_path}")

    if args.open:
        import webbrowser
        webbrowser.open(f"file://{out_path}")


if __name__ == "__main__":
    main()
