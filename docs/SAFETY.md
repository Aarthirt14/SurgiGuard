# Nonclinical safety case and validation roadmap

## Intended use
Synthetic scripted pre-incision simulations and controlled research. This is not clinically validated decision support, an approved surgical checklist, or a medical device release. No diagnosis, treatment advice or autonomous completion. The six-item fixture is intentionally simplified.

## Controls and limits

| Claim | Control | Limit |
|---|---|---|
| Speech cannot complete an item | Server accepts evidence into pending only; explicit confirmation is separate | No claim of clinical language comprehension |
| Unknown/low confidence fails closed | Unknown or <0.85 confidence produces unresolved flag | Prototype threshold, not clinically calibrated |
| Required-role authority | Fixed account roles, named assignments, server checks on evidence and confirmation | Accounts are not professional credential verification or voice biometrics |
| Unrelated users cannot access sessions | Membership checked on all read/action paths | Coordinators can review workspace studies |
| Contradictions remain unresolved | Negative/unexpected response rules reject bounded evidence | Rules cannot understand every negation or clinical utterance |
| Context survives interruption | Persistent item state, explicit interruption events and recovery count | Optional browser echo cancellation and playback guards are unvalidated; no robust acoustic overlap detector |
| Prior decisions are reviewable | Hash-linked timestamps, authenticated account attribution, corrections and export | DB administrators can rewrite records and recompute hashes |
| Stale writes do not overwrite | Version check and serialized transaction | Stale request must refresh/retry |
| Closure is gated | All items must be explicitly confirmed; only coordinator closes | Closure refers only to a simulation, not clinical clearance |
| Protocol context is stable | Draft approval gate and frozen case/protocol/team snapshot | Local research approval is not clinical approval; bounded definitions are edited in code |

## Privacy and access
Use synthetic data only. Browser speech may transmit audio to its provider after explicit consent. App stores final transcripts and metadata, not raw audio. SQLite has no at-rest encryption or automatic retention cleanup. Limit operating-system access, protect backups and exclude DBs, keys and sensitive exports from Git.

Password hashing uses salted PBKDF2-HMAC-SHA256. Eight-hour login tokens are hashed in storage, held in browser session storage and revoked on logout. Login throttling is in memory, not distributed. Only coordinator accounts create staff, approve research protocols and set up sessions. Only coordinators can inject controlled synthetic evidence on behalf of other roles. Live/typed evidence is attributed to the authenticated clinician.

No SSO, MFA, password reset, staff deactivation UI, production rate limiting or external audit signing. Standard-library HTTP server is for localhost/isolated research use. Network binding requires a workspace setup key; remote use requires TLS and restricted network access. Treat browser/XSS and database-administrator compromise as unresolved production threats. HTML output is escaped, API mutations require JSON and same-origin browser requests, and static file serving is allowlisted.

## Evaluation
Counterbalance assisted/static order and keep case, protocol and task endpoint consistent. Record participant roles and independent reference labels. Distinguish ASR errors from semantic-mapping errors. Measure completion accuracy, omission recall, false prompts, speech-end-to-prompt latency, interruption recovery, task time and a standardized workload instrument. The bundled 0–10 rating is not NASA-TLX.

The 36 automated fixtures measure rule transitions only, not actual noise robustness or speaker separation. For acoustic studies use consented synthetic utterances, licensed room noise mixed at defined SNRs, controlled overlapping tracks and independent turn labels. No validated acoustic dataset is bundled.

## Before any clinical use
1. Institution-specific full protocol, roles and approved version governance.
2. Validated streaming ASR, calibrated confidence, diarization, echo cancellation, silence/overlap detection and timeouts.
3. Staff identity integration, least privilege, recovery, encryption, retention and externally secured audit storage.
4. Independent safety engineering, threat modeling and human-factors testing including automation bias.
5. Controlled nonclinical trials followed by ethics/governance-approved clinical validation.

## Local audio extension

See [AUDIO.md](AUDIO.md) for setup, enrollment and privacy behavior and [VALIDATION.md](VALIDATION.md) for the evidence plan. Three-sample speaker matching is an experimental input filter, not authentication. Other-speaker clusters are never granted roles. Unknown, short or ambiguous embeddings abstain. A mixed utterance can still match the enrolled speaker, so this is not reliable overlap rejection. Capture remains active during playback but recognition is discarded until a post-playback guard expires. Local audio abstentions and final evidence are audited; PCM and embeddings are not persisted.
