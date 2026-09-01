# Activation checklist

Do not create a live Automation until every item is confirmed.

1. Exact repo/trigger/tool scope is written in the editor, not inferred.
2. The prompt in the editor is a self-contained prompt with no private
   workspace references.
3. A user drafts the Automation, then confirms readiness in the Agents
   Window.
4. Editor validation succeeds for identity, secrets, egress, and memory.
5. A harmless test PR produces the schema-constrained static result.
6. An adversarial fixture that tries to run PR-head code is denied or
   returns `INCONCLUSIVE`.
7. A head-movement test returns non-passing `INCONCLUSIVE`.
8. Deep runtime verification remains inactive unless PR-head hook isolation
   is proven. Unproven isolation must return `INCONCLUSIVE`.
9. Cloud retention, screenshot redaction, and log inventory are reviewed
   before any production or shared-customer data could be in scope.
   Synthetic data only until that review is complete.
