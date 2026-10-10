import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

import attack

load_dotenv()

NEATLOGS_API_KEY = os.environ["NEATLOGS_API_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

import neatlogs
from opentelemetry.trace import Status, StatusCode

neatlogs.init(
    api_key=NEATLOGS_API_KEY,
    workflow_name="heal",
)

from openai import OpenAI

client = neatlogs.wrap(
    OpenAI(
        api_key=GEMINI_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
)

ROOT = Path(__file__).resolve().parent
APP_INIT = ROOT / "app" / "__init__.py"
LOG_PATH = ROOT / "evidence" / "app_run.log"
VERIFY_LOG_PATH = ROOT / "evidence" / "quarantine_run.log"
QUARANTINE = ROOT / "quarantine" / "app" / "__init__.py"
LESSONS = ROOT / "lessons.json"
ANTIBODY_TEST = ROOT / "tests" / "test_antibody.py"
ANTIBODY_PAYLOADS = [[1, 2], "hello", 123, True]
MODEL = "gemini-3.8-flash"
BASE_URL = "http://localhost:5000"
HEALTH_URL = f"{BASE_URL}/health"
PORT = "5000"
VERIFY_BASE_URL = "http://localhost:5001"
VERIFY_PORT = "5001"

DETECT_SYSTEM = (
    "You are a senior Python debugging assistant. "
    "Given a Flask crash traceback and the application source, identify the single "
    "root cause of the crash. Respond ONLY with JSON of the form "
    '{"root_cause": "<concise explanation>"}.'
)

DIAGNOSE_SYSTEM = (
    "You are a senior Python engineer. Given the root cause of a Flask crash and the "
    "current source of app/__init__.py, produce a corrected FULL replacement of the "
    "file that fixes the crash while preserving all existing behavior and routes. "
    "Do not add new dependencies. Respond ONLY with JSON of the form "
    '{"corrected_file": "<complete contents of app/__init__.py>"}.'
)

ANTIBODY_TEMPLATE = '''import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.mark.parametrize("payload", {payloads})
def test_rejects_malformed_item(client, payload):
    resp = client.post("/items", json=payload)
    assert resp.status_code == 400
'''


def extract_traceback(log_text):
    marker = "Traceback (most recent call last):"
    idx = log_text.rfind(marker)
    if idx == -1:
        return log_text.strip()
    return log_text[idx:].strip()


def count_crashed(attack_stdout):
    return sum(
        1 for line in attack_stdout.splitlines() if line.rstrip().endswith("CRASH")
    )


def parse_json(text):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start : end + 1])
        raise


def wait_for_health(health_url, timeout=20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(health_url, timeout=1)
            if resp.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.3)
    return False


def detect(traceback_text, source, crashed_count):
    with neatlogs.trace("detect", kind="CHAIN") as span:
        span.set_attribute("attacks.crashed", crashed_count)
        if crashed_count > 0:
            span.set_status(
                Status(StatusCode.ERROR, f"{crashed_count} attack(s) returned 5xx")
            )
        else:
            span.set_status(Status(StatusCode.OK))

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": DETECT_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"TRACEBACK:\n{traceback_text}\n\n"
                        f"SOURCE (app/__init__.py):\n{source}"
                    ),
                },
            ],
        )
        result = response.choices[0].message.content
        span.set_attribute("output.value", result)
        return result


@neatlogs.span(kind="CHAIN", name="diagnose")
def diagnose(root_cause, traceback_text, source):
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": DIAGNOSE_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"ROOT CAUSE:\n{root_cause}\n\n"
                    f"TRACEBACK:\n{traceback_text}\n\n"
                    f"CURRENT app/__init__.py:\n{source}"
                ),
            },
        ],
    )
    return response.choices[0].message.content


def stop_server(server, log_file):
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait()
    log_file.close()


@neatlogs.span(kind="CHAIN", name="quarantine")
def quarantine(corrected_file):
    QUARANTINE.parent.mkdir(parents=True, exist_ok=True)
    QUARANTINE.write_text(corrected_file, encoding="utf-8")
    return QUARANTINE


@neatlogs.span(kind="CHAIN", name="verify")
def verify():
    VERIFY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(VERIFY_LOG_PATH, "w")
    server = subprocess.Popen(
        [sys.executable, "-m", "flask", "--app", "app", "run", "--port", VERIFY_PORT],
        cwd=QUARANTINE.parent.parent,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    try:
        if not wait_for_health(f"{VERIFY_BASE_URL}/health"):
            return "quarantined app did not become healthy in time"

        attack = subprocess.run(
            [sys.executable, "attack.py", VERIFY_BASE_URL],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        print(attack.stdout, end="")
        if attack.returncode != 0:
            return "attack.py still crashes the quarantined app"
    finally:
        stop_server(server, log_file)

    tests = subprocess.run(
        [sys.executable, "-m", "pytest", str(ROOT / "tests"), "-q", "-o", "pythonpath="],
        cwd=QUARANTINE.parent.parent,
        env={**os.environ, "PYTHONPATH": str(QUARANTINE.parent.parent)},
        capture_output=True,
        text=True,
    )
    print(tests.stdout, end="")
    if tests.returncode != 0:
        return "pytest failed on the quarantined app"

    return None


@neatlogs.span(kind="CHAIN", name="promote")
def promote():
    corrected_file = QUARANTINE.read_text(encoding="utf-8")
    APP_INIT.write_text(corrected_file, encoding="utf-8")
    return APP_INIT


def write_antibody_test():
    ANTIBODY_TEST.parent.mkdir(parents=True, exist_ok=True)
    ANTIBODY_TEST.write_text(
        ANTIBODY_TEMPLATE.format(payloads=repr(ANTIBODY_PAYLOADS)),
        encoding="utf-8",
    )
    return ANTIBODY_TEST


def uncovered_attacks():
    return [body for body in attack.bodies if body not in ANTIBODY_PAYLOADS]


def append_lesson(cause, fix, verified, attacks_not_covered):
    lessons = []
    if LESSONS.exists():
        try:
            loaded = json.loads(LESSONS.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                lessons = loaded
        except json.JSONDecodeError:
            lessons = []
    lessons.append(
        {
            "cause": cause,
            "fix": fix,
            "verified": verified,
            "attacks_not_covered": attacks_not_covered,
        }
    )
    LESSONS.write_text(json.dumps(lessons, indent=2) + "\n", encoding="utf-8")
    return LESSONS


def main():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(LOG_PATH, "w")
    server = subprocess.Popen(
        [sys.executable, "-m", "flask", "--app", "app", "run", "--port", PORT],
        cwd=ROOT,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    try:
        if not wait_for_health(HEALTH_URL):
            print("Flask app did not become healthy in time.")
            return 2

        attack = subprocess.run(
            [sys.executable, "attack.py", BASE_URL],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        print(attack.stdout, end="")

        crashed_count = count_crashed(attack.stdout)

        if attack.returncode != 1:
            print(f"attack.py exited {attack.returncode}; no crash detected.")
            return 0

        log_file.flush()
        log_text = LOG_PATH.read_text(encoding="utf-8", errors="replace")
        traceback_text = extract_traceback(log_text)
        source = APP_INIT.read_text(encoding="utf-8")

        detect_result = parse_json(detect(traceback_text, source, crashed_count))
        root_cause = detect_result.get("root_cause", "").strip()

        diagnose_result = parse_json(diagnose(root_cause, traceback_text, source))
        corrected_file = diagnose_result.get("corrected_file", "")
        if isinstance(corrected_file, str):
            corrected_file = corrected_file.rstrip("\n") + "\n"

        print("\n=== DIAGNOSIS ===")
        print(f"Root cause: {root_cause}")
        print("\nProposed app/__init__.py:\n")
        print(corrected_file)

        quarantine(corrected_file)
        print(f"\nSaved proposal to {QUARANTINE.relative_to(ROOT)}")

        reason = verify()
        if reason is not None:
            print(f"Rejected: {reason}")
            return 1

        promote()
        print(f"Promoted fix to {APP_INIT.relative_to(ROOT)}")

        write_antibody_test()
        print(f"Wrote antibody test to {ANTIBODY_TEST.relative_to(ROOT)}")

        append_lesson(root_cause, corrected_file, True, uncovered_attacks())
        print(f"Appended lesson to {LESSONS.relative_to(ROOT)}")
        return 0
    finally:
        stop_server(server, log_file)
        neatlogs.flush()
        neatlogs.shutdown()


if __name__ == "__main__":
    sys.exit(main())
