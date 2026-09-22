"""Run against a live OpenJev server with only Python's standard library."""

import json
from urllib.request import Request, urlopen

payload = {
    "model": "openjev-local",
    "state": "耳机坏了，我想退货退款。",
    "questions": {
        "intent": {
            "type": "choice",
            "instructions": "顾客想做什么？",
            "criteria": {"refund": "顾客希望退货退款。", "buy": "顾客想购买新的产品。"},
        },
        "defective": {"type": "noul", "instructions": "耳机存在故障。"},
    },
}
request = Request("http://127.0.0.1:8766/v1/systemone", data=json.dumps(payload).encode(),
                  headers={"Content-Type": "application/json"})
with urlopen(request, timeout=120) as response:
    print(json.dumps(json.load(response), indent=2, ensure_ascii=False))
