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

## The generation resolution sweep

Node 37 changed, everything else held fixed - same source, same mask, same
seed - driving ComfyUI directly with the connector's own `workflow.json`.
Subject was a real 5184x3888 frame with the sky masked.

| node 37 | time | result |
| --- | --- | --- |
| 1280 (default) | 16.1 s | ok |
| 1536 | 23.1 s | ok |
| 1664 | 29.2 s | ok |
| 1728 | 0.6 s | **fails** |
| 2048 | 0.6 s | **fails** |

### There is a hard ceiling on Apple Silicon, and it is not memory

    RuntimeError: MPSGraph does not support tensor dims larger than INT_MAX

Raised from the VAE encoder's mid-block self-attention, not from the sampler,
and it is not an out-of-memory condition - the machine has 128 GB and ComfyUI
explicitly checks for OOM and re-raises this as something else.

The arithmetic is exact. The VAE bottleneck attends at `side/8`, so the
attention matrix holds `(side/8)^2` squared elements, and MPSGraph indexes
with a signed 32-bit integer:

    side 1664 -> 43264 tokens -> 1,871,773,696 elements  under INT_MAX
    side 1728 -> 46656 tokens -> 2,176,782,336 elements  over INT_MAX

Predicted ceiling `8 * (2^31-1)^0.25` = **1722 px**. Tested 1664 and 1728 to
bracket it; both behaved exactly as predicted. So the usable range is 1280 to
about 1712, and 2048 is not reachable on MPS without tiled VAE encoding.

### Same seed does not mean same image

Changing node 37 changes the latent dimensions, so the noise lands
differently and the clouds come out somewhere else entirely. Measured against
the 1280 render, mean absolute difference over the generated band was 7.6
levels at 1536 and 11.2 at 1664 - different weather, not the same weather in
more detail. Resolution cannot be A/B tested at a fixed seed.

### What the extra time actually buys

Detail proxies over the regenerated band:

| node 37 | mean gradient | Laplacian variance |
| --- | --- | --- |
| 1280 | 0.6347 | 12.216 |
| 1536 | 0.7002 | 12.255 |
| 1664 | 0.7783 | 12.574 |

Mean gradient rises 23 percent from 1280 to 1664; Laplacian variance barely
moves at 3 percent. For 80 percent more time, that is a poor trade **on this
subject** - and the caveat matters, because an overcast sky is nearly the
worst possible test for detail. There is almost no high-frequency content for
the extra resolution to resolve. A textured subject - foliage, brickwork,
water, fabric - is where the difference should show, and that test has not
been run.

Provisional recommendation: leave node 37 at 1280 for skies and other smooth
areas, and re-test on texture before changing the default.

## Quick Erase ghosting - the feather, not the model

A running figure erased with Quick Erase left a visible ghost. Root-caused
2026-09-10.

**It never reached ComfyUI.** The connector log has no matching request, and
the sidecar records `type: quick-eraser` with an empty `prompt`. Quick Erase
uses RapidRAW's own bundled LaMa (`lama_fp16.onnx` in Application Support),
not the SDXL workflow. Worth checking first whenever a generative result looks
wrong: the two paths fail differently.

**LaMa's fill is clean.** Decoding `patchData.color` from the sidecar shows the
fence, grass and chairs reconstructed with no trace of the figure. The model
did its job.

**The ghost is in the composite.** Decoding `patchData.mask` from the same
patch, over a 463x760 region:

    full strength (>0.99)   9.3%
    partial (0.01-0.99)    58.9%
    zero (<0.01)           31.8%

Across nearly 60 percent of the patch, the original pixels are blended back
over the clean fill. That is the ghost, and it is arithmetic, not a model
failure. The figure's feet come out worst - the mask reaches only about half
strength there, so half the shoes survive.

**Cause: the default feather.** The sidecar records `grow: 75, feather: 75`,
and `AIPanel.tsx` defines exactly those as the Quick Eraser defaults:

    [Mask.QuickEraser]: {
      parameters: [
        { key: 'grow',    min: -100, max: 100, step: 1, defaultValue: 75 },
        { key: 'feather', min: 0,    max: 100, step: 1, defaultValue: 75 },
      ],
    }

75 percent feather is reasonable for blending a tonal adjustment. It is wrong
for erasing an object, where the mask interior must be fully opaque or the
subject shows through. Both sliders are adjustable in the AI panel.

**Fix:** keep `grow` high, drop `feather` to roughly 10-20. Grow covers the
subject and its contact shadow; a small feather is all that is needed to hide
the seam.

Upstream inconsistency spotted while confirming this: `maskUtils.ts` creates a
Quick Eraser submask with `grow: 50, feather: 50`, while `AIPanel.tsx`
declares defaults of 75. The panel wins in practice. Harmless, but it means
the "default" depends on where you look.

## The ghost is the feather, and the graph already blends its own seam

Second attempt at removing a running figure, this time routed deliberately
through ComfyUI rather than the bundled LaMa. It hit Comfy - 20.8s of sampling,
prompt "Remove the runner", crop bounds x=2770 y=1000 w=415 h=713. The result
still ghosted, worse than before.

Three hypotheses, tested one at a time against the same source, mask and seed.

### Ruled out: the prompt

`engine.py:306` splices RapidRAW's prompt into node **7**, the *positive*
conditioning:

```python
wf["7"]["inputs"]["text"] = ", ".join(filter(None, [prompt, wf["7"]["inputs"]["text"]]))
```

So "Remove the runner" asks the model to *paint* a runner, and it obliged with a
dark humanoid blob. Worth knowing, but not the cause: re-running with an empty
prompt and with a descriptive one ("wooden fence, dry grass, white adirondack
chairs, trees") ghosted just as badly.

Note `cfg: 1`, required by the Lightning checkpoint, disables classifier-free
guidance - so node 8's negative prompt is inert. Phrasing a removal as a
negative cannot work here. For removal, describe what should *be* there, or
send nothing.

### Ruled out: the ControlNet hint

The graph blanks the hint with a hard threshold before conditioning on it:

```
[10] ThresholdMask value=0.5      <- [36] cropped mask
[11] ImageCompositeMasked          destination=cropped image, source=black, mask=[10]
[14] ControlNetApplyAdvanced       strength=1.0, image=[11]
```

Since the mask was 86.9% partial, only ~46% of its pixels clear 0.5, so this
looked like the culprit - a control image still showing the subject's edges at
strength 1.0. Dumping node 11 through a `SaveImage` disproved it: the runner is
solidly black in the hint. Threshold 0.5 sits well inside the feather ramp.

### Confirmed: the feather

Same source, same seed, same empty prompt, the mask binarised at 25/255 as the
only change:

| | core (mask=255) | feathered ring (1-254) |
| --- | --- | --- |
| soft mask, as the app sent it | 27.8 | **7.5** |
| same mask binarised | 29.5 | **17.9** |

(mean absolute difference from the source; higher means more of the subject
actually replaced). The feathered ring is **86.9% of the masked area**, and
across it the original pixels are largely retained. The binarised run is clean -
fence, chairs, grass and tree all reconstructed, no figure.

Two mechanisms compound, both downstream of the hint:

- `SetLatentNoiseMask` (node 16) takes the *soft* mask, so the edges are only
  partially denoised.
- `InpaintStitchImproved` (node 35) blends the result back by the same soft
  mask, laying the original over the fill.

### The fix

Set feather to **0**. The graph already blends its own seam:

```
[36] InpaintCropImproved   mask_blend_pixels: 32
```

RapidRAW's feather is therefore redundant *and* harmful - it double-blends, and
the outer blend is applied to the subject rather than to the seam. Keep `grow`
positive and generous; that is what pulls the mask past the subject's edges.

Defaults that produce this, for the fork:

- `src/components/panel/right/AIPanel.tsx:131` - `feather` defaultValue 75
- `src/utils/maskUtils.ts:48` - `feather: 50` (inconsistent with the above)

### Separately: the mask missed the shoes

Overlaying the mask on the source shows good coverage of the body but only faint,
low-value blobs over the shoes, which survive every run including the binarised
one. That is a masking gap, not a model failure - brush them in or raise `grow`.

## Feather 0 confirmed, and why Subject select drops the shoes

### The fix holds

Brush mask, feather 0, empty prompt, 16.6s. Clean removal - runner gone including
the shoes, fence, chairs, grass and tree all reconstructed. Mask composition
moved from 13.1% full strength to **58.4%**.

The remaining 41.6% partial is not the feather slider. Profiling the mask edge
shows a ramp roughly 25-30px wide, with the deep interior (>25px in) 87.1% full
at mean value 251.9. That is the brush's own edge falloff, not `feather`. It is
small enough not to ghost, but worth knowing there is a floor.

### Subject select and the shoes

Not a bug in the mask index. `ai_processing.rs:1271` takes SAM's first mask:

```rust
let first_mask_slice = &mask_slice[0..area];
```

The decoder returns 4 mask tokens plus `iou_predictions`, and RapidRAW ignores
the scores - which looked like the cause. Running the same encoder and decoder
directly with a box around the runner disproves it:

| token | iou | area |
| --- | --- | --- |
| **masks[0]** | **0.904** | 65824 |
| masks[1] | 0.859 | 69388 |
| masks[2] | 0.883 | 65716 |
| masks[3] | 0.876 | 59063 |

All four are near-identical and `argmax(iou)` picks 0 anyway. RapidRAW's choice
is correct.

The real reason is that SAM segments *the person*, and the shoes are a distinct
object. The returned mask includes the socks and ankles but stops at the dark
shoe bodies. Enlarging the rectangle cannot help: the box bounds the search, it
does not force inclusion.

Adding one positive point per shoe does help - and SAM agrees it is a better
mask:

| prompt | iou |
| --- | --- |
| box only | 0.904 |
| box + 2 shoe points | **0.919** |

The front shoe becomes fully covered; the rear one improves but stays partial.

**The backend already supports this and the UI never uses it.**
`run_sam_decoder` builds `point_labels` with `1.0` for positive points
(`ai_processing.rs:1203`), but `GenerateAiSubjectMask` is invoked with only
`startPoint` and `endPoint` (`src/hooks/useAiMasking.ts:180`). Exposing
click-to-add-point on the subject tool is a UI change over a backend that is
already there - a good first candidate for the fork.

Until then the working sequence is Subject select, then a second **additive**
submask (`SubMaskMode.Additive`, `src/utils/maskUtils.ts:8`) brushed over the
shoes.

Worth noting the subject tool's defaults are already sane -
`{ grow: 0, feather: 0 }` at `maskUtils.ts:43` - unlike Quick Eraser's 75/75.

## Large masks: an empty prompt is not neutral, and resolution plateaus

A flock of sandpipers on a rock, brushed out in one mask. Mask quality was
finally perfect - **100% full strength, 0% partial** - so feather is no longer a
variable. But the result invented new birds.

### Why the birds came back

The mask covers **29.7% of the frame**, bbox 3737x2794. That is not inpainting,
it is generative fill: the model must invent a region larger than most whole
images. The surrounding *unmasked* pixels still show rock, water and birds, so
with an empty prompt the model completes the obvious pattern.

An empty prompt is neutral only when the surroundings are unambiguous. On the
runner it was fine - a fence and grass imply fence and grass. On a bird colony
it implies birds.

Since the prompt lands in the *positive* conditioning (see above), describing
the desired content is the working lever. `"bare granite rock, dry grass, still
water, empty shoreline"` removed them completely.

### Resolution, measured on real texture

This mask is the first to sit in the regime where node 37 matters at all -
context 5606px clamped to the 5184px frame, a **4.05x downscale** to 1280.
Measuring the fill's high-frequency content (mean absolute Laplacian) against
the *real* texture in a band just outside the mask gives a base-independent
ratio, so composition re-rolls do not confound it:

| run | fill hi-freq | real nearby | ratio | time |
| --- | --- | --- | --- | --- |
| empty prompt @1280 | 0.98 | 3.39 | 0.29 | 16.1s |
| described @1280 | 0.98 | 3.39 | 0.29 | 15.2s |
| described @1536 | 1.19 | 3.41 | **0.35** | 25.2s |
| described @1664 | 1.19 | 3.42 | **0.35** | 31.4s |
| (original content) | 4.78 | 3.59 | 1.33 | - |

Two findings:

- **1280 -> 1536 gains 21%. 1536 -> 1664 gains nothing** while costing 24% more
  time. The plateau is well below the ~1722px MPS ceiling, so that ceiling is
  not the binding constraint - the sampler is.
- **Even at 1664 the fill carries only ~35% of the high-frequency detail of the
  real texture beside it.** No available resolution closes that gap.

### The real constraint is mask size, not resolution

From `crop_magic_im`, the sampled crop is the mask bbox grown by
`context_from_mask_extend_factor` then rescaled to the node 37 target, and
`InpaintStitchImproved` scales the result back down:

```
crop_side ~= 1.5 x max(mask_bbox_w, mask_bbox_h)
```

Filling 3737px from a 1536px sample means a 2.4x upscale on the way out. That,
not the model, is why it is soft.

The practical answer is to **split a large removal into several smaller masks**.
Keeping each bbox under ~850px puts `crop_side` under 1280, so the region is
sampled at native resolution or better and the fill stays sharp. One 3700px
mask cannot be rescued by any node 37 value.

Corollary: for small masks (`crop_side` < 1280) the crop is *upscaled* before
sampling and the excess is discarded on stitch, so raising node 37 does nothing
at all. The runner edit (bbox 433x693, crop ~1039) was already in that regime.
