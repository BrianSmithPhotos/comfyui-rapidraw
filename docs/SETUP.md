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

    uv venv --python 3.13
    # pin the nightly torch index, then
    uv pip install -r requirements.txt
    uv run main.py

Set `use_uv` in ComfyUI-Manager's `config.ini` once Manager is installed.

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

## The old installs are not reusable

`~/.pyenv` (4.2 G), `~/mambaforge` (3.9 G) and `~/miniforge3` (3.8 G) hold
`lstein-stable-diffusion` and `ldm` from 2022 and `invokeai` from 2024. Their
PyTorch long predates current MPS support, so none of it helps here - a fresh
uv install is the right move regardless. Clearing them also shrinks the VS Code
interpreter scan that produced a spurious "no Python found" prompt after a
reboot on 2026-09-09.

## Sources

- https://github.com/comfyanonymous/ComfyUI
- https://github.com/CyberTimon/RapidRAW
- https://github.com/CyberTimon/RapidRAW-AI-Connector
- https://pypi.org/project/comfyui-manager/
