#!/usr/bin/env bun
/**
 * Company OS — State Resolver (TypeScript / Bun entry point)
 */

import { readFileSync, existsSync } from "fs";
import { resolve, dirname } from "path";

const STAGE_HIERARCHY: Record<string, number> = {
  idea: 0,
  pre_seed: 1,
  seed: 2,
  series_a: 3,
  series_b_plus: 4,
  bootstrapped: 2,
};

interface Condition {
  stage_gte?: string;
  stage_in?: string[];
  employees_gte?: number;
  triggers_any?: string[];
  regulated_in?: string[];
}

interface Override {
  when: Condition;
  level: string;
}

interface ArtifactNode {
  id: string;
  name: string;
  root: string;
  type: string;
  criticality: string;
  owner_role: string;
  review_cadence_days: number;
  depends_on?: string[];
  evidence_types?: string[];
  framework_mappings?: string[];
  requirement: {
    default: string;
    overrides?: Override[];
  };
  why: string;
}

function evaluateCondition(
  cond: Condition,
  stage: string,
  employees: number,
  triggers: string[],
  regulated: string[]
): [boolean, string] {
  if (cond.stage_gte) {
    const target = cond.stage_gte.toLowerCase();
    const currVal = STAGE_HIERARCHY[stage] || 0;
    const tgtVal = STAGE_HIERARCHY[target] || 0;
    if (currVal >= tgtVal) return [true, `Stage ${stage} >= ${target}`];
    return [false, ""];
  }
  if (cond.stage_in) {
    const targets = cond.stage_in.map((s) => s.toLowerCase());
    if (targets.includes(stage)) return [true, `Stage ${stage} in [${targets}]`];
    return [false, ""];
  }
  if (cond.employees_gte !== undefined) {
    if (employees >= cond.employees_gte) return [true, `Headcount ${employees} >= ${cond.employees_gte}`];
    return [false, ""];
  }
  if (cond.triggers_any) {
    const matched = cond.triggers_any.filter((t) => triggers.includes(t));
    if (matched.length > 0) return [true, `Matched trigger(s): ${matched.join(", ")}`];
    return [false, ""];
  }
  if (cond.regulated_in) {
    const matched = cond.regulated_in.filter((r) => regulated.includes(r));
    if (matched.length > 0) return [true, `Regulated activities: ${matched.join(", ")}`];
    return [false, ""];
  }
  return [false, ""];
}

export function resolveState(profilePath: string, rulesPath?: string) {
  const rootDir = resolve(dirname(new URL(import.meta.url).pathname), "..");
  const rPath = rulesPath || resolve(rootDir, "rules/core-artifacts.json");

  const profile = JSON.parse(readFileSync(profilePath, "utf-8"));
  const rules = JSON.parse(readFileSync(rPath, "utf-8"));

  const stage = (profile.stage?.funding_stage || "seed").toLowerCase();
  const employees = profile.stage?.employee_count || 1;
  const triggers: string[] = profile.triggers || [];
  const regulated: string[] = profile.business?.regulated_activities || [];

  const artifacts: ArtifactNode[] = rules.artifacts || [];

  const evaluated = artifacts.map((art) => {
    let level = art.requirement.default;
    const reasons = [`Base default: ${level}`];

    if (art.requirement.overrides) {
      for (const ovr of art.requirement.overrides) {
        const [matched, condReason] = evaluateCondition(ovr.when, stage, employees, triggers, regulated);
        if (matched) {
          level = ovr.level;
          reasons.push(`Override applied: ${condReason} -> ${level}`);
        }
      }
    }

    return {
      id: art.id,
      name: art.name,
      root: art.root,
      criticality: art.criticality,
      level,
      reasons: reasons.join("; "),
      frameworks: art.framework_mappings || [],
      evidence: art.evidence_types || [],
    };
  });

  const requiredCount = evaluated.filter((a) => a.level === "required").length;
  const recommendedCount = evaluated.filter((a) => a.level === "recommended").length;
  const optionalCount = evaluated.filter((a) => a.level === "optional").length;

  return {
    company: profile.company?.legal_name || "Company",
    stage,
    employees,
    total: evaluated.length,
    requiredCount,
    recommendedCount,
    optionalCount,
    artifacts: evaluated,
  };
}

// CLI invocation
if (import.meta.main) {
  const file = process.argv[2];
  if (!file || !existsSync(file)) {
    console.error("Usage: bun resolver/index.ts <path-to-company-profile.json>");
    process.exit(1);
  }
  const result = resolveState(file);
  console.log(`Evaluated ${result.total} artifacts for ${result.company}:`);
  console.log(`  Required: ${result.requiredCount} (${Math.round((result.requiredCount / result.total) * 100)}%)`);
  console.log(`  Recommended: ${result.recommendedCount}`);
  console.log(`  Optional: ${result.optionalCount}`);
}
