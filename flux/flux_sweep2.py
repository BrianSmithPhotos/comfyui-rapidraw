"""Is the driftwood a seed accident or a systematic Flux Fill tendency?

Run A: an explicitly empty prompt - names absence, not scenery.
Run B: the original scene prompt at a different seed.
"""
import json, time, urllib.request, uuid, os

COMFY = "http://127.0.0.1:8188"
SENT = os.path.expanduser("~/git/RapidRAW-AI-Connector/cache/sent")
DESC = "bare granite rock, dry grass, still water, empty shoreline"
EMPTY = ("smooth bare granite rock surface, nothing on the rock, no objects, "
         "plain weathered stone, still water, empty")

RUNS = [("deny_g30", EMPTY, 30.0, 424242),
        ("desc_seed777", DESC, 30.0, 777),
        ("deny_seed777", EMPTY, 30.0, 777)]

def post(p, o):
    return json.load(urllib.request.urlopen(urllib.request.Request(
        COMFY+p, json.dumps(o).encode(), {"Content-Type": "application/json"})))
def get(p): return json.load(urllib.request.urlopen(COMFY+p))

here = os.path.dirname(os.path.abspath(__file__))
for label, text, guidance, seed in RUNS:
    wf = json.load(open(os.path.join(here, "workflow_flux.json")))
    wf["30"]["inputs"]["image"] = f"{SENT}/last_sent_image.jpg"
    wf["47"]["inputs"]["image"] = f"{SENT}/last_sent_mask.png"
    wf["7"]["inputs"]["text"] = text
    wf["28"]["inputs"]["seed"] = seed
    wf["52"]["inputs"]["guidance"] = guidance
    pid = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})["prompt_id"]
    t0 = time.time()
    while True:
        h = get(f"/history/{pid}")
        if pid in h and h[pid]["status"]["completed"]: break
        if time.time()-t0 > 1800: print(f"{label}: TIMEOUT", flush=True); break
        time.sleep(5)
    h = get(f"/history/{pid}"); st = h[pid]["status"]
    if st["status_str"] != "success":
        print(f"{label}: FAILED {json.dumps(st.get('messages', []))[:400]}", flush=True); continue
    img = next(i for o in h[pid]["outputs"].values() for i in o.get("images", []))
    data = urllib.request.urlopen(
        f"{COMFY}/view?filename={img['filename']}&subfolder={img.get('subfolder','')}&type={img['type']}").read()
    open(f"flux_{label}.png", "wb").write(data)
    print(f"{label:>13}  seed={seed:<7} {time.time()-t0:6.1f}s -> flux_{label}.png", flush=True)
