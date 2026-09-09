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

Not yet started. RapidRAW is not installed on this machine - `mdfind` finds no
bundle outside the git checkouts. Latest upstream release is **v1.6.3**
(2026-09-03). Two macOS arm64 builds are published, plain and `tethering`;
take the plain one unless camera tethering is wanted.

    02_RapidRAW_v1.6.3_macos-14_aarch64.dmg

Known hazards, from upstream issues rather than from running it:

| Hazard | Evidence | What it means here |
| --- | --- | --- |
| Not signed or notarised | issues #37 and #1438, both still open | Gatekeeper will refuse first launch. Expect to allow it in System Settings > Privacy and Security. Do not blanket-remove quarantine attributes. |
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
