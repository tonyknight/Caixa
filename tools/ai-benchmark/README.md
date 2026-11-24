# AI benchmark

A bake-off between **Apple Intelligence** (the Mac's own model) and **your own model** behind an
OpenAI-compatible endpoint (oMLX, LM Studio, Ollama…), on the two jobs Caixa gives a model:

- **Summaries:** one per mail conversation, 30–50 words in the conversation's language, exactly
  as a mail import writes them (35 conversations).
- **Translations:** each Portuguese email into English, exactly as an import translates (20
  emails).

- **Documents:** what each of twelve made-up documents is, who issued it and when, exactly as a
  PDF import reads it, scored against what is known about each (type, author, date, title).

`emails.json` holds 100 made-up emails in 35 conversations of 1 to 6 mails: 80 in English and 20
(7 conversations) in Portuguese. Every name and address is invented (the project's synthetic
family). `documents.json` holds the synthetic PDF family's twelve documents as a model is given
them (file name, properties, the text of each page, a scan's as OCR reads it) with their known
answers. It is written from the test fixtures, and a test checks it still matches them; to write it
again after changing them:

```bash
python -c "import json,sys; sys.path.insert(0,'tests/fixtures'); from pdf_family import benchmark_documents; open('tools/ai-benchmark/documents.json','w',encoding='utf-8').write(json.dumps({'documents': benchmark_documents()}, ensure_ascii=False, indent=2) + chr(10))"
```

Nothing from a box is used or sent.

## Running it

On the Mac, in the Caixa folder (the one you installed with `pip install -e tools/chattr -e .`).
Apple Intelligence needs its helper built and ready (see `tools/apple-intelligence/README.md`):

```bash
tools/apple-intelligence/.build/release/caixa-apple-intelligence --check
```

Then, with your oMLX server running, give its address and the model's name as oMLX lists them.
The key can be typed without showing it:

```bash
caixa benchmark --endpoint http://localhost:8000/v1 --model YOUR-MODEL-NAME --ask-key
```

Or put the key in the environment for this terminal:

```bash
export CAIXA_BENCHMARK_API_KEY='your-omlx-key'
```

```bash
caixa benchmark --endpoint http://localhost:8000/v1 --model YOUR-MODEL-NAME
```

(`--api-key KEY` works too, but the key then stays in your shell history.) Use the address and port
your oMLX server prints when it starts.

By default it times Apple Intelligence with 1, 2, 4 and 8 helpers at once and your endpoint with
1, 2 and 4 requests at once, for both jobs: 14 runs. That takes a while (a slow local model at one
request at a time may need several minutes per run). To change it:

| Option | What it does |
| --- | --- |
| `--apple-workers 2,4` | the helper counts to try for Apple Intelligence |
| `--endpoint-workers 1,2` | the requests at once to try for your endpoint |
| `--only apple` or `--only endpoint` | time one side only |
| `--tasks summaries` or `--tasks translations` | one job only |
| `--out FOLDER` | where the report goes (default: `ai-benchmark-<date-time>` in the current folder) |
| `--emails FILE` | other emails in the same form as `emails.json` |

Close other heavy programs while it runs, and run it on mains power: a laptop on battery slows down.

## Reading the results

Each run prints a line as it finishes, and at the end which side was faster at each job and by how
much. The folder holds:

- `report.md`: a table per job. *A second* is items finished per second over the whole run (higher
  is faster); *Each* is the run's time divided by the items done; *Slowest* is the longest single
  item. For summaries, *Words* is their average length (Caixa asks for 30–50) and *Portuguese
  kept* counts the 7 Portuguese conversations whose summary came back in Portuguese. *Problems*
  counts what failed or what Apple Intelligence's safety filter declined.
- `report.json`: the same, as data.
- `outputs/`: every summary and translation from every run (`apple-4-summaries.json`,
  `endpoint-2-translations.json`…), to compare their quality, not only their speed.

Every run is warmed up first (one small request per worker, not timed), so a model loading or the
helpers starting do not count against either side.

**What to look for:** the best *A second* for each side (the worker count where it stops getting
faster), whether Apple Intelligence keeps up on summaries (it reads less of a long conversation:
6,000 characters against 12,000), and whether its summaries and translations read as well as your
model's. If Apple Intelligence is clearly faster and reads well enough, choose it in Settings →
Summaries and → Translation.
