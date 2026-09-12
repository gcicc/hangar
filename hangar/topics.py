"""Topic tagging: regex-match headlines to the things these two companies do.

Same mechanism as clintrialist-report's ``topics.py`` - a pattern list per topic,
pre-compiled, multi-tag - with the therapeutic areas replaced by SpaceX/Tesla
subject matter. The first matching topic in TOPIC_ORDER colors the headline;
any others render as small badges.

Colors are chosen from the categorical slots in the shared design tokens rather
than from company brand palettes. Brand colors are used for identity chips only,
never to encode data.
"""

from __future__ import annotations

import re

# Spaceflight vocabulary used to disambiguate the verb "launch" - see the Launch
# topic below. Kept as a fragment so both word orders reuse one definition.
_SPACE_CONTEXT = (
    r"\b(rocket|orbit\w*|satellite|mission|launch pad|falcon|starship|super heavy"
    r"|booster|spacecraft|payload|astronaut|ISS|space station|droneship|stage|crew"
    r"|spacex|starlink|starshield|blue origin|ULA|rocket lab|NASA|flight)\b"
)

TOPICS: dict[str, dict] = {
    "launch": {
        "label": "Launch",
        "color": "#2a78d6",
        "patterns": [
            # "Launch" is the worst word in this corpus: NHTSA launches a probe,
            # Tesla launches a service, SpaceX launches a rocket. Blocklisting the
            # bureaucratic senses is a losing game, so the generic verb only counts
            # when spaceflight vocabulary sits near it, in either order.
            rf"\blaunch\w*\b.{{0,60}}{_SPACE_CONTEXT}",
            rf"{_SPACE_CONTEXT}.{{0,60}}\blaunch\w*\b",
            # Unambiguous on their own - no other industry uses these.
            r"\bliftoff\b",
            r"\bstatic fire\b",
            r"\bdroneship\b",
            r"\bsplashdown\b",
            r"\bscrub(bed)?\b.{0,40}\b(launch|flight|mission)\b",
            r"\bcountdown\b",
            r"\bdeploy(ed|ment)?\b.{0,20}\borbit\b",
            r"\bbooster\b",
            r"\b(landed|landing)\b.{0,40}\b(booster|droneship|pad|stage)\b",
        ],
    },
    "starship": {
        "label": "Starship",
        "color": "#eb6834",
        "patterns": [
            r"\bstarship\b",
            r"\bsuper heavy\b",
            r"\braptor\b",
            r"\bstarbase\b",
            r"\bflight \d+\b",
            r"\borbital flight test\b",
        ],
    },
    "starlink": {
        "label": "Starlink",
        "color": "#1baf7a",
        "patterns": [
            r"\bstarlink\b",
            r"\bdirect[- ]to[- ]cell\b",
            r"\bconstellation\b",
            r"\bbroadband\b.{0,20}\bsatellite\b",
            r"\bstarshield\b",
        ],
    },
    "optimus": {
        "label": "Optimus",
        "color": "#b8860b",
        "patterns": [
            r"\boptimus\b",
            r"\btesla bot\b",
            r"\bhumanoid\b",
            r"\bteslabot\b",
            # Generation labels appear without the product name in headlines
            # once a reader is assumed to know what is being counted.
            r"\boptimus\s+(gen|v)\s?\d",
            r"\bgen\s?\d\b.{0,30}\b(robot|humanoid|optimus)\b",
            r"\b(robot|humanoid)\b.{0,30}\b(hand|actuator|dexterity|gait|walking)\b",
        ],
    },
    "autonomy": {
        "label": "Autonomy",
        "color": "#6a1b9a",
        "patterns": [
            r"\brobotaxi\b",
            r"\bcybercab\b",
            r"\bfull self[- ]driving\b",
            r"\bFSD\b",
            r"\bautopilot\b",
            r"\bautonomous\b",
            r"\bdriverless\b",
            r"\bunsupervised\b",
        ],
    },
    "production": {
        "label": "Production",
        "color": "#e65100",
        "patterns": [
            r"\bgigafactory\b",
            r"\bgiga (texas|berlin|shanghai|nevada)\b",
            r"\bdeliver(y|ies)\b",
            r"\bproduction\b",
            r"\bcybertruck\b",
            r"\bmodel [3sxy]\b",
            r"\bassembly line\b",
            r"\bramp(-| )?up\b",
        ],
    },
    "energy": {
        "label": "Energy",
        "color": "#00695c",
        "patterns": [
            r"\bmegapack\b",
            r"\bpowerwall\b",
            r"\benergy storage\b",
            r"\bsupercharger\b",
            r"\bcharging network\b",
            r"\bNACS\b",
        ],
    },
    "money": {
        "label": "Money",
        "color": "#184f95",
        "patterns": [
            r"\bearnings\b",
            r"\brevenue\b",
            r"\bguidance\b",
            r"\bshares?\b",
            r"\bstock\b",
            r"\bvaluation\b",
            r"\block[- ]up\b",
            r"\bIPO\b",
            r"\bmarket cap\b",
            r"\banalyst\b",
            r"\bdowngrade|upgrade\b",
        ],
    },
    "regulatory": {
        "label": "Regulatory",
        "color": "#a52020",
        "patterns": [
            r"\bFAA\b",
            r"\bNHTSA\b",
            r"\bFCC\b",
            r"\bSEC\b",
            r"\brecall\b",
            r"\binvestigation\b",
            r"\bprobe\b",
            r"\blawsuit\b",
            r"\bapprov(al|ed|es)\b",
            r"\blicense\b",
            r"\benvironmental review\b",
            r"\banomaly\b",
            r"\bmishap\b",
        ],
    },
}

_COMPILED = {
    key: [re.compile(p, re.IGNORECASE) for p in spec["patterns"]] for key, spec in TOPICS.items()
}

# Display order. Ops topics first, then the money/regulatory pair, so a story
# that is both a launch and a filing colors as a launch.
TOPIC_ORDER = [
    "starship",
    "starlink",
    "launch",
    "optimus",
    "autonomy",
    "production",
    "energy",
    "regulatory",
    "money",
]


def tag_entry(entry: dict) -> list[str]:
    """Attach and return the topic keys matching an entry's title and summary."""
    text = f"{entry.get('title', '')} {entry.get('summary', '')}"
    tags = [key for key in TOPIC_ORDER if any(p.search(text) for p in _COMPILED[key])]
    entry["topics"] = tags
    return tags
