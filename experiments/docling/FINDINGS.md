# Docling spike findings

Question: does Docling recover the page 13, 94 and 97 facts that `pypdf` loses and that are hand-transcribed in `data/transcriptions.jsonl` (D27)? Experiment only; nothing is integrated.

## Setup

- Docling 2.128.0, CPU only, 8 cores. Command in the `parse.py` docstring.
- Default converter (table structure on, OCR default). One untimed warm-up on page 13, then one timed conversion per page.

| Run | Wall | CPU |
|---|---|---|
| Page 13 | 29.56 s | 114.45 s |
| Page 94 | 16.73 s | 63.55 s |
| Page 97 | 27.37 s | 102.49 s |
| Page 13, full-page OCR | 41.49 s | 158.81 s |

Preview run before this branch (not re-measured): install 1 min 45 s; first run including model downloads about 3.5 min.

## Page 13: troubleshooting matrix vs `p13-1`..`p13-6`

| Item | Result |
|---|---|
| Table detected | Yes, 12 rows x 6 columns |
| Causes | 11/11, text matches |
| Solutions | 11/11, paired with the right cause |
| Symptom list (1-6) | Recovered as list items above the table |
| Symptom column headers | 6 symptoms merged into 4 header cells: `1 2`, `3 4`, `5`, `6` |
| Symptom-to-cause links | 0/15; body rows have no cells in the symptom columns |
| ● markers | Absent from markdown and JSON |

- The ● markers are likely vector graphics rather than text or raster image. Unverified.
- Full-page OCR (`--full-ocr`) output is byte-identical to the default. `force_full_page_ocr` is deprecated in 2.128.0; setting it sets `mode = OcrMode.FULL_PAGE`.

## Page 94: Fig. 4 vs `p94-1`

| Item | Result |
|---|---|
| Captions `Fig. 3`, `Fig. 4` | Recovered, labelled `caption` |
| Label "Pump" (multilingual fragments) | Recovered |
| "Max. 2 m" | Recovered |
| Pump above the pool water level | Not recovered |
| Connections to pool and filter | Not recovered |

## Page 97: installation zones vs `p97-1`

| Item | Result |
|---|---|
| Zone labels (Zone 0/1/2, Outdoor area, Feet cleaning) | Recovered, not linked to regions |
| Distances (1,5 / 2,0 / 2,5 m) | Recovered as isolated values, not linked to zones |
| Radii `r1 = 2,0 m`, `r2 = 3,5 m` | Recovered, fragmented (`r` and `2 = 3,5 m` split) |
| Caption "Areas highlighted: the pump may be installed here" | Recovered, labelled `text` |
| Which zone is highlighted (Zone 2) | Not recovered |

## Picture descriptions (SmolVLM)

`--describe-pictures` (SmolVLM-256M-Instruct on pages 94 and 97) did not complete within the 300 s budget and produced no output. Whether model download or CPU inference took the time is not established. The flag stays in `parse.py`; it has never completed a run.

## Result

Docling does not recover the facts D27 transcribes by hand: 0/15 symptom-to-cause links on page 13, no pump position or connections on page 94, no highlighted zone on page 97. It does recover table text, labels and captions.

## Next step

- Keep the hand transcriptions for pages 13, 94 and 97.
- Docling is a candidate for tables and text in general.
- For markers and highlighted zones, test a vision model on page or table images, checked against `data/transcriptions.jsonl`.
