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
