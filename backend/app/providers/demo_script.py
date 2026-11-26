"""Demo script for the fake speech-to-text and the action-item pattern the fake LLM uses.

Vietnamese text is written with unicode escapes to keep the source ASCII.
"""
# ruff: noqa: E501

import re

ACTION_RE = re.compile(
    r"\b(i will|i'll|we will|we'll|we need to|i can|t\u00f4i s\u1ebd|m\u00ecnh s\u1ebd|em s\u1ebd|anh s\u1ebd|ch\u1ecb s\u1ebd"
    r"|ch\u00fang ta c\u1ea7n)\b",
    re.IGNORECASE,
)
SCRIPT_SPEAKERS = (1, 2, 1, 3, 2, 1, 3, 1)
SCRIPT = {
    "en": (
        "Welcome everyone, this is the {stem} meeting. Let us start with the release status.",
        "The release candidate is ready and the tests are passing.",
        "Great. Can we ship it this week?",
        "I will send the release note today.",
        "I'll fix the remaining login bug by Thursday.",
        "What about the customer demo on Friday?",
        "I will prepare the demo slides and share them tomorrow.",
        "Thanks all. We will meet again next week.",
    ),
    "vi": (
        "Ch\u00e0o m\u1ecdi ng\u01b0\u1eddi, \u0111\u00e2y l\u00e0 cu\u1ed9c h\u1ecdp {stem}. B\u1eaft \u0111\u1ea7u v\u1edbi t\u00ecnh tr\u1ea1ng b\u1ea3n ph\u00e1t h\u00e0nh nh\u00e9.",
        "B\u1ea3n ph\u00e1t h\u00e0nh th\u1eed \u0111\u00e3 s\u1eb5n s\u00e0ng v\u00e0 c\u00e1c b\u00e0i ki\u1ec3m tra \u0111\u1ec1u \u0111\u1ea1t.",
        "T\u1ed1t qu\u00e1. Tu\u1ea7n n\u00e0y m\u00ecnh c\u00f3 ph\u00e1t h\u00e0nh \u0111\u01b0\u1ee3c kh\u00f4ng?",
        "T\u00f4i s\u1ebd g\u1eedi ghi ch\u00fa ph\u00e1t h\u00e0nh trong h\u00f4m nay.",
        "Em s\u1ebd s\u1eeda l\u1ed7i \u0111\u0103ng nh\u1eadp c\u00f2n l\u1ea1i tr\u01b0\u1edbc th\u1ee9 N\u0103m.",
        "C\u00f2n bu\u1ed5i demo cho kh\u00e1ch h\u00e0ng v\u00e0o th\u1ee9 S\u00e1u th\u00ec sao?",
        "M\u00ecnh s\u1ebd chu\u1ea9n b\u1ecb slide demo v\u00e0 chia s\u1ebb v\u00e0o ng\u00e0y mai.",
        "C\u1ea3m \u01a1n m\u1ecdi ng\u01b0\u1eddi. Tu\u1ea7n sau ch\u00fang ta h\u1ecdp l\u1ea1i nh\u00e9.",
    ),
}
