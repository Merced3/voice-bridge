# Core constraints — paths and rules where changes stay human-reviewed

Everything listed here is load-bearing for what voice-bridge IS. Automated
agents (the dev loop) may propose changes to these in discussion, but must
never include them in a commit; a human makes those edits. Merges touching
these paths always require the owner's explicit approval.

## The transport boundary (ADR 0001)

voice-bridge is **transport-only**: a token-gated phone/browser page with
hold-to-talk duplex audio, exposing the same consumer contract as
discord-hub's `/voice/stream`. The following are out of scope forever, and
any change that smells like them is wrong here:

- **No brain.** No STT, no TTS, no LLM, no conversation policy, no
  transcripts, no turn-taking logic. The brain belongs to the consuming
  project.
- **No Discord code, ever.** Discord voice lives in discord-hub; this is
  the alternative transport, byte-compatible at the contract level.
- **Wire adaptation is mono↔stereo only** (browsers speak s16le 48 kHz
  mono; consumers get the hub-mirrored stereo contract). Any other
  per-transport deviation needs an ADR first.

Guardian files for this boundary:

- `docs/decisions/0001-transport-only-web-channel.md` (and all ADRs)
- `docs/api.md` — the consumer contract; changing it is a versioning
  decision for every consumer, never a drive-by
- `src/` stream-ownership and PCM framing code — one owned stream at a
  time; frames are the contract

## Deploy and access safety

- `.github/` — CI and automation wiring (shared-checklist caller,
  Dependabot, auto-merge)
- `pyproject.toml` dependency pins that affect the Docker image (a missing
  package once made `/health` green while voice was 100% broken —
  `websockets`, `libopus0`; RUNBOOK 2026-10-17)
- Token gating: empty token = local-only trust, and off-LAN is Tailscale,
  never a public tunnel (ADR 0001 §3). Any change to how the page or
  stream authenticates is human-only.

## Rule of thumb

If a change could make `/health` pass while voice is broken, weaken the
token gate, or add "meaning" to the transport — it belongs to a human.
