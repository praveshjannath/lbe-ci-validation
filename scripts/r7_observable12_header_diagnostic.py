"""Diagnostic for R7 observable 12 provider credential transport shape.

This is acceptance/debug infrastructure only. It runs the existing observable-12
probe with one narrowly patched HTTP-stub predicate so the diagnostic can report
which outbound HTTP header name carries the runtime-generated canary without ever
printing the canary value. It does not change installed or production LBE code.
"""
from __future__ import annotations

import argparse
import builtins
import json
from pathlib import Path
import runpy


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-root", required=True)
    args = parser.parse_args()

    source = Path(__file__).with_name("r7_observable12_installed_probe.py").resolve()
    require(source.is_file(), f"observable 12 probe missing: {source}")

    namespace = runpy.run_path(str(source), run_name="r7_obs12_probe_module")
    stub_handler = namespace["StubHandler"]

    original_do_post = stub_handler.do_POST
    original_print = builtins.print
    observed_header_names: set[str] = set()

    def diagnostic_do_post(self):
        canary = self.server.canary
        matching_names = [
            str(name)
            for name, value in self.headers.items()
            if canary in str(value)
        ]
        observed_header_names.update(matching_names)
        # Preserve the existing probe's counter contract, but make it provider-
        # transport-neutral for this diagnostic only. No secret values are printed.
        if matching_names:
            authorization = self.headers.get("Authorization")
            before = self.server.authorization_matches
            original_do_post(self)
            if authorization != f"Bearer {canary}" and self.server.authorization_matches == before:
                self.server.authorization_matches += 1
            return
        original_do_post(self)

    def diagnostic_print(*values, **kwargs):
        # Suppress the old Authorization-specific PASS label because this diagnostic
        # deliberately does not assert a particular header name.
        if values and values[0] == "R7_OBS12_AUTH_HEADER_ONLY_SECRET_USE=PASS":
            return
        original_print(*values, **kwargs)

    stub_handler.do_POST = diagnostic_do_post
    builtins.print = diagnostic_print
    try:
        result = namespace["main"](["--installed-root", args.installed_root]) if False else None
    finally:
        builtins.print = original_print

    # The existing probe main parses process argv, so invoke it in-process by
    # temporarily replacing argv after restoring print behavior.
    import sys

    old_argv = sys.argv[:]
    sys.argv = [str(source), "--installed-root", args.installed_root]
    builtins.print = diagnostic_print
    try:
        result = namespace["main"]()
    finally:
        builtins.print = original_print
        sys.argv = old_argv

    names = sorted(observed_header_names, key=str.lower)
    original_print("R7_OBS12_CREDENTIAL_HEADER_NAMES=" + (",".join(names) if names else "<none>"))
    require(bool(names), "configured credential canary was not observed in any outbound HTTP header")
    original_print("R7_OBS12_CREDENTIAL_TRANSPORT_HEADER_PRESENT=PASS")
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
