#!/usr/bin/env python3
"""Checks every extension and builds the signed catalogue the ClipBridge app downloads.

    python3 tools/build.py --check                 # check only (pull requests)
    python3 tools/build.py --out dist/catalogue.json   # check, build and sign

Signing reads the Ed25519 private key (32 raw bytes, base64) from the
CATALOGUE_SIGNING_KEY environment variable, or from --key-file. The output is

    {"format": 1, "keyId": "...", "payload": "<base64 index>", "signature": "<base64>"}

where the index is {"format": 1, "sequence": <unix seconds>, "generated": "...",
"extensions": [...]}. The app checks the signature with the public key built
into it, and refuses a sequence lower than one it has already seen.

Needs: pip install jsonschema cryptography
"""

import argparse
import base64
import datetime
import json
import os
import pathlib
import sys
import time

import jsonschema
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = pathlib.Path(__file__).resolve().parent.parent
KEY_ID = "cb-catalogue-1"
BUILT_IN = {"keys_mouse", "clipboard", "history", "dongles", "store", "settings", "keyboard"}
MAX_EXTENSION_BYTES = 64 * 1024


def block_ids(blocks):
    return [b["id"] for b in blocks]


def page_block_ids(page):
    ids = block_ids(page.get("actions", []))
    for s in page["sections"]:
        ids += block_ids(s["blocks"]) if s["type"] == "grid" else [s["block"]["id"]]
    return ids


def explain(error):
    """The real problems behind an error. "Not valid under any of the given
    schemas" (a section, action or step that can be one of several kinds)
    becomes the problems in the kind its "type" or "t" says it is."""
    if error.validator not in ("oneOf", "anyOf") or not error.context:
        return [error]
    branches = {}
    for c in error.context:
        branches.setdefault(c.schema_path[0], []).append(c)

    def picks_kind(errs):
        # The branch for its kind has no complaint about the type/t field itself.
        return not any(
            c.validator == "const" and c.relative_path and c.relative_path[-1] in ("type", "t")
            for c in errs
        )

    chosen = [b for b in branches.values() if picks_kind(b)]
    best = min(chosen or branches.values(), key=len)
    return [deep for c in best for deep in explain(c)]


def check(path, schema_validator):
    """The problems with one extension file, as strings."""
    problems = []
    raw = path.read_bytes()
    if len(raw) > MAX_EXTENSION_BYTES:
        return [f"bigger than {MAX_EXTENSION_BYTES // 1024} KB"]
    try:
        ext = json.loads(raw)
    except json.JSONDecodeError as e:
        return [f"isn't JSON: {e}"]
    for top in schema_validator.iter_errors(ext):
        for e in explain(top):
            where = "/".join(str(p) for p in e.absolute_path) or "(top)"
            message = e.message if len(e.message) < 200 else e.message[:200] + "…"
            problems.append(f"{where}: {message}")
    problems.sort()
    if problems:
        return problems
    if path.stem != ext["id"]:
        problems.append(f'file name should be {ext["id"]}.json')
    if ext["id"] in BUILT_IN:
        problems.append(f'id "{ext["id"]}" is a built-in app')
    ids = page_block_ids(ext["page"])
    section_ids = [s["id"] for s in ext["page"]["sections"]]
    for name, values in [("block", ids), ("section", section_ids)]:
        dupes = {v for v in values if values.count(v) > 1}
        if dupes:
            problems.append(f"page: duplicate {name} ids {sorted(dupes)}")
    widget_ids = [w["id"] for w in ext.get("widgets", [])]
    if len(set(widget_ids)) != len(widget_ids):
        problems.append("duplicate widget ids")
    for w in ext.get("widgets", []):
        wb = block_ids(w["blocks"])
        if len(set(wb)) != len(wb):
            problems.append(f'widget {w["id"]}: duplicate block ids')
    return problems


def load_all():
    schema = json.loads((ROOT / "schema" / "extension.schema.json").read_text())
    validator = jsonschema.Draft202012Validator(schema)
    extensions, failed = [], False
    seen = set()
    for path in sorted((ROOT / "extensions").glob("*.json")):
        problems = check(path, validator)
        if problems:
            failed = True
            print(f"✗ {path.name}")
            for p in problems:
                print(f"    {p}")
            continue
        ext = json.loads(path.read_text())
        if ext["id"] in seen:
            failed = True
            print(f'✗ {path.name}: id "{ext["id"]}" is used twice')
            continue
        seen.add(ext["id"])
        extensions.append(ext)
        print(f'✓ {path.name}  {ext["name"]} {ext["version"]}')
    return extensions, failed


def signing_key(key_file):
    text = pathlib.Path(key_file).read_text() if key_file else os.environ.get("CATALOGUE_SIGNING_KEY")
    if not text:
        sys.exit("No signing key: set CATALOGUE_SIGNING_KEY or pass --key-file.")
    seed = base64.b64decode(text.strip())
    if len(seed) != 32:
        sys.exit("The signing key should be 32 bytes, base64.")
    return Ed25519PrivateKey.from_private_bytes(seed)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="check the extensions; don't build or sign")
    ap.add_argument("--out", default="dist/catalogue.json", help="where to write the signed catalogue")
    ap.add_argument("--key-file", help="read the private key from this file instead of the environment")
    ap.add_argument("--sequence", type=int, help="the index's sequence (default: now, in unix seconds)")
    args = ap.parse_args()

    extensions, failed = load_all()
    if failed:
        sys.exit("\nSome extensions need fixing.")
    print(f"\n{len(extensions)} extensions are fine.")
    if args.check:
        return

    sequence = args.sequence or int(time.time())
    index = {
        "format": 1,
        "sequence": sequence,
        "generated": datetime.datetime.fromtimestamp(sequence, datetime.timezone.utc).isoformat(),
        "extensions": extensions,
    }
    payload = json.dumps(index, ensure_ascii=False, separators=(",", ":")).encode()
    signature = signing_key(args.key_file).sign(payload)
    envelope = {
        "format": 1,
        "keyId": KEY_ID,
        "payload": base64.b64encode(payload).decode(),
        "signature": base64.b64encode(signature).decode(),
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(envelope, indent=1) + "\n")
    print(f"Signed catalogue (sequence {sequence}) written to {out}.")


if __name__ == "__main__":
    main()
