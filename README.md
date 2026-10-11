# Patient Zero

An app that gets attacked, heals itself, and writes an antibody so the same failure can't come back. Built solo for #neatHack (team: Trace Element).

## How it works
1. **Detect:** attack.py sends malformed requests to a small Flask app. Any 5xx is a crash.
2. **Diagnose:** the healer reads the traceback and source, and Gemini proposes a fix.
3. **Quarantine:** the fix runs on a copy of the app (port 5001).
4. **Verify:** attack.py and pytest must both pass against the copy.
5. **Promote:** only then is the fix copied into the real app. Otherwise it is rejected.
6. **Antibody:** a regression test (tests/test_antibody.py) and a lesson (lessons.json) are saved.

## Result
- Before: 5 attacks crashed the app with a 500 (body was a list, "hello", 123, true or [[1]]).
- After: all 5 return 400, and 8 tests pass.
- Honest gap: `{"name": 123}` still returns 201, because the app stores a number as a name. It does not crash, so the healer did not cover it.

## How we used the required tools
- **neatlogs:** every heal run is traced with spans detect, diagnose, quarantine, verify and promote. See docs/neatlogs-*.png.
- **Entire:** the whole build is recorded as checkpoints (OpenCode sessions linked to commits). See docs/entire-*.png.
- **cfo.ai:** a business plan for Patient Zero (price, costs, revenue, runway). See docs/cfo-*.png. Price ($49 per protected app per month) and cost per heal are assumptions, not measurements.
  Runway if revenue stopped: base case 17.1 months before a founder salary and 6.3 after, growth case 13.9 and 5.0.

## Evidence
- Business plan: docs/cfo-1-runway-stress-test.png, cfo-2-runway-table.png, cfo-3-scenarios.png, cfo-4-assumptions.png
- Entire: docs/entire-1-checkpoints.png and the other entire-*.png files
- neatlogs traces: docs/neatlogs-*.png
- Before-fix evidence: evidence/ folder
- Built in public: [PASTE YOUR #neatHack POST LINKS HERE]
- Demo video: [PASTE VIDEO LINK HERE]

## Run it
pip install -r requirements.txt, add GEMINI_API_KEY and NEATLOGS_API_KEY to .env, then run python heal.py.
