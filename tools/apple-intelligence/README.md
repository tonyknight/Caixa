# caixa-apple-intelligence

A small Swift program that lets Caixa use **Apple Intelligence**, the Mac's own on-device model
(Apple's Foundation Models), to write mail summaries and translations. Nothing leaves the Mac.

It needs macOS 26 or later on Apple silicon, with Apple Intelligence turned on (System Settings,
Apple Intelligence & Siri), and Xcode or its command-line tools to build (`xcode-select --install`).

## Building

Caixa builds it by itself the first time Apple Intelligence is chosen in Settings. To build it
yourself, from the repository's root:

```bash
swift build -c release --package-path tools/apple-intelligence
```

Then check that the model can be used:

```bash
tools/apple-intelligence/.build/release/caixa-apple-intelligence --check
```

It prints `{"ready":true}`, or why not: `not_eligible` (this Mac cannot run it), `not_enabled`
(Apple Intelligence is off), `not_ready` (the model is still downloading).

## How Caixa talks to it

Without arguments it reads one request per line on its input and writes one answer per line:

```
{"id":1,"instructions":"Summarize…","prompt":"Ana Costa, 2025-01-15: …","temperature":0.2}
{"id":1,"text":"Ana writes to Maria about…"}
{"id":2,"error":"declined by the safety filter","refused":true}
```

Each request gets a session of its own. Caixa runs as many of these programs at once as its
**Workers** setting (`caixa/apple_intelligence.py`). The on-device model reads about 4,000 tokens,
so Caixa sends at most 6,000 characters of a conversation (its first and last mails).
