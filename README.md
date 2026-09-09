# comfyui-rapidraw

Notes and setup for running ComfyUI and the RapidRAW AI connector under `uv`,
on Apple Silicon. Nothing is installed yet - see `docs/SETUP.md` for the plan.

Three pieces, only two of which are Python:

| Piece | Language | Managed by |
| --- | --- | --- |
| RapidRAW | Rust + Tauri | downloaded app, nothing to manage |
| RapidRAW-AI-Connector | Python 3.10+ | `uv` |
| ComfyUI | Python 3.13 | `uv` |

RapidRAW talks to the connector; the connector talks to ComfyUI. The connector
is deliberately separate so it can be updated without reinstalling RapidRAW.

Paths and hosts live in `.env` (gitignored). Copy `.env.example` to start.

## Status

Planned, not built. Deferred until the SwiftPhotoLog copy-in finishes, to keep
the NAS walk and a multi-gigabyte torch download off the same machine at once.
