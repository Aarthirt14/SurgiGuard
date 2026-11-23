# Voice enrollment repair and unchanged-corpus retest

## Defect and correction

The original enrollment path required minimum ASR word confidence of 0.85 before it accepted a speaker embedding. All three original enrollment recordings had valid 128-dimensional embeddings and 384–468 speaker frames, but minimum word confidence was only 0.21–0.39. This incorrectly coupled a voice reference to successful word recognition.

Enrollment now checks clipping, speaker-frame count, vector validity and consistency between **every pair** of enrollment samples. It remains separate from evidence submission. Three samples are required and enrollment is capped after completion. Non-finite frame counts are rejected. Voice similarity remains 0.75; ambiguity margin remains 0.10. Subsequent checklist evidence still requires minimum word confidence 0.85. No speech event confirms an item.

The live interface instructs users to stay silent until the enrollment counter advances. A one-second pause was insufficient for some recognizer endpoints during continuous replay; this is distinct from the original confidence-gate defect.

## Measured evidence

The original [failure report](acoustic-bench-results.json) is retained. The [repaired small-model run](acoustic-enrollment-fix-results.json) uses the same local WAV files, model and thresholds for evidence. It records file hashes and diagnostic confidence values. All three voice references enroll. The 26 evaluation trials still yield **0% target acceptance**, so enrollment success is not overall speech success. All eight non-target/overlap controls are rejected, but that cannot establish useful discrimination when no target is accepted. Minor WER differences between reruns must not be interpreted as improvement from this gate change.

Automated verification: 30 Python tests passed, including authenticated WebSocket, role, confirmation, timeout, overlap and study tests; JavaScript audio framing/barge-in/backpressure tests passed. New regression tests exercise low-confidence enrollment followed by rejection of the same low-confidence checklist evidence, inconsistent sample pairs, invalid frame counts and bounded enrollment. A real-model streaming replay also reached enrollment-ready without emitting uncertain checklist evidence. These checks are engineering evidence, not live-device performance validation.

## Larger-model experiment

The [Vosk 0.22 lgraph run](acoustic-lgraph-results.json), using the same recordings, reduced aggregate word error rate from about 109% to 85%. However, its third enrollment embedding failed the unchanged pairwise similarity requirement. Speaker acceptance metrics therefore remain null for that run. The larger model is **not promoted as a solution**. Both reports include input hashes, model identifiers and evidence thresholds. This is a development comparison, not a held-out validation claim; neither model meets reliable-audio acceptance on this corpus.

Model source: https://alphacephei.com/vosk/models (Apache 2.0 model listings). To reproduce the experiment after downloading and extracting the 0.22-lgraph model, substitute `models/vosk-model-en-us-0.22-lgraph` for the model argument below and use a different output path.

## Reproduce

```bash
python -m unittest discover -s tests -v
node tests/test_audio_client.cjs
python scripts/evaluate_audio.py data/audio-corpus/study.json --model models/vosk-model-small-en-us-0.15 --speaker-model models/vosk-model-spk-0.4 --output audio-report-repaired.json
```

Keep the original corpus and reports. Do not regenerate or overwrite them to improve results. Corpus generation is described in REQUIREMENTS.md; generated speech is not human or operating-room audio.

Clinician approval, held-out microphone testing and the controlled participant comparison remain external acceptance tasks. This repair does not establish clinical reliability, mixed-waveform separation or reliable full-duplex behavior.
