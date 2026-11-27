# forecart

A shopping agent that answers before the shopper finishes typing.

**Live demo (replay real traces, or type your own request):** https://aditya2375.github.io/forecart/

Requests arrive one word at a time ("black running shoes, size nine, under two
thousand ..."). Most assistants wait for the end of the sentence and then search.
forecart re-reads the request after every word, keeps its own picture of the
shopper's filters, checks how many products still fit, and shows the product the
moment the fit is unique and the shopper has moved on, never earlier.

Built for AgentX: The Agentic Commerce Challenge (Challenge 1, Anticipatory
Commerce), Techfest 2026-27, IIT Bombay. Team **Do You Care** (TM-AEFE9948F9D).

## Results

Scored with the organisers' own `evaluate.py`, standard library only.

| | score | accuracy | wrong commits | searches / request |
|---|---|---|---|---|
| forecart, public dev set (300 requests) | **42.3** | **1.000** | **0** | 1.13 |
| starter-kit baseline, same set | 20.0 | 0.527 | 0 | 1.53 |
| forecart, 9,600 generated stress requests | **44.7** | **1.000** | **0** | 1.05 |

On the dev set, every filter (category, colour, size, brand, budget) is extracted
correctly on all 300 requests, and accuracy is 1.000 in every bucket (plain,
correction, late constraint, Hindi-English code-mixed). Latency is about 0.2 ms
per word on one CPU core. No model calls, no network, no API cost.

Per-request log of the dev run: `results.jsonl`.

### What the stress set is, and is not

`stress.py` builds requests from real catalogue products, so the target is known.
Its phrasing pools are wider than the dev set: English and Hindi number words,
`1.5k` / `Rs.` / `rupees` budgets, category and colour synonyms, size forms
(`2XL`, `double XL`, `32 waist`, `UK 9`), corrections and late constraints.
It is our own generator, so it tests the parser and commit policy for robustness.
It is not the organisers' hidden set and says nothing about phrasing neither of us
thought of. Running it found two latent bugs, both fixed:

- an opening "please find ..." was counted as a closing cue, which could commit
  too early when a correction came later;
- number words next to "UK" or "waist" could be read as part of a budget
  ("ten chhe hazaar" became 16,000).

```
python stress.py --seed 21 --n 1500 --out stress.jsonl
python evaluate.py --agent agent.py --data stress.jsonl
```

## How it works

```
word stream --> re-parse whole text so far --> filters changed? --> one counted search
                    (parsing.py)                      |                     |
                last mention of each            unique product AND      update candidate
                field wins (handles             fully specified AND     (else keep waiting)
                corrections + late              a closing cue seen?
                constraints)                          |
                                               commit: show the product
```

1. **Closed-world vocabulary.** Every brand, category, colour and size in the
   catalogue is enumerable, so extraction is matching against known surface forms
   ("runners", "jogging shoes", "slides", "floaters", "rucksack", "wristwatch",
   "double XL", "2xl", "32 waist", "kaala", "gulabi", "saadhe teen hazaar",
   "pandrah sau se kam") instead of guessing. Budgets accept digits, `1.5k`,
   `Rs. 4000`, English number words and Hindi amounts.
2. **Last mention wins.** The whole text so far is re-parsed after each word, so a
   correction ("black, no wait, white") or a late constraint ("oh, and in blue")
   just changes the latest mention of that field. There is no correction state
   machine to get wrong.
3. **Commit on a closer.** A product is shown only when it is the unique match of
   a fully specified reading (category, colour, size, brand, budget; size is not
   needed for watches, wallets, caps, headphones and backpacks, which the
   catalogue never sizes) and the
   shopper has moved on: a closing marker ("please", "if you have it",
   "chahiye"), or the first word of one ("for", "as", "need") right after the
   reading stopped changing. A wrong commit costs 1.0 and the whole earliness
   bonus is at most 0.6, so the agent would rather be a few words late than wrong.
   Words that can also start a correction ("it", "no", "that") are not closers.
   At the end, `finish()` re-reads the complete request and answers with the
   product that fits everything, relaxing the softest constraint (budget, then
   size, then brand, then colour) only if nothing fits.

**Search discipline.** The catalogue is treated as a remote store: products are
only looked up through counted searches. A search fires only when the filter
reading changes and is specific enough to commit on, and identical lookups are
memoised.

**Known limit.** Earliness is modest (4.3% of the request on dev, against 16.3%
for a perfect oracle). Requests that end with a late constraint ("... oh, and in
blue") cannot be committed earlier without guessing, and the commit policy
assumes a correction comes right after the field it corrects, as in the dev set.

## Rezolve Labs search

All retrieval goes through one counted call, `tools.search`. That call is the
wiring point for Rezolve Labs semantic product search: replace the local ranker
with the endpoint and the parser, commit policy and search budget stay as they
are. The shipped build uses the kit's local catalogue search; no Rezolve code is
included because no access has been issued.

## Files

| file | what it is |
|---|---|
| `agent.py` | the agent: streaming loop, commit policy, final answer |
| `parsing.py` | request text to catalogue filters (vocabulary, prices, sizes, cues) |
| `stress.py` | held-out request generator used for the stress runs |
| `results.jsonl` | per-request results on the public dev set |
| `tune.py` | grid search over the commit-policy constants (dev set) |
| `docs/` | the live demo page (static HTML, real traces; the in-browser mode runs these same Python files) |
| `catalogue.csv`, `dev.jsonl`, `search.py`, `evaluate.py` | the organisers' starter kit, unmodified |

Reproduce: `python evaluate.py --agent agent.py --log results.jsonl` (Python 3, standard library only).
