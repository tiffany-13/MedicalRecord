# D25 Prompt Candidate State Record

## 1. Identity and usability

| Field | Value |
|---|---|
| candidate_id | `v1.2-clinical-candidate` |
| base_version | `v1.1-clinical-candidate` (advisory-reviewed) |
| status | `candidate` |
| usability | `review-only` |
| char_count | 3204 |
| byte_count | 7980 |
| content_sha256 | `355c2daf233ec2188524ae9025501efe719ad7a17bc8579f650692c4b4fe89ea` |
| file_sha256 | `355c2daf233ec2188524ae9025501efe719ad7a17bc8579f650692c4b4fe89ea` |
| line_ending | `LF` |
| authoring_date | 2026-11-18 |
| consumer | reviewer, C, E |
| source_path | `prompts/candidates/system_v1_2_candidate.txt` |
| reviewer_ref | `documents/临床智录_D_临床审核记录.md` |

The candidate is addressed by path and digest only; no second copy is embedded here.

## 2. Measurement convention

- `char_count` = LF-normalised decoded text, trailing newlines stripped.
- `byte_count` = UTF-8 length of the same text.
- `content_sha256` = SHA-256 over LF bytes; `file_sha256` over checkout bytes.
- Draft: 1,248 / 3,082 / `5121dd88…`; v1.1 advisory: 2,856 / 7,028 / `acce17433…`; **v1.2 current: 3,204 / 7,980 / `355c2daf…`**, 0 CRLF.
- v1.1 is the reviewed advisory candidate; v1.2 is current and requires re-review.
- The 87-character evidence clarification is retained.
- OI-38 remains **LF canonical**.

## 3. Eleven checks

| # | Check | Result | Basis |
|---|---|---|---|
| 1 | Six blocks present | pass | six `#` markers, each once |
| 2 | Five medical red lines present | pass | `①`–`⑤`, each once |
| 3 | Five fields and field rules present | pass | all five names and field rules |
| 4 | JSON-only / no fences | pass | one legal JSON object required |
| 5 | Static text | pass | no per-case placeholders; no case data |
| 6 | Schema | pass | five fields; no sixth wrapper key |
| 7 | Measurement | pass | 3,204 / 7,980; hash recomputes |
| 8 | Length decision against 4,000 | pass | 3,204 ≤ 4,000; no compression |
| 9 | Usability / sign-off state | pass | review-only; `signoff_state=null` |
| 10 | Candidate overlap | pass | no ten-character overlap with `input.json` |
| 11 | Disclaimer completeness | pass | teaching-only, not diagnosis/treatment/orders, clinician review |

## 4. Disclaimer elements

The candidate contains: teaching competition scope; not a diagnosis/treatment/order basis; not direct clinical-record use; qualified clinician review required.

## 5. Disposition reference

Dispositions are recorded once in spec 5.10.2 and D26; this state record does not restate them. The advisory review of v1.1 is not approval of v1.2.

## 6. Changelog

`prompts/CHANGELOG.md` is the only prompt changelog. The v1.2 entry must record 3,204 / 7,980 / `355c2daf…` and the advisory revision source.

## 7. DP-1 = B, closed-by-decision 2026-11-18

- Decision: Option B — keep full clinical text; no compression.
- Ceiling: **4,000** loader sanity; the former internal cap is retired/suspended.
- Candidate: **3,204 characters**, accepted without compression.
- Usability: **review-only** — not runtime insertion, not freeze, not clinical approval.
- Reopening condition: a published organizer hard limit creates a superseding version state.

## 8. DP-6 gate kept and dates

- `signoff_state = null`; no named clinician signed v1.2.
- The 2026-11-15 review is a medical-logic review of v1.1, not clinical sign-off.
- Internal freeze target **2026-11-24**; fallback **2026-11-23**; organizer has no 11-17 node.
- Runtime remains `v1-draft` / `system_v1.txt`; candidate is not referenced by runtime.

## 9. Open items

| Item | State |
|---|---|
| OI-25 prompt length | closed-by-decision (DP-1 B) |
| OI-31 differential count | closed team-interim (2–3 target; zero allowed with reason) |
| OI-38 LF/CRLF | closed (LF canonical) |
| OI-51 v1.2 identity/re-review | open — current hash `355c2daf…`; D26 re-review required |
| OI-52 ST-1…ST-10 extension | closed — fixture and D27 now hold 10 cases |
| OI-53 documented-normal false positive | open — C validator fix required |
| OI-54 model object vs program array | open — D7/D29 update required |
| OI-26 parametric knowledge | pending organizer |
| OI-27 seed acceptance / OI-28 model ID | pending endpoint/organizer |

## 10. Status boundary

- Status is `candidate`; usability is `review-only`; no approval claimed.
- No runtime insertion, no freeze, no clinical approval; `prompts/system_v1.txt` unchanged.
- The candidate is not referenced by `main.py`, `src/`, or a runtime constant.