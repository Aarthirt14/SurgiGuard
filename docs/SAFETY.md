# Nonclinical safety case and validation plan

## Intended use
Synthetic, scripted pre-incision checklist demonstrations and controlled research sessions. Not clinical decision support, not an approved checklist, not a medical device release. No diagnosis, treatment decision or autonomous completion. Users retain authority; an item’s designated demo role explicitly confirms it.

## Safety claims and evidence

| Claim | Control | Verification / remaining limitation |
|---|---|---|
| Speech alone cannot complete an item | Evidence only enters pending; a separate authenticated session action is required | Server tests reject completion without evidence; role identity is a demo assignment |
| Uncertain recognition is not accepted | Missing confidence or score below 0.85 leaves a flag | Threshold is a prototype constant, not clinically calibrated |
| Role mismatch cannot confirm | Both evidence role and acting token role checked | No automatic speaker identification; intentional role switching exists for demonstration |
| Contradictions stay unresolved | Negative and unexpected response patterns are rejected | Bounded rules do not understand all negations or clinical language; false acceptance remains possible outside the script |
| Interruptions preserve context | Server stores state and explicit interruption events; UI pins speech to item/role | Browser speechstart is not reliable overlap detection; an operator can explicitly flag overlap |
| Prior actions are reviewable | Timestamped server audit chain, correction snapshots, exported records | DB administrator can reconstruct hashes; external signing and immutable storage not implemented |
| Concurrent writes do not silently overwrite | Version checked in a serialized transaction | Stale requests require refresh/retry |

## Privacy and threats
Only synthetic data. Browser speech may use external services; explicit consent precedes capture. No raw audio stored by this app. Final transcripts persist in SQLite with no automatic retention period or encryption at rest. Limit OS access and use a disposable demo database when appropriate. Never commit DB files, exports containing sensitive data, workspace keys or tokens.

Session tokens are unguessable, stored as hashes server-side, and expire after 24 hours. Export excludes tokens. Network-bound startup requires a workspace key. This is not a clinician login system. Role switching is deliberate for demonstration. Origin checks, JSON-only mutations, request size limits, HTML escaping and restricted static routes reduce common web risks. The standard-library server lacks production rate limiting, federated identity, hardened deployment and recovery UI. Do not expose it as a production medical service.

## Evaluation protocol
Use synthetic cases and a frozen approved-for-study script. Randomize/counterbalance assisted versus static order. Record participant role, case, session export, independent reference completion state, omissions, false prompts, observed overlap and recovery. Separate ASR errors from item mapping errors. Use the same script and task endpoint for both modes. Measure completion accuracy, omission recall, false prompts per opportunity, speech-end-to-prompt latency, recovery success, task time and a standardized workload questionnaire; the included single 0–10 rating is only a convenience measure, not NASA-TLX.

The automated evaluation is only a deterministic smoke benchmark over 36 labeled rule fixtures. It does not simulate actual acoustic noise. For acoustic evaluation, record or synthesize consented synthetic utterances, mix licensed room noise at defined SNRs, include scripted overlapping tracks, and independently label speaker turns. No such acoustic dataset or validated speech benchmark is bundled here.

## Roadmap
1. Clinician review of complete institution-specific protocol, required roles and confirmation policy; sign versioned approvals.
2. Streaming ASR/diarization adapter with calibrated scores, echo cancellation, true barge-in, explicit silence/overlap detection and fail-closed timeouts.
3. Authenticated staff identities, least-privilege roles, access logs, encryption, retention controls, signed audit events and recovery workflow.
4. Independent safety engineering, threat modeling and usability review, including automation bias and workload.
5. Controlled nonclinical evaluation, then ethics/governance-approved clinical validation. No real operating-room deployment before these gates.
