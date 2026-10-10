import argparse
import sys

import requests

DEFAULT_BASE_URL = "http://localhost:5000"

bodies = [
    [1, 2],
    "hello",
    123,
    None,
    True,
    [[1]],
    {"name": 123},
]


def main():
    parser = argparse.ArgumentParser(
        description="Send malformed payloads to the app's /items endpoint."
    )
    parser.add_argument(
        "base_url",
        nargs="?",
        default=DEFAULT_BASE_URL,
        help=f"Base URL of the target app (default: {DEFAULT_BASE_URL})",
    )
    args = parser.parse_args()
    url = args.base_url.rstrip("/") + "/items"

    crashed = False

    for body in bodies:
        try:
            resp = requests.post(url, json=body)
            status = resp.status_code
            label = " CRASH" if 500 <= status < 600 else ""
            print(f"{body!r} -> {status}{label}")
            if label:
                crashed = True
        except requests.RequestException as exc:
            print(f"{body!r} -> ERROR {exc}")

    return 1 if crashed else 0


if __name__ == "__main__":
    sys.exit(main())
