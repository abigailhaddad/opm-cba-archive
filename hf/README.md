---
license: other
license_name: us-government-public-records
pretty_name: OPM federal collective bargaining agreements
language:
- en
tags:
- labor
- unions
- federal-government
- legal
configs:
- config_name: default
  data_files: agreements.csv
---

# OPM federal collective bargaining agreements

Every federal union contract in OPM's public database ([opm.gov](https://www.opm.gov/policy-data-oversight/labor-management-relations/collective-bargaining-agreements/)), as PDFs with extracted text.

- `pdfs/<id>.pdf`: the agreement as OPM serves it, named by OPM's record id
- `text/<id>.txt`: `pdftotext -layout` output (scanned agreements have little or no text; no OCR was run)
- `agreements.csv`: one row per record, with OPM's fields, the file's SHA-256, page and word counts, text status, and a first-pass flag for termination under the executive orders that removed agencies from collective bargaining

The flags, their sources, the scripts and the counts are documented at [github.com/abigailhaddad/opm-cba-archive](https://github.com/abigailhaddad/opm-cba-archive). The flags are leads to check, not findings.

Some records share one file, and a few listed files couldn't be downloaded; both are marked in `agreements.csv`.

The agreements are documents agencies submitted to OPM, which publishes them. This is an unofficial copy.
