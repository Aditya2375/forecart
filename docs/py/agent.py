"""Forecart: an anticipatory shopping agent.

A request arrives one word at a time. After every word the whole text so far
is re-read into catalogue filters (parsing.parse); when the reading changes,
one counted search checks how many products still fit. The agent commits to a
product only when the fit is unique and the reading has been quiet for a
while, so it is early when the request is clear and silent when it is not.

At the end, finish() re-reads the full request and answers with the product
that fits every filter, relaxing the softest constraint only if nothing fits.
"""
import parsing
from search import load_catalogue

FILTER_KEYS = ("category", "colour", "size", "brand", "max_price")

# commit policy (tuned on dev.jsonl; see tune.py)
QUIET_WORDS = 1        # words since the reading last changed
CUE_WINDOW = 4         # no correction cue within this many recent words
MIN_TOKENS = 6         # never commit before the request is at least this long
REQUIRE_WRAP = True    # commit only once a wrap-up marker has been seen
# A shopper who has just finished the filters moves on to a closer ("for my
# brother", "if you have it", "please", "chahiye"). Seeing the first word of one
# right after the reading went quiet is the same signal as the full marker,
# a few words sooner. Words that can also start a correction ("it", "no",
# "that") are deliberately left out.
CLOSER_STARTS = frozenset({
    "for", "if", "as", "please", "pls", "thanks", "thank", "need", "nothing",
    "this", "chahiye", "milega", "dikhao", "hai",
})

# order in which constraints are relaxed if the full reading fits nothing
RELAX_ORDER = ("max_price", "size", "brand", "colour")


class Agent:
    def __init__(self, tools):
        self.tools = tools
        cat = load_catalogue()
        parsing.set_brands({p["brand"] for p in cat if p["brand"]})
        # categories the catalogue never sizes (watches, wallets, caps ...):
        # for them "fully specified" means four fields, not five
        sized = {p["category"] for p in cat if p["size"]}
        self.sizeless = {p["category"] for p in cat} - sized
        self._cache = {}

    # ------------------------------------------------------------- helpers

    def _search(self, query, filters, k=3):
        """One counted search, memoised: identical lookups are never re-run."""
        key = (query, tuple(sorted((k_, str(v)) for k_, v in filters.items())), k)
        if key not in self._cache:
            self._cache[key] = self.tools.search(query, filters, k)
        return self._cache[key]

    def _candidates(self, text, filters):
        return self._search(text, filters, 3)

    # ---------------------------------------------------------------- loop

    def start(self, request_id):
        self.words = []
        self.last_filters = None
        self.quiet = 0
        self.committed = None
        self.current = None

    def _complete(self, filters):
        """True when every field this kind of product can be filtered by is set."""
        need = ("category", "colour", "brand", "max_price")
        if filters.get("category") not in self.sizeless:
            need += ("size",)
        return all(k in filters for k in need)

    def _read(self, text):
        parsed = parsing.parse(text)
        if parsed.filters.get("category") in self.sizeless:
            parsed.filters.pop("size", None)      # a stray size word means nothing here
        return parsed

    def observe(self, word):
        self.words.append(word)
        text = " ".join(self.words)
        parsed = self._read(text)
        filters = parsed.filters

        if filters != self.last_filters:
            # a single field never pins a product; save the search until the
            # reading is specific enough that a commit is even possible
            if self._complete(filters):
                hits = self._candidates(text, filters)
                self.current = hits[0]["product_id"] if len(hits) == 1 else None
            else:
                self.current = None
            self.last_filters = filters
            self.quiet = 0
        else:
            self.quiet += 1

        if self._safe_to_commit(parsed):
            self.committed = self.current
            return {"commit": self.current, "filters": dict(filters),
                    "confidence": round(0.5 + 0.1 * parsed.n_fields, 2)}
        return {"filters": dict(filters),
                "confidence": round(0.3 + 0.1 * parsed.n_fields, 2)}

    def _safe_to_commit(self, parsed):
        if self.current is None:
            return False
        if parsed.n_tokens < MIN_TOKENS:
            return False
        if not self._complete(parsed.filters):
            return False
        if self.quiet < QUIET_WORDS:
            return False
        if parsed.cue_tok >= 0 and parsed.n_tokens - 1 - parsed.cue_tok < CUE_WINDOW:
            return False
        if REQUIRE_WRAP and not parsed.wrap:
            closer = self.words[-1].lower().strip(",.?!;:")
            if closer not in CLOSER_STARTS:
                return False
        return True

    def finish(self):
        text = " ".join(self.words)
        filters = self._read(text).filters
        if filters == self.last_filters and self.current is not None:
            return self.current          # the last counted search already settled it
        hits = self._candidates(text, filters)
        if hits:
            return hits[0]["product_id"]
        relaxed = dict(filters)
        for key in RELAX_ORDER:
            relaxed.pop(key, None)
            hits = self._candidates(text, relaxed)
            if hits:
                return hits[0]["product_id"]
        hits = self._candidates(text, {})
        return hits[0]["product_id"] if hits else self.committed
