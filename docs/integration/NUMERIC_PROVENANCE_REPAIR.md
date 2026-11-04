# Strict numeric provenance repair

2026-11-02. Parent `6ec15cf5dac89e96272b0a276eaf34d025cd0922`.
Narrow follow-up to independent upload-corrections evaluation
`4e93b5c80e1b3368f3617533900fc6f80fe6d869`.

The original unchanged `test_sync_metadata.py` reproduced **11 pass / 1 fail**:
changing only saved camera `playback_offset_s` from numeric zero to JSON false
was served with HTTP 200. Python dictionary equality aliases False and zero.
The same 12 assertions now pass unchanged. No reference labels, expectations,
provider outputs or historical jobs were edited.

## Correction

`saved_provenance.py` validates supplied JSON numeric metadata without coercion
and uses type-aware recursive equality for approved records, source mappings,
saved analysis copies and track extraction metadata. Provenance equality remains
exact: citation timestamp tolerances are not reused for metadata comparisons.
Boolean, null, empty and
numeric-string values cannot replace numeric offsets, timestamps, frame indices
or crop coordinates. Non-finite numbers are rejected. Explicit integer/float
zero is valid; omitted optional legacy fields and an explicitly uncropped
`crop: null` retain their existing meaning. A missing crop is not converted into
a zero rectangle. Content hashes and complete source/crop/frame binding remain
separate checks.

`multicamera.py` uses strict numeric types for new JSON camera offsets, crop and
layout pixels, shared windows and layout-preview time. `live_api.py` validates
root-track numeric metadata, including a camera provenance record supplied
without a redundant top-level camera ID. Camera artifact routes use the same
authoritative checks. Invalid source bindings quarantine with HTTP 409; no
attempt is made to repair saved evidence in place.

`criterionContext.ts` rejects malformed offset, native/shared time, frame-bound,
FPS and duration types before JavaScript subtraction/division can coerce them.
The existing `validateCitations` entry point also validates supplied camera/source
numeric metadata before saved results or new results reach video playback.
Existing citation bindings and source-seek safeguards are retained.

Focused regressions include changed provenance files, consistently approved
synthetic malformed metadata, source timestamp arrays, crop zero, frame aliases,
frame mappings, camera/root tracks, strict preparation inputs, valid numeric
zero, int/float equivalence and valid legacy records. Each new completed-job
fixture first proves its corresponding route is valid, so missing job artifacts
cannot masquerade as successful quarantine. Two initial new-test fixture/route
assumptions were corrected; independent assertions were never changed.

Development receipts are under ignored `qa-browser-artifacts/numeric-integrity-final`:
original synchronization before/after XML, `integrated-python-final.log`,
`integrated-react.json` and `integrated-build.log`. Combined public-candidate
verification and its selective file transfer are recorded separately in
`COMBINED_RELEASE_REVIEW.md` in the separate public-release checkout.

No general accuracy, new physical-action recognition or full accessibility
certification is claimed. No paid inference, push, merge, deployment, publication
or video edit is part of this repair.
