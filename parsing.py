"""Turn a shopping request (complete or still arriving) into catalogue filters.

One public function: parse(text) -> ParsedRequest. The same function is used
word-by-word while the request streams in and once more on the full text, so
corrections ("black, no wait, white") and late constraints ("oh, and in blue")
are handled by a single rule: the last mention of each field wins.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------- vocabulary

CATEGORY_FORMS = [
    # longest / most specific first; value is the exact catalogue category
    ("hooded sweatshirt", "hoodies"),
    ("running sneakers", "running shoes"),
    ("running shoes", "running shoes"),
    ("jogging shoes", "running shoes"),
    ("casual sneakers", "sneakers"),
    ("casual shoes", "sneakers"),
    ("track pants", "track pants"),
    ("trackpants", "track pants"),
    ("wrist watch", "watches"),
    ("wristwatch", "watches"),
    ("pair of jeans", "jeans"),
    ("t-shirts", "t-shirts"),
    ("t shirt", "t-shirts"),
    ("tshirt", "t-shirts"),
    ("sweatshirt", "hoodies"),
    ("runners", "running shoes"),
    ("sneakers", "sneakers"),
    ("sneaker", "sneakers"),
    ("joggers", "track pants"),
    ("headphones", "headphones"),
    ("headphone", "headphones"),
    ("headset", "headphones"),
    ("earphones", "headphones"),
    ("backpacks", "backpacks"),
    ("backpack", "backpacks"),
    ("bag pack", "backpacks"),
    ("bagpack", "backpacks"),
    ("rucksack", "backpacks"),
    ("slides", "sandals"),
    ("floaters", "sandals"),
    ("sandals", "sandals"),
    ("hoodies", "hoodies"),
    ("hoodie", "hoodies"),
    ("kurtas", "kurtas"),
    ("kurta", "kurtas"),
    ("dresses", "dresses"),
    ("dress", "dresses"),
    ("jackets", "jackets"),
    ("jacket", "jackets"),
    ("denims", "jeans"),
    ("jeans", "jeans"),
    ("shirts", "shirts"),
    ("shirt", "shirts"),
    ("tees", "t-shirts"),
    ("tee", "t-shirts"),
    ("watches", "watches"),
    ("watch", "watches"),
    ("wallets", "wallets"),
    ("wallet", "wallets"),
    ("caps", "caps"),
    ("cap", "caps"),
]

COLOUR_FORMS = [
    ("navy blue", "navy"),
    ("olive green", "olive"),
    ("kaala", "black"),
    ("kala", "black"),
    ("safed", "white"),
    ("laal", "red"),
    ("neela", "blue"),
    ("hara", "green"),
    ("peela", "yellow"),
    ("gulabi", "pink"),
    ("bhura", "brown"),
    ("golden", "gold"),
    ("beige", "beige"),
    ("black", "black"),
    ("blue", "blue"),
    ("brown", "brown"),
    ("gold", "gold"),
    ("green", "green"),
    ("grey", "grey"),
    ("gray", "grey"),
    ("maroon", "maroon"),
    ("navy", "navy"),
    ("olive", "olive"),
    ("pink", "pink"),
    ("red", "red"),
    ("silver", "silver"),
    ("tan", "tan"),
    ("white", "white"),
    ("yellow", "yellow"),
]

SIZE_WORDS = {
    "extra small": "XS", "xs": "XS",
    "small": "S", "s": "S",
    "medium": "M", "m": "M",
    "large": "L", "l": "L",
    "extra large": "XL", "xl": "XL",
    "double xl": "XXL", "2xl": "XXL", "xxl": "XXL",
}

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    # Hindi
    "ek": 1, "do": 2, "teen": 3, "chaar": 4, "paanch": 5, "panch": 5,
    "chhe": 6, "che": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
    "gyarah": 11, "barah": 12, "terah": 13, "chaudah": 14, "pandrah": 15,
    "solah": 16, "satrah": 17, "atharah": 18, "unnis": 19, "bees": 20,
    "pachees": 25, "tees": 30, "paintis": 35, "chalis": 40,
    "paintalis": 45, "pachas": 50, "saath": 60, "sattar": 70, "assi": 80,
}
HINDI_HALF = {"dedh": 1.5, "dhai": 2.5, "dhaai": 2.5}   # dedh/dhai hazaar

CORRECTION_CUES = [
    "oops", "sorry", "i mean", "i meant", "wait", "no no", "no,", "nahi",
    "change that", "change it", "make that", "make it", "actually",
    "or rather", "matlab",
]

WRAP_MARKERS = [
    # politeness / sentence closers
    "please", "thanks", "thank you", "if you have it", "hai kya", "milega",
    "chahiye", "dikhao", "pls",
    # purpose clauses: shoppers add these when they are done with filters
    "for the", "for my", "for office", "for a", "as a gift", "need it",
    "this week", "nothing too",
]

PRICE_TRIGGERS = [
    "not more than", "less than", "under", "below", "within", "up to",
    "upto", "max", "budget", "ke andar", "andar", "se kam", "kam",
]
POSTFIX_TRIGGERS = {"tak", "kam", "andar"}   # amount comes BEFORE these

# ------------------------------------------------------------------- helpers

_ws = re.compile(r"\s+")
_comma_num = re.compile(r"\b(\d{1,3}(?:,\d{3})+)\b")
_k_suffix = re.compile(r"\b(\d+(?:\.\d+)?)\s*k\b")
_digits = re.compile(r"\b(\d+(?:\.\d+)?)\b")


def normalize(text):
    t = text.lower()
    t = _comma_num.sub(lambda m: m.group(1).replace(",", ""), t)
    t = re.sub(r"\brs\.?\b", " ", t)
    t = _k_suffix.sub(lambda m: str(int(float(m.group(1)) * 1000)), t)
    t = re.sub(r"[^\w\s]", " ", t)          # punctuation -> space
    return _ws.sub(" ", t).strip()


def _find_forms(norm, forms):
    """All (start, end, value) matches of each surface form, longest-form priority
    resolving overlaps; caller picks the last surviving match per field."""
    hits = []
    for surface, value in forms:
        for m in re.finditer(r"\b" + re.escape(surface) + r"\b", norm):
            hits.append((m.start(), m.end(), value, len(surface)))
    hits.sort(key=lambda h: -h[3])          # longest first wins overlaps
    taken = []
    for s, e, v, ln in hits:
        if any(s < te and e > ts for ts, te in taken):
            continue
        taken.append((s, e))
        yield s, e, v


def _last_form(norm, forms):
    best = None
    for s, e, v in _find_forms(norm, forms):
        if best is None or s > best[0]:
            best = (s, e, v)
    return best


def _number_words_value(tokens, i):
    """Parse a number-word phrase starting at tokens[i]; returns (value, next_i) or None."""
    total, current, seen = 0, 0, False
    j = i
    while j < len(tokens):
        w = tokens[j]
        if w in NUMBER_WORDS:
            current += NUMBER_WORDS[w]
            seen = True
        elif w in HINDI_HALF:
            current += HINDI_HALF[w]
            seen = True
        elif w == "saadhe":
            current += 0.5
            seen = True
        elif w == "hundred" or w == "sau":
            current = (current or 1) * 100
            seen = True
            # catalogue prices are round hundreds; stop here so a following
            # unrelated number word ("... five hundred. one more thing")
            # is not swallowed into the amount
            j += 1
            break
        elif w == "thousand" or w == "hazaar":
            total += (current or 1) * 1000
            current = 0
            seen = True
        else:
            break
        j += 1
    if not seen:
        return None
    v = total + current
    return (int(v) if float(v).is_integer() else v), j


def _prices(norm, want_spans=False):
    """(start_pos, value) for every 'trigger + amount' budget mention.
    With want_spans, also return char spans of the amount phrases consumed."""
    out, spans = [], []
    tokens = norm.split()
    # word index -> char offset
    offsets, pos = [], 0
    for t in tokens:
        offsets.append(pos)
        pos += len(t) + 1
    for i, w in enumerate(tokens):
        for trig in PRICE_TRIGGERS:
            tparts = trig.split()
            if tokens[i:i + len(tparts)] != tparts:
                continue
            k = i + len(tparts)
            # skip filler between trigger and amount
            while k < len(tokens) and tokens[k] in ("rs", "rupees", "of", "about"):
                k += 1
            if k >= len(tokens):
                continue
            m = _digits.fullmatch(tokens[k])
            if m:
                out.append((offsets[k], int(float(tokens[k]))))
                spans.append((offsets[k], offsets[k] + len(tokens[k])))
                continue
            parsed = _number_words_value(tokens, k)
            if parsed:
                value, endk = parsed
                if isinstance(value, (int, float)) and value >= 100:
                    out.append((offsets[k], int(value)))
                    spans.append((offsets[k], offsets[endk - 1] + len(tokens[endk - 1])))
    # postfix triggers: "do hazaar tak", "1700 se kam", "satrah sau ke andar"
    for i, w in enumerate(tokens):
        if w not in POSTFIX_TRIGGERS or i == 0:
            continue
        if w == "kam" and (i < 2 or tokens[i - 1] != "se"):
            continue
        if w == "andar" and tokens[i - 1] == "ke":
            pass  # "ke andar" postfix after amount
        trig_start = i - 1 if (w == "kam" or (w == "andar" and tokens[i - 1] == "ke")) else i
        # find the earliest start of the amount phrase ending just before the trigger
        end = trig_start
        if end == 0:
            continue
        if _digits.fullmatch(tokens[end - 1]):
            out.append((offsets[end - 1], int(float(tokens[end - 1]))))
            spans.append((offsets[end - 1], offsets[end - 1] + len(tokens[end - 1])))
            continue
        for j in range(max(0, end - 7), end):
            parsed = _number_words_value(tokens, j)
            if parsed and parsed[1] == end:
                value = parsed[0]
                if isinstance(value, (int, float)) and value >= 100:
                    out.append((offsets[j], int(value)))
                    spans.append((offsets[j], offsets[end - 1] + len(tokens[end - 1])))
                break
    # fallback: a bare large digit (>= 300) is a budget even without a trigger
    # word; sizes and quantities in this catalogue never reach 300
    for i, t in enumerate(tokens):
        if not _digits.fullmatch(t) or "." in t:
            continue
        v = int(t)
        if v < 300:
            continue
        if i > 0 and tokens[i - 1] in ("size", "uk", "waist", "number"):
            continue
        if i + 1 < len(tokens) and tokens[i + 1] in ("size", "uk", "waist", "number"):
            continue
        s, e = offsets[i], offsets[i] + len(t)
        if any(s >= ps and e <= pe for ps, pe in spans):
            continue
        out.append((s, v))
        spans.append((s, e))
    return (out, spans) if want_spans else out


def _sizes(norm, tokens, price_spans):
    """(start_pos, size) mentions. Context forms first, then standalone forms;
    longest match wins overlaps, and tokens already used by a price are skipped."""
    out = []
    for m in re.finditer(r"\b(?:size|uk|waist|number)\s+([a-z0-9]+(?:\s(?:xl|xs))?)\s*(uk)?\b", norm):
        out.append((m.start(), m.end(1), _size_value(m.group(1).strip())))
    for m in re.finditer(r"\b([a-z0-9]+)\s+(?:uk|size|number|waist)\b", norm):
        out.append((m.start(), m.end(1), _size_value(m.group(1))))
    # standalone apparel forms: "extra large", "2xl", "medium", ...
    # single letters (s/m/l) need context: after punctuation-stripping, "it's"
    # leaves a bare "s" token that must not read as size S
    standalone = {k: v for k, v in SIZE_WORDS.items() if len(k) > 1}
    for surface, value in standalone.items():
        for m in re.finditer(r"\b" + re.escape(surface) + r"\b", norm):
            out.append((m.start(), m.end(), value))
    # bare shoe-size number words ("size eight actually six slides"): allowed
    # when a footwear category is present and the token is not part of a price
    if re.search(r"\b(slides|floaters|sandals|sneakers|runners|shoes)\b", norm):
        offsets, pos = [], 0
        for t in tokens:
            offsets.append((pos, pos + len(t)))
            pos += len(t) + 1
        for i, t in enumerate(tokens):
            if t in NUMBER_WORDS and 5 <= NUMBER_WORDS[t] <= 12 and t not in ("one", "two"):
                s, e = offsets[i]
                if any(s >= ps and e <= pe for ps, pe in price_spans):
                    continue
                out.append((s, e, str(NUMBER_WORDS[t])))
    # resolve overlaps: longest span first, then the latest surviving mention wins
    out = [o for o in out if o[2]]
    out.sort(key=lambda o: -(o[1] - o[0]))
    kept, taken = [], []
    for s, e, v in out:
        if any(s < te and e > ts for ts, te in taken):
            continue
        taken.append((s, e))
        kept.append((s, v))
    return kept


def _size_value(raw):
    raw = raw.strip().lower()
    if raw in SIZE_WORDS:
        return SIZE_WORDS[raw]
    if raw.isdigit():
        return raw
    if raw in NUMBER_WORDS:
        return str(NUMBER_WORDS[raw])
    return None


# -------------------------------------------------------------------- result

@dataclass
class ParsedRequest:
    filters: dict
    n_fields: int                     # distinct fields set
    last_mention_tok: int             # token index where the newest winning mention ends
    cue_tok: int                      # token index of the last correction cue (-1)
    wrap: bool                        # request carries a wrap-up marker
    n_tokens: int
    mentions: dict = field(default_factory=dict)


def parse(text):
    norm = normalize(text)
    tokens = norm.split()
    nt = len(tokens)

    def tok_of(char_pos):
        # token index containing char_pos
        idx, pos = 0, 0
        for i, t in enumerate(tokens):
            end = pos + len(t)
            if pos <= char_pos <= end:
                return i
            pos = end + 1
        return nt - 1

    filters, mentions = {}, {}

    b = _last_form(norm, [(br.lower(), br) for br in BRANDS])
    if b:
        filters["brand"] = b[2]
        mentions["brand"] = b

    c = _last_form(norm, CATEGORY_FORMS)
    if c:
        filters["category"] = c[2]
        mentions["category"] = c

    col = _last_form(norm, COLOUR_FORMS)
    if col:
        filters["colour"] = col[2]
        mentions["colour"] = col

    ps, price_spans = _prices(norm, want_spans=True)
    if ps:
        p, v = max(ps, key=lambda x: x[0])
        filters["max_price"] = v
        mentions["max_price"] = (p, p, v)

    szs = _sizes(norm, tokens, price_spans)
    if szs:
        p, v = max(szs, key=lambda x: x[0])
        filters["size"] = v
        mentions["size"] = (p, p, v)

    cue_tok = -1
    for cue in CORRECTION_CUES:
        for m in re.finditer(r"\b" + re.escape(cue.rstrip(",")) + r"\b", norm):
            cue_tok = max(cue_tok, tok_of(m.start()))

    last_mention = max((tok_of(m[1] - 1) for m in mentions.values()), default=-1)
    wrap = any(re.search(r"\b" + re.escape(mk) + r"\b", norm) for mk in WRAP_MARKERS)

    return ParsedRequest(filters=filters, n_fields=len(filters),
                         last_mention_tok=last_mention, cue_tok=cue_tok,
                         wrap=wrap, n_tokens=nt, mentions=mentions)


BRANDS = []   # filled from the catalogue by the agent at init


def set_brands(brands):
    global BRANDS
    BRANDS = sorted(brands, key=len, reverse=True)
