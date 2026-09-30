---
doc_id: POLICY-ESCALATION
title: Investigation Escalation Criteria
dispute_type: general
---
### Clause C1: High-Value Escalation
Any dispute on a transaction at or above the high-value threshold is
escalated to a human analyst regardless of the copilot's confidence.

### Clause C2: High Fraud-Score Escalation
A fraud score at or above the high-fraud-score threshold triggers
escalation even for a low transaction amount, since a pattern of
repeated fraud claims on one account is itself a risk signal.

### Clause C3: Low-Confidence Escalation
If the classification or decision confidence is below the configured
threshold after one reflection pass, the case is escalated to a human
analyst rather than auto-decided.

### Clause C4: Ambiguous or Out-of-Scope Requests
A narrative that does not describe a specific transaction dispute (a
general question, an unrelated request, or an attempt to access another
account) is not classified as a dispute type; it is routed to a human
for clarification rather than guessed at.
