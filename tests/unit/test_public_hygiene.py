"""This repository is public. Nothing in it may name a real client, person or private path.

Client and people names are stored as truncated SHA-256 hashes so this file doesn't publish the
list it guards against. To add a name: python3 -c "import hashlib;print(hashlib.sha256(b'name').hexdigest()[:16])"
"""

import hashlib
import re
import subprocess

from conftest import REPO

DENY_HASHES = {
    "e2dbc1e3ae97ea68",  # 7 chars
    "d40f9c796ebf74fb",  # 7 chars
    "ccd4dd6357198ead",  # 13 chars
    "3c1fffa10255c5e4",  # 8 chars
    "f8fe32467f9c2d6a",  # 6 chars
    "43188edff8709eb6",  # 4 chars
    "d1007b74b9b7d106",  # 7 chars
    "7a0223bc155f0d4a",  # 12 chars
    "ba0a5096cdb80573",  # 6 chars
    "6e80a32b1d0612dc",  # 14 chars
    "d726e7eac71579cc",  # 8 chars
    "9773d54954d9d776",  # 11 chars
    "8a65a23f3bd1b1aa",  # 5 chars
    "aaf2c65298d5c732",  # 7 chars
    "83964c3edb8b2356",  # 12 chars
    "3e5de6cdee001ed8",  # 10 chars
    "43163cef22e5d2d7",  # 6 chars
    "a4eb411e1a63bee4",  # 7 chars
    "ee69b1359fada701",  # 5 chars
    "3dfbf1fbdbf9d2eb",  # 5 chars
    "5f3d6952c5c5e220",  # 6 chars
    "d1ee4d385d3054b2",  # 6 chars
    "145773c7abaa7686",  # 10 chars
    "962cd22346a772be",  # 5 chars
    "3f9ae4d29f2cc663",  # 4 chars
    "8b04871d9242d20c",  # 7 chars
    "870c9640d0c84ee6",  # 16 chars
    "ea57acee2cff459a",  # 12 chars
    "1fcff1fe7e601e10",  # 2 chars
    "0a7aacae9b43f934",  # 2 chars
}
PRIVATE = [
    (re.compile(r"/Users/[a-z]"), "a personal macOS path"),
    (re.compile(r"\bclaude-(opus|sonnet|haiku|fable)-\d"), "a dated model ID (use the aliases opus, sonnet, haiku)"),
    (re.compile(r"[\w.+-]+@daylightcreative\.tech"), "a personal email address"),
]
SKIP = {"tests/unit/test_public_hygiene.py"}


def tracked_text_files():
    out = subprocess.run(["git", "-C", str(REPO), "ls-files", "--cached", "--others", "--exclude-standard"],
                         capture_output=True, text=True, check=True).stdout.split()
    for rel in out:
        path = REPO / rel
        if rel in SKIP or not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" not in data[:4096]:
            yield rel, data.decode("utf-8", "replace")


def test_no_client_or_people_names():
    hits = []
    for rel, text in tracked_text_files():
        for number, line in enumerate(text.splitlines(), 1):
            for token in set(re.findall(r"[a-zà-ÿ0-9]+", line.lower())):
                if hashlib.sha256(token.encode()).hexdigest()[:16] in DENY_HASHES:
                    hits.append("%s:%d" % (rel, number))
    assert hits == []


def test_no_private_paths_emails_or_dated_model_ids():
    hits = []
    for rel, text in tracked_text_files():
        for number, line in enumerate(text.splitlines(), 1):
            for pattern, what in PRIVATE:
                if pattern.search(line):
                    hits.append("%s:%d %s" % (rel, number, what))
    assert hits == []


def test_the_denylist_still_matches_what_it_should():
    # Guards the guard: a known-bad token must hash into the list.
    assert hashlib.sha256(b"minerbox").hexdigest()[:16] in DENY_HASHES
