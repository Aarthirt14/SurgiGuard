# Local streaming audio (experimental)

This optional mode runs actual Vosk ASR and speaker embeddings on your own Python server. It is an engineering prototype for synthetic simulations, not a clinically validated system. The standard `python server.py` mode still works without audio dependencies.

## Start on Windows, macOS or Linux

Use Python 3.10–3.12 and a supported Vosk platform. From the repository directory:

```bash
python -m pip install -r requirements-audio.txt
```

Download and extract these official models from [Vosk Models](https://alphacephei.com/vosk/models):

- `vosk-model-small-en-us-0.15` (speech recognition)
- `vosk-model-spk-0.4` (speaker embeddings)

Place the extracted directories under `models/`, then run:

```bash
python audio_server.py --model models/vosk-model-small-en-us-0.15 --speaker-model models/vosk-model-spk-0.4
```

Open `http://localhost:8000`. Stop any existing server using that port first. The gateway serves both the application and authenticated WebSocket on the same port. No model download happens automatically; missing models fail at startup. Model files and recordings are excluded from Git.

For network trials use HTTPS through a WebSocket-capable reverse proxy and restrict access to a test network. Set `SURGIGUARD_ACCESS_KEY` before non-loopback binding, as with the ordinary server. Do not expose the Python services as an internet production application.

## Try the workflow

1. Coordinator creates a simulation-approved protocol, assigned team and assisted session, then starts it.
2. Sign in as an assigned clinician in a separate browser profile. Select an item assigned to that role.
3. Select **Enable microphone → Local streaming + speaker gate** and grant microphone access.
4. Read three different synthetic sentences, one at a time, pausing after each. For example: “This is a synthetic training exercise with our simulation team today.” Use several seconds of natural speech per sentence. The interface reports enrollment progress. Enrollment never submits checklist evidence.
5. Read the displayed expected response. A sufficiently long, confident utterance matching the enrolled voice may become pending evidence. Minimum word confidence must be at least 0.85, speaker similarity at least 0.75, and ambiguity margin at least 0.10. These are provisional, uncalibrated thresholds, not clinical acceptance criteria.
6. Stop the microphone, inspect the evidence and explicitly confirm. The server still enforces the designated account's role. A successful voice match never confirms an item.
7. Try another speaker, a short response, noise, or **Read prompt** followed by an interruption. Review rejection messages and audit events. Reconnect/re-enroll after changing item, pausing, or another account changes session state.

## What runs

`AudioWorklet` captures mono samples continuously and produces PCM16 at 16 kHz in 100 ms packets. Browser echo cancellation, noise suppression and gain control are requested; the UI reports whether echo cancellation is enabled. A bounded same-origin WebSocket sends ordered packets to Vosk. Partial transcripts appear immediately; final results go through word-confidence, clipping and speaker gates. A signed-in account supplies the role; acoustic matching is never proof of professional identity.

Three consented enrollment utterances form a connection-local speaker reference. Subsequent utterances are automatically compared to that reference. Other voices receive bounded anonymous cluster labels and are rejected. Short, ambiguous and missing embeddings are rejected. All enrollment samples and embeddings disappear on disconnect; they are not persisted or exported.

During assistant playback capture continues to detect a sustained energy rise, cancel output and preserve the selected item. Recognition is intentionally discarded during playback and for 600 ms afterward to reduce echo acceptance. The user must repeat the complete response. **This is guarded duplex capture with barge-in, not proven simultaneous recognition and playback.** Energy is a simple heuristic and can mistake residual echo or noise for an interruption.

Transport checks enforce account authorization, origin, ordered frames, bounded frame size/rate, four concurrent streams, one stream per account/session, a 30-minute limit and a 30-second receive timeout. Backpressure or session-version conflicts stop capture rather than silently replaying old evidence. Partial speech is discarded on disconnect. Ordinary browser transcription remains an explicitly selected fallback; it is never silently enabled.

## Important limits

- Turn-level speaker matching is not separation of mixed waveforms. Two simultaneous voices may produce one embedding, possibly matching an enrolled speaker. No reliable acoustic overlap detector is included. Test overlapping recordings and keep all results nonclinical.
- Natural speech may not match the fixed protocol patterns; no general clinical language model is added.
- Some accents/names and short checklist phrases will be rejected. ASR confidence and cosine similarity are not calibrated probabilities.
- The small model and averaging resampler favor an inexpensive proof of concept. Headset/microphone selection, echo behavior and real-time throughput need testing on target hardware.
- Local recognition keeps microphone audio on the local/test server. Browser speech synthesis may depend on installed or remote voices. The browser-transcription fallback may send audio to its vendor.
- Rejected final text/reasons, accepted evidence, account attribution and events are stored in the session audit. Raw PCM and embeddings are memory-only. Do not use patient data or nonconsenting voices.

## Recording evaluation

Record consented speakers reading fictional scripts as mono, 16-bit PCM WAV at 16 kHz. Keep recordings outside Git. Independently label expected speaker, overlap, transcript and condition. Do not use the same recording for enrollment and evaluation. An example manifest structure (replace all paths with your own recordings):

```json
{
  "synthetic_only": true,
  "enrollment": ["enroll-1.wav", "enroll-2.wav", "enroll-3.wav"],
  "trials": [
    {"id":"clean-01","file":"clean.wav","condition":"quiet","reference":"all team members introduced","expected_speaker":true,"overlap":false},
    {"id":"other-01","file":"other.wav","condition":"different speaker","reference":"all team members introduced","expected_speaker":false,"overlap":false},
    {"id":"mix-01","file":"mix.wav","condition":"overlap","reference":"all team members introduced","expected_speaker":true,"overlap":true}
  ]
}
```

```bash
python scripts/evaluate_audio.py study.json --model models/vosk-model-small-en-us-0.15 --speaker-model models/vosk-model-spk-0.4 --output audio-report.json
```

The report includes WER, target acceptance, false acceptance (other-speaker or overlap recordings) and offline real-time factor. Missing denominators are `null`, never manufactured as perfect scores. Labels are used only for scoring; they do not control recognition. Offline file acceptance requires every recognized segment to pass and does not exactly reproduce live partial-event timing. Use the live simulation for task-time, interruption and confirmation studies. No acoustic performance claims are supplied without recordings.

## Sources

- [Vosk streaming server example](https://github.com/alphacep/vosk-server/blob/master/websocket/asr_server.py)
- [Vosk speaker identification example](https://github.com/alphacep/vosk-api/blob/master/python/example/test_speaker.py)
- [MDN AudioWorklet](https://developer.mozilla.org/en-US/docs/Web/API/AudioWorklet)
- [MDN echo cancellation constraints](https://developer.mozilla.org/en-US/docs/Web/API/MediaTrackConstraints/echoCancellation)

## Verification recorded during implementation

The actual speech and speaker models loaded and processed the upstream Vosk `python/example/test.wav` fixture: three nonempty final transcripts and three speaker vectors were returned. This is only a model-loading/inference smoke test. It is not a held-out speaker test, checklist benchmark, noise test or clinical validation. The transport tests use an injected recognizer so authorization and failure paths can be exercised deterministically. Run the optional JavaScript capture/transport tests with `node tests/test_audio_client.cjs`.

## Duplex and multi-channel extension

The default remains guarded playback. The new **Experimental duplex recognition** checkbox keeps ASR running during playback; echo-contaminated turns are rejected rather than silently accepted. This option is unvalidated and requires a headset. Separate assigned accounts can keep different checklist-item channels open concurrently. An energy-based overlap monitor taints simultaneous channels so their turns are repeated. It cannot separate a mixed single-microphone waveform and is sensitive to cross-talk and network jitter. Changes to the selected item still stop stale capture; unrelated item changes no longer disconnect the channel. Enrollment completion arms a 30-second response deadline.

See [REQUIREMENTS.md](REQUIREMENTS.md) for real corpus results, reproducible noise generation and remaining tests. The newly published generated corpus failed voice enrollment; the earlier upstream model-loading smoke test did not establish speech or speaker accuracy.
