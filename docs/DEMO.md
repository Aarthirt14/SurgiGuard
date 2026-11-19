# Demonstration runbook

Create a coordinator and three clinician accounts. Inspect and approve the fixed protocol for simulation with a research rationale. Create an assisted session for SIM-024 with trial ID `trial-01`, assigning each clinician.

Use separate browser profiles for concurrent accounts, or sign out/in on one laptop. Microphone permission is not required for a deterministic demonstration.

1. Coordinator starts the session and injects a clear Team introductions response. It becomes pending, not confirmed.
2. Coordinator cannot confirm. Nurse signs in, opens the assigned session and explicitly confirms. Inspect named-user attribution in the audit view.
3. Coordinator selects Patient, procedure & site and injects low confidence. Confirmation remains blocked for Surgeon too.
4. Inject wrong-role, contradictory and overlap responses. They remain unresolved and all evidence remains auditable.
5. Submit a clear response; Surgeon confirms. The same checklist context is recovered.
6. Remaining items: assigned accounts type the displayed expected response and confirm. For microphone input, use the assigned account, grant permission, use headphones and speak the synthetic expected response; missing ASR confidence abstains.
7. Nurse reopens an item with a reason, resubmits and confirms. Compare old/new evidence in the audit trail.
8. Record workload. Coordinator closes the fully confirmed session and adds a research review. Checklist records are now read-only.
9. Create a static session using the same case, team and trial ID. Members manually confirm assigned items. Export and compare in Evaluation.

State accurately: roles are authenticated accounts, not voice recognition. Noise/overlap buttons inject fixtures; they do not analyze acoustic tracks. Local simulation approval is not clinical certification. No real surgery, diagnosis or treatment use is supported.
