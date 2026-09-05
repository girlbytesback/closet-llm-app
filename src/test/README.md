# Tests

```bash
uv run pytest                # everything
uv run pytest src/test/unit  # one layer
```

No test calls the Anthropic API or needs a key — `conftest.py`'s `fake_model`
fixture replaces the client with scripted replies. No test writes to `data/`;
`data_paths` redirects both JSON stores into a tmp directory.

| Layer | What it holds |
|---|---|
| `unit/` | One module at a time: the colour chain, `extract`'s disk I/O and folder walk, `images`, `match`'s four functions, CLI parsing, the eval harnesses. |
| `contract/` | Promises to something outside Python — the HTTP responses the React app fetches, the shape of `matches.json` it imports, and the tool schemas we send the model versus the keys the parsing code reads back. |
| `integration/` | Photos in, matched closet out, with the model faked: extract → JSON on disk → match → API response, plus the caching and resume behaviour that only shows up across runs. |
| `regression/` | Pinned numbers — published sRGB/Lab values, frozen distances, the tuned cutoffs, and the eval figures the README quotes (9/48 within ΔE ≤ 5, +7.3 L\*, +5.4 chroma). Also invariants over the committed `data/*.json`. |

The two files at the top level (`test_color_calculations.py`, `test_matching.py`)
predate this layout; `test_color_calculations.py` is what checks CIEDE2000
against the Sharma reference set in `ciede2000testdata.txt`.

## Data drift, resolved

Three tests used to be `xfail` against drift in the committed data. Both causes
are fixed; the notes stay because the first one will come back.

**`clothes/GARMENT_1.jpg` was renamed to `GARMENT_1.jpeg`.** `extract.run` only
ever adds keys; it never prunes ones whose photo has gone. So the store kept the
orphaned `.jpg` entry (`#C275AC`) *and* added a fresh `.jpeg` one (`#C173AB`) —
the same garment, extracted twice, 0.57 ΔE apart. The orphan was dropped from
`clothes.json` and `answer_key.py` rekeyed to `.jpeg`, which is what moved the
published chroma bias from +5.3 to +5.4. Any future rename leaves the same
orphan behind until `extract.run` learns to prune.

**`src/ui/src/data/matches.json` listed `GARMENT_35.jpg`,** which had left both
`clothes/` and `clothes.json`. Regenerated with `closetllm match --out`; rerun
that whenever either store changes.
