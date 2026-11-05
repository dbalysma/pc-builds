# QA sign-off

*Blank template. Copy it into the private client record before filling it in. Never commit a filled-in copy.*

**Job number:** DBPC-____-____ **Date:** ____

## Outcome rules
- **PASS:** the test completed and its result was seen and recorded.
- **FAIL:** the test completed and showed a problem.
- **INCOMPLETE:** the test was started but didn't finish, or its result wasn't seen.
- **BLOCKED:** the test couldn't be run (with the reason).

Never mark PASS from a progress percentage, from how long a test ran, from the machine booting, or
from a screenshot that wasn't checked. Each result needs an evidence reference in the private record
(photo, log or screen capture, with date and time).

## Checks
| Check | Tool | Result | Outcome | Evidence ref (private) |
|---|---|---|---|---|
| All installed components recognised | BIOS/UEFI | | | |
| Memory: total and configured speed | BIOS/UEFI or OS tool | | | |
| Memory test | e.g. vendor UEFI diagnostics, MemTest86 | | | |
| Other hardware diagnostics for the job | | | | |
| Operating system boots; no device errors | OS | | | |
| Idle temperatures | | | | |
| Load temperatures | | | | |
| Realistic workload, stated duration | the customer's own use case | | | |
| Repeat of each [pre-service baseline](pre-service-checklist.md) measurement | same tool as before | | | |

## Summary
- Everything PASS? yes / no
- Anything FAIL, INCOMPLETE or BLOCKED, and what happens next: ____
- Limitations the customer must be told at handover: ____

Signed off by: ____ **Date:** ____

A job with any FAIL, INCOMPLETE or BLOCKED item isn't handed over as complete. Either it's resolved, or
the customer agrees in writing to take it with that limitation stated.
