---
{
  "name": "reply_drafting",
  "version": "1.0",
  "triggers": ["verified facts available", "store operator requests AI reply"],
  "non_triggers": ["no verified facts", "high-risk reply without review context"],
  "inputs": ["email", "verified_facts", "reply_basis_results", "risk_context"],
  "outputs": ["draft_subject", "draft_body", "used_basis", "uncertainties"],
  "steps": [
    "Use only verified facts returned by local Tools.",
    "Use matching read-only reply basis snippets and the tone guidance.",
    "Write concise, polite English with one factual update or request and one next step.",
    "Mark unsupported facts and uncertainties instead of filling them with general knowledge.",
    "Save the draft only after the calling flow provides confirmation and an operation_id."
  ],
  "tools": ["search_reply_basis", "get_reply_tone", "save_reply_draft"],
  "forbidden": ["promise a refund", "promise compensation", "promise an exact delivery time", "hide uncertainty"],
  "escalation_conditions": ["basis not found", "basis conflict", "draft contains a commitment", "risk level is high"],
  "examples": ["Shipment status reply", "Size exchange clarification reply"]
}
---

# Reply Drafting

This Skill produces an editable English draft for the aggregated station-message thread. It is a drafting aid, not a sender and not a replacement for the local risk gateway.

## Fact and basis boundary

Facts must come from `find_order` or `get_shipping_status`. Guidance must come from the local read-only basis search. The Skill must expose which basis sections it used so the store operator can inspect the evidence.

## Review boundary

The final customer-facing text can differ from the AI draft after store-operator editing. A draft is not a simulated send. The send Tool remains responsible for confirmation and idempotency.
