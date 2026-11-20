# Validation plan — evidence pending

Clinical validation cannot be implemented or inferred from software tests. This document defines the next evidence collection stages; it does not authorize patient use. All current workflows remain nonclinical and require explicit clinician confirmation.

## 1. Engineering verification

Run the unit/integration suite, including authenticated WebSocket transport. Check enrollment never emits evidence, unknown speakers are rejected, playback guards prevent echo submission, stale versions fail, revoked tokens stop capture and no audio event confirms an item. Repeat on Windows/Chrome and intended test hardware. Record OS, browser, microphone, headset, model checksums, dependency versions, commit, thresholds and failures.

## 2. Acoustic bench study

Collect consenting volunteers reading synthetic scenarios. Split enrollment, threshold development and held-out evaluation by recording; test previously unseen speakers and devices. Include quiet speech, accents, low volume, reverberation, clipping, background conversation, instrument-like sounds, simultaneous speech and assistant-playback interruptions. Record measured noise level/SNR where available. Never label a script-injected noise event as an acoustic test.

Use `scripts/evaluate_audio.py` for actual model replay. Independently annotate transcripts, speaker identities, overlaps and onset/offset times. Report WER, unknown-speaker false acceptance, enrolled-speaker false rejection, overlap false acceptance and subgroup/device results. Report confidence intervals and sample counts. The current pipeline does not separate simultaneous voices: failures here are expected and must remain visible.

For live duplex trials measure microphone onset → assistant cancellation, end of utterance → displayed prompt, interruption → successful repeat, dropped packets and capture discontinuities. Record distributions (median/p95), not only mean processing time. Distinguish browser/device failures from model failures. Raw recording capture is a separate consented research activity, not automatic application logging.

## 3. Controlled usability simulation

Compare assisted and static modes using matched fictional cases and counterbalanced order. Use independently scored omissions and contradictory responses. Predefine item-completion accuracy, omission recall, false prompts per opportunity, latency, interruption recovery, task time and workload. Retain incomplete/failed sessions and protocol deviations. Account for participant/team learning and repeated measurements. A study lead must choose sample size and acceptance thresholds before collecting held-out data.

A local “simulation-approved” protocol is only research attestation. Obtain content review from appropriate clinical specialists before using institution-specific checklist semantics in a study. Verify that every completion remains a deliberate action by the assigned clinician.

## 4. Before any clinical study

Require institutional clinical leadership, ethics/privacy review as applicable, specialist-approved protocols, a documented intended use and hazard analysis, secure deployment, incident handling, monitoring and a prospectively approved study protocol. Establish an independent stop rule for false completion, wrong-role acceptance or missed contradictions. Evaluate applicable oversight requirements with qualified specialists. No transition to clinical operation is enabled by this repository.

## Evidence register

| Claim | Present evidence | Remaining evidence |
| --- | --- | --- |
| Explicit confirmation and authorization | Engine and WebSocket tests | Independent review and deployment testing |
| Continuous capture and barge-in | AudioWorklet implementation and playback state tests | Real microphone/echo/noise timing study |
| Enrolled-speaker gate | Vector tests; actual Vosk integration | Held-out acoustic accuracy and threshold calibration |
| Simultaneous speaker separation | Not implemented | Source separation/overlap model and evaluated recordings |
| Clinical benefit/safety | No evidence claimed | Approved prospective clinical evaluation |

Passing a software test or obtaining a good demo recording does not establish clinical reliability.
