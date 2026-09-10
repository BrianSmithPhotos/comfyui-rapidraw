# Setup plan

Verified 2026-09-09 against the upstream repos. Not yet executed.

## Why uv works here

ComfyUI is an ordinary Python app plus PyTorch. On Apple Silicon this is the
easy case: MPS needs no CUDA or ROCm index, so the index juggling that makes
uv awkward on other platforms does not apply.

Two caveats found upstream:

- The Mac instructions call for **PyTorch nightly**, not the stable PyPI wheel.
  That is a second index - a line of config in `[tool.uv.sources]`, not nothing.
- **Python 3.13** is very well supported. 3.14 works but breaks some custom
  nodes. 3.12 is the conservative fallback. Start on 3.13.

ComfyUI-Manager installs custom-node dependencies at runtime by shelling out,
which is where uv purity usually breaks. It has a `use_uv` switch in
`config.ini` - set it, or Manager will quietly reintroduce pip.

## ComfyUI

Installed and verified 2026-09-09 at v0.35.0. **Order matters**: `torch` is
unpinned in `requirements.txt`, so nightly goes in first and the rest follows.
Doing it the other way round gets the stable PyPI wheel.

    uv venv --python 3.13
    uv pip install --pre torch torchvision torchaudio \
      --index-url https://download.pytorch.org/whl/nightly/cpu
    uv pip install -r requirements.txt
    uv run python main.py --listen 127.0.0.1 --port 8188

The second install leaves the nightly alone - checked, torch was still
`2.15.0.dev20260908` afterwards. On macOS the nightly MPS build ships in the
`/nightly/cpu` channel; there is no separate mps index.

Verified rather than assumed: `torch.backends.mps.is_available()` is true, and
a 1024x1024 matmul on the `mps` device returns the correct sum. ComfyUI then
reports device `mps` with the full 128 GB of unified memory as VRAM.

Two benign startup warnings on Darwin: `comfy-aimdo` logs "Could not autodetect
AIMDO implementation, assuming Nvidia" and then that it only supports Windows
and Linux. Nothing to fix.

Set `use_uv` in ComfyUI-Manager's `config.ini` once Manager is installed.

## What the connector's workflow actually needs

`workflow.json` is not a generic graph - it pins specific weights and one
custom node. Nothing renders until these are present:

| Requirement | Kind | Approx |
| --- | --- | --- |
| `XL_RealVisXL_V5.0_Lightning.safetensors` | SDXL Lightning checkpoint | 6.5 G |
| `diffusion_pytorch_model_promax.safetensors` | ControlNet Union Promax SDXL | 2.5 G |
| `sdxl_vae.safetensors` | SDXL VAE | 335 M |
| `InpaintCropImproved`, `InpaintStitchImproved` | custom node | small |

The two nodes come from `lquesada/ComfyUI-Inpaint-CropAndStitch` (GPL-3.0,
actively maintained). Every other node in the graph is core in v0.35.0 -
checked one by one. KSampler sits at `steps: 8, cfg: 1`, which is consistent
with the Lightning checkpoint and means renders should be fast.

## RapidRAW-AI-Connector

The easiest piece. Python 3.10+, a `requirements.txt` of pure-Python web stack
with no compiled ML and no torch:

    fastapi, uvicorn[standard], pydantic-settings, aiohttp,
    websockets, aiofiles, numpy, Pillow, python-multipart

    uv venv
    uv pip install -r requirements.txt
    uv run python main.py

Configured entirely through environment variables (`COMFY_HOST`, `COMFY_PORT`),
which suits the `.env` convention. In RapidRAW's settings, point the
Self-Hosted AI Backend at the connector's address.

It caches images rather than resending them: the full image goes over once, and
subsequent edits transfer only the mask and prompt.

Upstream calls it work in progress and not ready for production.

## The old installs are gone

Removed 2026-09-09: `~/.pyenv` (4.2 G), `~/mambaforge` (3.9 G) and
`~/miniforge3` (3.8 G), which held `lstein-stable-diffusion` and `ldm` from
2022 and `invokeai` from 2024. Their PyTorch long predated current MPS support,
so none of it carried over - a fresh uv install was the right move regardless.
Verified gone, along with any stray `anaconda3` or `miniconda3`.

Clearing them also removes the VS Code interpreter scan that produced a
spurious "no Python found" prompt after a reboot on 2026-09-09: discovery took
20.2 seconds crawling all three before resolving on its own.

Homebrew Python remains and is what uv will draw on: 3.13.14 is installed at
`/opt/homebrew/bin/python3.13`, which is the version this plan targets.

## Sources

- https://github.com/Comfy-Org/ComfyUI
- https://github.com/CyberTimon/RapidRAW
- https://github.com/CyberTimon/RapidRAW-AI-Connector
- https://github.com/Comfy-Org/ComfyUI-Manager (moved from ltdrdata/)

## The absolute-path failure, and the fix

The connector does not work against a stock ComfyUI. Found by reading the
source, then reproduced deliberately before fixing anything.

**Symptom.** `POST /inpaint` returns 500. ComfyUI logs:

    Failed to validate prompt for output 41:
    * LoadImage 47:
      - Custom validation failed: image - Invalid image file: .../cache/mask_<uuid>.png
    * LoadImage 30:
      - Custom validation failed: image - Invalid image file: .../cache/sources/<id>.png

**Root cause.** `build_workflow` in `engine.py` writes absolute paths into the
workflow's two `LoadImage` nodes (30 = source, 47 = mask). ComfyUI resolves
those in `folder_paths.get_annotated_filepath`, where two lines interact badly:

    filepath = os.path.abspath(os.path.join(base_dir, name))
    if not is_within_directory(base_dir, filepath):
        raise ValueError(...)

`os.path.join` discards `base_dir` when `name` is absolute, so `filepath`
becomes the connector's path, which is not inside ComfyUI's input directory,
so the guard rejects it. This is a deliberate path-traversal defence, not a
bug in ComfyUI - the connector is the side making the wrong assumption.

**Fix, no code change.** Point ComfyUI's input directory at the connector's
cache root. Sources are written to `cache/sources/` and masks to `cache/`, so
both fall inside it and the guard passes:

    --input-directory "$CONNECTOR_DIR/cache"

`scripts/run-comfyui.sh` does this from `.env`.

**Better fix, for the fork.** Have the connector POST images to ComfyUI's
`/upload/image` endpoint and reference the returned name, instead of passing
filesystem paths. That also survives ComfyUI moving to another machine, which
the current design cannot. This is the natural first change to make in a fork
we own.

## End-to-end proof

Verified 2026-09-09 with a script standing in for RapidRAW: upload a synthetic
1024x1024 source, then request an inpaint over a 264x264 rectangular mask.

    upload -> {'status': 'cached', ...}
    inpaint completed in 22.8s
    response keys: ['x', 'y', 'width', 'height', 'color', 'mask']
      color: (297, 297) RGBA
      mask:  (297, 297) L

The prompt was "a bunch of red roses, sharp focus" and the render contains red
roses, blended to the source's colour. 22.8 s on MPS at 8 steps.

Note what comes back: a patch, not a frame. The response carries an offset, a
size, and a 297x297 region - the mask plus the workflow's 32 px padding. The
caching claim holds in both directions, so only the changed region travels.

## Phase 3: what to expect from RapidRAW.app

RapidRAW is not installed on this machine - `mdfind` finds no bundle outside
the git checkouts. Latest upstream release is **v1.6.3** (2026-09-03). Two
macOS arm64 builds are published, plain and `tethering`; take the plain one
unless camera tethering is wanted.

Downloaded 2026-09-09 to `~/Downloads`. Integrity confirmed against the digest
GitHub publishes for the asset - identical, not merely "downloaded fine":

    size   29843165 bytes
    sha256 949aea4fb2ee9bd3e7fbcc1af63a1076b81d68a4ca6a11c31fdf6a909ccc913a

Inspected by mounting the image read-only. No app was launched.

| | |
| --- | --- |
| Version | 1.6.3 |
| Bundle ID | `io.github.CyberTimon.RapidRAW` |
| Architecture | `arm64` only, not universal |
| Signature | `adhoc, linker-signed`, TeamIdentifier not set |
| `spctl -a -t exec` | rejects it |

So issue #37 is confirmed by inspection, not just by report: the build carries
no Developer ID and is not notarised.

    02_RapidRAW_v1.6.3_macos-14_aarch64.dmg

Known hazards, from upstream issues rather than from running it:

| Hazard | Evidence | What it means here |
| --- | --- | --- |
| Not signed or notarised | confirmed by inspection, above; issues #37 and #1438 both open | Gatekeeper refuses the bundle. Allow it in System Settings > Privacy and Security on first launch. Do not blanket-remove quarantine attributes. |
| The dmg carries no quarantine flag | `xattr` reports no `com.apple.quarantine` | Because it was fetched with `gh`, not a browser. A copy out of this image will therefore skip the first-launch prompt entirely. That is a real reduction in checking, and the reason it is acceptable here is the digest match above - the bytes are provably GitHub's. |
| `failed to save changes: operation not permitted (os error 1)` | issue #1616, open, Apple Silicon, v1.6.2 | Reported as SIP; far more likely TCC. If it appears, grant RapidRAW access to the photo folder in Privacy and Security > Files and Folders. |
| Poor performance on recent macOS | issue #515, open, "Tahoe" (macOS 26) | We are a major version further on at 27. Treat any slowness as expected-unknown, not as a local misconfiguration. |
| Backend address field drops focus per keystroke | issue #197, closed | If typing the connector URL misbehaves, paste it instead. |
| `workflow.json` will not load in the ComfyUI editor | issue #424, closed | It has no `version` key, so the ComfyUI UI rejects it with a Zod error. It is fine over the API, which is how the connector uses it. Do not "fix" it to make the editor happy. |

The connector README states the setting plainly: point RapidRAW's `Self-Hosted`
AI Backend at the connector, not at ComfyUI.

    http://127.0.0.1:5000

Also from that README: official support was declared to begin at RapidRAW
v1.4.9, and the connector is still labelled unstable upstream.

### Andy Hutchinson's write-up

Brian flagged a parallel walkthrough. Both copies are paywalled and could not
be read - Patreon returns 403 to any non-member fetch, and the Substack
mirror cuts off above the technical content:

- https://www.patreon.com/AndyHutchinson/posts/generative-adobe-168829104
- https://ahutchinson.substack.com/p/generative-remove-without-the-adobe

If the text is pasted in, cross-check it against the absolute-path finding
above: that is the failure most likely to differ between his setup and ours,
since it only bites when ComfyUI and the connector disagree about the input
directory.

## Phase 3 confirmed: RapidRAW.app to connector to ComfyUI

Verified 2026-09-09 16:31 from a real edit made in the app - prompt "Stormy
clouds" on a 5184x3888 frame. Clean 200, no errors:

    16:31:12 POST /inpaint       404   (source not cached yet)
    16:31:13 POST /upload_source 200   (7855112 bytes)
    16:31:13 POST /inpaint       200
             Workflow completed in 16.3975s
             Crop bounds: x=0, y=0, w=5184, h=1783
             Total Request Time: 17.6733s

**The 404 is not a fault.** RapidRAW asks first and uploads only if told the
source is unknown, which is the whole point of the cache. Expect exactly one
404 per new image per connector run, then never again for that image.

**Timing.** The first render of a session was 22.5 s because it loaded the
checkpoint, VAE, CLIP and ControlNet. Warm steady state is about 16 s, and
ComfyUI logs no further "Requested to load" lines. Source resolution barely
matters - see below for why.

### The resolution ceiling - important for real photographs

`workflow.json` renders every edit at **1280 px**, whatever the frame size.
Node 37 is a `PrimitiveInt` of 1280 wired into `InpaintCropImproved`'s
`output_target_width` and `output_target_height`, and into the `EmptyImage`
that seeds the masked area. The chain is:

    LoadImage -> InpaintCropImproved (crop to mask, 1.5x context, resize to 1280)
              -> KSampler (8 steps, cfg 1, euler/ddim_uniform)
              -> InpaintStitchImproved (scale back, blend 32 px, full resolution)

So the generated pixels are synthesised at 1280 and then scaled up to fill the
masked area. On the stormy-clouds edit the masked region spanned the full
5184 px width, so the new content was enlarged roughly 4x on its long edge.
That is the quality ceiling, and it is why a 20 MP source costs no more time
than a 1 MP one.

Raising node 37 trades time and memory for detail. It is a workflow edit, not
a code change, and it is the obvious first experiment for photographic work.

### What the app actually sends

| | |
| --- | --- |
| Source | a 5184x3888 **JPEG** render, not the RAW |
| Mask | full-resolution RGBA PNG |
| Seed | supplied per request; the smoke test's fixed 42 was ours, not the app's |
| Model | `XL_RealVisXL_V5.0_Lightning.safetensors` with SDXL VAE and a promax union ControlNet in `repaint` mode |

The connector mirrors both inputs to `cache/sent/` on every request, so
`last_sent_image.jpg` and `last_sent_mask.png` are always the last thing
ComfyUI was asked to work on. Useful when a result looks wrong: check the mask
there before suspecting the model.

## Phase 4: building RapidRAW from source

Fork cloned to a sibling checkout, `upstream` push disabled, working on a
`build/v1.6.3` branch cut from the tag rather than `main`. `main` was 20
commits ahead at the time; building the exact tag that we already proved works
as a binary means any difference is the build, not upstream's work in progress.

### Toolchain: check the pin before starting a build

    src-tauri/rust-toolchain.toml   channel = "1.98"
    src-tauri/Cargo.toml            rust-version = "1.98", edition = "2024"

The machine had Homebrew Rust 1.96.0. **Homebrew's rust ignores
`rust-toolchain.toml`** - that file is a rustup feature - so the pin would not
have corrected it and the build would have failed on MSRV partway through.
Homebrew stable happened to be 1.98.0, so `brew upgrade rust` was enough and
no rustup install was needed. Now on 1.98.1.

The Tauri CLI is an npm devDependency (`@tauri-apps/cli`), so `npm install`
provides it. There is no need for `cargo install tauri-cli` and its long
build.

    npm install
    npm run tauri build

### Two things in Cargo.toml worth knowing

    wgpu = "29.0" # Downgraded to prevent P3 color shifts on Apple devices
    objc = "0.2"

The first is a colour-management problem serious enough that upstream pinned
an old graphics abstraction to avoid it - which matters more here than in most
apps, since the whole point is looking at photographs.

The second is the unmaintained `objc` crate, used in
`src-tauri/src/window_customizer.rs` to reach AppKit through raw `msg_send!`
for window corner rounding. Any new macOS bridging we write should use
`objc2`, which is maintained and has sound `msg_send!` semantics. Noted for
phase 5.

### Build result

Built clean on the first attempt once Rust was at 1.98.

    Finished `release` profile [optimized] target(s) in 9m 34s
    Built application at: src-tauri/target/release/RapidRAW
    Bundling RapidRAW.app
    Bundling RapidRAW_1.6.3_aarch64.dmg

Wall clock 10m 10s at 247 percent CPU, so it is nowhere near saturating 20
cores - the long pole is a dependency chain, not parallel work.

| | ours | released |
| --- | --- | --- |
| Version | 1.6.3 | 1.6.3 |
| Architecture | arm64 | arm64 |
| Signature | adhoc, linker-signed | adhoc, linker-signed |
| Executable size | 36215840 | 36215840 |
| Executable SHA-256 | `f6f64818...` | `dbe7ffca...` |

Same size to the byte, different hash. So the build is faithful but **not**
bit-reproducible - expected, since Rust embeds absolute source paths and the
Mach-O carries a fresh `LC_UUID` per link. Not a cause for concern, but worth
knowing before anyone tries to verify a build by hash.

### The build reaches out to the network

    Downloading ONNX Runtime library for macos-aarch64...
    URL: https://huggingface.co/CyberTimon/RapidRAW-Models/resolve/main/
         onnxruntimes-v1.22.0/libonnxruntime-macos-aarch64.dylib
    Successfully downloaded and verified src-tauri/resources/libonnxruntime.dylib

`build.rs` pulls a 32 MB ONNX Runtime dylib from the maintainer's own Hugging
Face repo at build time, rather than from Microsoft's releases or a crate.
It does verify integrity after download. Two consequences: the build is not
offline-capable on a clean tree, and the binary carries a native library from
a personal account. Neither is unusual for a hobby project, and neither is
hidden - but it belongs in the notes rather than being discovered later.

Fork hygiene holds: the dylib lands in a gitignored path, and `git status` is
clean after a full release build.
