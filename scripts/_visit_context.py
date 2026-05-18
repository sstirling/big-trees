"""Shared classifier that labels a tree by how a visitor can actually see it.

The big-tree registries publish street addresses for trees on private property
as well as public land. For a regional field-trip context, "this tree exists
at X" isn't enough — readers need to know whether they're walking into a park
or up to a stranger's lawn. This classifier returns a short, human-readable
label per tree based on keyword matches in the address.

Keyword rules are intentionally conservative. False positives are worse than
false negatives — better to label a park-tree as "residence" than to send
someone confidently to a homeowner's door.

Used by:
  - scripts/fetch_nj_data.py (tags every tree with visit_context)
  - scripts/build_nj_trips.py (tallies access_mix per trip)
"""

from __future__ import annotations

import re

# Each (regex, label) pair is tried in order. First match wins.
# Word boundaries are critical — "Park Ave" must NOT match "park",
# so we require the keyword to appear as a whole word AND not be preceded
# by a numeric address bit.
_RULES = [
    (
        re.compile(r"\b(park|forest|preserve|reservation|arboretum|wildlife|botanic(?:al)?\s+garden)s?\b", re.I),
        "In a park or preserve",
    ),
    (
        re.compile(r"\b(school|college|university|academy|seminary)s?\b", re.I),
        "At a school or campus",
    ),
    (
        re.compile(r"\b(church|cemetery|memorial|chapel|sanctuary|abbey|temple|synagogue|mosque)s?\b", re.I),
        "At a religious or memorial site",
    ),
    (
        re.compile(r"\b(library|museum|hospital|courthouse|town\s+hall|borough\s+hall)s?\b", re.I),
        "At a public institution",
    ),
]

DEFAULT_LABEL = "At a private residence — view from public sidewalk only"

# Short keys used by the frontend for icon / chip styling, parallel to the labels above.
LABEL_TO_KEY = {
    "In a park or preserve": "park",
    "At a school or campus": "school",
    "At a religious or memorial site": "religious",
    "At a public institution": "public",
    DEFAULT_LABEL: "residence",
}


def classify(address: str | None) -> tuple[str, str]:
    """Returns (label, key). Key is a short slug for CSS/data; label is human text."""
    if not address:
        return DEFAULT_LABEL, "residence"
    # Strip street-name false positives: "Park Ave", "Church St", "Chapel Rd",
    # "Forest Dr" are residential streets, not parks or churches. If the
    # keyword is followed by a clear street-type suffix, blank that bit out
    # before running the rules so it doesn't match.
    street_suffix = r"(ave|avenue|road|rd|street|st|dr|drive|ln|lane|blvd|boulevard|way|ct|court|place|pl|terrace|ter|cir|circle|highway|hwy|pike|trail|trl|run|row|crossing|parkway|pkwy)"
    suffix_demote = re.compile(
        r"\b(park|forest|preserve|arboretum|church|chapel|cemetery|memorial|school|college|academy|library|hall)\b\s+" + street_suffix + r"\b",
        re.I,
    )
    cleaned = suffix_demote.sub("", address)

    for rule, label in _RULES:
        if rule.search(cleaned):
            return label, LABEL_TO_KEY[label]
    return DEFAULT_LABEL, "residence"
