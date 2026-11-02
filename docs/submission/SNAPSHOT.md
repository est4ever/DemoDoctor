# Separate public-release snapshot

This tree was exported from committed integration checkpoint
`05b175db352ae306c8607e6e08f06036f330b55b` (application freeze `736e4e1`).
It imports no original `.git`, parent commits, remotes, stash, branches or private
history. A new root commit records this release; it does not imply new authorship
of the entire project during the hackathon. BUILD_HISTORY.md preserves that distinction.

Application Python/React/CSS source, launcher scripts, all tests and dependency
lockfiles retain the archive-export bytes. Git archive on Windows serialized some
text as CRLF; comparison with committed blobs accepts only CRLF/LF differences.
The public .gitattributes disables conversion so replay/manifest hashes remain
valid under different user Git settings. The private maintainer-only replay
packaging script is omitted because it contains local input defaults and is not
needed to consume the bundled demonstrations. All other retained source/scripts
are byte-identical; no model, threshold, runtime handler or scientific result was changed.

Excluded: original Git data; personal environment/configuration; raw provider
transport/request logs; internal handoffs, plans and QA receipts; unused research
fixtures/previews; duplicate prototype recordings; full raw videos; dependency
environments; compiled builds; final-video production and audio. Selected
dataset-derived historical fixtures used by replay/regression tests are retained,
not arbitrary private user uploads. Optional legacy raw-response text is omitted;
validated explanations and original evidence package bindings remain.

Exported fixture copies have only workstation-prefix paths made relative and
provider-operation fields omitted. The complete field-level change list and
source/public SHA256 pairs are in SNAPSHOT_PROVENANCE.json. Numerical scientific
claims, object/evidence IDs, event/frame timestamps, verdicts, uncertainty and
model explanations remain unchanged. These sanitized fixture copies must not
be described as byte-identical frozen experiment directories; their original
integrity records describe the source experiment, not a new re-run.

All 19 files named by data/submission_demo/MANIFEST.json retain their exact hashes,
including PILOT historical/current packages. Model citations remain bound to
their original packages. No provider call was made for this export or validation.

The complete release source-file inventory and SHA256 values are in
SOURCE_MANIFEST.json (the manifest excludes itself). Test receipts and environments
remain local and untracked; VALIDATION.md publishes only the non-sensitive results.
Original LICENSE, NOTICE and dataset/robot copyright notices are retained.

This source snapshot does not grant new rights in upstream datasets, model outputs
or final-video audio. Publisher-declared dataset licenses, parser SAM License and
provider/audio permissions remain distinct; see THIRD_PARTY.md.

## Incremental update — November 1, 2026

The public root commit 26a8a9f remains the parent history of this update. Approved
source/test/required setup-asset changes from f60965f and 097f8e1 were transferred
as files, without copying Git metadata or private commit objects. Sanitized
fixtures, all 19 replay asset hashes, licenses and notices remain unchanged.
Documentation now distinguishes implemented self-service Real Analysis from
credential-free replay and mocked validation. SOURCE_MANIFEST.json describes
the updated source tree; original export metadata remains in
SNAPSHOT_PROVENANCE.json with an appended incremental-update record.

## Final incremental candidate — November 1

This candidate descends from public commits 26a8a9f and 35b0050. It transfers
approved changes through private source checkpoint `cc5c3ab3e68f27bb4427aef5a23c3e7c794ca622` as files only.
No private history, personal job, DROID video, credentials or video-production
asset is imported. Existing sanitized fixtures, all 19 replay hashes and notices
remain byte-identical. Six optional criterion presentations are generated against
the public catalogs. Missing raw research-cache/reference inputs produce explicit
test skips; synthetic/core checks run normally. Only evaluation tooling/test
packaging was adjusted to disclose these intentional exclusions; no inference
algorithm or scientific result was changed. Current results are in FINAL_UPDATE_20261101.md.

## Frozen diagnostic-context update

Current source freeze: `de5009f26818d6d8a6cc0b15ba87fd89004095b6`. The incremental parent is `c1cebf3f353eb62422cabacce3922bda1b166609`. Only reviewed source/tests/docs were transferred; personal analyst reviews and all private job/video data remain excluded. Existing public history, licenses and original result hashes are preserved. See RELEASE_READINESS_20261101.md for current checks and limitations.

## Defensive integrity update — November 2

Public parent: `0e2e69690a81b8188b8fdcd5b367dc60673fc696`. This incremental
release selectively ports reviewed source-bound criterion guards, temporal
provenance checks and citation-binding repairs through development checkpoint
`c0f28c3eb370355750dd34fe86fed7c58924265e`. Experimental pixel/action detectors
and their API/UI are excluded. Original private history is not imported. Existing
public code line endings and byte-preserving attributes are retained. The citation
registry hashes unchanged public source artifacts; no original result is rewritten.
All 19 replay hashes, provider artifacts, licenses/notices, README media and build
history remain unchanged. The current SOURCE_MANIFEST includes this incremental
tree; earlier export provenance records remain preserved. See
[defensive release review](../integration/DEFENSIVE_INTEGRITY_RELEASE.md) for exact
source scope, tests, skipped research fixtures and native browser checks.

## Combined local candidate — November 2

Public parent: `27375223d2740e4a3570c5212632a8be15bf008c`. Selective integration through development checkpoint
`bb5c509ac2dff14b3c1c0dcc2afdbe5d9407cebf` preserves the public Git history and prior defensive
release adaptations. Reviewed workstation/upload corrections and strict JSON numeric
metadata checks are included; experimental physical-action detectors remain excluded.
No original media, citations, outcomes, notices or private jobs are changed or added.
See [combined review](../integration/COMBINED_RELEASE_REVIEW.md) for exact tests,
file scope, remaining P2 issues and independent-review status. Publication is pending.

## Local-prototype preparation follow-up — November 2

Parent: `d9b9bb4ffff86349c23f8fba688516f7e22bfd21`, after independent acceptance.
This small follow-up improves execution-mode descriptions, narrow navigation
focus, out-of-window warning readability and on-demand temporal previews. It
adds user instructions and focused tests, not inference algorithms or new model
results. Local provider-record labels are not remote authentication or physical
verification. Original media, provider outputs, citations, task assessments,
licenses, notices and build-history disclosure are preserved. See
[release preparation](../integration/LOCAL_PROTOTYPE_RELEASE_PREPARATION.md).
