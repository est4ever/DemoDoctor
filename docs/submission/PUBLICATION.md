# Proposed incremental public update — owner approval required

The existing public repository is https://github.com/est4ever/DemoDoctor.
This local update preserves its original root commit 26a8a9f. Do not recreate
it, force-push it, or attach private development history. The separate private
DemoDoctor_Predevelopment and its PR #3 are unaffected.

Nothing in this update authorizes a push, merge, deployment or submission.
After approval of the exact local update commit, use only this separate checkout:

```powershell
Set-Location '<path-to-the-separate-public-release-checkout>'
$approvedSha = '<OWNER-APPROVED-UPDATE-SHA>'
if ((git branch --show-current).Trim() -ne 'release/validated-update-20261101') { throw 'Wrong branch' }
if ((git rev-parse HEAD).Trim() -ne $approvedSha) { throw 'Unapproved commit' }
if (git status --porcelain) { throw 'Working tree not clean' }
if ((git remote get-url origin).Trim() -ne 'https://github.com/est4ever/DemoDoctor.git') { throw 'Wrong repository' }
git fetch origin
if ($LASTEXITCODE -ne 0) { throw 'Fetch failed' }
git merge-base --is-ancestor origin/main HEAD
if ($LASTEXITCODE -ne 0) { throw 'Remote main changed; review integration first' }
git push origin release/validated-update-20261101
if ($LASTEXITCODE -ne 0) { throw 'Push failed; do not force' }
gh pr create --repo est4ever/DemoDoctor --base main --head release/validated-update-20261101 --title 'Update local analysis workflow and saved diagnostic presentation' --body-file '<reviewed-PR-description-file>'
```

Review the public PR file list, history, checks, docs and demo assets. Merge only
with separate owner approval. Then verify the public README, notices, setup guide,
EP005 hypothesis/uncertainty and six replay assets at the approved commit. No
public FastAPI deployment is included. This procedure never touches private PR #3.
