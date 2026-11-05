# Case-study gate

*Every item must be ticked before a case study is merged or published. Copy this list into the case
study's pull request.*

**Job number:** DBPC-____-____

## Consent
- [ ] The customer agreed specifically to publication as an anonymised case study, separately from any
      consent to use footage, and the agreement is recorded in the private client record (date ____)
- [ ] The customer knows they can ask for it to be taken down

## Anonymisation
- [ ] No name, initials, handle, contact detail, address or location
- [ ] No serial numbers, diagnostic pass IDs, licence keys or order numbers
- [ ] No prices, costs, deposits or payment details
- [ ] Nothing that identifies the customer in combination (for example a rare setup plus a date and a public post)

## Evidence
- [ ] Every result is labelled **captured on the machine**, **not measured**, or **customer-reported**
- [ ] Every "captured" result traces to a dated item in the private evidence
- [ ] Nothing claims an improvement that wasn't measured before and after
- [ ] Photos (if any): serial labels blurred and image metadata removed

## Checks
- [ ] `python tools/audit_public.py` passes
- [ ] Reviewed by a second model or person, and the review is recorded
- [ ] Dylan approves the merge
- [ ] For a public repository: Dylan approves publication separately
