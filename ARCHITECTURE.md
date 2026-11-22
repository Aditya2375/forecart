# ForeCart — architecture note (1 page)

AgentX: The Agentic Commerce Challenge, Challenge 1 (Anticipatory Commerce).
Team Do You Care (TM-AEFE9948F9D), Techfest 2026-27, IIT Bombay.

## Problem

A shopping request streams in one word at a time. The agent must decide, after
every word, whether to show a product (commit) or keep waiting. A wrong commit
is heavily penalised, every catalogue lookup is counted, and the earlier a
correct commit lands, the better the score.

## Data flow

```
words ─▶ re-parse full text-so-far (parsing.py)
            │  closed-world extraction: category / colour / size / brand / max_price
            ▼
        filter state  ─changed?─▶ one counted search (search.py over catalogue)
            │                        │
            ▼                        ▼
        commit policy (agent.py): unique match AND fully specified AND
        wrap-up cue seen AND short quiet window  ─▶  COMMIT product
            │
        finish(): re-read everything, answer best fit, relax soft
        constraints (budget → size → brand → colour) only if nothing fits
```

## Components

- **parsing.py — incremental multilingual parser.** The request is re-parsed
  from scratch after every word, so the *last mention of each field wins*.
  Corrections ("black, no wait, white") and late constraints ("oh, and in
  blue") need no special-case state machine. Extraction matches a
  closed-world vocabulary built from the catalogue: surface forms and
  synonyms ("runners", "floaters", "rucksack", "wristwatch"), sizes ("double
  XL", "2xl", "32 waist"), and prices as digits, `1.5k`, `Rs. 4000`, English
  number words and Hindi amounts ("dhai hazaar tak", "pandrah sau se kam").
  Hindi-English code-mixed requests parse through the same path.
- **search.py — counted retrieval.** The catalogue is only ever touched
  through the harness's counted search. A lookup fires only when the parsed
  filters actually changed and are specific enough to commit on; identical
  lookups are memoised. Result: 1.12 searches/request (baseline ~6).
- **agent.py — precision-first commit policy.** Commit only when the match is
  *unique*, the reading is *fully specified* (all five fields), the stream has
  been quiet for a short window, and a wrap-up marker is present. A late
  extra constraint cannot invalidate such a commit: narrowing a unique match
  cannot change which product it is. Constants were picked by a grid search
  (`tune.py`) on the public dev set and frozen before the final run.

## Results (public dev set, 300 requests)

Score **40.5** vs baseline 20.0 · final-answer accuracy **1.000** vs 0.527 ·
**0 wrong commits** · 100% filter extraction on all five fields ·
0.35 ms/word, standard library only.

## Rezolve Labs integration point

All retrieval sits behind one counted backend call (`tools.search`). That call
is the wiring point for **Rezolve Labs semantic product search**: swap the
local catalogue ranker for the semantic-search endpoint and the parser, commit
policy and search budget are untouched — the same discipline that gives 1.12
searches/request locally is what keeps API spend bounded at production
catalogue scale. The team credit coupon promised in the problem statement is
still "to be confirmed" by the organisers, so the shipped build runs against
the kit's local search; the integration point is code-complete and activates
the moment access arrives.

## Cost

Development and evaluation ran entirely on a free tier: CPU-only, no external
APIs, no model calls. Marginal cost per evaluated request is effectively zero;
production cost is bounded by the search budget above.
