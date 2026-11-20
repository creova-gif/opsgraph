#!/usr/bin/env python3
"""
OpsGraph — Operational Readiness Certificate generator.

Renders the CALIBRATION-series certificate (docs/design/certificate.html)
filled with real engine output: gap score, drift counts, ruleset version,
approver chain. It certifies a measurement, not compliance — the
attestation line stays verbatim on every render.
"""

from __future__ import annotations

import datetime
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

from dashboard.generator import _load_tokens
from gap_engine.analyzer import GapAnalyzer
from guardian.guardian import CompanyGuardian
from inventory.scanner import InventorySnapshot
from resolver.resolver import StateResolver
from store.store import company_id_for


class CertificateGenerator:
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
        approver: Optional[str] = None,
        run_ref: Optional[str] = None,
    ) -> str:
        resolution = self.resolver.resolve(profile_data)
        gap = self.analyzer.analyze(resolution, inventory)
        digest = self.guardian.audit(profile_data, inventory)

        score = gap.infrastructure_score
        if score < 40:
            tag, tag_cls = "[CRITICAL DRIFT]", "reject"
        elif score < 75:
            tag, tag_cls = "[DRIFT]", "drift"
        else:
            tag, tag_cls = "[IN TOLERANCE]", "pass"

        slug = company_id_for(profile_data)
        scan_date = gap.scanned_at.split(" ")[0].replace("-", "")
        cert_no = f"OG-{slug[:6].upper()}-{scan_date}"
        domain = (profile_data.get("workspace") or {}).get("domain", slug)
        ruleset = f"opsgraph-seed@{self.resolver.rules_data.get('version', '0.2')}"
        flagged = sum(1 for i in gap.items if i.status != "PRESENT_CURRENT")
        marker = min(max(score, 0), 100)

        tokens = _load_tokens()
        return _TEMPLATE.format(
            tokens=tokens,
            cert_no=cert_no,
            score=f"{score:g}",
            marker=marker,
            tag=tag,
            tag_cls=tag_cls,
            company=gap.company_name,
            domain=domain,
            ruleset=ruleset,
            scanned_at=gap.scanned_at,
            artifact_count=len(gap.items),
            flagged=flagged,
            drift_events=digest.total_drift_events,
            missing=gap.missing_count,
            stale=gap.present_stale_count,
            approver=approver or "unrecorded",
            chain=run_ref or "generated from live engines",
        )


_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Operational Readiness Certificate</title>
<link href="https://api.fontshare.com/v2/css?f[]=cabinet-grotesk@700,800&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@0,400;0,600&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{{
  --paper:{tokens[paper]}; --surface:{tokens[surface]}; --sunk:{tokens[sunk]};
  --ink:{tokens[ink]}; --ink-muted:{tokens[ink-muted]}; --hairline:{tokens[hairline]};
  --spec:{tokens[spec]}; --drift:{tokens[drift]}; --drift-text:{tokens[drift-text]};
  --pass:{tokens[pass]}; --pass-text:{tokens[pass-text]};
  --reject:{tokens[reject]}; --reject-text:{tokens[reject-text]};
  --font-display:"Cabinet Grotesk",sans-serif; --font-body:"Instrument Sans",sans-serif;
  --font-mono:"JetBrains Mono",monospace;
}}
@page{{size:letter landscape;margin:0}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--paper);color:var(--ink);font-family:var(--font-body);-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.mono{{font-family:var(--font-mono)}}
.sheet{{width:11in;height:8.5in;padding:.55in .7in;position:relative;display:flex;flex-direction:column}}
.frame{{position:absolute;inset:.28in;border:1px solid var(--ink);pointer-events:none}}
.frame::after{{content:"";position:absolute;inset:5px;border:1px solid var(--hairline)}}
.cert-head{{display:flex;justify-content:space-between;align-items:baseline;font-size:11px;letter-spacing:.08em;color:var(--ink-muted)}}
.title-band{{display:flex;justify-content:space-between;align-items:flex-end;margin-top:.5in;gap:.5in}}
.mark{{display:flex;align-items:center;gap:10px}}
.mark svg{{width:44px;height:44px}}
.wordmark{{font-family:var(--font-display);font-weight:700;font-size:15px;letter-spacing:.02em}}
h1{{font-family:var(--font-display);font-weight:800;font-size:44px;letter-spacing:-.01em;line-height:1.05;max-width:6.4in;margin-top:14px}}
.cert-kind{{font-size:11px;letter-spacing:.08em;color:var(--ink-muted);margin-top:10px}}
.numeral-block{{text-align:right;flex-shrink:0;border-left:1px solid var(--hairline);padding-left:.4in}}
.num-label{{font-size:11px;letter-spacing:.08em;color:var(--ink-muted)}}
.numeral{{font-family:var(--font-display);font-weight:800;font-size:110px;line-height:.9;letter-spacing:-.03em;font-variant-numeric:tabular-nums}}
.tolerance{{width:120px;height:3px;background:var(--hairline);position:relative;margin:10px 0 8px auto}}
.tolerance::after{{content:"";position:absolute;right:0;top:0;height:100%;width:27%;background:var(--pass)}}
.marker{{position:absolute;top:-5px;width:2px;height:13px;background:var(--ink)}}
.tag{{font-family:var(--font-mono);font-size:11px;letter-spacing:.05em;padding:3px 8px;border:1px solid currentColor}}
.tag.pass{{color:var(--pass-text)}}
.tag.drift{{color:var(--drift-text)}}
.tag.reject{{color:var(--reject-text)}}
.fields{{margin-top:.45in;border-top:1px solid var(--ink)}}
.frow{{display:grid;grid-template-columns:1.1in 1fr 1.1in 1fr;gap:.15in .3in;padding:10px 0;border-bottom:1px solid var(--hairline)}}
.k{{font-family:var(--font-mono);font-size:11px;letter-spacing:.06em;color:var(--ink-muted)}}
.v{{font-size:13px}}
.attest{{margin-top:.35in;display:grid;grid-template-columns:1fr 1fr 1fr;gap:.4in}}
.sig{{font-size:11px;line-height:1.5;color:var(--ink-muted);border-top:1px solid var(--ink);padding-top:8px}}
.cert-foot{{margin-top:auto;display:flex;justify-content:space-between;font-family:var(--font-mono);font-size:11px;letter-spacing:.08em;color:var(--ink-muted)}}
</style>
</head>
<body>
<div class="sheet">
  <div class="frame"></div>

  <div class="cert-head mono">
    <span>CERT {cert_no} · REV B</span>
    <span>INSTRUMENT OF OPERATIONAL READINESS</span>
    <span>[OBSERVED]</span>
  </div>

  <div class="title-band">
    <div class="title-left">
      <div class="mark">
        <svg viewBox="0 0 48 48" aria-hidden="true">
          <circle cx="24" cy="24" r="21" fill="none" stroke="#1B1A17" stroke-width="2.5"/>
          <line x1="24" y1="4.5" x2="24" y2="9" stroke="#1B1A17" stroke-width="2.5"/>
          <line x1="41" y1="12" x2="37" y2="14.5" stroke="#1B1A17" stroke-width="2.5"/>
          <line x1="41" y1="36" x2="37" y2="33.5" stroke="#1B1A17" stroke-width="2.5"/>
          <line x1="24" y1="43.5" x2="24" y2="39" stroke="#1B1A17" stroke-width="2.5"/>
          <line x1="7" y1="36" x2="11" y2="33.5" stroke="#1B1A17" stroke-width="2.5"/>
          <line x1="24" y1="24" x2="34" y2="12" stroke="#1B1A17" stroke-width="2.5"/>
          <circle cx="24" cy="24" r="3" fill="#1B1A17"/>
        </svg>
        <span class="wordmark">OpsGraph</span>
      </div>
      <h1>Operational Readiness Certificate</h1>
      <div class="cert-kind mono">WORKSPACE INVENTORY / GAP MEASUREMENT / CALIBRATION RECORD</div>
    </div>
    <div class="numeral-block">
      <div class="num-label mono">READINESS</div>
      <div class="numeral">{score}</div>
      <div class="tolerance"><div class="marker" style="left:{marker}%"></div></div>
      <div class="readout"><span class="tag {tag_cls}">{tag}</span></div>
    </div>
  </div>

  <div class="fields">
    <div class="frow">
      <div class="k">COMPANY</div><div class="v">{company}</div>
      <div class="k">CERT NO</div><div class="v">{cert_no}</div>
    </div>
    <div class="frow">
      <div class="k">WORKSPACE</div><div class="v">Google Drive / {domain}</div>
      <div class="k">RULESET</div><div class="v">{ruleset}</div>
    </div>
    <div class="frow">
      <div class="k">SCAN</div><div class="v">{scanned_at}</div>
      <div class="k">MEASUREMENT</div><div class="v">{artifact_count} artifacts / {flagged} flagged / {drift_events} drift events</div>
    </div>
    <div class="frow">
      <div class="k">READING</div><div class="v">READINESS {score} · {missing} missing · {stale} stale · {tag}</div>
      <div class="k">NEXT CHECK</div><div class="v">Guardian watch / continuous</div>
    </div>
    <div class="frow">
      <div class="k">APPROVER</div><div class="v">{approver}</div>
      <div class="k">CHAIN</div><div class="v">{chain}</div>
    </div>
  </div>

  <div class="attest">
    <div class="sig">OBSERVED — Workspace inventory from a credentialed scan.
      Simulated outputs are marked [SIMULATION] and never counted as observed state.</div>
    <div class="sig">REQUIRED — Measured against the stage-appropriate ruleset.
      Gap report is deterministic and reproducible from the same snapshot.</div>
    <div class="sig">GATED — No consequential change without recorded approval.
      This certificate certifies a measurement, not compliance.</div>
  </div>

  <div class="cert-foot">
    <span>OPSGRAPH / CALIBRATION SERIES</span>
    <span>PAGE 1 OF 1</span>
  </div>
</div>
</body>
</html>
"""


def main():
    import argparse
    import json
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from inventory.scanner import WorkspaceScanner

    p = argparse.ArgumentParser(description="Generate an Operational Readiness Certificate")
    p.add_argument("profile")
    p.add_argument("inventory")
    p.add_argument("--output", default="certificate.html")
    p.add_argument("--approver", default=None)
    p.add_argument("--run-ref", default=None)
    args = p.parse_args()

    with open(args.profile, encoding="utf-8") as f:
        profile = json.load(f)
    inventory = WorkspaceScanner().load_snapshot(Path(args.inventory))
    html = CertificateGenerator().generate(profile, inventory,
                                           approver=args.approver,
                                           run_ref=args.run_ref)
    Path(args.output).write_text(html, encoding="utf-8")
    print(f"Certificate written: {args.output}")


if __name__ == "__main__":
    main()
