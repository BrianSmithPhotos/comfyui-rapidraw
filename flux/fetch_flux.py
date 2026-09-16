"""Fetch FLUX.1-Fill-dev and its encoders into the ComfyUI model tree.

All four come from ungated repos. Both black-forest-labs Flux repos are gated,
so the fill model comes from the Comfy-Org mirror and the autoencoder from a
third-party mirror - the Comfy-Org repackages split the VAE out and do not
carry it. SHA256 guards that mirror: four independent mirrors publish the same
bytes, so a mismatch means the file changed, not that the hash is wrong.
t5xxl is fp16, not fp8: fp8 compute is NVIDIA-only in ComfyUI.
"""
import hashlib, os, sys, time
from huggingface_hub import hf_hub_download

MODELS = os.path.expanduser("~/git/ComfyUI/models")
JOBS = [
    ("Comfy-Org/flux1-dev", "split_files/diffusion_models/flux1-fill-dev.safetensors",
     f"{MODELS}/diffusion_models", 23.8),
    ("comfyanonymous/flux_text_encoders", "t5xxl_fp16.safetensors",
     f"{MODELS}/text_encoders", 9.8),
    ("comfyanonymous/flux_text_encoders", "clip_l.safetensors",
     f"{MODELS}/text_encoders", 0.25),
    ("second-state/FLUX.1-schnell-GGUF", "ae.safetensors",
     f"{MODELS}/vae", 0.34),
]

# Only the third-party mirror needs verifying; the rest are first-party repacks.
SHA256 = {"ae.safetensors":
          "afc8e28272cd15db3919bacdb6918ce9c1ed22e96cb12c4d5ed0fba823529e38"}

for repo, path, dest, gb in JOBS:
    name = os.path.basename(path)
    target = os.path.join(dest, name)
    if os.path.exists(target):
        print(f"skip {name} (already present)", flush=True)
        continue
    print(f"fetching {name}  ~{gb} GB  from {repo}", flush=True)
    t0 = time.time()
    p = hf_hub_download(repo_id=repo, filename=path, local_dir=dest)
    # split_files/... lands nested; flatten so ComfyUI sees it
    if p != target:
        os.replace(p, target)
    dt = time.time() - t0
    want = SHA256.get(name)
    if want:
        got = hashlib.sha256(open(target, "rb").read()).hexdigest()
        if got != want:
            os.remove(target)
            sys.exit(f"  sha256 mismatch for {name}: got {got}, removed the file")
        print(f"  sha256 ok", flush=True)
    size = os.path.getsize(target) / 1e9
    print(f"  done {size:.2f} GB in {dt:.0f}s ({size/max(dt,1)*1000:.0f} MB/s)", flush=True)

print("\nall files present:", flush=True)
for _, path, dest, _ in JOBS:
    t = os.path.join(dest, os.path.basename(path))
    print(f"  {os.path.getsize(t)/1e9:7.2f} GB  {t.replace(os.path.expanduser('~'),'~')}", flush=True)
