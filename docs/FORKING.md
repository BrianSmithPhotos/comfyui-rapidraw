# Forking plan

How the three upstream repos get forked, cloned and laid out, and what this
repo is for. Written 2026-09-09. Nothing forked yet.

## The three upstreams are not alike

| Upstream | Licence | Size | Pace | Fork it? |
| --- | --- | --- | --- | --- |
| `Comfy-Org/ComfyUI` | GPL-3.0 | 98 MB | release most weeks | fork, but stay on upstream |
| `CyberTimon/RapidRAW` | AGPL-3.0 | 351 MB | active | fork, later |
| `CyberTimon/RapidRAW-AI-Connector` | Apache-2.0 | 37 KB | quiet | fork first |

Two things follow from that table.

**ComfyUI does not want to be forked for features.** Its extension model is
custom nodes - a `custom_nodes/` directory that is not part of the repo. Carry
your own commits on a fork and every weekly release becomes a rebase. Fork it
anyway (a fork costs nothing to hold, and it is where PR branches live), but
keep `master` byte-identical to upstream and put your own work in a separate
custom-node repo.

**Licences differ where it matters.** The connector is Apache-2.0, so anything
added to it is yours to license as you like. RapidRAW is AGPL-3.0: a published
fork stays AGPL, and so does any macOS 27 Swift code linked into it. Not a
blocker, but decide it knowingly rather than discover it later.

## Layout: siblings, not submodules

    ~/git/
      comfyui-rapidraw/          <- this repo: notes, .env, scripts. No upstream code.
      ComfyUI/                   <- clone of the fork
      RapidRAW/                  <- clone of the fork
      RapidRAW-AI-Connector/     <- clone of the fork

Submodules would pin 351 MB of RapidRAW into this repo's history and turn every
`git pull` into two steps - precisely the friction you do not want when the
whole point is tracking a fast upstream. Siblings keep this repo tiny and keep
the checkouts free to move at their own pace.

The wiring already exists: `.env` carries `COMFYUI_DIR` and `CONNECTOR_DIR`.
Add `RAPIDRAW_DIR` when that checkout appears.

Nesting the checkouts inside this repo and gitignoring them also works, but one
missed gitignore entry publishes a macOS path. Siblings cannot make that
mistake.

## Fork hygiene

`gh repo fork --clone --remote` sets up the standard triangle in one command:

    origin    BrianSmithPhotos/<repo>    push here
    upstream  <original>/<repo>          fetch only

Then disable pushing to upstream so it cannot happen by accident:

    git remote set-url --push upstream DISABLED

Keep `master`/`main` tracking upstream and do all work on branches. That way
`git fetch upstream && git merge upstream/master` is always a fast-forward.

## Order of work

Each phase ends with something demonstrably running. Do not start the next
until the current one does.

**0. Give this repo a remote.** It has none - it is local-only on `master`.
Create `BrianSmithPhotos/comfyui-rapidraw` and push.

**1. Connector only.** Fork, clone, `uv venv`, `uv run python main.py`, confirm
it serves. 37 KB and a permissive licence make this the cheapest way to prove
the fork-and-uv pattern before spending it on something large.

**2. ComfyUI.** Fork, clone, `uv venv --python 3.13`, nightly torch per
`SETUP.md`, and get one render out of a stock workflow. No custom nodes yet.

**3. Wire the chain with zero source changes.** Point the connector at ComfyUI,
then point the *downloaded* RapidRAW.app at the connector via Self-Hosted AI
Backend. This proves the whole path works before any building from source.

**4. Fork RapidRAW and build it.** Only now. Rust 1.96 and Node 22 are already
installed; Tauri needs its CLI. Building a 351 MB Tauri app before knowing the
stock binary works means debugging two things at once.

**5. macOS 27 spike, on its own.** Tauri is Rust, and Rust cannot call
Foundation Models directly. The realistic path is a Swift helper binary the
Rust side shells out to, or an `objc2` shim. That is a research task, not a
step in this sequence - and per the Xcode note it must build with
`DEVELOPER_DIR=/Applications/Xcode-beta.app/Contents/Developer`.

## Where your own capabilities go

- **ComfyUI features** -> a new custom-node repo, symlinked into
  `ComfyUI/custom_nodes/`. Never a patch to the ComfyUI fork.
- **Connector features** -> straight into the connector fork. `workflow.json` is
  the ComfyUI graph it injects, so changing what the pipeline does is often just
  that file plus `engine.py`.
- **RapidRAW UI or macOS 27 work** -> the RapidRAW fork, on a branch, AGPL.
