# MERGE_REPORT — Phase A2 (incremental avatar dataset merge)

## Original dataset (pre-merge)

394 accepted clips, readiness 87/100,
48.7 accepted minutes.

## Incremental dataset (A1)

68 accepted clips offered; verdict READY TO MERGE.

## Merged dataset

- Files merged: **67** (accepted only; 0 rejected clips copied)
- Duplicates skipped (SHA256): 1
- Final accepted clips: **461**
- Final accepted duration: 61.0 min
- Metadata: dataset.sqlite/csv/xlsx rewritten with sequential ids and
  provenance (`original:` / `incremental:` prefix on every row's source);
  pre-merge metadata backed up in `reports/premerge_a2/`.

## Readiness

- Old Avatar Readiness Score: **87/100**
- New Avatar Readiness Score: **95/100**

## Remaining missing viewpoints

- Need more side-profile clips (left/right)
- Need more static talking-to-camera clips
- Need more close-up videos (larger face in frame)
(From A1 coverage: Looking Up, Serious, Walking, Sitting remain < 1 usable min.)

## Integrity validation

- [x] every merged file exists
- [x] metadata accepted rows match files on disk
- [x] sqlite consistent
- [x] csv consistent
- [x] xlsx consistent
- [x] no duplicate sha256 introduced by merge
- [x] no orphan metadata
- [x] no missing thumbnails (merged clips)
- [x] ids unique and sequential
- [x] provenance on every row

Notes:
- 3 duplicate file(s) pre-date A2 inside the original accepted set (duplicate source videos); left untouched.

## Why 461 and not the expected 462

The phase brief projected 394 + 68 = 462, but it also mandates SHA256
duplicate detection with automatic skipping. One A1 clip — **`Part_1.MOV`** —
is byte-identical to a video already in the production accepted set (the same
recording was present in both the original raw dump and the new ZIP drop), so
it was skipped. The production dataset therefore holds **461 unique accepted
clips**; nothing was lost, the 462nd file was already there.
