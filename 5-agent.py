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
MIN_FIELDS = 5         # commit only on a fully-specified reading
CUE_WINDOW = 4         # no correction cue within this many recent words
MIN_TOKENS = 6         # never commit before the request is at least this long
REQUIRE_WRAP = True    # commit only once a wrap-up marker has been seen

# order in which constraints are relaxed if the full reading fits nothing
RELAX_ORDER = ("max_price", "size", "brand", "colour")


class Agent:
    def __init__(self, tools):
        self.tools = tools
        parsing.set_brands({p["brand"] for p in load_catalogue() if p["brand"]})
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

    def observe(self, word):
        self.words.append(word)
        text = " ".join(self.words)
        parsed = parsing.parse(text)
        filters = parsed.filters

        if filters != self.last_filters:
            # a single field never pins a product; save the search until the
            # reading is specific enough that a commit is even possible
            if parsed.n_fields >= MIN_FIELDS:
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
        if parsed.n_fields < MIN_FIELDS:
            return False
        if self.quiet < QUIET_WORDS:
            return False
        if parsed.cue_tok >= 0 and parsed.n_tokens - 1 - parsed.cue_tok < CUE_WINDOW:
            return False
        if REQUIRE_WRAP and not parsed.wrap:
            return False
        return True

    def finish(self):
        text = " ".join(self.words)
        filters = parsing.parse(text).filters
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
