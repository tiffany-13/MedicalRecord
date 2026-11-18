# D25 Prompt Candidate State Record

## 1. Identity and usability

| Field | Value |
|---|---|
| candidate_id | `v1.1-clinical-candidate` |
| base_version | `v1-draft` |
| status | `candidate` |
| usability | `review-only` |
| char_count | 2856 |
| byte_count | 7028 |
| content_sha256 | `acce17433cde615f344b043000d6faf6be7c2062ae7f7416fbaecc20258204aa` |
| file_sha256 | `acce17433cde615f344b043000d6faf6be7c2062ae7f7416fbaecc20258204aa` |
| line_ending | `LF` |
| authoring_date | 2026-11-18 |
| consumer | reviewer, C, E |
| source_path | `prompts/candidates/system_v1_1_candidate.txt` |
| reviewer_ref | `documents/临床智录_D_临床审核记录.md` |

The candidate is addressed by path and digest only; no second copy is embedded here.

## 2. Measurement convention

- `char_count` = LF-normalised decoded text, trailing newlines stripped.
- `byte_count` = UTF-8 length of the same text.
- `content_sha256` = SHA-256 over LF bytes; `file_sha256` over checkout bytes.
- Draft: 1,248 chars / 3,082 bytes / content `5121dd88…` / file `b78e3026…` / 25 CRLF.
- Candidate M1: 2,856 / 7,028 / `acce17433…` / 0 CRLF / 58 LF.
- Candidate M0 reconstruction: 2,757 / 6,853 / `4a4e969d…`; delta 99 = 12 heading-prefix chars + 87-char evidence clarification.
- OI-38 is **closed-by-decision 2026-11-18: LF is the canonical internal convention**; the retired internal cap and the LF/CRLF representation are not organizer rules.

## 3. Eleven checks

| # | Check | Result | Basis |
|---|---|---|---|
| 1 | Six blocks present | pass | `# 角色` / `# 资料边界` / `# 输出内容` / `# 事实与推断` / `# 输出格式` / `# 五条医学红线`, each once |
| 2 | Five medical red lines present | pass | `①`–`⑤`, each once |
| 3 | Five fields and field rules present | pass | all five names; occurrence counts 4/4/4/7/6; presence invariant |
| 4 | JSON-only / no fences | pass | one legal JSON object required; Markdown fences and prose forbidden |
| 5 | Static text | pass | no `{case_id}`, `{record_cutoff}`, `{sources}`, `$` placeholders; no case data |
| 6 | Schema | pass | no sixth/renamed field; no new wrapper key; no denylist token |
| 7 | Measurement | pass | 2,856 / 7,028; hash recomputes |
| 8 | Length decision against 4,000 | pass | 2,856 ≤ 4,000; former internal cap retired; no compression |
| 9 | Usability / sign-off state | pass | `review-only`; `signoff_state=null`; not insertion, not freeze, not approval |
| 10 | Candidate overlap | pass | no shared ten-character run with `input.json` sources |
| 11 | Disclaimer completeness | pass | teaching scope; not diagnosis, treatment, orders, direct clinical use; clinician review |

## 4. Disclaimer elements

The candidate contains: teaching competition draft scope; not a diagnosis/treatment/order basis; not direct clinical-record use; qualified clinician review required. All five classes are present and marked `pass`.

## 5. Disposition reference

Dispositions are recorded once in spec 5.10.2 and D26; this state record does not restate them. Every reviewer item appears exactly once across D25/D26.

## 6. State record versus changelog

`prompts/CHANGELOG.md` is the only prompt changelog. The candidate entry lives there (Task 12.1); D25 is a state record. The candidate entry is still missing from the changelog and must record 2,856 / 7,028 / `acce17433…`.

## 7. DP-1 = B, closed-by-decision 2026-11-18

- Decision: Option B — keep the full clinical text; no compression.
- Authority: team decision, not an organizer answer.
- Recorded: ceiling **4,000 characters** (loader sanity); the former internal cap is retired/dropped.
- Candidate: **2,856 characters**, accepted without compression; no red-line clause removed or weakened.
- Usability: **review-only** — usable for clinical review, **not for runtime insertion**, not for freeze, not for clinical approval.
- DP-1 acceptance does not satisfy DP-6.
- Reopening condition: a published organizer hard limit creates a new superseding version state; the hard-limit branch is documented and not triggered.

## 8. DP-6 gate kept and dates

- `signoff_state = null`; no named clinician has signed this exact hash.
- The 2026-11-15 review is a medical-logic review, not clinical sign-off.
- Internal freeze target: **2026-11-24**; fallback: **2026-11-23**.
- The organizer has no 2026-11-17 node; anchors are 11-14 / 11-19 / 11-26.
- Runtime remains `v1-draft` / `system_v1.txt`; candidate is not referenced by runtime.
- No freeze/approval claim is made while DP-6 is unsigned.

## 9. Organizer confirmations

| Item | State | Interim rule |
|---|---|---|
| OI-25 prompt length | closed-by-decision (DP-1 B) | 4,000 sanity ceiling; 2,856 accepted; no compression |
| OI-26 parametric medical knowledge | pending organizer | facts only from case sources; general reasoning marked inference, no source_id |
| OI-31 differential count | closed team-interim | 2–3 target; fewer only with explicit insufficiency; padding prohibited; ST-8 unchanged |
| OI-38 LF/CRLF | closed-by-decision | LF canonical; hash over LF bytes |
| OI-27 seed acceptance | endpoint pending | no determinism claim |
| OI-28 exact model identifier | pending | `qwen3.8 27b` placeholder only |

## 10. Status boundary

- Status is `candidate`; usability is `review-only`; no approval is claimed.
- No runtime insertion, no freeze, no clinical approval; no prompt edit was made to `prompts/system_v1.txt`.
- The candidate is not referenced by `main.py`, `src/`, or any runtime constant.