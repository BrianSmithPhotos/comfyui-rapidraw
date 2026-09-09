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
