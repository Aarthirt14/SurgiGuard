# SurgiGuard AI

A working **nonclinical, synthetic-data prototype** for a bounded pre-incision verification workflow. Professional browser UI, Python API, SQLite persistence, microphone transcription where supported, spoken prompts, explicit role-bound confirmation, corrections, overrides, audit export, and controlled scripted scenarios.

## Run locally (Windows, macOS or Linux)

Install Python 3.10 or later. No Python packages, Node packages, API keys or paid model accounts are needed for the local core.

```bash
git clone https://github.com/Aarthirt14/SurgiGuard.git
cd SurgiGuard
python server.py
```

Open **http://localhost:8000** in Chrome or Edge. On Windows, use `py server.py` if `python` is unavailable. Create a session, start it, and select an item. Chrome/Edge microphone support depends on the browser, network and speech provider; localhost is a permitted secure-context exception. Remote access requires HTTPS for microphone permission.

### First demo

1. Create an assisted session with **Nurse** as the acting role; click **Start session**.
2. Run **Clear response** for Team introductions. The item becomes **Confirm required**, never automatically completed.
3. Click the item and **Confirm this item**. The server verifies the designated role before accepting.
4. Select Patient, procedure & site. Run noise, contradiction, role mismatch or overlap scenarios: confirmation remains blocked.
5. Run a clear response, switch the acting role to **Surgeon**, and confirm.
6. For real microphone transcription, select the speaking role, click **Enable microphone**, accept the in-app disclosure and browser permission, and say the displayed expected response. Unknown or low recognition confidence is rejected. Click **Read prompt** for speech output; headphones reduce feedback. Transcripts do not auto-confirm.
7. Use **Interrupt / resume context** to mark a real interruption that the browser did not detect. Resubmit a clear response to recover the same item.
8. Inspect the **Audit trail**, then **Export session**. Under Evaluation, record workload and start a static session to compare.

Changing the selected item, actor or speaking role stops recognition so queued speech cannot be attributed to a different item or role. Browser speech detection cancels ongoing assistant speech; simultaneous-speaker diarization and echo cancellation are **not** implemented.

## Implemented versus outstanding

| Capability | Current implementation |
|---|---|
| Real speech input | Browser Web Speech API; interim text, final transcript and reported confidence; explicit opt-in |
| Spoken prompts | Browser speech synthesis; cancellation on detected speech/interruption |
| Protocol lookup | Versioned deterministic fixture; expected evidence, required role and source shown per item |
| Safety state | Python-enforced waiting → pending → explicit confirmation; unknown/low confidence, mismatched role, negative or unrecognized evidence stay unresolved |
| Interruption memory | Server retains item/evidence state and records interruption/recovery; operator can flag undetected overlap |
| Persistence | SQLite session state, role tokens and hash-linked audit events survive restart |
| Correction/override | Required reason and designated role; prior evidence retained in audit; override never completes an item |
| Evaluation | 36 labeled deterministic fixtures, assisted/static modes, workload rating, task time, export comparison |
| Full-duplex audio / automatic diarization | **Not complete**: browser-dependent overlap behavior; no multi-speaker separation or clinical voice identity |
| Approved knowledge base | **Not complete**: simplified unapproved simulation fixture; no claim of clinical approval |
| Production security / clinical validation | **Not complete**: demo roles, local HTTP server and administratively mutable DB are not clinical deployment infrastructure |

The application is rule-based. It does not call an LLM and does not diagnose, recommend treatment or authorize surgery. The fixture intentionally accepts bounded response patterns, not arbitrary clinical conversation. All confidence values on injected scenarios are scripted; typed evidence has a manual-input confidence marker of 1.0, not an ASR quality estimate.

## Tests and evaluation

```bash
python -m unittest discover -s tests -v
python scripts/evaluate.py
python scripts/compare_sessions.py assisted-export.json static-export.json
python scripts/verify_audit.py exported-session.json
```

Tests exercise authorization, all six item paths, uncertain/negative/mismatched evidence, stale state rejection, correction/override, interruption recovery, restart persistence, audit chain integrity, HTTP access and static mode. Fixture evaluation reports state classification accuracy, omission recall, false prompts and rule execution time. **Rule execution time is not end-to-end speech latency**; fixture results are not clinical or real-ASR performance claims. Use exported sessions with independent annotation for real trial metrics.

## Architecture

- `server.py`: standard-library HTTP API, SQLite storage, session capability tokens, concurrency/version checks, audit hashing.
- `protocol.py`: immutable-in-session version reference, synthetic item definitions and conservative bounded matching rules.
- `web/`: responsive interface, speech adapter, server-backed workflow.
- `tests/`: unit and HTTP integration tests.
- `scripts/`: fixture evaluation, trial export comparison and audit chain verification.
- `docs/SAFETY.md`: limitations, privacy, threats, safety case and validation roadmap.

API: `POST /api/sessions`, `GET /api/session`, `POST /api/action`, `GET /api/health`. Session access uses an opaque bearer token stored in browser session storage and hashed in SQLite; expires after 24 hours. Tokens are not exported. Actor-role changes are intentionally available to demo users and logged; this is **not identity verification**. Multiple clients cannot silently overwrite a state because mutations require the current session version.

## Hosting and data

Default binding is localhost. Data is in `data/surgiguard.sqlite3`; keep it out of Git. Export before switching sessions or closing a browser whose session token you need. The prototype has no account-based session recovery UI. Server restart retains sessions, but uptime gaps during an active session contribute to elapsed time; pause before stopping the server.

For an isolated test network, set `SURGIGUARD_ACCESS_KEY` in the environment before using `--host 0.0.0.0`. Put a TLS reverse proxy in front for remote browser speech, restrict network access, and use synthetic data only. A workspace key limits session creation; it does not authenticate clinician identity. This standard-library development server is not intended for internet production exposure.

Docker is optional:

```bash
docker build -t surgiguard .
docker run --rm -p 127.0.0.1:8000:8000 -e SURGIGUARD_ACCESS_KEY -v surgiguard-data:/app/data surgiguard
```

Set `SURGIGUARD_ACCESS_KEY` in your shell first; enter it when creating a session. No credentials should be committed.

Browser microphone recognition may transmit audio to the browser vendor’s speech service. SurgiGuard stores final transcripts, confidence, roles and events, not raw audio. Read the disclosure before enabling it. Local data has no automated retention deletion and no at-rest encryption in this prototype.

### Browser API references

- https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API/Using_the_Web_Speech_API
- https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition/continuous
- https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition/interimResults

The earlier static Sites mockup is separate. This version requires the Python server and cannot run as a GitHub Pages-only website.
