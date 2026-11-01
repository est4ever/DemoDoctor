# Demonstrated results and limits

| Recorded example | Demonstrated behavior | Boundary |
|---|---|---|
| SO-101 pilot | 2 checked claims; 609.01 px endpoint difference; 632/737 observed frames | 105 unobserved frames, missing tray mask; task uncertain |
| BotFails ep010, development | Video/SAM/timeline synchronization; measured opening at 44.50s supports an inferred release outside target | Holding and intent are not measurable; not a held-out timed-localization result |
| BotFails ep003 | 2D containment criterion met; saved application label is success | Plate orientation remains unverified; not proof of full physical-task completion |
| BotFails ep013 | End-state-supported failure | No invented timed failure event |
| BotFails ep005 | Muse-only false success, evidence-grounded abstention | Orientation cannot be established from 2D containment |
| BotFails ep006 | Evidence abstention | Insufficient end-state geometry |

Frozen held-out four-episode comparison: Muse-only 3/4 decisions correct (75%);
evidence-grounded 2/2 decisions correct with 50% coverage/50% abstention and zero
false definitive verdicts. This is a small workflow comparison with different
prompts/schemas, not statistical superiority and not a SAM-alone ablation.
The cost of conservative abstention must be shown alongside decision accuracy.

Replays reuse previous real SAM/Muse runs. Packaging and submission QA make no
paid inference calls. Upload dry runs skip inference and intentionally produce
no physical findings; they are not evidence of new-video analysis quality.

Original raw provider responses, request logs and full scientific caches are not
part of the distributable package. Public replay JSON preserves the evidence
needed for inspection but is not a substitute for the full research audit.
