# Court status recheck, 2026-11-15

Checked on 2026-11-15 (between 05:25 and 05:33 UTC) against the public CourtListener docket pages and the free RECAP copies of filings. No PACER purchases, so documents marked "Buy on PACER" were not read; only their docket text was. CourtListener dockets are only as current as their last update, which is listed for each one. A filing made after that date would not show up here.

No flag changes come out of this check. The orders the flags rest on are still in place as far as these dockets show. The table in `data/cba_agreements.csv` is not touched.

| Case | Flags that depend on it | Status found | Docket last updated on CourtListener |
|---|---|---|---|
| AFL-CIO v. Trump, D.D.C. 1:25-cv-02445 (PI of Oct 1 2025, S12) and appeal D.C. Cir. 25-5436 | 108 of the 110 `uncertain_injunction` rows (all but the 2 FEA rows; see note 1) | PI in effect. Government appealed Dec 1 2025; no stay motion appears on either docket. District case stayed Dec 29 2025. Appeal held in abeyance Mar 23 2026 until the D.C. Circuit decides 25-5157, 25-5184 and 25-5303. | D.D.C. Mar 9 2026; D.C. Cir. May 18 2026 |
| FEA v. Trump, D.D.C. 1:25-cv-01362 (PI of Aug 14 2025) and appeal D.C. Cir. 25-5303 | 2 `uncertain_injunction` rows (FEA) | PI in effect. D.C. Circuit denied a stay pending appeal Sept 25 2025; district court denied one Oct 16 2025. Argued Dec 15 2025 with 25-5157 and 25-5184. No decision found. District case stayed Dec 22 2025. | D.D.C. Oct 8 2026; D.C. Cir. Feb 27 2026 |
| NTEU v. Trump, D.C. Cir. 25-5157 (argued with the two above) | none directly; its decision will move the two appeals above | No opinion. Docket shows Rule 28(j) letters through Oct 29 2026, nothing after. | Nov 9 2026 |
| AFGE Local 1410 v. DoD, D. Md. 1:26-cv-02653 | DoD `inferred` rows for the plaintiff AFGE/NFFE locals and councils | No injunction. First PI motion (ECF 11) withdrawn Sept 1 2026 after DoD's Aug 24 2026 memo. Second amended complaint (ECF 32) and renewed PI motion (ECF 29) pending. DoD moved to dismiss, transfer or stay Oct 20 2026 (ECF 38). No ruling on the docket. | Oct 28 2026 |
| National Council of Prison Locals v. BOP, D. Conn. 3:25-cv-01907 | 1 `confirmed_then_reinstated` row (cbee84d4) | CBA reinstated and still in force by court order. Nov 10 2026 order (ECF 95): BOP may re-terminate only after the court grants a properly filed motion to dissolve or modify the PI; the expedited motion (ECF 85) was terminated. BOP opposed the union's motion to supplement on Nov 12 (ECF 96). | Nov 13 2026 |
| AFGE Local 2305 v. VA, D.R.I. 1:25-cv-00583; appeals 1st Cir. 26-1321 and 26-1904 | 1 `confirmed` row (cb2c7ad6, VA-AFGE master), marked contested | Still contested. PI of Mar 13 2026 (reinstate the CBA) stands. The First Circuit on Oct 2 2026 granted VA's motion to stay the second enforcement order (the Aug 7/11 2026 order that blocked VA from treating the CBA as ended Aug 8 2026). The union moved Oct 16 2026 to modify the PI and for an indicative ruling (ECF 80); briefing closed Nov 3; no ruling on the docket. | D.R.I. Nov 13 2026; 1st Cir. Oct 2 2026 (its entries stop at Sept 16) |

Note 1: the 110 `uncertain_injunction` rows are 103 DoD rows matched to the AFL-CIO PI list, 2 DoD FEA rows, and 5 non-DoD rows named in the same AFL-CIO PI (EPA IFPTE Local 20, two Coast Guard metal trades councils, Coast Guard IAM Local 2203, DOE OPEIU Local 2001). One of the 103 is IFPTE Local 386, which is not on the PI's list (see METHODS.md). So 108 rows rest on the AFL-CIO PI and 2 on the FEA PI.

## What each finding rests on

AFL-CIO v. Trump
- D.D.C. docket: https://www.courtlistener.com/docket/70951028/american-federation-of-labor-and-congress-of-industrial-organizations-v/ . ECF 49 notice of appeal (Dec 1 2025). Minute order of Dec 29 2025: "all proceedings in this matter ... are STAYED pending further order of the Court" and the parties report within 14 days of the D.C. Circuit's decision in 25-5157, 25-5184 and 25-5303. ECF 51 joint status report (local copy `agent_sources/gov.uscourts.dcd.283118.51.0.pdf`): defendants reserved the right to seek a stay of the PI; none appears on the docket after it.
- D.C. Cir. 25-5436 docket: https://www.courtlistener.com/docket/72000482/american-federation-of-labor-v-donald-trump/ . Clerk's order of Mar 23 2026 holding the appeal in abeyance (local copy `agent_sources/gov.uscourts.cadc.42668.01208833310.0.pdf`).

FEA v. Trump
- D.C. Cir. 25-5303 docket: https://www.courtlistener.com/docket/71154941/federal-education-association-v-donald-trump/ . Per curiam order of Sept 25 2025 dissolving the administrative stay and denying a stay pending appeal (local copy `agent_sources/gov.uscourts.cadc.42321.01208779590.0.pdf`). Oral argument Dec 15 2025.
- D.D.C. docket: https://www.courtlistener.com/docket/70137963/federal-education-association-v-trump/ . Oct 16 2025 order denying a stay; Dec 22 2025 minute order staying the case pending the D.C. Circuit's decisions.

No D.C. Circuit decision in 25-5157, 25-5184, 25-5303 or 25-5436
- Check 1: the 25-5157 docket (https://www.courtlistener.com/docket/70001074/national-treasury-employees-union-v-donald-j-trump/), updated Nov 9 2026, shows only 28(j) letters and responses after argument, the last on Oct 29 2026.
- Check 2: CourtListener's opinion search (which pulls opinions from the D.C. Circuit's site) for docket numbers 25-5157, 25-5184, 25-5303 and 25-5436 returns 6 published items, the newest the FEA stay order of Sept 25 2025. https://www.courtlistener.com/?q=docketNumber%3A%2225-5157%22+OR+docketNumber%3A%2225-5303%22+OR+docketNumber%3A%2225-5184%22+OR+docketNumber%3A%2225-5436%22&type=o&court=cadc&order_by=dateFiled+desc
- Not done: the D.C. Circuit's own opinion search (media.cadc.uscourts.gov/opinions) did not return results for a docket number in a scripted browser, so it was not used.

AFGE Local 1410 v. DoD
- Docket: https://www.courtlistener.com/docket/73576166/american-federation-of-government-employees-local-1410-v-united-states/ . ECF 26 (local copy not saved; https://storage.courtlistener.com/recap/gov.uscourts.mdd.608535/gov.uscourts.mdd.608535.26.0.pdf): plaintiffs withdraw the first PI motion "in light of Defendants' August 24, 2026 memorandum." ECF 27 paperless order approving withdrawal. ECF 29 renewed PI motion (Sept 14). ECF 32 second amended complaint (Sept 30). ECF 38 motion to dismiss with a certified administrative record (Oct 20; PACER only, not read). A duplicate docket for 8:26-cv-02653 holds only the complaint (https://www.courtlistener.com/docket/73572529/american-federation-of-government-employees-local-1410-v-united-states/).

BOP
- Docket: https://www.courtlistener.com/docket/71907982/national-council-of-prison-locals-american-federation-of-government/ . ECF 95 (Nov 10 2026) docket text quotes ECF 84: "The CBA shall remain in effect until either the expiration of the agreed upon term of the agreement on May 28, 2029, or until the Court grants a properly filed motion by Defendants to dissolve or clarify the PI Order to permit re-termination." ECF 96 (local copy `agent_sources/gov.uscourts.ctd.167896.96.0.pdf`), BOP's own filing, says the court "voided Defendants' attempted re-termination." No Second Circuit appeal turned up in a CourtListener search of ca2 and ctd for "Prison Locals".

VA-AFGE
- D.R.I. docket: https://www.courtlistener.com/docket/71873221/american-federation-of-government-employees-local-2305-v-united-states/ . ECF 79 (entered Oct 5 2026) is the First Circuit's Oct 2 2026 order: "The motion for a stay of the second enforcement order is granted." Local copy `agent_sources/gov.uscourts.rid.60786.79.0_2.pdf`; the PDF's text layer is garbled, so the `.txt` beside it is Tesseract OCR of the page images. ECF 80 union motion to modify the PI (Oct 16), ECF 82 VA opposition (Oct 28), ECF 83 reply (Nov 3).
- 1st Cir. 26-1904 docket: https://www.courtlistener.com/docket/74190826/american-federation-of-govt-employees-local-2305-v-united-states/ (appeals consolidated Sept 16 2026; RECAP copy ends there).

## Not checked
- PACER-only filings, including DoD's Oct 20 2026 motion to dismiss and administrative record in D. Md., VA's Oct 28 2026 opposition in D.R.I., and the AFGE appellate briefs.
- Anything filed after each docket's last CourtListener update.
- Whether any agency has acted against the AFL-CIO or FEA injunctions in practice. These are court records only.
