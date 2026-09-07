# Design and reliability review — 0.2.0

The first public version had a real Python implementation, but its presentation obscured the most useful evidence. The page emphasized slogans, personality-based policy names, and a static workflow diagram. The duplicate shipment was easy to miss.

Three independent AI reviewers assessed the design and language, Python capture/replay boundaries, and browser lifecycle behavior. The implementation was revised in response, then the design reviewer inspected built desktop and 390px mobile screenshots. This is a documented review process, not independent certification or user research.

## What changed

- The incident, run action, and observed outcome lead the interface. A default failing run says **2 shipments for 1 order**.
- Policy names describe code behavior: **No retries**, **Unchecked retries**, and **Validated retries**.
- The trace shows each explicit commit beside the call that produced it, including commits before a lost acknowledgement.
- Results distinguish requested shipments, committed shipments, confirmation, recorded calls, refused attempts, and simulated time.
- Recorded examples and executed results remain labeled. Changed settings do not silently relabel old evidence. Exports and shared settings describe the displayed result.
- Code examples reproduce the displayed configuration locally. Scenario-specific checks and trace-level CLI checks are distinguished.
- Mobile uses stacked comparison rows. Decorative diagrams, ungrounded severity labels, and repeated promotional slogans were removed.

## Qualitative design judgment

The reviewer used six criteria: immediate comprehension, evidence hierarchy, copy precision, visual specificity, interaction/readability, and honesty/traceability. The first version scored 2/5 on the first four, 3/5 on interaction, and 4/5 on traceability. The revised version scored 4/5 on all six: clear and purpose-built, with no additional blocking design issue identified in the assessed tasks.

These judgments informed iteration. They are not a public product score and do not replace functional or accessibility checks. Screenshots came from the built application; the final automated contrast and no-JavaScript checks followed the visual review.

## Reliability findings retained as regressions

| Finding | Correction |
| --- | --- |
| A failed dynamic import remained cached inside the Python worker, defeating Retry. | Dispose of failed workers and start a fresh worker on the next run. |
| Cancelled or timed-out work could leave lifecycle state ambiguous. | Bound startup to 90 seconds, clear pending requests, and ignore stale results with an attempt token. |
| Home navigation could retain edited or previously shared settings. | Start a fresh experiment when returning Home; preserve query-driven initialization and test browser history. |
| Deferred clipboard permission could overwrite a later navigation. | Update the settings URL before awaiting clipboard access; test delayed completion after navigation. |
| Mobile failure feedback was below the visible area. | Put retry feedback beside the run controls and focus the actionable error. |
| Replacement configurations and deeply nested outputs could make reports unavailable. | Validate replacement capture before execution and reserve the serialized report's nesting overhead. |
| Imported evidence could declare a probability-zero fault as exercised. | Reject impossible fault outcomes and replacement/output inconsistencies. |

CI tests these behaviors against the real Python worker and fresh distribution installations. See [validation.md](validation.md) for scope and limits and the [CI history](https://github.com/shi1720/toolstorm/actions/workflows/ci.yml) for run evidence.
