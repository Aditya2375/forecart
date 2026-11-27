# forecart: architecture note (1 page)

AgentX: The Agentic Commerce Challenge, Challenge 1 (Anticipatory Commerce). Team Do You Care (TM-AEFE9948F9D), Techfest 2026-27, IIT Bombay.

## Problem

A request streams in one word at a time. After every word the agent either commits to a product or waits. A wrong commit costs 1.0, every catalogue lookup is counted, and a correct commit earns more the earlier it lands. Requests carry corrections ("black, no wait, white"), late constraints ("oh, and in blue") and Hindi-English mixing.

## Data flow

```
word --> re-parse full text so far (parsing.py) --> filters {category, colour, size, brand, max_price}
              |
              +-- changed and fully specified? --> one counted search (memoised)
              |
         unique match AND quiet for a word AND a closing cue seen? --> COMMIT
              |
         finish(): re-read everything, answer the best fit, relax budget, size, brand, colour in that order only if nothing fits
```

## Components

- **parsing.py** is the whole language layer. Extraction matches a closed-world vocabulary built from the catalogue: surface forms and synonyms (runners, floaters, rucksack, wristwatch), sizes (double XL, 2xl, 32 waist, UK 9), budgets as digits, 1.5k, Rs. 4000, English number words and Hindi amounts (dhai hazaar tak, pandrah sau se kam). The text is re-parsed from scratch after each word, so the last mention of a field wins and corrections need no state machine. Number phrases are checked for well-formedness so a size next to a budget ("ten chhe hazaar") is not merged into it.
- **agent.py** is the commit policy. Commit only when the match is unique, every field that product type has is set (size is skipped for watches, wallets, caps, headphones, backpacks), the reading has been quiet for a word, no correction cue is in the last four words, and a closer comes after the newest field mention: a marker such as "please", "if you have it", "chahiye", or the first word of one ("for", "as", "need"). Words that can start a correction ("it", "no", "that") are not closers.
- **Search budget.** Retrieval is only through the counted search call. It fires when the filters change and are specific enough to commit on, and repeats are memoised: 1.13 searches per request on dev (baseline 1.53).

## Results

| set | score | accuracy | wrong commits |
|---|---|---|---|
| public dev set, 300 requests | 42.3 (baseline 20.0) | 1.000 (baseline 0.527) | 0 |
| 9,600 generated stress requests (stress.py) | 44.7 (baseline 16.5) | 1.000 | 0 |

All five filters are extracted correctly on all 300 dev requests. About 0.2 ms per word on CPU, standard library only, no model calls. The stress set is our own generator (new phrasings, number forms, synonyms); it measures robustness, not the organisers' hidden set. Earliness is 4.3% of the request on dev against 16.3% for a perfect oracle: the policy trades it for zero wrong commits.

## Rezolve Labs integration point

All retrieval sits behind one counted call, `tools.search`. Swapping the local ranker for the Rezolve Labs semantic-search endpoint changes that call only; the parser, the commit policy and the search budget stay as they are, and the budget is what would bound API spend on a large catalogue. The shipped build uses the kit's local search because no Rezolve access has been issued; no Rezolve code is included.

## Cost and scale

Development and evaluation ran on free tooling: one CPU core, no external APIs, no model calls. Per-word work is a regex pass over the text so far, which is linear in request length and independent of catalogue size. Catalogue size only affects the counted search, which is already isolated behind one interface.
