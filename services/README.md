# Service workflow

How a PC build, upgrade, repair or diagnostics job runs, from first message to handover. The same
steps for every job, so nothing is skipped and every result can be traced to evidence.

```
Enquiry ─▶ Quote ─▶ Job sheet ─▶ Pre-service checks ─▶ Service ─▶ QA sign-off ─▶ Handover ─▶ (optional) Case study
            (private)
```

| Step | Template | What it settles |
|---|---|---|
| 1. Enquiry | [enquiry-intake.md](templates/enquiry-intake.md) | What the customer wants, on which machine, by when |
| 2. Quote | *(private quote calculator, not in this repository)* | Price, deposit and terms, agreed in writing |
| 3. Job sheet | [job-sheet.md](templates/job-sheet.md) | Agreed scope, authorisation, backups and consent |
| 4. Pre-service checks | [pre-service-checklist.md](templates/pre-service-checklist.md) | What is actually installed, and how it performs, before anything changes |
| 5. Service | [hardware-service-checklist.md](templates/hardware-service-checklist.md) | Safe, clean, correctly seated and connected work |
| 6. QA sign-off | [qa-signoff.md](templates/qa-signoff.md) | Measured results, each marked PASS, FAIL, INCOMPLETE or BLOCKED |
| 7. Handover | [handover.md](templates/handover.md) | What was done, what it shows, what it doesn't, and what's next |
| 8. Case study | [case-study-gate.md](templates/case-study-gate.md) | Whether a job may be published, and how it is anonymised |

## Where things live

| In this repository | In the private client record, never here |
|---|---|
| These blank templates | Every filled-in copy |
| Anonymised case studies that passed the gate | Customer names, contact details, addresses |
| | Quotes, prices, costs, deposits, invoices, payments |
| | Serial numbers, diagnostic pass IDs, licence keys |
| | Photos, video and test logs, unredacted |
| | Consent records |

Jobs are numbered `DBPC-YYYY-NNN` (for example `DBPC-2026-001`). The number links the anonymised case
study to the private record without identifying anyone.

## Rules that apply to every job

- **Inspect before planning.** Plans are based on what is installed, not on what the customer or an
  order record says is installed.
- **Measure before and after.** A change can only be called an improvement if the same measurement was
  taken both times.
- **Never infer a pass.** A result is PASS only when the test completed and its result was seen and
  recorded. Not from a progress bar, not from how long it ran, not from the machine booting, and not
  from a screenshot that wasn't checked.
- **Record what wasn't done.** Untested items are marked INCOMPLETE or BLOCKED, with the reason.
- **Never ask for the customer's password.** Use BIOS/UEFI tools, or have the customer sign in.
- **Consent is specific.** Consent to use footage is not consent to publish a case study. Each is
  asked for and recorded separately.
