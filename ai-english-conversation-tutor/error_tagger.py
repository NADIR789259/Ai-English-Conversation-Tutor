"""
Rule-based automatic error-type tagging module.
Makes no additional LLM calls; classification uses keywords in correction
explanations and simple diff heuristics on original/corrected text.

Categories:
    tense        verb tense
    article      articles (a/an/the)
    preposition  prepositions
    word_order   word order
    subject_verb subject-verb agreement
    plural       singular/plural
    vocabulary   word choice
    spelling     spelling
    other        other

Evaluation order (return the first match):
    1. Match keywords in the explanation (priority: word_order → subject_verb →
       tense → article → preposition → plural → spelling → vocabulary)
       Compound phrases such as "third-person singular" require more specific
       categories to be checked first.
    2. Apply diff heuristics to original/corrected text.
    3. Return "other" if no category matches.
"""

import difflib
import re

# Valid category list (for external reference)
ERROR_TYPES = [
    "tense", "article", "preposition", "word_order",
    "subject_verb", "plural", "vocabulary", "spelling", "other",
]

# ------------------------------------------------------------
# 1. Match explanation keywords (priority order, regular expressions)
# ------------------------------------------------------------
_KEYWORD_RULES: list[tuple[str, list[str]]] = [
    ("word_order", [
        r"word order", r"order of (?:the )?words?", r"語順", r"並び順",
    ]),
    ("subject_verb", [
        r"agreement", r"subject[- ]verb", r"third[- ]person", r"3rd[- ]person",
        r"主語と動詞", r"三単現", r"三人称単数",
    ]),
    ("tense", [
        r"tense", r"past (?:form|simple|participle)", r"present perfect",
        r"past continuous", r"future", r"時制", r"過去形", r"現在完了",
        r"過去分詞", r"未来形",
    ]),
    ("article", [
        r"article", r"冠詞", r"\ba/an\b", r"['\"]a['\"]", r"['\"]an['\"]",
        r"['\"]the['\"]", r"\bdefinite\b", r"\bindefinite\b",
    ]),
    ("preposition", [
        r"preposition", r"前置詞",
    ]),
    ("plural", [
        r"plural", r"singular", r"uncountable", r"countable",
        r"複数形", r"単数形", r"単複", r"可算", r"不可算",
    ]),
    ("spelling", [
        r"spell", r"typo", r"misspel", r"スペル", r"綴り",
    ]),
    ("vocabulary", [
        r"word choice", r"vocabulary", r"wrong word", r"better word",
        r"correct word", r"more natural word", r"語彙", r"言葉の選", r"単語の選",
    ]),
]

# Compiled patterns (OR-joined for each category)
_COMPILED_RULES = [
    (etype, re.compile("|".join(patterns), re.IGNORECASE))
    for etype, patterns in _KEYWORD_RULES
]

# ------------------------------------------------------------
# 2. Vocabulary data for diff heuristics
# ------------------------------------------------------------
_ARTICLES = {"a", "an", "the"}

_PREPOSITIONS = {
    "in", "on", "at", "to", "for", "with", "by", "from", "of", "about",
    "into", "onto", "during", "since", "until", "over", "under",
    "between", "through", "before", "after", "against",
}

# Pairs commonly swapped for subject-verb agreement (either order)
_SV_PAIRS = {
    frozenset(p) for p in [
        ("is", "are"), ("was", "were"), ("has", "have"),
        ("does", "do"), ("doesn't", "don't"), ("am", "are"), ("am", "is"),
    ]
}

# Irregular verb base form → past tense pairs (matched in either order)
_IRREGULAR_PAST_PAIRS = {
    frozenset(p) for p in [
        ("go", "went"), ("eat", "ate"), ("see", "saw"), ("do", "did"),
        ("have", "had"), ("come", "came"), ("get", "got"), ("take", "took"),
        ("make", "made"), ("say", "said"), ("buy", "bought"),
        ("think", "thought"), ("teach", "taught"), ("catch", "caught"),
        ("run", "ran"), ("write", "wrote"), ("speak", "spoke"),
        ("meet", "met"), ("find", "found"), ("give", "gave"),
        ("know", "knew"), ("tell", "told"), ("feel", "felt"),
        ("leave", "left"), ("begin", "began"), ("drink", "drank"),
        ("swim", "swam"), ("sing", "sang"), ("sleep", "slept"),
    ]
}

# Present ↔ past tense pairs for the verb "be"
_BE_TENSE_PAIRS = {
    frozenset(p) for p in [("is", "was"), ("are", "were"), ("am", "was")]
}

# Auxiliary verbs whose addition or removal can indicate a tense change
_TENSE_MARKERS = {"will", "did", "had", "has", "have", "was", "were"}

# Third-person singular subjects (when preceding, classify as subject_verb, not plural)
_SINGULAR_SUBJECTS = {"he", "she", "it", "this", "that"}


def _tokenize(text: str) -> list[str]:
    """Extract English words only, in lowercase."""
    return re.findall(r"[a-zA-Z']+", (text or "").lower())


def _is_tense_pair(a: str, b: str) -> bool:
    """Check whether two words form a tense-change pair (regular, irregular, or "be")."""
    pair = frozenset((a, b))
    if pair in _IRREGULAR_PAST_PAIRS or pair in _BE_TENSE_PAIRS:
        return True
    # Regular forms: play → played, like → liked, etc.
    for x, y in ((a, b), (b, a)):
        if y == x + "ed" or y == x + "d":
            return True
        # y → ied changes such as study → studied
        if x.endswith("y") and y == x[:-1] + "ied":
            return True
    return False


def _is_plural_pair(a: str, b: str) -> bool:
    """Check whether two words form a singular/plural pair (s / es / ies ending)."""
    for x, y in ((a, b), (b, a)):
        if y == x + "s" or y == x + "es":
            return True
        if x.endswith("y") and y == x[:-1] + "ies":
            return True
    return False


def _diff_heuristic(original: str, corrected: str) -> str:
    """Infer the error type from the word diff between original/corrected text."""
    orig = _tokenize(original)
    corr = _tokenize(corrected)
    if not orig or not corr:
        return "other"

    # Word order: same words, different order
    if orig != corr and sorted(orig) == sorted(corr):
        return "word_order"

    # Compute the diff and collect replacement pairs, insertions, and deletions
    sm = difflib.SequenceMatcher(a=orig, b=corr)
    replaced_pairs: list[tuple[str, str]] = []  # (original word, corrected word)
    inserted: list[tuple[int, str]] = []        # (position in corrected text, word)
    removed: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "replace":
            r, a = orig[i1:i2], corr[j1:j2]
            if len(r) == len(a):
                replaced_pairs.extend(zip(r, a))
            else:
                removed.extend(r)
                inserted.extend((j1 + k, w) for k, w in enumerate(a))
        elif tag == "delete":
            removed.extend(orig[i1:i2])
        elif tag == "insert":
            inserted.extend((j1 + k, w) for k, w in enumerate(corr[j1:j2]))

    added_words = [w for _, w in inserted]
    changed = removed + added_words + [w for pair in replaced_pairs for w in pair]

    # Subject-verb agreement: replacement pairs such as is/are, has/have
    if any(frozenset(p) in _SV_PAIRS for p in replaced_pairs):
        return "subject_verb"

    # Third-person singular: if an s-ending replacement follows he/she/it, classify as subject_verb
    for j, (a, b) in enumerate(replaced_pairs):
        if _is_plural_pair(a, b):
            idx = corr.index(b) if b in corr else -1
            if idx > 0 and corr[idx - 1] in _SINGULAR_SUBJECTS:
                return "subject_verb"

    # Tense: regular/irregular forms or addition/removal of auxiliaries such as will/did
    if any(_is_tense_pair(a, b) for a, b in replaced_pairs):
        return "tense"
    if any(w in _TENSE_MARKERS for w in added_words + removed):
        return "tense"

    # Articles: addition, removal, or replacement of a/an/the
    if any(w in _ARTICLES for w in changed):
        return "article"

    # Prepositions: replacement, addition, or removal of a preposition
    if any(a in _PREPOSITIONS and b in _PREPOSITIONS for a, b in replaced_pairs):
        return "preposition"
    if any(w in _PREPOSITIONS for w in added_words + removed):
        return "preposition"

    # Singular/plural: changes to s/es/ies endings
    if any(_is_plural_pair(a, b) for a, b in replaced_pairs):
        return "plural"

    # Spelling: treat highly similar replacement pairs as typos
    for a, b in replaced_pairs:
        if a != b and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8:
            return "spelling"

    # Vocabulary: word replacements not covered above
    if replaced_pairs:
        return "vocabulary"

    return "other"


def tag_correction(original: str, corrected: str, explanation: str) -> str:
    """
    Determine and return the error type for one correction.
    Evaluate explanation keywords, then diff heuristics, and return the first
    matching category (or "other" if none match).
    """
    text = explanation or ""
    for etype, pattern in _COMPILED_RULES:
        if pattern.search(text):
            return etype
    return _diff_heuristic(original or "", corrected or "")
