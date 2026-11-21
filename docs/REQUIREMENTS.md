# Problem-statement traceability and acceptance record

This record separates delivered software from external approval and performance evidence. No row should be interpreted as certification or permission for patient use.

| PS deliverable | Delivered implementation | Evidence / remaining acceptance |
| --- | --- | --- |
| 1. Approved KB, synthetic cases, omissions and noise scenarios | Frozen reviewed protocol snapshots; source references; synthetic case library; scripted disruptions; reproducible 26-recording noise/overlap corpus | Local simulation-review approval is supported. Institutional clinician approval is not supplied by code. Corpus is generated TTS, not OR recordings. |
| 2. Streaming ASR and speaker/turn handling | Local Vosk, AudioWorklet PCM, enrollment gates, anonymous other-speaker labels; simultaneous activity monitoring across assigned microphones | Transport and gate tests pass. Held-out acoustic reliability is not established; current synthetic enrollment run failed. |
| 3. Grounded dialogue, state, confidence and abstention | Fixed role/source/evidence graph; conservative matching; uncertainty/contradiction gates; server-side response deadlines; experimental duplex recognition with contamination rejection | Rule tests and timeout tests pass. General language understanding, mixed-room source separation and reliable echo cancellation are not claimed. |
| 4. Confirmation, correction, override, audit | Role-bound explicit confirmation, append-only events, interruption context, corrections, exports and scored-study provenance | Account/closure/version tests pass. Admin rewriting of SQLite remains possible. |
| 5. Nonclinical interface | Routed workspace with synthetic-only labels, protocol review, sessions, audio selection and Trial scoring | Browser smoke test submitted a clearly labeled synthetic UI score. |
| 6. Static comparison using seven measures | Assisted/static modes; observer labels; accuracy, omission recall, false prompts, latency median/p95, recovery, task time and workload; pair-validation export script | Automated paired exercise executed. Human controlled comparison and live microphone latency measurements have not been conducted. Null means unmeasured, not zero. |
| 7. Safety case, privacy and clinical-validation roadmap | SAFETY.md, AUDIO.md and VALIDATION.md with hazards, controls, retention and evidence stages | Draft engineering documents. Need specialist review before any clinical study. |

## New workflows

- **Request response · 30s** arms the selected item's response deadline. The background server checks it even when no browser is polling. Pauses suspend the clock. An acceptable response cancels the deadline; otherwise one omission event is emitted. Explicitly request again to start another interval. Static mode never prompts. Enrollment completion automatically arms the local channel's first response deadline.
- **Experimental duplex recognition** keeps transcription active during prompt playback. Any utterance touching playback or its echo guard is rejected and repeated. This improves observation/turn continuity, not acoustic safety certification. The conservative guarded mode remains the default.
- **Separate microphones:** each assigned clinician signs in on their own device/profile and selects their own item. Activity overlapping across channels flags those turns. This is energy-based overlap monitoring across isolated channels, not separation of voices mixed into one microphone. Cross-talk and network jitter can cause misses/false alarms. Prefer headsets.
- **Trial scoring:** pause the session; enter every outcome explicitly against independently prepared labels or recordings. Save a pseudonymous team code and measurement method. Scores are append-only and record the exact state version. Save workload in Session review before scoring. Latency remains blank unless measured. Export both paired records and run `scripts/compare_sessions.py`.

## Reproduce the engineering evidence

```bash
python -m unittest discover -s tests -v
node tests/test_audio_client.cjs
python scripts/run_paired_simulation.py
# Requires FFmpeg compiled with libflite and the downloaded Vosk models:
python scripts/build_audio_corpus.py
python scripts/evaluate_audio.py data/audio-corpus/study.json --model models/vosk-model-small-en-us-0.15 --speaker-model models/vosk-model-spk-0.4 --output docs/acoustic-bench-results.json
```

See [automated paired results](paired-simulation-results.json) and [actual acoustic model results](acoustic-bench-results.json). The former uses scripted actors, not people. The latter includes poor/noisy transcription and failed enrollment. WER can exceed 100% when insertions exceed the reference length. Speaker acceptance rates are null when enrollment fails. No thresholds were relaxed to manufacture passing results.

## Remaining acceptance gates

1. A qualified reviewer approves the exact simulation checklist version, expected responses and role assignments. WHO reference provenance does not imply WHO endorsement or local approval.
2. Consent-based, independently labeled recordings on target microphones validate enrollment, unknown-speaker rejection, overlap, accents, noise and echo. Tune on development recordings; evaluate on held-out recordings. Do not use the test corpus to declare clinical reliability.
3. A counterbalanced controlled participant study compares assisted/static modes. Collect workload and end-of-speech latency, including failures and incomplete sessions. The supplied automated run cannot substitute for participants.
4. Review the safety/privacy package and clinical-validation roadmap with institutional stakeholders.

The software provides tools for each PS deliverable, but the PS is **not fully accepted** until the remaining approval and performance evidence exists. Clinical validation itself is a future roadmap requirement in the supplied PS, not a completed clinical deployment requirement.
