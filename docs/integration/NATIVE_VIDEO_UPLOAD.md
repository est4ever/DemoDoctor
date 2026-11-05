# Experimental native-video analysis in Import Footage

This is the normal React investigation workstation, not a separate research viewer. It adds a **single-camera native Meta Muse Spark 1.3** proposal path alongside the existing SAM/Fireworks workflow. It makes no SAM calls. New uploads supply no historical masks, rack template, reference answers or known event intervals.

## Try the complete interface without provider calls

After following the README installation instructions, activate the project's Python environment and run from the repository root:

```powershell
npm run build --prefix web
python scripts/serve-placement-candidate.py --port 18902 --mock-native
```

Open **http://127.0.0.1:18902/#upload**. Stop this foreground server with **Ctrl+C**. Use an unused port if another server is already running; do not kill unrelated processes. The ordinary DemoDoctor launcher remains offline by default.

1. Find **Experimental Native Video Analysis** and confirm **OFFLINE MOCK**.
2. Select your own compatible silent MP4: one video stream, at most 100 MiB, 90 seconds, 1920x1080 pixels, with original timestamps starting at zero. Unsupported inputs are rejected, not silently truncated or stripped of audio.
3. Enter the robot task and intended end state. Click **Prepare native video plan**. Preparation makes no provider calls.
4. Review the complete frame count, time range, original and upload hashes, one upload plus one model request, and **$1.33 simulated reservation**. Review and explicitly check all six controls.
5. Click **Run offline mock native analysis**. These are test responses over your real footage, not genuine visual reasoning. They must not be used as scientific findings.
6. In **Findings**, click a proposal's time interval, expand **Source frames, masks and measurement limitations**, and inspect an original frame.
7. Refresh, or return to **Import Footage → Recent Investigations → Open Investigation**. Saved reopening makes no additional upload or model request.

## Real execution requires separate operator enablement and user approval

The real Meta client is connected, but a fresh genuine run through this new upload UI was **not executed during product acceptance**. Acceptance used the actual SDK with an offline MockTransport. Previously completed genuine BF010 results were tested as historical replay, not new inference.

Configure `MODEL_API_KEY` only in the backend process environment using your existing secure credential handling. Do not place secrets in React, browser storage, command arguments, screenshots or Git. This path does not use Fireworks. Have an existing, reconciled spending ledger whose owner-approved limits admit the plan. The launcher does not create or raise real limits.

Only after review and separate authorization, use the following instead of mock mode (replace the ledger path with your existing private ledger):

```powershell
python scripts/serve-placement-candidate.py --port 18902 --native-live --reviewed-implementation 742e85a146b33416fd73e8d983b7e9e317be7f8af239ad6a686c930ae7e4c12c --ledger 'C:\private\budget_ledger.json'
```

Startup makes no inference request. In the UI, verify **Fresh native-video path**, check that no execution blockers are reported, prepare your exact video/task plan, attest to current account credits, exclusive use, reconciled requests, data-processing permission and billing uncertainty, then approve **Run authorized native video analysis** for the exact plan and reservation yourself. Presence of a key does not establish account funding or provider access.

The reviewed implementation hash must match. Offline mode, missing credentials, insufficient limits, unsettled requests, an active execution lock or missing approval block execution. There is one upload and one full-video model request per attempt, no automatic retry, no fallback or extra SAM operation. Failures preserve operation records and stop; reconcile uncertain execution before any separately authorized new attempt.

The **$1.33 reservation is an application admission limit, not a provider-enforced billing guarantee**. Admission also respects the existing total budget and the worker's $4.50 experiment ceiling. The ordinary $1.00 per-run cap intentionally blocks this plan; changing it requires separate owner authorization. No payment or provider execution is authorized by this documentation.

## Scientific scope and saved genuine results

Events on new uploads remain **UNVERIFIED proposals**, with original-frame citations and an **Uncertain** task outcome. A source-linked image is not proof of drop, grasp, release, physical cause or task completion. There is no general object/destination geometry verifier on arbitrary uploads. Proposed intervals are not independently verified failure-onset times. Empty detections do not mean Success.

The six bundled replays remain separate. BF010's historical genuine native-video job is **not bundled**, so a fresh clone does not invent that Recent Investigations entry. Owners of a legitimate authenticated local saved job may recover a copy with `scripts/import-native-saved.py --source <saved-job-directory> --source-sha256 <original-video-sha256> --permissions-and-privacy-reviewed`. The helper validates the existing seal, source hash and genuine execution receipts, refuses overwrite, and reseals a local copy. It makes no inference request. Keep the source store's authority key in its original location for validation; do not publish keys, raw jobs or ledgers.

The existing [portable assisted-placement setup](PORTABLE_PLACEMENT_SETUP.md) is optional and distinct: it enables registered original-video measurements, not general native-video verification. Model requests, saved original responses and assisted source measurements retain their separate labels. This is a localhost prototype, not an authenticated Internet-facing inference service.
