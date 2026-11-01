# Proposed publication: new repository, explicit approval required

This runbook is for **only this separate release directory**. Do not execute it
from an existing development worktree. The original private repository is
`est4ever/DemoDoctor_Predevelopment`; PR #3 stays open and unmerged. Its history
and remote must not be replaced or connected to the new public repository.

The new repository must be **est4ever/DemoDoctor**, never DemoDoctor-Hackathon.
No GitHub repository creation or push occurred during snapshot preparation.

After the owner approves the exact release commit, rights/privacy disclosures,
and public GitHub creation/push, run in Windows PowerShell:

```powershell
Set-Location '<path-to-the-separate-release-checkout>'
$ErrorActionPreference = 'Stop'
$approvedSha = '<OWNER-APPROVED-INITIAL-RELEASE-SHA>'
if ($approvedSha -notmatch '^[0-9a-f]{40}$') { throw 'Set approved full SHA' }
if ((git branch --show-current) -ne 'main') { throw 'Wrong branch' }
if ((git rev-parse HEAD).Trim() -ne $approvedSha) { throw 'Unapproved commit' }
if (git status --porcelain) { throw 'Working tree is not clean' }
if ((git rev-list --count HEAD).Trim() -ne '1') { throw 'Unexpected history' }
if (git remote) { throw 'Unexpected existing remote; inspect, do not overwrite' }
git fsck --full
if ($LASTEXITCODE -ne 0) { throw 'Local repository integrity failed' }

# Creation must succeed as a NEW repository; do not use a redirect or rename.
gh repo create est4ever/DemoDoctor --public --source . --remote origin
if ($LASTEXITCODE -ne 0) { throw 'Creation failed; do not reuse/alter another repo' }
$newRepo = gh repo view est4ever/DemoDoctor --json nameWithOwner,visibility,id | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $newRepo.nameWithOwner -ne 'est4ever/DemoDoctor' -or
    $newRepo.visibility -ne 'PUBLIC' -or $newRepo.id -eq 'R_kgDOVWVH_w') {
  throw 'New public repository identity was not verified'
}
if ((git remote get-url origin).Trim() -ne 'https://github.com/est4ever/DemoDoctor.git') {
  throw 'Unexpected new-release remote'
}
git -c push.followTags=false push --no-follow-tags -u origin main
if ($LASTEXITCODE -ne 0) { throw 'Push failed; do not force' }
gh repo edit est4ever/DemoDoctor --default-branch main
if ($LASTEXITCODE -ne 0) { throw 'Default-branch verification required' }
gh repo view est4ever/DemoDoctor --json nameWithOwner,url,visibility,defaultBranchRef
git ls-remote origin refs/heads/main
```

The old name may currently redirect to the private repository until the new
repository is created. A redirect is not proof that the new repository exists or
that the name is available; creation must return a distinct canonical identity.
If unavailable, stop; do not invent a different name, delete/rename the private
repository, merge PR #3, force push or publish its history.

After push, verify exact remote SHA and logged-out README/LICENSE/NOTICE/source
archive access. Download the public source into another directory, install
dependencies explicitly, and verify PILOT plus EP010/EP005/EP003/EP013/EP006 with
no credentials. Record actual public URLs and the new initial SHA. A GitHub page
alone is not a demonstration playback check. No tag/release/deployment is included.

Before final hackathon submission, confirm the accepted-participant guide/form,
Indie new-work eligibility for the October 24 foundation, dataset/model/audio
permissions, video host and public link. Upload the unchanged 180-second video
only after separate approval. Obtain final-submit approval and retain the receipt
before November 4, 2026, 9 PM Eastern (November 5, 02:00 UTC).
