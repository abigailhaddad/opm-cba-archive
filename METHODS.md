# Methods and full counts

The counts and tables below describe the **2026-11-01 pull**, and this file is not regenerated. From then on the weekly refresh keeps the dataset current and rewrites `data/SUMMARY.md` each time it publishes; the termination-flag sources and rules below are still the ones a person maintains by hand.

A local archive of OPM's public database of federal collective bargaining agreements (CBAs), pulled on
**2026-11-01** (listing fetched 2026-11-01 23:59:22 UTC, i.e. 6:59 PM ET; files downloaded 2026-11-01 23:59:51 UTC to 2026-11-02 00:32:36 UTC (6:59-7:32 PM ET)), with
a first-pass flag for agreements that appear to have been terminated under Executive Orders 14251 and 14343.


## Counts

| Step | Count | Notes |
|---|---:|---|
| Records in the API listing | 1,248 | `rowCount` 1,248; 1,248 distinct ids and file URLs; all PDFs. 889 are DoD. |
| Download attempted | 1,248 | |
| Downloaded OK | 1,243 | All 1,243 start with `%PDF-`; all 1,243 byte counts are within 1% of the listing's `fileSize`. |
| Download failed | 5 | All HTTP 404, retried once with curl a few minutes later, still 404. All five are National Guard Bureau records (Alaska ACT 84, Georgia ACT, Arizona ACT 71, California LIUNA 1776, Indiana ACT 72). The listing points to files OPM no longer serves. |
| Unique files (SHA-256) | 1,240 | 3 pairs of records share an identical file (see below). |
| Bytes on disk | 1,861,818,204 | 1,856,943,663 unique. Under the 3 GB cap. |
| Pages (pdfinfo) | 93,948 | across the 1,243 files |
| Text extracted (`text`) | 1,222 | |
| Scanned, no text (`no_text`) | 11 | 0 extractable words. Need OCR. |
| Mostly scanned (`low_text`) | 7 | 1-24 words per page; the next file up has 66, so the cutoff of 50 sits in a clear gap. |
| Submission form only | 3 | A one-page OPM "CBA Submission Form" was posted instead of the agreement. |
| Not processed | 5 | the 5 failed downloads |

1,222 + 11 + 7 + 3 + 5 = 1,248. pdftotext returned 0 for every file; 10 files printed font or syntax
warnings but all 10 produced text. 7 files are flagged encrypted (owner-password only); all 7 still extracted.

Duplicate files (same SHA-256, two listing records each):
- `10530990` and `f271226d`: Army MEDCOM 410th CSB, LIUNA Local 28, same agreement uploaded twice under two file names.
- `c8950c3f` and `8ab9eef7`: Defense Commissary Agency, IFPTE Local 4, same file name and content (also both scanned, no text).
- `4aaa2245` and `285e45d1`: Arkansas National Guard, ACT Chapters 131 and 117, one file listed under both chapters.

**Second check of the downloads.** 14 files (10 random, the smallest, the largest, and both members of one
duplicate pair) were downloaded again with curl and hashed. All 14 matched both the logged hash and the file
on disk (`data/download_recheck_sample.txt`). Every file's size was also checked against the listing's own
size field (all within 1%).

## Termination findings

**Short version.** Of the 1,248 listed agreements, 21 are tied to a termination by a source that names
the agency and the union: 16 by an agency document or court record, 4 by press reports only, and 1 (Bureau of
Prisons) that was terminated and then restored by court order. Another 700 are `inferred`: almost all (686)
are DoD agreements swept in by DoD's April 2026 order to end "all collective bargaining agreements to which
the department is a party," with no carve-out visible in the listing. 110 are probably shielded by a court
injunction (current status unverified). These are flags for follow-up, not findings.

| Flag | DoD | Non-DoD | Total |
|---|---:|---:|---:|
| `confirmed` (agency doc or court record names agency + union) | 2 | 14 | 16 |
| `confirmed_secondary` (press names agency + union) | 0 | 4 | 4 |
| `confirmed_then_reinstated` | 0 | 1 | 1 |
| `inferred` | 686 | 14 | 700 |
| `uncertain_injunction` | 105 | 5 | 110 |
| `uncertain_certification` | 14 | 0 | 14 |
| `not_flagged_exempt_psf` (police/fire indicator) | 82 | 0 | 82 |
| `not_flagged_no_source_found` (covered by the EOs, no source found) | 0 | 114 | 114 |
| `not_flagged_agency_not_named` | 0 | 207 | 207 |
| **Total** | **889** | **359** | **1,248** |

EO coverage from listing fields alone: 1,003 `covered`, 38 `partly_or_unclear`, 207 `not_named`.

**Confirmed (21 records).** Source ids refer to `data/terminations/sources.csv`.

| Record | Agency / unit | Union | Terminated | Source |
|---|---|---|---|---|
| cb2c7ad6 | VA (master) | AFGE | Aug 6 2025; again Mar 26 2026 | S20, S01 (VA memo). Contested: court reinstatements, 1st Cir. stay Oct 2 2026 (S10) |
| f4600eb5 | VA (master) | NNOC/NNU | Aug 6 2025 | S20 (VA press release) |
| 4c76718f | VA (master) | NFFE | Aug 6 2025 | S20 |
| f5d2eb42 | VA (master) | NAGE | Aug 6 2025 | S20 |
| c9fce5ab | DoD, DFAS | AFGE Council 171 | Apr 17 2026 | S02 (DFAS memo: "all" AFGE-DFAS CBAs) |
| 9469fd7a | DoD, DFAS (listing says "AFMC") | AFGE | Apr 17 2026 | S02; the PDF is the "Master Collective Bargaining Agreement AFGE & DFAS" |
| b682407a | Treasury Departmental Offices | NTEU (Ch. 297) | Feb 24 2026 | S13 (agency notice in court exhibit) |
| bd4e0bdc | Bureau of the Fiscal Service | NTEU | Feb 25 2026 | S13 |
| 2440e6e1 | IRS | NTEU (national) | Feb 27 2026 | S13 |
| 7d0f2ce4 | IRS Office of Chief Counsel | NTEU | Feb 27 2026 | S13 |
| 7d6d0651 | OCC | NTEU | Mar 3 2026 | S13 |
| 7969b75e | TTB | NTEU | Mar 9 2026 | S13 |
| b85e43e4 | DOE Headquarters | NTEU Ch. 213 and 228 | Mar 6 2026 | S13 |
| 557d782a | EPA | NTEU | Mar 10 2026 | S13 |
| bcd9cffc | EPA | AFGE Council 238 | Aug 8 2025 | S18 (union complaint, an allegation), S19 (press quoting EPA email) |
| dfb82a28 | USDA APHIS | NAAE | Aug 12 2025 | S21 (APHIS notice quoted in court complaint) |
| 2328010f | FEMA | AFGE Local 4060 | Aug 2025 | press only (S23) |
| 11116e53 | USCIS | AFGE Council 119 | Aug 8 2025 | press only (S24) |
| 4e08b08c | EPA Narragansett | NAGE R1-240 | Aug 2025 | press only (S19, quoting EPA email) |
| f8f86227 | EPA Gulf Breeze | NAIL Local 9 | Aug 2025 | press only (S19) |
| cbee84d4 | Bureau of Prisons | AFGE Council of Prison Locals | Sept 25 2025; reinstated by court Sept 29 2026; re-terminated Oct 7 2026; re-termination declared VOID Oct 16 2026 | S14-S17 |

Several of the confirmed records are older versions of the agreement that was actually terminated. For
example, the listed IRS-NTEU file expired in 2021, while the notice terminates the 2022 National Agreement.
The agency and union match, but the specific document OPM posts has been superseded. Each such case is noted in
`termination_basis`.

**DoD (889 records).** The Apr 9 2026 memo (S03) could not be retrieved: media.defense.gov returned HTTP 403
to both curl and WebFetch. What it says comes from GovExec's quotes (S11) and the DFAS memo that cites it
(S02). A replacement memo dated Aug 24 2026 (S04) is known only from one advocacy newsletter. Rules applied, in
order:
1. Police/firefighter/guard indicator in union or unit name (IAFF, FOP, "police", "force protection", etc.) →
   `not_flagged_exempt_psf` (82). The memo excludes their "local employing offices".
2. Union and local listed in the AFL-CIO v. Trump preliminary injunction (S12, Oct 1 2025: 21 IFPTE locals,
   AFT Overseas Federation of Teachers, metal trades councils, IOMM&P, MEBA, UA Local 100, 4 IBEW locals, 13 IAM
   locals), or FEA (separate injunction per S11) → `uncertain_injunction` (105). One IFPTE local (386) is not on
   the PI list but IFPTE says all its locals were protected; it is flagged with a note.
3. Location possibly inside one of the 4 subdivisions certified at 90 FR 17052 (S05: Air Force Test Center,
   Air Force Sustainment Center, Fleet Readiness Center Southeast, Letterkenny Munition Center; FWS trades
   only) → `uncertain_certification` (14). Base names such as Edwards, Tinker, Hill and Robins were treated as
   candidates. Letterkenny **Army Depot** records were deliberately not matched: the depot is a different
   subdivision from Letterkenny **Munition Center**.
4. Everything else → `inferred` (686). The 2 DFAS-AFGE records are hand-confirmed (S02) and are not in this count.

**Non-DoD inferred (14).** 4 VA local agreements (LIUNA 1322 Providence ×2, WFNHP 5032 Milwaukee, UNAC/UHCP
Loma Linda). These were protected by VA's Apr 2025 suspension order (S06), which VA says it rescinded Nov 13
2025, when it "terminated all collective bargaining agreements held with its local unions" (S01). Also 8 CDC/FDA
agreements: press (S25) says unions were "de-recognized" at CDC and FDA but doesn't name these locals. Plus
FSIS-AFGE (press says FSIS cancelled contracts, agreement not named) and EPA Atlanta NAGE (press quotes "NAGE
R4", read here as EPA Region 4).

**Non-DoD under injunction (5).** EPA IFPTE Local 20 (listed as "Engineers and Scientists of CA"), 2 Coast
Guard metal trades councils, Coast Guard IAM Local 2203, and DOE OPEIU Local 2001 are all named in the S12
injunction. No termination notice was found for the Coast Guard or DOE units.

**Searched and not found** (does not mean no termination happened): Commerce ITA, USPTO/POPA, NOAA NWS/NWSEO,
NESDIS, State, USAID, NRC, NSF, USITC, GSA, ICE, CISA, BOEM, BSEE, Bureau of Reclamation hydropower units,
other HHS units, DOJ components other than BOP. NASA sent a Sept 2025 notice of *intent* to terminate (S26),
and GovExec reported in Mar 2026 that NASA had not formally terminated the IFPTE contract (S27). NASA's 10
records are `not_flagged_no_source_found`. A paywalled Bloomberg headline says DHS ended its AFGE Local 918
contract (FPS/CISA) in Aug 2025. It was not read, so listing record 42983732 (NPPD-AFGE 918) is not flagged.
The NTEU notice to BLM was to Chapter 341 and ended two MOUs, not a term agreement. The listing's BLM-NTEU
record is Chapter 342, so it was **not** matched.

**OPM's role.** OPM's Mar 27 2025 guidance (S28) was followed by an FAQ telling agencies not to terminate
CBAs until litigation ended (S29). In Sept 2025 OPM said to hold off on NTEU units, according to BOP's quote of
it in S16. On Feb 12 2026 (revised Feb 17) OPM told covered agencies to terminate and issued a template notice
(S30, S31). The S30 memo requires each covered agency to report the status of every CBA to OPM monthly on an
attached spreadsheet "until all termination notices are executed and reported." That spreadsheet, or OPM's
compilation of the reports, would be the authoritative list. It was not found publicly.

## What is where

| Path | What |
|---|---|
| `data/raw/cba_listing_20261101T235922Z.json` | Raw API response, unmodified (1,248 records). Response headers alongside. |
| `data/raw/cba_landing_page_20261101.html` | The public landing page as served that evening. |
| `data/files/<id>.pdf` | Every agreement file, named by the listing record `id`. **Gitignored** (~1.86 GB). |
| `data/text/<id>.txt` | `pdftotext -layout` output. Gitignored. |
| `data/download_log.jsonl` | One line per download attempt: URL, time, HTTP status, bytes, SHA-256, first 5 bytes. |
| `data/download_recheck_sample.txt` | Result of re-downloading a 14-file sample and comparing hashes. |
| `data/extract_log.jsonl` | One line per file: pdfinfo page count, encryption, pdftotext return code, word and character counts. |
| `data/cba_agreements.csv` | The main table: one row per listing record, with listing fields, hash, pages, text status, EO coverage and termination flag. All fields quoted as text. |
| `data/terminations/sources.csv` | Every termination-related source used, with URL, local copy, hash, and what it says. |
| `data/terminations/record_flags.csv` | Hand-made matches of specific listing records to specific sources (the only route to `confirmed`). |
| `data/terminations/*.pdf, *.txt` | Local copies of the source documents that could be downloaded, and their text. |
| `data/terminations/agent_findings.json`, `agent_sources/` | Raw notes and documents from a research pass on non-DoD agencies (see caveats). |
| `scripts/` | `download.py`, `extract.py`, `coverage.py` (EO coverage rules), `build_table.py`. |

To rebuild the table: `python3 -I scripts/build_table.py`. To resume an interrupted download:
`python3 -I scripts/download.py data/raw/cba_listing_20261101T235922Z.json data/files data/download_log.jsonl <deadline-epoch>`
(it skips ids already logged as ok).

## Method

**Listing.** `POST https://www.opm.gov/cba/api/documents/published` with body
`{"recsPerPage":5000,"currentPage":1}`. This is the undocumented API behind the OPM page. It returned
`rowCount` 1,248, `pageCount` 1, and 1,248 results with 1,248 distinct `id`s and 1,248 distinct `fileUrl`s.
All 1,248 have `documentType` 1 and a `.pdf` file name. A listing saved earlier the same day by a previous
session had the same 1,248 ids with identical field values.

**Download.** One request at a time, at least 1 second apart, with a User-Agent that includes a contact
address. File URLs contain spaces, which were percent-encoded. Each file was written under its record id,
hashed with SHA-256, and checked for the `%PDF-` header. As a second check, the downloaded byte count was
compared with the listing's own `fileSize` field (e.g. "1.76 MB", binary units) for every file.

**Text.** `pdftotext -layout` (poppler) per file, `pdfinfo` for page counts. `text_status` is:
`text` (at least 50 words of 3+ letters per page on average), `low_text` (under 50 per page: mostly scanned,
maybe a typed cover), `no_text` (nothing extractable: scanned image only, needs OCR),
`submission_form_only` (a 1-2 page OPM "CBA Submission Form" rather than an agreement), or `error`.
No OCR was run.

**EO coverage** (`eo_coverage`, `scripts/coverage.py`). A rule set that reads the agency and sub-agency
fields and checks them against the agencies and subdivisions named in EO 14251 s.1-4 (as amended by EO 14343).
`covered` means the listing's agency/subdivision is named in the orders. `partly_or_unclear` means only part
of it is named (e.g. NIH, where only NIAID is named; Bureau of Reclamation, where only hydropower units are;
USPTO, where only the patents side is) or the listing doesn't say enough. `not_named` means the listing's
agency/subdivision isn't in the orders. This is coverage, not termination: being covered does not mean the
agency actually terminated the agreement.

**Termination flag** (`termination_flag`):

- `confirmed`: a source document names this agency **and** this union or bargaining unit (or this specific
  agreement) as terminated. Every one is a hand match in `record_flags.csv` with the reason written out.
- `inferred`: a source says the agency terminated all agreements in a category (e.g. "all collective
  bargaining agreements to which the department is a party", or "all ... agreements held with its national
  unions"), this record falls in that category, and nothing in the listing fields points to a carve-out. The
  union or unit is not named in the source.
- `uncertain_injunction`: the agency's termination order exists, but the union was reported to be protected by
  a court order at the time. Current status not verified.
- `uncertain_certification`: DoD record at a location that may belong to one of the four subdivisions DoD
  certified as staying under the labor statute (Federal Wage System trades only).
- `not_flagged_exempt_psf`: DoD record with a police, firefighter or security-guard indicator in the union or
  unit name. The EO and DoD memos carve out "the immediate, local employing offices" of these employees.
- `not_flagged_no_source_found`: within EO coverage, but no termination source naming it was found in this
  pass.
- `not_flagged_agency_not_named`: agency/subdivision not named in the orders.

## Caveats

- **As-of.** Listing pulled 2026-11-01 6:59 PM ET, files 6:59-7:32 PM ET. OPM's database is what agencies
  submitted under EO 13836. Many records are old (350 list a 2020 expiration date) and the database is not a
  list of agreements currently in force. A termination applies to whatever agreement was in effect, which may
  not be the posted version.
- **"Inferred" is not a finding.** For DoD it rests on a memo we could not retrieve, applied through
  listing fields that don't say who is in each bargaining unit. A wall-to-wall unit at a base may include
  firefighters or police whose offices are carved out. Federal Wage System trades at certified subdivisions are
  carved out too. National Guard dual-status technicians (ACT, 68 records) were treated like other DoD units,
  but no source was found specifically about Guard technician contracts.
- **Court status moves fast.** The injunction-related flags reflect orders as of the dates cited. Not checked:
  the outcome of the appeal of S12, the status of the FEA injunction, the AFGE/NFFE v. DoD case (D. Md.
  1:26-cv-02653, PI motion filed July 2026), anything after Oct 16 2026 in the BOP case, and the current state of
  the VA-AFGE dispute.
- **Matching rules** (`scripts/coverage.py`, `scripts/build_table.py`) read free-text fields that are
  inconsistent. For example, the same component appears as "Department of Army", "DEPARTMENT OF ARMY",
  "Army", and with trailing spaces. The DFAS master agreement is listed under "AFMC". The Federal Grain
  Inspection Service is listed under APHIS. The police/fire pattern intentionally does not use the bare word
  "guard", because that would match "National Guard" (~95 records). A looser search for
  police/fire/security/protection words among unflagged rows turned up 11 more rows, reviewed by hand: e.g.
  IBFO (Firemen and Oilers, a boiler trade), FWS Office of Law Enforcement (Interior, not covered), and NPPD AFGE
  918 (likely Federal Protective Service officers; left unflagged with a note here).
- **Sources not read in full.** The DoD memos (S03, S04) and a few press items reached through a summarizer
  (S19, S22-S25, S27). Their quotes should be checked against the live pages before use. Six quotes in the
  research notes come from OCR of image pages. The S12 order's DoD unit list was also checked visually against
  page 2.
- **Research split.** A sub-agent did the non-DoD source search. Its raw notes are
  `data/terminations/agent_findings.json`. Every source used for a `confirmed` flag was opened and the
  supporting passage located in the local copy before the flag was written. Exceptions: press-only items are
  marked `confirmed_secondary`.
- **No OCR** was run. 18 agreements (11 `no_text` + 7 `low_text`) need it for full-text search.
- **Untrusted files.** Downloads live under `data/`, processed with `python3 -I`, `pdfinfo` and `pdftotext`
  only.
