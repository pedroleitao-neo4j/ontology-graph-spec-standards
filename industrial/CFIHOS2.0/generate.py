#!/usr/bin/env python3
"""Generates the CFIHOS 2.0 ontology from the official CFIHOS V2.0 Data Dictionary (C-DM-002).

Usage: python3 generate.py [path/to/C-DM-002-Data-Dictionary-V2.0-FINAL.xlsx]

Without a path, the data dictionary is downloaded from the JIP36 CFIHOS site. Writes model.json and model.yaml next to
this script. Uses only the Python standard library.
"""

import json
import re
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

DATA_DICTIONARY_URL = (
    "https://www.jip36-cfihos.org/wp-content/uploads/2024/10/C-DM-002-Data-Dictionary-V2.0-FINAL.xlsx"
)
SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
PCA = "https://www.posccaesar.org/cfihos/v2.0/"
MAX_DESCRIPTION = 1024

# Supertype/subtype pairs. The dictionary records these as unnamed identifying relationships; in the graph a subtype
# node also carries its supertype's label.
SUBTYPES = {
    "LEAF NODE COMMISSIONING UNIT": "COMMISSIONING UNIT",
    "VENDOR DOCUMENT": "DOCUMENT MASTER",
    "EQUIPMENT MODEL PART": "MODEL PART",
    "SPARE PART": "MODEL PART",
    "KIT": "MODEL PART",
    "SPECIAL TOOL": "MODEL PART",
    "CONSUMABLE": "MODEL PART",
    "QUALITATIVE PROPERTY": "PROPERTY",
    "QUANTITATIVE PROPERTY": "PROPERTY",
    "PURCHASE ORDER ITEM FOR TAG": "PURCHASE ORDER ITEM",
    "PURCHASE ORDER ITEM FOR MODEL PART": "PURCHASE ORDER ITEM",
    "PURCHASE ORDER ITEM FOR BULK": "PURCHASE ORDER ITEM",
    "TAG CLASS": "TAG OR EQUIPMENT CLASS",
    "EQUIPMENT CLASS": "TAG OR EQUIPMENT CLASS",
    "NON ABSTRACT TAG OR EQUIPMENT CLASS": "TAG OR EQUIPMENT CLASS",
    "TAG CLASS PROPERTY": "TAG OR EQUIPMENT CLASS PROPERTY",
    "EQUIPMENT CLASS PROPERTY": "TAG OR EQUIPMENT CLASS PROPERTY",
}

# Relationship verbs for the unnamed relationships that aren't subtypes, keyed by (parent, child).
UNNAMED_VERBS = {
    ("MODEL PART", "MODEL PART"): "is the original model part of",
    ("COMPONENT ROLE", "TAG OR EQUIPMENT CLASS COMPONENT"): "is the role of",
    ("PROPERTY GROUP ALLOWED FOR PURPOSE", "PROPERTY TO GROUP ASSIGNMENT"): "groups",
    ("TAG", "SPARE PART INTERCHANGEABILITY RECORD EQUIPMENT"): "is fulfilled by",
}

# Relationship types for verbs that don't read well as a type once upper-cased, keyed by verb.
TYPE_OVERRIDES = {
    "is complemented by zero, one or more": "IS_COMPLEMENTED_BY",
    "can be implement through": "CAN_BE_IMPLEMENTED_THROUGH",
    "is document in": "IS_DOCUMENTED_IN",
    "is composing (or a part) of": "IS_PART_OF",
    "is made of / has": "IS_MADE_OF",
    "parent class is specialised in child class": "IS_SPECIALISED_IN",
    "is, for this purchase order, the status required at hand over": "IS_THE_STATUS_REQUIRED_AT_HANDOVER_FOR",
    "is the dimension in which are measured, when quantitative,": "IS_THE_DIMENSION_OF",
}

TYPES = {"Integer": "INTEGER", "Boolean (Yes/No)": "BOOLEAN", "Date": "DATE", "NUM": "FLOAT"}

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def read_sheets(path):
    """Reads every sheet of an xlsx workbook as a list of rows of strings."""
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
    workbook = ET.fromstring(z.read("xl/workbook.xml"))
    targets = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    sheets = {}
    for sheet in workbook.find("m:sheets", NS):
        target = targets[sheet.get(f"{{{NS['r']}}}id")].lstrip("/")
        target = target if target.startswith("xl/") else "xl/" + target
        rows = []
        for row in ET.fromstring(z.read(target)).iter(f"{{{NS['m']}}}row"):
            cells = {}
            for c in row.findall("m:c", NS):
                if c.get("t") == "inlineStr":
                    value = "".join(t.text or "" for t in c.iter(f"{{{NS['m']}}}t"))
                else:
                    v = c.find("m:v", NS)
                    value = None if v is None else v.text
                    if value is not None and c.get("t") == "s":
                        value = shared[int(value)]
                if value is not None:
                    column = 0
                    for ch in re.match(r"[A-Z]+", c.get("r")).group():
                        column = column * 26 + ord(ch) - 64
                    cells[column - 1] = value.replace("_x000D_", "").strip()
            if cells:
                rows.append([cells.get(i, "") for i in range(max(cells) + 1)] + [""] * 14)
        sheets[sheet.get("name")] = rows[1:]
    return sheets


def words(text):
    return re.findall(r"[A-Za-z0-9]+", text)


def label(entity):
    return "".join(w.capitalize() for w in words(entity))


def camel(name):
    ws = [w.lower() for w in words(name)]
    return ws[0] + "".join(w.capitalize() for w in ws[1:])


def rel_type(verb):
    return TYPE_OVERRIDES.get(verb) or "_".join(w.upper() for w in words(verb))


def tidy(text):
    """Collapses whitespace and normalises the doubled quotes the dictionary uses."""
    return re.sub(r"\s+", " ", text.replace("''", "'")).strip()


def sentence(text):
    text = tidy(text)
    return text if not text or text[-1] in ".:!?" else text + "."


def describe(*parts):
    """Joins the parts that fit within the description limit, keeping the first one even when it must be cut."""
    out = ""
    for i, part in enumerate(p for p in parts if p):
        candidate = f"{out} {part}".strip()
        if len(candidate) <= MAX_DESCRIPTION:
            out = candidate
        elif i == 0:
            out = part[: MAX_DESCRIPTION - 1].rsplit(" ", 1)[0] + "…"
    return out


def example(text):
    text = tidy(re.sub(r"^Example\s*:\s*", "", text))
    return f"e.g. `{text}`." if text and "`" not in text else ""


def build(sheets):
    dictionary = sheets["Data Dictionary"]
    entities, attributes = {}, {}
    for row in dictionary:
        if row[1].startswith("Entity"):
            entities[row[2]] = row
            attributes[row[2]] = []
        elif row[1].startswith("Attribute"):
            attributes[row[2]].append(row)

    nodes = {}
    for name, row in entities.items():
        node_label = label(name)
        properties, keys, constraints = {}, [], {}
        for attr in attributes[name]:
            pid = camel(attr[3])
            fmt = attr[8]
            length = re.match(r"Text, max (\d+) characters", fmt)
            prop = {
                "type": "STRING" if length else TYPES.get(fmt, "FLOAT" if fmt.startswith("Decimal") else "STRING"),
                "name": pid,
            }
            prop["description"] = describe(
                sentence(attr[4]),
                f"Must be present in {attr[9]}." if attr[9] else "",
                f"At most {length.group(1)} characters." if length else "",
                example(attr[6]),
                sentence(attr[5]),
            )
            if attr[10]:
                prop["reference"] = PCA + attr[10]
            if length:
                prop["pattern"] = f"^[\\s\\S]{{0,{length.group(1)}}}$"
            prop["extensions"] = {"custom": {"cfihosCode": attr[10], "format": fmt, "requirement": attr[7]}}
            properties[pid] = prop
            if attr[7] == "Identifier":
                keys.append(pid)
            elif attr[7] == "Mandatory":
                constraints[f"exists_{node_label}_{pid}"] = {
                    "type": "EXISTS",
                    "properties": [pid],
                    "name": f"{pid}_{node_label}_exists",
                }
        if keys:
            constraints = {
                f"key_{node_label}": {
                    "type": "KEY",
                    "properties": keys,
                    "name": f"{'_'.join(keys)}_{node_label}_key",
                },
                **constraints,
            }
        labels = {"identifier": node_label}
        if name in SUBTYPES:
            labels["implied"] = [label(SUBTYPES[name])]
        nodes[node_label] = {
            "labels": labels,
            "description": describe(sentence(row[4]), sentence(row[5])),
            "reference": PCA + row[10],
            "properties": properties,
            "constraints": constraints,
            "extensions": {"custom": {"cfihosCode": row[10], "section": row[0], "dataSource": row[11]}},
        }

    # The parent-to-child verb of an unnamed relationship is otherwise recorded on the child's foreign key attributes.
    attribute_verbs = {}
    for name, attrs in attributes.items():
        for attr in attrs:
            if attr[9] and attr[13] and attr[13] != "is subtype of":
                attribute_verbs.setdefault((attr[9], name), attr[13])

    relationships = {}
    for row in sheets["Relationships"]:
        section, p2c, parent, verb, child, kind, _, optionality, c2p = row[:9]
        if not verb:
            if SUBTYPES.get(child) == parent or (parent == child and parent in SUBTYPES):
                continue  # A subtype, or a subtype's copy of its supertype's self relationship.
            verb = UNNAMED_VERBS.get((parent, child)) or attribute_verbs[(parent, child)]
            p2c = f"One {parent} {verb} zero, one or more {child}(S)"
        rtype = rel_type(verb)
        rid = f"{label(parent)}_{rtype}_{label(child)}"
        mandatory = optionality == "Mandatory"
        relationships[rid] = {
            "type": rtype,
            "from": {"node": label(parent)},
            "to": {"node": label(child), **({"count": 1} if mandatory else {"max_count": 1})},
            "description": describe(
                sentence(p2c),
                f"Each {child} has {'exactly one' if mandatory else 'at most one'} {parent}.",
                f"Identifying: the {parent} identifier is part of the {child} key." if kind == "Identifying" else "",
            ),
            "extensions": {"custom": {"verb": verb, "section": section, "identifying": kind == "Identifying"}},
        }

    return {
        "schema": SCHEMA,
        "version": "2.0",
        "id": "cfihos-2.0",
        "name": "CFIHOS 2.0",
        "description": (
            "The Capital Facilities Information Handover Specification (CFIHOS) V2.0 data model, published by IOGP "
            "JIP36 (https://www.jip36-cfihos.org/cfihos-standards/). CFIHOS standardises the engineering data and "
            "documents that contractors and suppliers hand over to the owner/operator of a process or energy "
            "facility: the plant breakdown structure and its tags, the equipment and model parts that fulfil them, "
            "purchase orders and spares, the reference data library (tag and equipment classes, properties, units of "
            "measure, disciplines and document types) that classifies them, and the documents that describe them. "
            "Generated from the CFIHOS V2.0 Data Dictionary (C-DM-002): each entity is a node, each attribute a "
            "property, each identifier a key, and each relationship a relationship from parent to child entity."
        ),
        "nodes": nodes,
        "relationships": relationships,
    }


def yaml(value, indent=0):
    """Emits YAML in block style, with every string JSON-quoted so it is read back unchanged."""
    pad = "  " * indent
    lines = []
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{json.dumps(k)}:")
                lines.append(yaml(v, indent + 1))
            else:
                lines.append(f"{pad}{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}")
    else:
        for v in value:
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}-")
                lines.append(yaml(v, indent + 1))
            else:
                lines.append(f"{pad}- {json.dumps(v, ensure_ascii=False)}")
    return "\n".join(lines)


def main():
    if len(sys.argv) > 1:
        source = sys.argv[1]
    else:
        source = Path(tempfile.mkdtemp()) / "C-DM-002.xlsx"
        # The site rejects Python's default user agent.
        request = urllib.request.Request(DATA_DICTIONARY_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request) as response:
            source.write_bytes(response.read())
    model = build(read_sheets(source))
    out = Path(__file__).parent
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(yaml(model) + "\n")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships")


if __name__ == "__main__":
    main()
