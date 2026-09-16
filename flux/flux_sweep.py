"""Flux Fill prompt/guidance sweep on the sandpiper frame.

First run paid the 34 GB model load; later runs reuse it, so the reported
time is the honest per-image cost only from run 2 onwards.
"""
import json, time, urllib.request, uuid, os, sys

COMFY = "http://127.0.0.1:8188"
SENT = os.path.expanduser("~/git/RapidRAW-AI-Connector/cache/sent")
SEED = 424242
DESC = "bare granite rock, dry grass, still water, empty shoreline"

RUNS = [("empty_g30", "", 30.0),
        ("desc_g10", DESC, 10.0),
        ("empty_g10", "", 10.0),
        ("desc_g50", DESC, 50.0)]

def post(p, o):
    return json.load(urllib.request.urlopen(urllib.request.Request(
        COMFY+p, json.dumps(o).encode(), {"Content-Type": "application/json"})))
def get(p): return json.load(urllib.request.urlopen(COMFY+p))

here = os.path.dirname(os.path.abspath(__file__))
for label, text, guidance in RUNS:
    wf = json.load(open(os.path.join(here, "workflow_flux.json")))
    wf["30"]["inputs"]["image"] = f"{SENT}/last_sent_image.jpg"
    wf["47"]["inputs"]["image"] = f"{SENT}/last_sent_mask.png"
    wf["7"]["inputs"]["text"] = text
    wf["28"]["inputs"]["seed"] = SEED
    wf["52"]["inputs"]["guidance"] = guidance
    pid = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})["prompt_id"]
    t0 = time.time()
    while True:
        h = get(f"/history/{pid}")
        if pid in h and h[pid]["status"]["completed"]: break
        if time.time()-t0 > 1800:
            print(f"{label}: TIMEOUT", flush=True); break
        time.sleep(5)
    h = get(f"/history/{pid}"); st = h[pid]["status"]
    if st["status_str"] != "success":
        print(f"{label}: FAILED {json.dumps(st.get('messages', []))[:500]}", flush=True); continue
    img = next(i for o in h[pid]["outputs"].values() for i in o.get("images", []))
    data = urllib.request.urlopen(
        f"{COMFY}/view?filename={img['filename']}&subfolder={img.get('subfolder','')}&type={img['type']}").read()
    open(f"flux_{label}.png", "wb").write(data)
    print(f"{label:>10}  g={guidance:<5}  {time.time()-t0:6.1f}s  -> flux_{label}.png", flush=True)
