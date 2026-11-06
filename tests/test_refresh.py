"""Tests for the weekly refresh: the download plan, the stop rules, the checks before publishing, the
commit plan, and the rule that curated flags are never touched. No network and no Hugging Face."""
import csv
import datetime as dt
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import urllib.error

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import cba_pipeline as cp  # noqa: E402
import refresh  # noqa: E402

NOW = dt.datetime(2026, 11, 9, 12, 0, tzinfo=dt.timezone.utc)
PDF = b"%PDF-1.4\n% fake body\n"


def rec(i, agency="Department of the Treasury", **kw):
    r = {"id": f"id{i}", "documentType": 1, "agencyName": agency, "subAgencyOrComponent": None,
         "activityOfficeRegion": None, "laborUnionName": f"Union {i}", "local": str(i), "busCodes": ["1"],
         "expirationDate": "2029-01-01T00:00:00", "fileUrl": f"https://x.test/files/{i}.pdf",
         "fileName": f"{i}.pdf", "fileSize": "1 MB"}
    r.update(kw)
    return r


def ok_row(i, sha="a", t="2026-11-01T00:00:00Z"):
    url = cp.quote_url(f"https://x.test/files/{i}.pdf")
    return {"id": f"id{i}", "url": url, "t": t, "status": "ok", "bytes": 10, "sha256": sha * 64, "magic": "%PDF-"}


def err_row(i, t="2026-11-01T00:00:00Z", http=404):
    return {"id": f"id{i}", "url": cp.quote_url(f"https://x.test/files/{i}.pdf"), "t": t, "status": "error", "http": http}


def pub(i, size="1 MB", url=None):
    """A row of the published table: what the listing showed when the file was last fetched."""
    return {"id": f"id{i}", "listed_fileSize": size, "fileUrl": url or f"https://x.test/files/{i}.pdf"}


def plan(records, log, hf=(), published=None, **kw):
    state = cp.latest_download_state(log)
    return cp.plan_downloads(records, state, set(hf), published, now=NOW, **kw)


# ---------- the download plan ----------

def test_plan_new_record_is_downloaded():
    p = plan([rec(1), rec(2)], [ok_row(1)], hf={"id1"})
    assert [(x["id"], x["reason"]) for x in p] == [("id2", "new")]


def test_plan_nothing_to_do():
    assert plan([rec(1)], [ok_row(1)], hf={"id1"}) == []


def test_plan_changed_url_and_changed_file_size():
    changed_url = rec(1, fileUrl="https://x.test/files/1-v2.pdf")
    resized = rec(2, fileSize="2 MB")
    p = plan([changed_url, resized], [ok_row(1), ok_row(2)], hf={"id1", "id2"}, published=[pub(1), pub(2)])
    assert {x["id"]: x["reason"] for x in p} == {"id1": "url_changed", "id2": "file_changed"}


def test_plan_expiration_date_change_alone_downloads_nothing():
    new = [rec(1, expirationDate="2031-01-01T00:00:00")]
    assert plan(new, [ok_row(1)], hf={"id1"}, published=[pub(1)]) == []


def test_plan_does_not_redownload_a_changed_file_again_once_it_is_published():
    resized = rec(1, fileSize="2 MB")
    assert [x["reason"] for x in plan([resized], [ok_row(1)], hf={"id1"}, published=[pub(1)])] == ["file_changed"]
    # after the refresh the published table carries the new size, so the next week finds nothing
    assert plan([resized], [ok_row(1)], hf={"id1"}, published=[pub(1, size="2 MB")]) == []


def test_plan_file_missing_from_hugging_face():
    p = plan([rec(1)], [ok_row(1)], hf=set())
    assert [(x["id"], x["reason"]) for x in p] == [("id1", "missing_on_hf")]


def test_plan_failed_download_is_retried_only_after_a_week():
    recent = err_row(1, t="2026-11-05T00:00:00Z")   # 4 days ago
    old = err_row(2, t="2026-11-01T00:00:00Z")      # 8 days ago
    p = plan([rec(1), rec(2)], [recent, old])
    assert [(x["id"], x["reason"]) for x in p] == [("id2", "retry")]


def test_plan_a_later_success_beats_an_earlier_failure():
    p = plan([rec(1)], [err_row(1, t="2026-10-01T00:00:00Z"), ok_row(1)], hf={"id1"})
    assert p == []


def test_plan_forced_ids_and_order_and_limit():
    recs = [rec(i) for i in range(1, 6)]
    log = [ok_row(1), ok_row(2), err_row(3, t="2026-10-01T00:00:00Z")]
    p = plan(recs, log, hf={"id1", "id2"}, force_ids=["id1"])
    assert [(x["id"], x["reason"]) for x in p] == [
        ("id1", "forced"), ("id4", "new"), ("id5", "new"), ("id3", "retry")]
    assert len(plan(recs, log, hf={"id1", "id2"}, force_ids=["id1"], limit=2)) == 2


def test_plan_ignores_records_no_longer_listed():
    # id9 is in the log but not in the listing: nothing to fetch
    assert plan([rec(1)], [ok_row(1), ok_row(9)], hf={"id1"}) == []


# ---------- downloading ----------

def http_error(code):
    return urllib.error.HTTPError("https://x.test", code, "msg", {}, None)


def test_download_stops_at_first_403_or_429(tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        if len(calls) == 2:
            raise http_error(429)
        return 200, "application/pdf", PDF

    items = [{"id": f"id{i}", "url": f"https://x.test/{i}.pdf", "reason": "new"} for i in range(4)]
    log = tmp_path / "log.jsonl"
    res = cp.download_files(items, fetch, str(tmp_path / "files"), str(log), sleep=0)
    assert res["blocked"] and res["ok"] == ["id0"] and res["failed"] == ["id1"]
    assert len(calls) == 2                      # id2 and id3 were never requested
    lines = [json.loads(x) for x in log.read_text().splitlines()]
    assert [(l["id"], l["status"]) for l in lines] == [("id0", "ok"), ("id1", "error")]
    assert lines[1]["http"] == 429
    assert not list((tmp_path / "files").glob("*.part"))


def test_download_carries_on_after_a_404_and_rejects_non_pdfs(tmp_path):
    bodies = {"a": PDF, "b": b"<html>not a pdf</html>"}

    def fetch(url):
        if url.endswith("gone.pdf"):
            raise http_error(404)
        return 200, "x", bodies["a" if url.endswith("a.pdf") else "b"]

    items = [{"id": n, "url": f"https://x.test/{n}.pdf", "reason": "new"} for n in ("gone", "a", "b")]
    res = cp.download_files(items, fetch, str(tmp_path / "f"), str(tmp_path / "l.jsonl"), sleep=0)
    assert not res["blocked"] and res["ok"] == ["a"] and res["failed"] == ["gone", "b"]
    row = json.loads((tmp_path / "l.jsonl").read_text().splitlines()[1])
    assert row["sha256"] == hashlib.sha256(PDF).hexdigest() and row["magic"] == "%PDF-"
    assert os.path.exists(tmp_path / "f" / "a.pdf") and not os.path.exists(tmp_path / "f" / "b.pdf")


def test_http_fetch_retries_server_errors_but_not_client_errors(monkeypatch):
    seq = []

    class Resp:
        status = 200
        headers = {"Content-Type": "application/pdf"}
        def read(self): return PDF
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=0):
        seq.append(1)
        if len(seq) == 1:
            raise http_error(503)
        return Resp()

    monkeypatch.setattr(cp.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(cp.time, "sleep", lambda s: None)
    assert cp.http_fetch("https://x.test/a.pdf")[2] == PDF and len(seq) == 2

    seq.clear()
    monkeypatch.setattr(cp.urllib.request, "urlopen", lambda req, timeout=0: (seq.append(1), (_ for _ in ()).throw(http_error(404))))
    with pytest.raises(urllib.error.HTTPError):
        cp.http_fetch("https://x.test/a.pdf")
    assert len(seq) == 1                        # a 404 is not retried


# ---------- checks before publishing ----------

def table_row(i, sha="a", flag="not_flagged_no_source_found", **kw):
    r = {"id": f"id{i}", "download_status": "ok", "sha256": sha * 64, "is_pdf_magic": "True",
         "termination_flag": flag, "eo_coverage": "covered", "in_current_listing": "True",
         "agencyName": "A", "subAgencyOrComponent": "", "activityOfficeRegion": "", "laborUnionName": "U",
         "local": str(i)}
    r.update(kw)
    return r


def verify(rows, listing, prev, pdfs=None, texts=None, redown=()):
    ids = {r["id"] for r in rows}
    return cp.verify_table(rows, listing, prev, ids if pdfs is None else pdfs, ids if texts is None else texts, redown)


def test_verify_clean_table_passes():
    rows = [table_row(1), table_row(2)]
    assert verify(rows, [rec(1), rec(2)], [table_row(1)]) == []


def test_verify_row_count_must_match_the_listing():
    rows = [table_row(1), table_row(2)]
    assert any("listing has 3" in p for p in verify(rows, [rec(1), rec(2), rec(3)], []))


def test_verify_no_row_may_be_lost_from_the_published_table():
    rows = [table_row(1)]
    assert any("missing from the new one" in p for p in verify(rows, [rec(1)], [table_row(1), table_row(2)]))


def test_verify_a_record_removed_from_the_listing_is_kept_not_lost():
    gone = table_row(2, in_current_listing="False")
    assert verify([table_row(1), gone], [rec(1)], [table_row(1), table_row(2)]) == []


def test_verify_downloaded_rows_need_sha_pdf_and_text():
    assert any("no valid sha256" in p for p in verify([table_row(1, sha="")], [rec(1)], []))
    assert any("no valid sha256" in p for p in verify([dict(table_row(1), sha256="xyz")], [rec(1)], []))
    assert any("not a PDF" in p for p in verify([table_row(1, is_pdf_magic="False")], [rec(1)], []))
    assert any("no PDF" in p for p in verify([table_row(1)], [rec(1)], [], pdfs=set()))
    assert any("no text" in p for p in verify([table_row(1)], [rec(1)], [], texts=set()))


def test_verify_a_hash_may_only_change_when_the_file_was_downloaded_again():
    new, old = [table_row(1, sha="b")], [table_row(1, sha="a")]
    assert any("hash changed" in p for p in verify(new, [rec(1)], old))
    assert verify(new, [rec(1)], old, redown=["id1"]) == []


def test_verify_curated_flag_changes_fail_the_run():
    old = [table_row(1, flag="confirmed")]
    new = [table_row(1, flag="inferred")]
    assert any("curated flag" in p for p in verify(new, [rec(1)], old))
    # an uncurated flag may change when the listing fields change
    assert verify([table_row(1, flag="inferred")], [rec(1)], [table_row(1, flag="not_flagged_no_source_found")]) == []


def test_flag_changes_lists_only_existing_rows():
    prev = [table_row(1, flag="inferred")]
    rows = [table_row(1, flag="uncertain_injunction"), table_row(2, flag="inferred")]
    assert cp.flag_changes(rows, prev) == [("id1", "inferred", "uncertain_injunction")]


# ---------- the Hugging Face commit plan ----------

def make_files(tmp_path, ids):
    pdf, txt = tmp_path / "pdf", tmp_path / "txt"
    pdf.mkdir(); txt.mkdir()
    for i in ids:
        (pdf / f"{i}.pdf").write_bytes(PDF)
        (txt / f"{i}.txt").write_text("text")
    csvp = tmp_path / "t.csv"
    csvp.write_bytes(b"new table")
    return str(pdf), str(txt), str(csvp)


def test_commit_plan_adds_new_pdf_text_and_table(tmp_path):
    pdf, txt, csvp = make_files(tmp_path, ["id2"])
    ops = cp.commit_plan([table_row(1), table_row(2)], [table_row(1)], {"pdfs/id1.pdf"}, pdf, txt, csvp, b"old", ["id2"])
    assert ops == [("pdfs/id2.pdf", f"{pdf}/id2.pdf"), ("text/id2.txt", f"{txt}/id2.txt"), ("agreements.csv", csvp)]


def test_commit_plan_skips_a_file_that_is_already_there_with_the_same_hash(tmp_path):
    pdf, txt, csvp = make_files(tmp_path, ["id1"])
    ops = cp.commit_plan([table_row(1)], [table_row(1)], {"pdfs/id1.pdf"}, pdf, txt, csvp, b"new table", ["id1"])
    assert ops == []


def test_commit_plan_overwrites_a_file_whose_hash_changed(tmp_path):
    pdf, txt, csvp = make_files(tmp_path, ["id1"])
    ops = cp.commit_plan([table_row(1, sha="b")], [table_row(1, sha="a")], {"pdfs/id1.pdf"}, pdf, txt, csvp, b"new table", ["id1"])
    assert [p for p, _ in ops] == ["pdfs/id1.pdf", "text/id1.txt"]


def test_commit_plan_never_contains_a_deletion(tmp_path):
    pdf, txt, csvp = make_files(tmp_path, ["id1", "id2"])
    # id9 was removed from the listing: its PDF stays on Hugging Face, nothing in the plan touches it
    rows = [table_row(1), table_row(2), table_row(9, in_current_listing="False")]
    ops = cp.commit_plan(rows, [table_row(9)], {"pdfs/id9.pdf", "text/id9.txt"}, pdf, txt, csvp, b"old", ["id1", "id2"])
    assert all(isinstance(p, str) and isinstance(l, str) for p, l in ops)
    assert not any("id9" in p for p, _ in ops)


def test_hf_client_refuses_anything_but_additions(monkeypatch):
    """HfClient.commit builds only CommitOperationAdd; its assertion guards against a future delete."""
    import hf_client
    src = open(hf_client.__file__).read()
    assert "CommitOperationDelete" not in src and "assert all(isinstance(o, CommitOperationAdd)" in src


def test_review_markdown_lists_only_new_agreements_in_covered_agencies():
    rows = [table_row(1, eo_coverage="covered", agencyName="Department of State"),
            table_row(2, eo_coverage="not_named"), table_row(3, eo_coverage="covered")]
    md = cp.review_markdown(rows, ["id1", "id2"], "2026-11-09")
    assert "Department of State" in md and "id2" not in md and "| U | 1 |" in md
    assert cp.review_markdown(rows, ["id2"], "2026-11-09") == ""


# ---------- the table build and the never-overwrite rule ----------

def build_root(tmp_path, records, flags=(), prev_csv=None, logs=True, prev_listing=None):
    """A tiny copy of the repo layout, and the build run against it."""
    data = tmp_path / "data"
    (data / "raw").mkdir(parents=True, exist_ok=True)
    (data / "terminations").mkdir(exist_ok=True)
    if prev_listing is not None:
        (data / "raw" / "cba_listing_20260101T000000Z.json").write_text(json.dumps({"results": prev_listing, "rowCount": len(prev_listing)}))
    (data / "raw" / "cba_listing_20260102T000000Z.json").write_text(json.dumps({"results": records, "rowCount": len(records)}))
    with open(data / "terminations" / "record_flags.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["record_id", "source_id", "level", "basis"])
        for rid, level in flags:
            w.writerow([rid, "S99", level, "test basis"])
    dl = [ok_row(int(r["id"][2:])) for r in records if logs]
    (data / "download_log.jsonl").write_text("".join(json.dumps(x) + "\n" for x in dl))
    ex = [{"id": r["id"], "pages": 10, "words": 5000, "pdftotext_rc": 0, "encrypted": False} for r in records if logs]
    (data / "extract_log.jsonl").write_text("".join(json.dumps(x) + "\n" for x in ex))
    if prev_csv is not None:
        (data / "cba_agreements.csv").write_bytes(prev_csv)
    return str(tmp_path)


def run_build(root):
    env = dict(os.environ, CBA_ROOT=root)
    for script in ("build_table.py", "summary.py"):
        r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", script)], env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    return {r["id"]: r for r in csv.DictReader(open(os.path.join(root, "data", "cba_agreements.csv")))}


def test_new_agreement_gets_the_default_flag_and_a_curated_flag_is_never_overwritten(tmp_path):
    records = [rec(1, agency="Department of State"), rec(2, agency="Department of State"), rec(3, agency="Library of Congress")]
    root = build_root(tmp_path, records, flags=[("id1", "confirmed")])
    t = run_build(root)
    assert t["id1"]["termination_flag"] == "confirmed"           # curated
    assert t["id2"]["termination_flag"] == "not_flagged_no_source_found"   # covered by the orders, no source yet
    assert t["id3"]["termination_flag"] == "not_flagged_agency_not_named"
    terminations = tmp_path / "data" / "terminations"
    before = {p.name: p.read_bytes() for p in terminations.iterdir()}

    # a new agreement arrives, then the build runs again on the table it wrote last time
    records.append(rec(4, agency="Department of State"))
    root = build_root(tmp_path, records, flags=[("id1", "confirmed")], prev_csv=open(tmp_path / "data" / "cba_agreements.csv", "rb").read())
    t2 = run_build(root)
    assert t2["id1"]["termination_flag"] == "confirmed"
    assert t2["id4"]["termination_flag"] == "not_flagged_no_source_found"
    assert {p.name: p.read_bytes() for p in terminations.iterdir()} == before   # curated files untouched


def test_a_record_removed_from_the_listing_stays_in_the_table(tmp_path):
    records = [rec(1), rec(2)]
    root = build_root(tmp_path, records)
    run_build(root)
    prev = open(tmp_path / "data" / "cba_agreements.csv", "rb").read()
    root = build_root(tmp_path, [rec(1)], prev_csv=prev)
    t = run_build(root)
    assert set(t) == {"id1", "id2"}
    assert t["id1"]["in_current_listing"] == "True" and t["id2"]["in_current_listing"] == "False"
    # the kept row is byte-for-byte what was published, apart from the new column value
    old = {r["id"]: r for r in csv.DictReader(io.StringIO(prev.decode()))}
    assert {k: v for k, v in t["id2"].items() if k != "in_current_listing"} == {k: v for k, v in old["id2"].items() if k != "in_current_listing"}


def test_bare_submission_forms_survive_a_clone_with_no_text_files(tmp_path):
    """data/text is not in git. A row once marked submission_form_only keeps that status when the text is absent."""
    records = [rec(1)]
    root = build_root(tmp_path, records)
    run_build(root)
    p = tmp_path / "data" / "cba_agreements.csv"
    s = p.read_text().replace('"text",', '"submission_form_only",', 1)
    assert "submission_form_only" in s
    (tmp_path / "data" / "extract_log.jsonl").write_text(json.dumps({"id": "id1", "pages": 1, "words": 40, "pdftotext_rc": 0}) + "\n")
    p.write_text(s)
    assert run_build(str(tmp_path))["id1"]["text_status"] == "submission_form_only"


def test_the_build_reproduces_the_published_table_from_the_repo_data(tmp_path):
    """On a fresh clone (no PDFs, no text) the build gives the committed table, plus one new column."""
    repo_data = os.path.join(ROOT, "data")
    committed = os.path.join(repo_data, "cba_agreements.csv")
    if not os.path.exists(committed) or "in_current_listing" in open(committed).readline():
        pytest.skip("committed table already has the new column")
    d = tmp_path / "data"
    d.mkdir()
    shutil.copy(committed, d / "cba_agreements.csv")
    for name in ("download_log.jsonl", "extract_log.jsonl"):
        shutil.copy(os.path.join(repo_data, name), d / name)
    os.symlink(os.path.join(repo_data, "raw"), d / "raw")
    os.symlink(os.path.join(repo_data, "terminations"), d / "terminations")
    before = open(committed).read().splitlines()
    run_build(str(tmp_path))
    after = open(d / "cba_agreements.csv").read().splitlines()
    assert after[0] == before[0] + ',"in_current_listing"'
    assert all(a == b + ",True" for a, b in zip(after[1:], before[1:])) and len(after) == len(before)


# ---------- the whole run, with fakes ----------

class FakeHf:
    def __init__(self, files, csv_bytes, token="t"):
        self.files, self.csv_bytes, self.token = set(files), csv_bytes, token
        self.commits = []

    def read_state(self):
        return "rev1", self.files, self.csv_bytes

    def commit(self, ops, message, parent):
        self.commits.append((list(ops), message, parent))


def fake_extract(src, dst):
    open(dst, "w").write("some text")
    return {"id": os.path.basename(src)[:-4], "pages": 12, "words": 6000, "pdftotext_rc": 0, "encrypted": False}


def setup_published(tmp_path, records):
    """A repo root that is fully published: every record downloaded, on HF, table equal to HF's."""
    root = build_root(tmp_path, records)
    run_build(root)
    csv_bytes = open(tmp_path / "data" / "cba_agreements.csv", "rb").read()
    ids = [r["id"] for r in records]
    files = {"README.md", "agreements.csv"} | {f"pdfs/{i}.pdf" for i in ids} | {f"text/{i}.txt" for i in ids}
    for i in ids:  # the checkout has no PDFs, like CI
        pass
    return root, csv_bytes, files


def good_fetch(url):
    return 200, "application/pdf", PDF


def run_refresh(root, hf, fetch=good_fetch, extra=()):
    return refresh.main(["--root", root, "--delay", "0", *extra], fetch=fetch, hf=hf, extract=fake_extract, sleep=0)


def test_run_with_nothing_new_changes_nothing_and_exits_zero(tmp_path, monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    records = [rec(1), rec(2)]
    root, csv_bytes, files = setup_published(tmp_path, records)
    hf = FakeHf(files, csv_bytes)
    logs_before = open(tmp_path / "data" / "download_log.jsonl").read()
    assert run_refresh(root, hf) == 0
    assert hf.commits == []
    assert open(tmp_path / "data" / "download_log.jsonl").read() == logs_before      # nothing was fetched or logged
    assert open(tmp_path / "data" / "cba_agreements.csv", "rb").read() == csv_bytes


def test_run_downloads_a_new_agreement_and_publishes_one_commit_of_additions(tmp_path):
    records = [rec(1), rec(2)]
    root, csv_bytes, files = setup_published(tmp_path, records)
    # OPM adds id3 and the listing is saved as a newer file
    all_records = records + [rec(3, agency="Department of State")]
    (tmp_path / "data" / "raw" / "cba_listing_20260103T000000Z.json").write_text(json.dumps({"results": all_records, "rowCount": 3}))
    hf = FakeHf(files, csv_bytes)
    assert run_refresh(root, hf) == 0
    assert len(hf.commits) == 1
    ops, message, parent = hf.commits[0]
    assert parent == "rev1"
    assert sorted(p for p, _ in ops) == ["agreements.csv", "pdfs/id3.pdf", "text/id3.txt"]
    table = {r["id"]: r for r in csv.DictReader(open(tmp_path / "data" / "cba_agreements.csv"))}
    assert set(table) == {"id1", "id2", "id3"} and table["id3"]["download_status"] == "ok"
    assert table["id3"]["termination_flag"] == "not_flagged_no_source_found"
    # a person-review list was written for the new agreement
    reviews = list((tmp_path / "data" / "changes").glob("review-*.md"))
    assert len(reviews) == 1 and "Department of State" in reviews[0].read_text()


def test_dry_run_commits_nothing(tmp_path):
    records = [rec(1)]
    root, csv_bytes, files = setup_published(tmp_path, records)
    (tmp_path / "data" / "raw" / "cba_listing_20260103T000000Z.json").write_text(json.dumps({"results": records + [rec(2)], "rowCount": 2}))
    hf = FakeHf(files, csv_bytes)
    assert run_refresh(root, hf, extra=["--dry-run"]) == 0
    assert hf.commits == []


def test_missing_token_with_something_to_publish_is_a_red_run(tmp_path, monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    records = [rec(1)]
    root, csv_bytes, files = setup_published(tmp_path, records)
    (tmp_path / "data" / "raw" / "cba_listing_20260103T000000Z.json").write_text(json.dumps({"results": records + [rec(2)], "rowCount": 2}))
    hf = FakeHf(files, csv_bytes, token=None)
    assert run_refresh(root, hf) == 4 and hf.commits == []


def test_a_block_publishes_what_was_fetched_then_fails(tmp_path):
    records = [rec(1)]
    root, csv_bytes, files = setup_published(tmp_path, records)
    more = records + [rec(2), rec(3), rec(4)]
    (tmp_path / "data" / "raw" / "cba_listing_20260103T000000Z.json").write_text(json.dumps({"results": more, "rowCount": 4}))
    n = []

    def fetch(url):
        n.append(url)
        if len(n) == 2:
            raise http_error(429)
        return good_fetch(url)

    hf = FakeHf(files, csv_bytes)
    assert run_refresh(root, hf, fetch=fetch) == 3
    assert len(n) == 2                                   # stopped; id4 never requested
    assert len(hf.commits) == 1 and "pdfs/id2.pdf" in [p for p, _ in hf.commits[0][0]]


def test_failed_checks_publish_nothing(tmp_path):
    records = [rec(1), rec(2)]
    root, csv_bytes, files = setup_published(tmp_path, records)
    # the published table has a row the new table would lose: simulate by publishing a table with an extra id
    extra = csv_bytes.decode().splitlines()
    ghost = next(l for l in extra[1:] if l.startswith('"id2"')).replace('"id2"', '"ghost"', 1)
    published = ("\n".join(extra + [ghost]) + "\n").encode()
    hf = FakeHf(files | {"pdfs/ghost.pdf", "text/ghost.txt"}, published)
    assert run_refresh(root, hf) == 2 and hf.commits == []


def test_the_curated_files_are_never_written_by_a_run(tmp_path):
    records = [rec(1, agency="Department of State"), rec(2)]
    root, csv_bytes, files = setup_published(tmp_path, records)
    (tmp_path / "data" / "raw" / "cba_listing_20260103T000000Z.json").write_text(json.dumps({"results": records + [rec(3)], "rowCount": 3}))
    term = tmp_path / "data" / "terminations"
    before = {p.name: p.read_bytes() for p in term.iterdir()}
    run_refresh(root, FakeHf(files, csv_bytes))
    assert {p.name: p.read_bytes() for p in term.iterdir()} == before


def test_most_new_downloads_failing_is_a_red_run(tmp_path):
    records = [rec(1)]
    root, csv_bytes, files = setup_published(tmp_path, records)
    more = records + [rec(i) for i in range(2, 8)]
    (tmp_path / "data" / "raw" / "cba_listing_20260103T000000Z.json").write_text(json.dumps({"results": more, "rowCount": 7}))

    def fetch(url):
        raise http_error(500)

    assert run_refresh(root, FakeHf(files, csv_bytes), fetch=fetch) == 6


def test_a_failed_hugging_face_commit_is_a_red_run(tmp_path):
    records = [rec(1)]
    root, csv_bytes, files = setup_published(tmp_path, records)
    (tmp_path / "data" / "raw" / "cba_listing_20260103T000000Z.json").write_text(json.dumps({"results": records + [rec(2)], "rowCount": 2}))

    class Failing(FakeHf):
        def commit(self, ops, message, parent):
            raise RuntimeError("412 the dataset changed since it was read")

    assert run_refresh(root, Failing(files, csv_bytes)) == 5


def test_an_unreadable_dataset_is_a_red_run(tmp_path):
    root, csv_bytes, files = setup_published(tmp_path, [rec(1)])

    class Gone(FakeHf):
        def read_state(self):
            return None, set(), None

    assert run_refresh(root, Gone(files, csv_bytes)) == 5


def test_the_card_goes_up_only_when_it_changed_in_git(tmp_path):
    records = [rec(1)]
    root, csv_bytes, files = setup_published(tmp_path, records)
    (tmp_path / "hf").mkdir()
    card = tmp_path / "hf" / "README.md"
    card.write_text("card v1")
    # nothing recorded yet: the card goes up with this run
    hf = FakeHf(files, csv_bytes)
    assert run_refresh(root, hf) == 0
    assert [p for p, _ in hf.commits[0][0]] == ["README.md"]
    recorded = (tmp_path / "data" / "hf_card.sha256").read_text().strip()
    assert recorded == hashlib.sha256(b"card v1").hexdigest()
    # unchanged card: nothing to publish
    hf2 = FakeHf(files, csv_bytes)
    assert run_refresh(root, hf2) == 0 and hf2.commits == []
    # edited in git: goes up again
    card.write_text("card v2")
    hf3 = FakeHf(files, csv_bytes)
    assert run_refresh(root, hf3) == 0 and [p for p, _ in hf3.commits[0][0]] == ["README.md"]


def test_a_published_week_is_not_reviewed_or_downloaded_again(tmp_path, monkeypatch):
    out = tmp_path / "gh_output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    records = [rec(1), rec(2, agency="Department of State")]
    root, csv_bytes, files = setup_published(tmp_path, records)
    (tmp_path / "data" / "raw" / "cba_listing_20260103T000000Z.json").write_text(
        json.dumps({"results": records + [rec(3, agency="Department of State")], "rowCount": 3}))
    hf = FakeHf(files, csv_bytes)
    assert run_refresh(root, hf) == 0 and len(hf.commits) == 1
    assert "review_count=1" in out.read_text()
    # next week: Hugging Face now holds what we published, and the listing has not changed
    out.write_text("")
    published_csv = open(tmp_path / "data" / "cba_agreements.csv", "rb").read()
    files2 = files | {"pdfs/id3.pdf", "text/id3.txt"}
    hf2 = FakeHf(files2, published_csv)
    logs = open(tmp_path / "data" / "download_log.jsonl").read()
    assert run_refresh(root, hf2) == 0
    assert hf2.commits == []
    assert open(tmp_path / "data" / "download_log.jsonl").read() == logs      # nothing fetched again
    assert "review_count=0" in out.read_text()
