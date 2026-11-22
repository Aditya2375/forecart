# forecart

A shopping agent that answers before the shopper finishes typing.

Requests arrive one word at a time ("black running shoes, size nine, under two
thousand …"). Most assistants wait for the end of the sentence and then search.
forecart re-reads the request after every word, keeps its own picture of the
shopper's filters, checks how many products in the catalogue still fit, and
shows the product the moment the fit is unique and the request is done
changing — never earlier.

Built for AgentX: The Agentic Commerce Challenge (Challenge 1 — Anticipatory
Commerce), Techfest 2026-27, IIT Bombay. Team **Do You Care** (TM-AEFE9948F9D).

## Results on the public dev set (300 requests)

| metric | forecart | baseline |
|---|---|---|
| score | **40.5** | 20.0 |
| accuracy (final answer) | **1.000** | 0.527 |
| wrong commits | **0** | 0 |
| filters extracted correctly (all 5 fields, all 300 requests) | **100%** | — |
| searches per request | **1.12** | ~6 |
| latency | 0.24 ms/word | — |

Breakdown by request kind (corrections, late constraints, Hindi-English
code-mixed, plain): accuracy 1.000 in every bucket, zero wrong commits in
every bucket. Per-request log: `results.jsonl` (regenerate with
`python evaluate.py --agent agent.py --log results.jsonl`).

## How it works

```
word stream ──▶ re-parse whole text so far ──▶ filters changed? ──▶ one counted search
                    (parsing.py)                      │                     │
                last mention of each            unique product AND      update candidate
                field wins (handles             fully specified AND     (else keep waiting)
                corrections + late              wrap-up marker seen?
                constraints)                          │
                                               commit: show the product
```

Three ideas do the work:

1. **Closed-world vocabulary.** Every brand, category, colour and size in the
   catalogue is enumerable, so extraction is matching against known values
   with their surface forms — "runners", "jogging shoes", "slides",
   "floaters", "rucksack", "wristwatch", "double XL", "2xl", "32 waist",
   "kaala", "gulabi", "saadhe teen hazaar", "pandrah sau se kam" — instead of
   guessing. Budgets handle digits, `1.5k`, `Rs. 4000`, English number words
   ("forty five hundred") and Hindi amounts ("dhai hazaar tak").
2. **Last mention wins.** The whole text-so-far is re-parsed after each word,
   so a correction ("black, no wait, white", "size M, oops, XS") or a late
   constraint ("oh, and in blue") simply changes the latest mention of that
   field. There is no correction-specific state machine to get wrong.
3. **A commit rule that would rather be early than sorry — and is never
   sorry.** Committing to the wrong product costs more than earliness can
   ever win back, so a product is shown only when it is the *unique* match of
   a *fully specified* reading (category, colour, size, brand, budget) that
   has stayed quiet for a beat and carries a wrap-up marker ("please",
   "thanks", "for the gym", "hai kya"). A late-arriving extra constraint can
   never invalidate such a commit: adding a filter to a unique match cannot
   change which product it is. At the end, `finish()` re-reads the complete
   request and answers with the product that fits everything, relaxing the
   softest constraint (budget, then size, then brand, then colour) only if
   nothing fits.

**Search discipline.** The catalogue is treated as a remote store: products
are only ever looked up through counted searches. A search is fired only when
the filter reading actually changes and is specific enough to commit on, and
identical lookups are memoised — 1.12 searches per request on the dev set,
against ~6 for the baseline.

## Rezolve Labs capability

The counted-search call goes through a single backend interface
(`tools.search` today, the kit's local catalogue search). The production
wiring point for **Rezolve Labs semantic product search** is that same call:
swap the local ranker for the semantic-search endpoint and the agent,
including the commit policy and the search budget, is unchanged. The team
credit coupon promised in the problem statement is still marked "to be
confirmed" by the organisers; the integration point is documented in
`ARCHITECTURE.md` and activates the moment the coupon arrives.

## Files

| file | what it is |
|---|---|
| `agent.py` | the agent: streaming loop, commit policy, final answer |
| `parsing.py` | request text → catalogue filters (vocabulary, prices, sizes, cues) |
| `results.jsonl` | per-request results on the public dev set |
| `tune.py` | the commit-policy grid search used to pick the shipped constants |
| `catalogue.csv`, `dev.jsonl`, `search.py`, `evaluate.py` | the organisers' starter kit, unmodified |

Python 3.9+, standard library only. Nothing to install.

```
python evaluate.py --agent agent.py --log results.jsonl
```

## Licence

MIT (see `LICENSE`). The starter-kit files remain the organisers'.
