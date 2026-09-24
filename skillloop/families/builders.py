"""Bounded artifact builders; business truth is checked by a separate oracle."""

from __future__ import annotations

import csv
import re
import unicodedata
from typing import Any

from skillloop.protocol import ProtocolError, canonical_json_line

from .registry import FamilyRegistry

_ID = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
_AMOUNT = re.compile(r"0|[1-9][0-9]{0,9}\Z")
_HEADING = re.compile(r"(#{1,6}) (.+)\Z")
_FENCE_OPEN = re.compile(r"```[a-z0-9_-]{0,20}\Z")
_LINK = re.compile(r"\[([^\[\]()]+)\]\(#([^\s\[\]()#]+)\)")


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise ProtocolError(reason)


def _text(raw: bytes, max_bytes: int) -> str:
    _require(type(raw) is bytes and len(raw) <= max_bytes, "source_byte_limit")
    try:
        value = raw.decode("utf-8")
    except UnicodeError as exc:
        raise ProtocolError("invalid_utf8") from exc
    _require(not value.startswith("\ufeff") and unicodedata.normalize("NFC", value) == value,
             "source_encoding")
    _require(all(not unicodedata.category(char).startswith("C") or char in "\r\n" for char in value),
             "control_or_format_character")
    return value


def _field(value: str, limit: int = 64) -> str:
    _require(0 < len(value) <= limit and value == value.strip(), "field_text_boundary")
    return value


def _csv_quote_grammar(line: str) -> None:
    state = "start"
    i = 0
    while i < len(line):
        char = line[i]
        if state == "quoted":
            if char == '"':
                if i + 1 < len(line) and line[i + 1] == '"':
                    i += 1
                else:
                    state = "closed"
        elif char == ",":
            state = "start"
        elif state == "closed":
            raise ProtocolError("csv_after_quote")
        elif char == '"':
            _require(state == "start", "csv_bare_quote")
            state = "quoted"
        else:
            state = "unquoted"
        i += 1
    _require(state != "quoted", "csv_unclosed_quote")


def _csv(raw: bytes, header: list[str], max_rows: int, max_bytes: int) -> list[dict[str, str]]:
    value = _text(raw, max_bytes)
    _require(value.endswith("\n"), "csv_final_newline")
    if "\r" in value:
        _require("\r" not in value.replace("\r\n", "") and "\n" not in value.replace("\r\n", ""),
                 "csv_mixed_line_endings")
        value = value.replace("\r\n", "\n")
    lines = value[:-1].split("\n")
    _require(1 <= len(lines) <= max_rows + 1, "csv_row_limit")
    decoded: list[list[str]] = []
    for line in lines:
        _require(bool(line), "csv_blank_record")
        _csv_quote_grammar(line)
        try:
            fields = next(csv.reader([line], strict=True))
        except csv.Error as exc:
            raise ProtocolError("csv_parse") from exc
        _require(len(fields) == len(header), "csv_column_count")
        decoded.append(fields)
    _require(decoded[0] == header, "csv_header_order")
    return [dict(zip(header, fields, strict=True)) for fields in decoded[1:]]


def _table(profile: dict[str, Any], inputs: dict[str, bytes]) -> dict[str, Any]:
    mapping, limits = profile["mapping"], profile["limits"]
    _text(inputs["notes"], limits["notes_source_bytes"])
    directory = _csv(inputs["directory"], mapping["directory_header"], limits["rows"], limits["source_bytes"])
    records = _csv(inputs["records"], mapping["records_header"], limits["rows"], limits["source_bytes"])
    buckets: dict[str, dict[str, Any]] = {}
    for row in directory:
        key = row[mapping["directory_key"]]
        _require(bool(_ID.fullmatch(key)) and key not in buckets, "directory_key")
        buckets[key] = {"label": _field(row[mapping["label"]], limits["name_codepoints"]),
                        "sum": 0, "count": 0}
    seen: set[str] = set()
    for row in records:
        record_id = row[mapping["record_id"]]
        key = row[mapping["foreign_key"]]
        amount = row[mapping["amount"]]
        state = row[mapping["state"]]
        _require(bool(_ID.fullmatch(record_id)) and record_id not in seen, "record_id")
        seen.add(record_id)
        _require(key in buckets, "foreign_key")
        _require(bool(_AMOUNT.fullmatch(amount)) and int(amount) <= 1_000_000_000, "amount_lexeme")
        _require(state in mapping["states"], "unknown_state")
        if state == mapping["included_state"]:
            buckets[key]["sum"] += int(amount)
            buckets[key]["count"] += 1
    output = mapping["output"]
    return {output["items"]: [{output["key"]: key, output["label"]: buckets[key]["label"],
                               output["total"]: buckets[key]["sum"],
                               output["count"]: buckets[key]["count"]} for key in sorted(buckets)]}


def _markdown(profile: dict[str, Any], inputs: dict[str, bytes]) -> dict[str, Any]:
    limits = profile["limits"]
    _text(inputs["notes"], limits["notes_source_bytes"])
    value = _text(inputs["document"], limits["source_bytes"])
    _require("\r" not in value and value.endswith("\n"), "markdown_line_endings")
    lines = value[:-1].split("\n")
    _require(len(lines) <= limits["lines"], "markdown_line_limit")
    headings: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    anchors: set[str] = set()
    fenced = False
    for line_number, line in enumerate(lines, 1):
        if line.startswith("```"):
            if fenced:
                _require(line == "```", "markdown_fence_close")
            else:
                _require(bool(_FENCE_OPEN.fullmatch(line)), "markdown_fence_open")
            fenced = not fenced
            continue
        if fenced:
            continue
        _require(line == line.strip(), "markdown_line_whitespace")
        if line.startswith("#"):
            match = _HEADING.fullmatch(line)
            _require(match is not None, "markdown_heading_syntax")
            title = _field(match.group(2))
            _require(all(char.isalnum() or char in " -" for char in title), "markdown_heading_text")
            stem = "-".join(title.lower().split())
            _require(bool(stem) and any(char.isalnum() for char in stem), "markdown_empty_anchor")
            anchor = stem
            suffix = 2
            while anchor in anchors:
                anchor = f"{stem}-{suffix}"
                suffix += 1
            anchors.add(anchor)
            headings.append({"anchor": anchor, "level": len(match.group(1)), "line": line_number, "text": title})
            continue
        _require(not any(char in line for char in "`\\<>!*_~"), "markdown_unsupported_syntax")
        cursor = 0
        for match in _LINK.finditer(line):
            _require(not any(char in line[cursor:match.start()] for char in "[]()"),
                     "markdown_unpaired_delimiter")
            label, target = _field(match.group(1)), match.group(2)
            _require(all(char.isalnum() or char == "-" for char in target), "markdown_local_target")
            links.append({"label": label, "line": line_number, "target": "#" + target})
            cursor = match.end()
        _require(not any(char in line[cursor:] for char in "[]()"), "markdown_unpaired_delimiter")
    _require(not fenced, "markdown_unclosed_fence")
    _require(bool(headings), "markdown_no_heading")
    _require(all(link["target"][1:] in anchors for link in links), "markdown_unresolved_link")
    return {"headings": headings, "links": links}


def build_value(profile_id: str, inputs: dict[str, bytes], registry: FamilyRegistry | None = None) -> dict[str, Any]:
    profile = (registry or FamilyRegistry()).profile(profile_id)
    _require(type(inputs) is dict and set(inputs) == set(profile["input_bindings"]), "input_binding_names")
    if profile["family_id"] == "table-report":
        return _table(profile, inputs)
    if profile["family_id"] == "markdown-index":
        return _markdown(profile, inputs)
    raise ProtocolError("unknown_family")


def build_artifact(profile_id: str, inputs: dict[str, bytes], registry: FamilyRegistry | None = None) -> bytes:
    loaded = registry or FamilyRegistry()
    value = build_value(profile_id, inputs, loaded)
    raw = canonical_json_line(value)
    _require(len(raw) <= loaded.profile(profile_id)["max_output_bytes"], "output_byte_limit")
    return raw
