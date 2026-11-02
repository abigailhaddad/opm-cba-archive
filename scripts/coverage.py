"""Rule-based EO 14251 / EO 14343 coverage of each listed agreement, from listing fields only.
This says whether the agreement's agency/subdivision is NAMED in the EOs (as amended), not whether
the agreement was terminated. Rules follow the EO text saved in data/terminations/fr_*.txt.
Returns (coverage, eo_section, note). coverage in {covered, partly_or_unclear, not_named}."""
import re

def norm(s): return (s or "").lower()

def coverage(r):
    a = norm(r["agencyName"]); s = norm(r["subAgencyOrComponent"]); reg = norm(r["activityOfficeRegion"])
    both = s + " | " + reg
    if a == "department of defense":
        return "covered", "14251 s.1-402", "DoD excluded department-wide except subdivisions certified at 90 FR 17052 (FWS trades at 4 subdivisions)"
    if a == "department of state": return "covered", "14251 s.1-401", ""
    if a == "department of the treasury":
        if "engraving" in s: return "not_named", "14251 s.1-403", "BEP expressly excepted"
        return "covered", "14251 s.1-403", ""
    if a == "department of veterans affairs": return "covered", "14251 s.1-404", "VA s.4 suspension order (FR Doc 2025-06566, Apr 17 2025) rescinded Nov 13 2025 per VA memo of Mar 26 2026"
    if a == "department of justice":
        if "marshals" in s: return "partly_or_unclear", "14251 s.1-405/1-499(b)", "USMS subdivisions not listed in s.1-209 are NOT excluded"
        return "covered", "14251 s.1-405", ""
    if a == "department of energy": return "covered", "14251 s.1-409", "DOE excluded except FERC"
    if a in ("environmental protection agency",): return "covered", "14251 s.1-412", ""
    if a.startswith("u.s. agency for international development"): return "covered", "14251 s.1-413", ""
    if a == "nuclear regulatory commission": return "covered", "14251 s.1-414", ""
    if a == "national science foundation": return "covered", "14251 s.1-415", ""
    if a == "u.s. international trade commission": return "covered", "14251 s.1-416", ""
    if a == "general services administration": return "covered", "14251 s.1-418", ""
    if a == "national aeronautics and space administration": return "covered", "14343 s.1-420", ""
    if a == "department of health and human services":
        if re.search(r"disease control|\bcdc\b", s): return "covered", "14251 s.1-406(c)", ""
        if re.search(r"\bfda\b|food and drug", s): return "covered", "14251 s.1-406(b)", ""
        if re.search(r"national institutes of health", s) and "environmental" not in s:
            return "partly_or_unclear", "14251 s.1-406(g)", "only NIAID within NIH is named; listing does not say which institute"
        if s == "": return "partly_or_unclear", "14251 s.1-406", "no subdivision given in listing"
        return "not_named", "", "HHS subdivision not named in s.1-406"
    if a == "department of homeland security":
        if re.search(r"citizenship and immigration|immigration and customs|coast guard|emergency management|cybersecurity", s):
            return "covered", "14251 s.1-407", ""
        if "national protection and programs" in s:
            return "covered", "14251 s.1-407(k)", "NPPD was renamed CISA in 2018 (inferred correspondence)"
        if "immigration statistics" in s:
            return "partly_or_unclear", "14251 s.1-407(c)?", "OIS sits in Office of Strategy, Policy, and Plans (inferred, verify)"
        return "not_named", "", "DHS subdivision not named in s.1-407 (e.g., CBP)"
    if a == "department of the interior":
        if re.search(r"\bblm\b|land management|ocean energy|safety and environmental enforcement|office of the secretary", s):
            return "covered", "14251 s.1-408", ""
        if "reclamation" in s:
            return "partly_or_unclear", "14343 s.1-408(e)", "only BOR units with primary responsibility for hydropower facilities are named"
        return "not_named", "", ""
    if a == "department of agriculture":
        if re.search(r"food safety", s): return "covered", "14251 s.1-410(a)", ""
        if re.search(r"aphis|animal and plant", s):
            if "grain inspection" in both: return "partly_or_unclear", "14251 s.1-410(b)?", "listing labels this APHIS but FGIS is normally part of AMS; verify"
            return "covered", "14251 s.1-410(b)", ""
        return "not_named", "", ""
    if a == "department of commerce":
        if re.search(r"international trade admin", both): return "covered", "14251/14343 s.1-411(a)", ""
        if "patent" in s: return "partly_or_unclear", "14343 s.1-411(b)", "only Office of the Commissioner for Patents and subordinate units named; trademark units not"
        if re.search(r"\bnws\b|weather service|nesdis|satellite|climatic data", both):
            return "covered", "14343 s.1-411(c)", "NCDC is now part of NESDIS (NCEI) - inferred" if "climatic" in both else ""
        if "nwseo" in norm(r["laborUnionName"]) or "weather service" in norm(r["laborUnionName"]):
            return "partly_or_unclear", "14343 s.1-411(c)", "NWSEO-represented unit; listing subdivision not NWS/NESDIS"
        return "not_named", "", ""
    return "not_named", "", "agency not named (s.1-419 CIO/IRM offices could still apply; not determinable from listing)"

PSF = re.compile(r"police|fire ?fight|\biaff\b|international association of fire|\bfop\b|fraternal order|security guard|guard force|force protection|\bfire (department|dept|division|protection|and emergency)", re.I)
# NOTE: plain "guard" is NOT used: it matches "National Guard" (~95 DoD records). "IBFO" (Firemen and
# Oilers) is a boiler/plant trades union, not firefighters, and is deliberately not matched.
def psf_hint(r):
    t = " | ".join(str(r.get(k) or "") for k in ("laborUnionName", "local", "subAgencyOrComponent", "activityOfficeRegion", "fileName"))
    m = PSF.search(t)
    return m.group(0) if m else ""
