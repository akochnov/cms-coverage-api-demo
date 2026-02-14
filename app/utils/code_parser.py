"""Parse CPT/HCPCS and ICD-10 code mappings from CMS article sub-endpoint data."""

import html
import re


def unescape_html(text: str) -> str:
    """Unescape CMS double-encoded HTML entities."""
    if not text:
        return ""
    text = (text
            .replace("&lt;", "<").replace("&gt;", ">")
            .replace("&sol;", "/").replace("&amp;", "&").replace("&quot;", '"'))
    return html.unescape(text)


def extract_cpt_codes_from_paragraph(paragraph_html: str) -> list[str]:
    """Extract CPT/HCPCS codes referenced in an ICD-10 group paragraph.

    Handles patterns like:
    - "CPT code 81235"
    - "CPT codes 81162-81167, 81212, 81215"
    - "HCPCS code J9271"
    - "CPT/HCPCS codes 99201-99215"
    Returns list of individual code strings (ranges expanded for numeric codes).
    """
    if not paragraph_html:
        return []

    text = unescape_html(paragraph_html)
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    codes: list[str] = []

    # Match "CPT code(s) <code_list>" or "HCPCS code(s) <code_list>"
    pattern = r"(?:CPT/?HCPCS|CPT|HCPCS)\s+codes?\s+([\w\d,\s\-/and]+?)(?:\s+(?:is|are|when|for|if|,\s*(?:CPT|HCPCS))|[.;:\(]|$)"
    for match in re.finditer(pattern, text, re.IGNORECASE):
        code_str = match.group(1).strip()
        codes.extend(_parse_code_list(code_str))

    # Also match standalone code patterns like "81235, 81236" after "for" or similar
    # and J-code patterns
    if not codes:
        jcode_pattern = r"\b([A-Z]\d{4})\b"
        for m in re.finditer(jcode_pattern, text):
            code = m.group(1)
            if code not in codes:
                codes.append(code)

    return codes


def _parse_code_list(code_str: str) -> list[str]:
    """Parse a comma/space separated list of codes, expanding numeric ranges."""
    codes: list[str] = []
    # Remove "and" conjunctions
    code_str = re.sub(r"\band\b", ",", code_str, flags=re.IGNORECASE)
    # Split on commas and slashes
    parts = re.split(r"[,/]+", code_str)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Check for range: "81162-81167"
        range_match = re.match(r"^(\d{4,5})\s*[-–]\s*(\d{4,5})$", part)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            if end - start <= 500:  # sanity check
                codes.extend(str(c) for c in range(start, end + 1))
            continue

        # Check for alpha-prefixed range: "J9271-J9275"
        alpha_range = re.match(r"^([A-Z])(\d{4})\s*[-–]\s*([A-Z])(\d{4})$", part)
        if alpha_range and alpha_range.group(1) == alpha_range.group(3):
            prefix = alpha_range.group(1)
            start, end = int(alpha_range.group(2)), int(alpha_range.group(4))
            if end - start <= 500:
                codes.extend(f"{prefix}{c:04d}" for c in range(start, end + 1))
            continue

        # Single code
        single = re.match(r"^([A-Z]?\d{4,5})$", part)
        if single:
            codes.append(single.group(1))

    return codes


def build_cpt_icd10_mapping(
    hcpc_codes: list[dict],
    icd10_covered: list[dict],
    icd10_covered_groups: list[dict],
) -> dict:
    """Build a structured CPT/HCPCS → ICD-10 mapping from article sub-endpoint data.

    Returns:
        {
            "by_cpt": {
                "81235": {
                    "code": "81235",
                    "description": "...",
                    "icd10_codes": [{"code": "C34.10", "description": "..."}]
                }
            },
            "groups": [
                {
                    "group_num": 1,
                    "paragraph": "...",
                    "cpt_codes": ["81235"],
                    "icd10_codes": [{"code": "C34.10", "description": "..."}]
                }
            ],
            "unmapped_icd10": [...]  # ICD-10 codes not linked to any specific CPT
        }
    """
    # Index HCPC codes by code_id
    hcpc_by_id = {}
    for h in hcpc_codes:
        cid = h.get("hcpc_code_id", "").strip()
        if cid:
            hcpc_by_id[cid] = {
                "code": cid,
                "description": h.get("long_description") or h.get("short_description", ""),
                "group": h.get("hcpc_code_group"),
            }

    # Index ICD-10 covered codes by group number
    icd10_by_group: dict[int, list[dict]] = {}
    for ic in icd10_covered:
        grp = ic.get("icd10_covered_group")
        entry = {
            "code": ic.get("icd10_code_id", "").strip(),
            "description": ic.get("description", ""),
            "asterisk": ic.get("asterisk", ""),
        }
        if grp is not None:
            icd10_by_group.setdefault(grp, []).append(entry)

    # Parse each covered group paragraph to extract CPT codes
    all_hcpc_ids = set(hcpc_by_id.keys())
    groups = []
    cpt_to_icd10: dict[str, list[dict]] = {}

    for grp in icd10_covered_groups:
        grp_num = grp.get("icd10_covered_group")
        paragraph = grp.get("paragraph", "")
        extracted_cpts = extract_cpt_codes_from_paragraph(paragraph)
        icd10_list = icd10_by_group.get(grp_num, [])

        groups.append({
            "group_num": grp_num,
            "paragraph": unescape_html(paragraph),
            "cpt_codes": extracted_cpts,
            "icd10_codes": icd10_list,
        })

        if extracted_cpts:
            for cpt in extracted_cpts:
                cpt_to_icd10.setdefault(cpt, []).extend(icd10_list)
        else:
            # Fallback: associate with all HCPCS codes in article
            for cpt in all_hcpc_ids:
                cpt_to_icd10.setdefault(cpt, []).extend(icd10_list)

    # Build by_cpt view
    by_cpt = {}
    for cpt_code, icd_list in cpt_to_icd10.items():
        # Deduplicate ICD-10 codes
        seen = set()
        deduped = []
        for ic in icd_list:
            if ic["code"] not in seen:
                seen.add(ic["code"])
                deduped.append(ic)
        info = hcpc_by_id.get(cpt_code, {"code": cpt_code, "description": ""})
        by_cpt[cpt_code] = {
            "code": cpt_code,
            "description": info["description"],
            "icd10_codes": deduped,
        }

    return {
        "by_cpt": by_cpt,
        "groups": groups,
        "hcpc_codes": hcpc_by_id,
    }


def build_icd10_to_cpt_mapping(
    hcpc_codes: list[dict],
    icd10_covered: list[dict],
    icd10_covered_groups: list[dict],
) -> dict:
    """Build an ICD-10 → CPT/HCPCS reverse mapping.

    Returns dict keyed by ICD-10 code with list of associated CPT codes.
    """
    forward = build_cpt_icd10_mapping(hcpc_codes, icd10_covered, icd10_covered_groups)
    reverse: dict[str, dict] = {}

    for cpt_code, cpt_info in forward["by_cpt"].items():
        for icd in cpt_info["icd10_codes"]:
            icd_code = icd["code"]
            if icd_code not in reverse:
                reverse[icd_code] = {
                    "code": icd_code,
                    "description": icd["description"],
                    "cpt_codes": [],
                }
            if cpt_code not in [c["code"] for c in reverse[icd_code]["cpt_codes"]]:
                reverse[icd_code]["cpt_codes"].append({
                    "code": cpt_code,
                    "description": cpt_info["description"],
                })

    return reverse
