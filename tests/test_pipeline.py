import json, os, sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import fetch_listing as fl
import diff_listing as dl


def rec(i, **kw):
    r = {"id": f"id{i}", "fileUrl": f"https://x/{i}.pdf", "fileName": f"{i}.pdf",
         "expirationDate": "2029-01-01T00:00:00", "agencyName": "A", "laborUnionName": "U", "local": "1"}
    r.update(kw)
    return r


def listing(recs):
    return {"results": recs, "rowCount": len(recs)}


def test_valid():
    assert fl.validate(listing([rec(1), rec(2)]))


@pytest.mark.parametrize("data", [
    [], "x", {"results": None}, {"results": [rec(1)], "rowCount": 2}, listing([]),
    listing([rec(1, fileUrl="")]), listing([{"fileUrl": "u"}]), listing([rec(1), rec(1)]),
])
def test_invalid(data):
    with pytest.raises(fl.ValidationError):
        fl.validate(data)


def test_drop_threshold():
    prev = listing([rec(i) for i in range(100)])
    fl.validate(listing([rec(i) for i in range(95)]), prev)  # exactly 5% ok
    with pytest.raises(fl.ValidationError):
        fl.validate(listing([rec(i) for i in range(94)]), prev)


def test_main_no_write_on_failure(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    assert fl.main(["--raw-dir", str(tmp_path), "--input", str(bad)]) == 1
    assert not list(tmp_path.glob("cba_listing_*"))
    bad.write_text(json.dumps({"results": [rec(1)], "rowCount": 5}))
    assert fl.main(["--raw-dir", str(tmp_path), "--input", str(bad)]) == 1
    assert not list(tmp_path.glob("cba_listing_*"))


def test_main_writes_on_success(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(listing([rec(1)])))
    assert fl.main(["--raw-dir", str(tmp_path), "--input", str(good)]) == 0
    assert len(list(tmp_path.glob("cba_listing_*.json"))) == 1


def test_diff():
    prev = listing([rec(1), rec(2), rec(3)])
    new = listing([rec(1), rec(2, fileUrl="https://x/2b.pdf", expirationDate="2030"), rec(4)])
    d = dl.diff(prev, new)
    assert [r["id"] for r in d["added"]] == ["id4"]
    assert [r["id"] for r in d["removed"]] == ["id3"]
    assert len(d["changed"]) == 1
    assert set(d["changed"][0][1]) == {"fileUrl", "expirationDate"}


def write(p, data):
    p.write_text(json.dumps(data))
    return str(p)


def test_diff_main_exit_codes(tmp_path):
    a = write(tmp_path / "a.json", listing([rec(1), rec(2)]))
    same = write(tmp_path / "s.json", listing([rec(2), rec(1)]))
    out = tmp_path / "changes"
    assert dl.main([a, same, "--out-dir", str(out), "--date", "2026-01-01"]) == 0
    assert not out.exists()
    chg = write(tmp_path / "c.json", listing([rec(1, fileName="z.pdf"), rec(2), rec(3)]))
    assert dl.main([a, chg, "--out-dir", str(out), "--date", "2026-01-02"]) == 10
    text = (out / "2026-01-02.md").read_text()
    assert "Added: 1, removed: 0, changed: 1" in text and "z.pdf" in text
    rm = write(tmp_path / "r.json", listing([rec(1)]))
    assert dl.main([a, rm, "--out-dir", str(out), "--date", "2026-01-03"]) == 11
    assert "id2" in (out / "2026-01-03.md").read_text()
