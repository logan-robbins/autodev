"""Runnable interface fixture. Business functionality is explicitly unavailable."""

import argparse
import json
from pathlib import Path


def deliver():
    return json.loads((Path(__file__).parent / "fixtures/result.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = deliver()
    if args.check:
        assert result["status"] == "unavailable"
        assert result["summary"]
    else:
        print(json.dumps(result, indent=2))
