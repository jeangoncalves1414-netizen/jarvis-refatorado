# Local identity work — validation record

The pre-change Git checkpoint is `6d03f7e`. Implementation is still in progress.

## Speech segmentation

Uses the MIT licensed pyannote segmentation 3.0 model exported by Sherpa-ONNX,
with ONNX Runtime CPU inference. No account, API key or paid service is needed.
The model is downloaded by the existing voice-model installation action. Downloads
and the extracted model are SHA-256 checked. Model licensing is included under
`docs/licenses/voice-models/segmentation-3.0.txt`.

Sources:
- https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/index.html
- https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-segmentation-models
- https://huggingface.co/pyannote/segmentation-3.0

The enrollment gate detects speech activity, multiple local speaker labels and overlapping
speech before extracting a single identity embedding. It rejects clips containing
at least 0.2 seconds of overlap or two local speakers with at least 0.2 seconds
each. These are operating thresholds, not calibrated confidence percentages.
The labels are local to each 10-second window, advanced by 5 seconds. Summary
durations are maxima per window, not total clip durations.

Conversation calls now use `voice_diarization.py`: segmentation yields timed
non-overlapping spans, each sufficiently long solo span is matched to enrolled
WeSpeaker embeddings, and consecutive spans with the same confirmed profile can
be joined. Local speaker indices are never equated across windows. Unenrolled
people are left unknown, rather than assigned persistent fictional identities.
Mixed turns have each solo span transcribed separately using the configured STT
provider, with at most two parallel calls. This associates text with the audio
span, not individual word timestamps. The original enrollment gate still rejects
mixed voices; it never saves a mixed template.

Short, overlapping or uncertain spans are not given a person's name. A group
never inherits an administrator's access. Consecutive microphone chunks buffered
in the UI are combined using server-issued, expiring, one-use tokens; names sent
as ordinary user text are not evidence. Single-speaker inference overlaps the
normal STT call and has a bounded extra wait of 350 ms; busy/timeout results stay
unknown. Recognition completeness therefore still depends on inference speed.

## Earlier model checks (before conversational diarization)

On this Windows CPU, the real model processed 10 seconds of silence in about
0.12–0.24 seconds. A public 56.86-second four-speaker sample from the release
was detected as containing multiple speakers in 1.07 seconds. Its first three
seconds were classified as one speaker, with about 2.45 seconds of speech.
Silence produced zero speech and zero overlap.

Artificial mixes of the sample's 1–5 second excerpt with the 25–29 and 50–54
second excerpts produced 0.52 and 0.51 seconds of detected overlap. Mixes with
the 15–19 and 45–49 second excerpts did not detect overlap. Speaker identities
of these excerpts were not manually annotated. These observations demonstrate
inference and some overlap detection, not an accuracy benchmark or complete
overlap recall. No household voices or faces were used in these tests.

24 tests passed across segmentation, voice identity, profiles and app lock.
They include synthetic class outputs for silence, sequential speakers, overlap,
padding exclusion, and rejection before identity inference. Unit tests do not
replace real microphone and multi-person evaluation.

## Remaining acceptance work

On 2026-11-14 the updated segmentation code also ran against the installed real
ONNX model with synthetic silence: 3, 10 and 20 seconds returned no speech and no
speaker spans. Inference took approximately 395 ms (initial load), 160 ms and
405 ms respectively while other checks were running. This is a smoke test, not
a live-call latency or speaker-accuracy benchmark. The updated Python suite
passed 151 tests, including separate sequential-speaker matching, overlap
rejection, per-span transcription, and fail-closed merging of buffered tokens.

- Measure false acceptance/rejection with enrolled and unknown people, including
  Jean visible while another person speaks off camera.
- Validate latency and recognition on the actual microphone, distance and noise.
- Evaluate the new temporal attribution with annotated sequential speakers,
  especially short phrases, window boundaries and missed overlaps.
- Validate the complete call UI and agent response path with real samples.
- Face presence alone must never be treated as proof of who spoke; audiovisual
  active-speaker verification is not implemented.
