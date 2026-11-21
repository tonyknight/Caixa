"""A stand-in for `caixa-apple-intelligence`, speaking its protocol, for tests on any computer.

`--check` answers as `STAND_IN_APPLE` says (`ready`, or a reason such as `not_enabled`). Otherwise it
reads one JSON request per line and answers each: the text is "<instructions word count> | <prompt>"
(so a test can see what was sent), after `STAND_IN_APPLE_DELAY` seconds; a prompt holding DECLINE is
declined as the model's safety filter would."""

from __future__ import annotations

import json
import os
import sys
import time


def main() -> None:
    if sys.argv[1:] == ["--check"]:
        state = os.environ.get("STAND_IN_APPLE", "ready")
        if state == "ready":
            print(json.dumps({"ready": True}))
        else:
            print(json.dumps({"ready": False, "reason": state, "message": f"stand-in: {state}"}))
        return
    delay = float(os.environ.get("STAND_IN_APPLE_DELAY", "0"))
    for line in sys.stdin:
        request = json.loads(line)
        time.sleep(delay)
        if "DECLINE" in request["prompt"]:
            answer = {
                "id": request["id"],
                "error": "declined by the safety filter",
                "refused": True,
            }
        else:
            words = len(request["instructions"].split())
            answer = {"id": request["id"], "text": f"{words} | {request['prompt']}"}
        sys.stdout.write(json.dumps(answer) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
