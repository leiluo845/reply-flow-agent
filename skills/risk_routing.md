---
{
  "name": "risk_routing",
  "version": "1.0",
  "triggers": ["triage completed", "draft completed", "Tool result changed"],
  "non_triggers": ["before the original email is read"],
  "inputs": ["email", "analysis", "verified_facts", "basis_results", "tool_errors", "draft"],
  "outputs": ["risk_level", "ai_level", "matched_rules", "allowed_actions", "blocked_actions", "checklist"],
  "steps": [
    "Apply deterministic local rules after analysis and again after drafting.",
    "Keep the highest applicable risk result; model confidence cannot lower it.",
    "Allow automatic handling only for the explicit low-risk allowlist.",
    "Require store-operator confirmation for the second level.",
    "Require a complete review checklist and second confirmation for the third level."
  ],
  "tools": ["save_reply_draft", "send_simulated_reply"],
  "forbidden": ["lower a local risk result", "auto-check a review item", "send to an external mailbox"],
  "escalation_conditions": ["refund", "compensation", "chargeback", "complaint", "legal threat", "identity conflict", "Tool error", "unsupported commitment"],
  "examples": ["Low-risk tracking update", "Chargeback threat requiring review"]
}
---

# Risk Routing

This Skill translates analysis and draft evidence into an operator-facing processing level. It does not create an approval queue and it does not authorize a real-world action.

## Control order

1. Run deterministic local checks.
2. Record matched rules and evidence identifiers.
3. Keep the most conservative applicable level.
4. Pass only an explicitly confirmed local action to the write Tool.

The Skill is intentionally small so its decisions can be tested independently from model orchestration.
