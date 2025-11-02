import os, json, uuid
from api.schemas import AnswerRequest

LKPD_DIR = "data/lkpd_outputs"
ANS_DIR = "data/answers"

def save_lkpd(data):
    lkpd_id = str(uuid.uuid4())[:8]
    with open(f"{LKPD_DIR}/{lkpd_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return lkpd_id

def load_lkpd(lkpd_id):
    path = f"{LKPD_DIR}/{lkpd_id}.json"
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_answers(req: AnswerRequest):
    path = f"{ANS_DIR}/{req.lkpd_id}.json"
    if not os.path.exists(path):
        with open(path, "w") as f: json.dump([], f)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data.append(req.dict())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_rekap(lkpd_id):
    path = f"{ANS_DIR}/{lkpd_id}.json"
    if not os.path.exists(path): return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def list_all_lkpd():
    return [f.split(".")[0] for f in os.listdir(LKPD_DIR) if f.endswith(".json")]
