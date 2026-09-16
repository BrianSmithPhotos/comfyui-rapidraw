"""One-shot Flux Fill removal on the sandpiper frame.

Same inputs, prompt, seed and crop target (node 37 = 1280) as the SDXL
one-shot baseline in bird_desc_1280.png, so the only variable is the model.
"""
import json, time, urllib.request, uuid, os, sys

COMFY = "http://127.0.0.1:8188"
SENT = os.path.expanduser("~/git/RapidRAW-AI-Connector/cache/sent")
SEED = 424242
DESC = "bare granite rock, dry grass, still water, empty shoreline"
STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 20
OUT = sys.argv[2] if len(sys.argv) > 2 else "flux_1280.png"

def post(p, o):
    return json.load(urllib.request.urlopen(urllib.request.Request(
        COMFY+p, json.dumps(o).encode(), {"Content-Type": "application/json"})))
def get(p): return json.load(urllib.request.urlopen(COMFY+p))

wf = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflow_flux.json")))
wf["30"]["inputs"]["image"] = f"{SENT}/last_sent_image.jpg"
wf["47"]["inputs"]["image"] = f"{SENT}/last_sent_mask.png"
wf["7"]["inputs"]["text"] = DESC
wf["28"]["inputs"]["seed"] = SEED
wf["28"]["inputs"]["steps"] = STEPS

pid = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})["prompt_id"]
print(f"prompt {pid}  steps={STEPS}", flush=True)
t0 = time.time()
while True:
    h = get(f"/history/{pid}")
    if pid in h and h[pid]["status"]["completed"]: break
    if time.time()-t0 > 3600:
        print("TIMEOUT after 3600s", flush=True); sys.exit(1)
    time.sleep(5)

h = get(f"/history/{pid}"); st = h[pid]["status"]
if st["status_str"] != "success":
    print("FAILED:", json.dumps(st.get("messages", []))[:2000], flush=True); sys.exit(1)
img = next(i for o in h[pid]["outputs"].values() for i in o.get("images", []))
data = urllib.request.urlopen(
    f"{COMFY}/view?filename={img['filename']}&subfolder={img.get('subfolder','')}&type={img['type']}").read()
open(OUT, "wb").write(data)
print(f"{time.time()-t0:.1f}s -> {OUT} ({len(data)/1e6:.1f} MB)", flush=True)
