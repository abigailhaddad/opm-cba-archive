"""Compare two listings; write data/changes/YYYY-MM-DD.md.

Exit 0 = no changes, 10 = changed/added only, 11 = records removed.
Also writes changed=/removed=/added= to $GITHUB_OUTPUT when set.
"""
import argparse, datetime as dt, json, os, sys

FIELDS = ("fileUrl", "fileName", "expirationDate")
CHANGES_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "changes")


def diff(prev, new):
    p = {r["id"]: r for r in prev["results"]}
    n = {r["id"]: r for r in new["results"]}
    added = [n[i] for i in n if i not in p]
    removed = [p[i] for i in p if i not in n]
    changed = []
    for i in n.keys() & p.keys():
        fields = {f: (p[i].get(f), n[i].get(f)) for f in FIELDS if p[i].get(f) != n[i].get(f)}
        if fields:
            changed.append((n[i], fields))
    changed.sort(key=lambda x: x[0]["id"])
    return {"added": added, "removed": removed, "changed": changed}


def label(r):
    return f"`{r['id']}` {r.get('agencyName')} / {r.get('laborUnionName')} local {r.get('local')} ({r.get('fileName')})"


def render(d, prev_name, new_name, date):
    lines = [f"# Listing changes {date}", "", f"Previous: `{prev_name}`  ", f"New: `{new_name}`", "",
             f"Added: {len(d['added'])}, removed: {len(d['removed'])}, changed: {len(d['changed'])}", ""]
    for key in ("added", "removed"):
        lines += [f"## {key.capitalize()} ({len(d[key])})", ""] + [f"- {label(r)}" for r in d[key]] + [""]
    lines += [f"## Changed ({len(d['changed'])})", ""]
    for r, fields in d["changed"]:
        lines.append(f"- {label(r)}")
        lines += [f"  - {f}: `{a}` -> `{b}`" for f, (a, b) in fields.items()]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("prev")
    ap.add_argument("new")
    ap.add_argument("--out-dir", default=CHANGES_DIR)
    ap.add_argument("--date", default=dt.date.today().isoformat())
    args = ap.parse_args(argv)
    d = diff(json.load(open(args.prev)), json.load(open(args.new)))
    any_change = any(d.values())
    if any_change:
        os.makedirs(args.out_dir, exist_ok=True)
        path = os.path.join(args.out_dir, f"{args.date}.md")
        with open(path, "w") as f:
            f.write(render(d, os.path.basename(args.prev), os.path.basename(args.new), args.date))
        print(f"wrote {path}")
    print(f"added={len(d['added'])} removed={len(d['removed'])} changed={len(d['changed'])}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"added={len(d['added'])}\nremoved={len(d['removed'])}\nchanged={len(d['changed'])}\n")
    if d["removed"]:
        return 11
    return 10 if any_change else 0


if __name__ == "__main__":
    sys.exit(main())
