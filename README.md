# comfyui-rapidraw

Notes and setup for running ComfyUI and the RapidRAW AI connector under `uv`,
on Apple Silicon. See `docs/SETUP.md` for the install plan and
`docs/FORKING.md` for the fork layout and phase order.

Three pieces, only two of which are Python:

| Piece | Language | Managed by |
| --- | --- | --- |
| RapidRAW | Rust + Tauri | downloaded app first, forked source later |
| RapidRAW-AI-Connector | Python 3.10+ | `uv` |
| ComfyUI | Python 3.13 | `uv` |

RapidRAW talks to the connector; the connector talks to ComfyUI. The connector
is deliberately separate so it can be updated without reinstalling RapidRAW.

Paths and hosts live in `.env` (gitignored). Copy `.env.example` to start.

This repo holds only notes, `.env` and scripts - no upstream code. The three
checkouts live as siblings under `~/git/`. See `docs/FORKING.md` for which
repos to fork, in what order, and where your own changes belong.

## Status

Old Python areas (`~/.pyenv`, `~/mambaforge`, `~/miniforge3`) cleared
2026-09-09. Working through the phases in `docs/FORKING.md`:

- [ ] 0. Remote for this repo
- [ ] 1. Connector: fork, clone, run under uv
- [ ] 2. ComfyUI: fork, clone, uv + nightly torch, one stock render
- [ ] 3. Wire the chain using the downloaded RapidRAW.app - no source changes
- [ ] 4. Fork and build RapidRAW from source
- [ ] 5. macOS 27 spike, separately
