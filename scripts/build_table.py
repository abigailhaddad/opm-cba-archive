"""Build data/cba_agreements.csv: listing fields + download hash + page count + text flag +
EO coverage + termination flag. Usage: python3 -I scripts/build_table.py
CBA_ROOT (env, optional) points the script at another copy of the repo layout, for tests.
Inputs: data/raw/cba_listing_*.json (latest), data/download_log.jsonl, data/extract_log.jsonl,
data/terminations/record_flags.csv (hand-curated confirmed matches), scripts/coverage.py rules."""
import json, glob, csv, os, sys, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coverage import coverage, psf_hint
from cba_pipeline import read_rows, typed_row
ROOT = os.environ.get("CBA_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
listing = sorted(glob.glob(P("data/raw/cba_listing_*.json")))[-1]
recs = json.load(open(listing))["results"]
# The table as last published. It keeps rows for records OPM has since removed from the listing, and it
# remembers which agreements are a bare submission form, which needs the text files a fresh clone lacks.
prev_rows = read_rows(P("data/cba_agreements.csv"))
prev_status = {r["id"]: r["text_status"] for r in prev_rows}
dl = {}
for l in open(P("data/download_log.jsonl")):
    j = json.loads(l)
    if j["status"] == "ok" or j["id"] not in dl: dl[j["id"]] = j
ex = {}
if os.path.exists(P("data/extract_log.jsonl")):
    for l in open(P("data/extract_log.jsonl")):
        j = json.loads(l); ex[j["id"]] = j
manual = collections.defaultdict(list)
mf = P("data/terminations/record_flags.csv")
if os.path.exists(mf):
    for row in csv.DictReader(open(mf)):
        manual[row["record_id"]].append(row)
sha_count = collections.Counter(d.get("sha256") for d in dl.values() if d.get("status") == "ok")
first_for_sha = {}
for r in recs:
    d = dl.get(r["id"], {})
    if d.get("sha256") and d["sha256"] not in first_for_sha: first_for_sha[d["sha256"]] = r["id"]

DOD_CERT = re.compile(r"letterkenny munition|air force test center|\baftc\b|412 test wing|edwards|air force sustainment center|\bafsc\b|air logistics|tinker|robins|hill a(ir )?f(orce )?b|fleet readiness center southeast|frcse", re.I)
INJ_UNION = re.compile(r"^IFPTE|^FEA-|Federal Education Association", re.I)
# Units listed in AFL-CIO v. Trump, D.D.C. 1:25-cv-02445-PLF, Doc 44 (PI order filed 2025-10-01), item (2) DoD units.
PI_DOD = {
    "IFPTE": {"1","3","4","7","8A","12","16","22","32","49","86","96","97","98","121","131","259","561","777","852","1437"},
    "IBEW": {"26","1688","2080","2219"},
    "IAM": {"97","174","225","282","726","1859","1998","2049","2296","2297","2424","2783","2902"},
    "UA": {"100"},
}
def local_tokens(x):
    return set(re.findall(r"[0-9]+[A-Za-z]?", (x or "").upper()))
def pi_dod_match(r):
    u = (r["laborUnionName"] or ""); loc = local_tokens(r["local"])
    U = u.upper()
    if U.startswith("IFPTE"): return ("IFPTE local in PI order" if loc & PI_DOD["IFPTE"] else "IFPTE (local not in PI order list)")
    if U.startswith("IBEW") and loc & PI_DOD["IBEW"]: return "IBEW local in PI order"
    if (U.startswith("IAMAW") or "MACHINISTS" in U) and loc & PI_DOD["IAM"]: return "IAM local in PI order"
    if ("PLUMBING" in U or "PIPE FITTING" in U) and loc & PI_DOD["UA"]: return "UA Local 100 in PI order"
    if re.search(r"METAL TRADES|^MTC|BMTC", U): return "metal trades council (PI order covers Metal Trades Department's councils)"
    if re.search(r"MASTERS,? MATES|IOMM", U): return "IOMM&P (in PI order)"
    if re.search(r"MARINE ENGINEERS", U): return "MEBA (PI order covers District No. 1, Pacific Coast District; verify district)"
    if "OVERSEAS FEDERATION OF TEACHERS" in U: return "AFT Overseas Federation of Teachers (in PI order)"
    if re.search(r"^FEA-|FEDERAL EDUCATION ASSOCIATION", U): return "FEA (separate PI reported by GovExec 2026-04-16)"
    return ""

def text_status(e, rid):
    if not e: return "not_processed"
    tp = P("data/text", rid + ".txt")
    if (e.get("pages") or 0) <= 2:
        if os.path.exists(tp):
            if re.search(r"Submission\s+Form", open(tp, errors="replace").read()[:3000]):
                return "submission_form_only"
        elif prev_status.get(rid) == "submission_form_only":
            return "submission_form_only"
    if e.get("error") or e.get("pdftotext_rc") not in (0, None): return "error"
    pages = e.get("pages") or 0; w = e.get("words") or 0
    if w == 0: return "no_text"
    if pages and w / pages < 50: return "low_text"
    return "text"

rows = []
for r in recs:
    d = dl.get(r["id"], {}); e = ex.get(r["id"])
    cov, sec, cnote = coverage(r); hint = psf_hint(r)
    m = manual.get(r["id"], [])
    flag, basis, srcs = "", "", ""
    if m:
        lv = [x["level"] for x in m]
        flag = "confirmed" if "confirmed" in lv else lv[0]
        basis = " || ".join(x["basis"] for x in m); srcs = ";".join(x["source_id"] for x in m)
    elif r["agencyName"] == "Department of Defense":
        sub = " | ".join(str(r.get(k) or "") for k in ("subAgencyOrComponent", "activityOfficeRegion", "fileName"))
        if hint:
            flag, basis = "not_flagged_exempt_psf", f"police/fire/guard indicator '{hint}': DoD memos exclude local employing offices of police, security guards, firefighters"
        elif pi_dod_match(r) and "not in PI order" not in pi_dod_match(r):
            flag, basis = "uncertain_injunction", pi_dod_match(r) + "; AFL-CIO v. Trump PI (Oct 1 2025) enjoins implementing EO 14251 s.2 for these units; DoD memos exclude units under an operative court order. Appeal outcome / current status not verified"
        elif pi_dod_match(r):
            flag, basis = "uncertain_injunction", pi_dod_match(r) + "; IFPTE says all its DoD locals were protected (S09), but this local number is not in the PI order list - verify"
        elif DOD_CERT.search(sub) and not re.search(r"defense", r.get("subAgencyOrComponent") or "", re.I):
            flag, basis = "uncertain_certification", "location may fall within a subdivision certified at 90 FR 17052 (FWS trades only); needs unit-level review"
        else:
            flag, basis = "inferred", "DoD Apr 9 2026 memo (and Aug 24 2026 replacement, per secondary source) directs termination of all DoD CBAs except listed carve-outs; no carve-out indicator in listing fields"
        srcs = "S03;S04;S11" + (";S12" if flag == "uncertain_injunction" else "")
    elif cov == "not_named":
        flag, basis = "not_flagged_agency_not_named", "agency/subdivision not named in EO 14251/14343 as read from listing fields"
    else:
        flag, basis = "not_flagged_no_source_found", "agency/subdivision appears within EO coverage but no termination source naming it was found/reviewed"
    rows.append({
        "id": r["id"], "agencyName": r["agencyName"], "subAgencyOrComponent": r["subAgencyOrComponent"],
        "activityOfficeRegion": r["activityOfficeRegion"], "laborUnionName": r["laborUnionName"], "local": r["local"],
        "busCodes": ";".join(r.get("busCodes") or []), "expirationDate": (r["expirationDate"] or "")[:10],
        "fileName": r["fileName"], "listed_fileSize": r["fileSize"], "fileUrl": r["fileUrl"],
        "download_status": d.get("status", "not_attempted"), "download_http": d.get("http"), "bytes": d.get("bytes"),
        "sha256": d.get("sha256"), "sha256_dup_count": sha_count.get(d.get("sha256")) if d.get("sha256") else None,
        "duplicate_of": first_for_sha.get(d.get("sha256")) if d.get("sha256") and first_for_sha.get(d.get("sha256")) != r["id"] else "",
        "is_pdf_magic": (d.get("magic") == "%PDF-") if d.get("status") == "ok" else None,
        "pages": (e or {}).get("pages"), "words": (e or {}).get("words"), "encrypted": (e or {}).get("encrypted"),
        "text_status": text_status(e, r["id"]),
        "eo_coverage": cov, "eo_section": sec, "eo_note": cnote, "psf_indicator": hint,
        "termination_flag": flag, "termination_basis": basis, "termination_sources": srcs,
        "in_current_listing": True,
    })
current_ids = {r["id"] for r in rows}
removed = 0
for p in prev_rows:
    if p["id"] not in current_ids:
        row = typed_row(p); row["in_current_listing"] = False
        rows.append(row); removed += 1
with open(P("data/cba_agreements.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]), quoting=csv.QUOTE_NONNUMERIC); w.writeheader(); w.writerows(rows)
c = collections.Counter
print("records", len(rows), f"({removed} no longer in the listing)")
print("download", c(x["download_status"] for x in rows))
print("unique sha", len({x["sha256"] for x in rows if x["sha256"]}))
print("text", c(x["text_status"] for x in rows))
print("coverage", c(x["eo_coverage"] for x in rows))
print("flag", c(x["termination_flag"] for x in rows))
