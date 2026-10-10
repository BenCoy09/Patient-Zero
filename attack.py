import sys

import requests

URL = "http://localhost:5000/items"

bodies = [
    [1, 2],
    "hello",
    123,
    None,
    True,
    [[1]],
    {"name": 123},
]

crashed = False

for body in bodies:
    try:
        resp = requests.post(URL, json=body)
        status = resp.status_code
        label = " CRASH" if 500 <= status < 600 else ""
        print(f"{body!r} -> {status}{label}")
        if label:
            crashed = True
    except requests.RequestException as exc:
        print(f"{body!r} -> ERROR {exc}")

sys.exit(1 if crashed else 0)
