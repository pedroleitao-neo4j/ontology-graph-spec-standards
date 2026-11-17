#!/usr/bin/env python3
"""Generates the IEC CIM (CGMES 3.0) ontology from the official CGMES 3.0 RDFS profile files published by ENTSO-E.

Usage: python3 generate.py [path/to/application-profiles-library | path/to/RDFS folder | path/to/archive.zip]

Without a path, the RDFS files are downloaded from the ENTSO-E application profiles library on GitHub, tag cgmes3.0.
Writes model.json and model.yaml next to this script. Uses only the Python standard library.
"""

import json
import re
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

COMMIT = "8eff738bda72dc3a97fc24bf021dc78773814111"  # tag cgmes3.0 of entsoe/application-profiles-library
RAW = f"https://raw.githubusercontent.com/entsoe/application-profiles-library/{COMMIT}/CGMES/RDFS"
BLOB = f"https://github.com/entsoe/application-profiles-library/blob/{COMMIT}/CGMES/RDFS"
VERSION = "3.0.0"  # of CGMES; the vocabularies are versioned 3.0.0, except the first dynamics profile, 1.0.0
SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
MAX_DESCRIPTION = 1024

# The profiles of IEC 61970-600-2, by the keyword each vocabulary declares, in the order that decides which profile a
# class or property is shown under when several declare it. The file header profile (FH) describes the header of an
# exchange file rather than the power system, so it isn't read.
PROFILES = {
    "EQ": "Equipment",
    "EQBD": "EquipmentBoundary",
    "OP": "Operation",
    "SC": "ShortCircuit",
    "TP": "Topology",
    "SSH": "SteadyStateHypothesis",
    "SV": "StateVariables",
    "DY": "Dynamics",
    "DL": "DiagramLayout",
    "GL": "GeographicalLocation",
}
FILE = "61970-600-2_{}-AP-Voc-RDFS2020.rdf"

BASE = "http://iec.ch/TC57/CIM100"  # the xml:base of every vocabulary, against which #Name references resolve
RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
RDFS = "{http://www.w3.org/2000/01/rdf-schema#}"
CIMS = "{http://iec.ch/TC57/1999/rdf-schema-extensions-19990926#}"
DCAT = "{http://www.w3.org/ns/dcat#}"
DCTERMS = "{http://purl.org/dc/terms/}"

PRIMITIVES = {
    "Float": "FLOAT",
    "Decimal": "FLOAT",
    "Integer": "INTEGER",
    "Boolean": "BOOLEAN",
    "String": "STRING",
    "URI": "STRING",
    "MonthDay": "STRING",
    "DateTime": "ZONED DATETIME",
    "Date": "DATE",
}
VALUE_KINDS = ("Primitive", "CIMDatatype", "Compound", "enumeration")  # stereotypes of the classes that are values


def words(text):
    """The words of a CamelCase name, e.g. DCConductingEquipment → DC, Conducting, Equipment."""
    return re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z\d]+|[A-Z]+|\d+", text)


def rel_type(name):
    return "HAS_" + "_".join(w.upper() for w in words(name))


def tidy(text):
    return re.sub(r"\s+", " ", text or "").strip()


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


def phrase(lower, upper):
    """How a multiplicity reads, e.g. (0, 1) → 'at most one'."""
    if (lower, upper) == (1, 1):
        return "exactly one"
    if (lower, upper) == (0, 1):
        return "at most one"
    if lower == 1 and upper is None:
        return "one or more"
    if lower == 0 and upper is None:
        return "zero or more"
    if lower == upper:
        return f"exactly {lower}"
    return f"between {lower} and {'*' if upper is None else upper}"


def multiplicity(lower, upper):
    return f"{lower}..{'*' if upper is None else upper}"


def ends(lower, upper):
    """The count constraints of a relationship end, from a multiplicity. Zero or more is unconstrained."""
    if (lower, upper) == (1, 1):
        return {"count": 1}
    if (lower, upper) == (0, 1):
        return {"max_count": 1}
    if (lower, upper) == (0, None):
        return {}
    return {k: v for k, v in (("min_count", lower), ("max_count", upper)) if v or v is not None}


#----------------------------------
#   Reading the RDFS profiles
#----------------------------------


def iri(ref):
    """A reference as a full IRI, e.g. #Terminal → http://iec.ch/TC57/CIM100#Terminal."""
    return BASE + ref if ref.startswith("#") else ref


def local(ref):
    return ref.rsplit("#", 1)[-1]


def resource(element, tag):
    found = element.find(tag)
    return iri(found.get(RDF + "resource")) if found is not None and found.get(RDF + "resource") else None


def read_multiplicity(ref):
    """A cims:multiplicity as (lower, upper), with None for unbounded, e.g. M:0..n → (0, None) and M:1 → (1, 1)."""
    bounds = local(ref).split(":", 1)[1].split("..")
    lower, upper = bounds[0], bounds[-1]
    return int(lower), None if upper == "n" else int(upper)


def read_profile(keyword, path):
    """The descriptions of one vocabulary, keyed by IRI, each with the line it starts on in the file."""
    lines = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = re.search(r'rdf:about\s*=\s*"([^"]+)"', line)
        if match:
            lines.setdefault(iri(match.group(1)), number)
    root = ET.parse(path).getroot()
    header = next(d for d in root if resource(d, RDF + "type") == "http://www.w3.org/2002/07/owl#Ontology")
    if header.findtext(DCAT + "keyword") != keyword:
        sys.exit(f"{path.name}: expected the {keyword} profile, found {header.findtext(DCAT + 'keyword')}")
    out = {}
    for d in root:
        about = d.get(RDF + "about")
        if not about:
            continue
        out[iri(about)] = {
            "label": d.findtext(RDFS + "label"),
            "comment": d.findtext(RDFS + "comment") or "",
            "type": resource(d, RDF + "type"),
            "stereotypes": [local(s.get(RDF + "resource")) if s.get(RDF + "resource") else s.text
                            for s in d.findall(CIMS + "stereotype")],
            "superclasses": [iri(s.get(RDF + "resource")) for s in d.findall(RDFS + "subClassOf")],
            "category": resource(d, CIMS + "belongsToCategory"),
            "domain": resource(d, RDFS + "domain"),
            "range": resource(d, RDFS + "range"),
            "dataType": resource(d, CIMS + "dataType"),
            "multiplicity": resource(d, CIMS + "multiplicity"),
            "inverse": resource(d, CIMS + "inverseRoleName"),
            "used": d.findtext(CIMS + "AssociationUsed"),
            "fixed": d.findtext(CIMS + "isFixed"),
            "profile": keyword,
            "reference": f"{BLOB}/{path.name}#L{lines.get(iri(about), 1)}",
        }
    return out, tidy(header.findtext(DCTERMS + "title"))


def find_files(source):
    """The RDFS file of each profile: downloaded, or found in a given folder or zip archive of the library."""
    if source is None:
        folder = Path(tempfile.mkdtemp())
        for name in PROFILES.values():
            with urllib.request.urlopen(f"{RAW}/{FILE.format(name)}") as response:
                (folder / FILE.format(name)).write_bytes(response.read())
        source = folder
    elif source.is_file():
        folder = Path(tempfile.mkdtemp())
        zipfile.ZipFile(source).extractall(folder)
        source = folder
    files = {}
    for keyword, name in PROFILES.items():
        # The library also holds draft (Beta) vocabularies of the next edition; only the CGMES 3.0 ones are read.
        found = [p for p in source.rglob(FILE.format(name)) if "Beta" not in str(p)]
        if not found:
            sys.exit(f"{source}: no {FILE.format(name)}")
        files[keyword] = found[0]
    return files


def merge(files):
    """Every class and property of every profile, keyed by IRI: the declarations of each, in profile order."""
    declarations, titles = {}, {}
    for keyword, path in files.items():
        profile, titles[keyword] = read_profile(keyword, path)
        for about, d in profile.items():
            declarations.setdefault(about, []).append(d)
    return declarations, titles


#----------------------------------
#   The CIM model as data
#----------------------------------


def build(files):
    declarations, titles = merge(files)

    def first(about, key):
        return next((d[key] for d in declarations.get(about, []) if d[key]), None)

    def stereotypes(about):
        return {s for d in declarations.get(about, []) for s in d["stereotypes"]}

    def is_class(about):
        return any(d["type"] == RDFS[1:-1] + "Class" for d in declarations[about])

    classes = [a for a in declarations if is_class(a) and not stereotypes(a) & set(VALUE_KINDS)]
    nodes_of = {a: local(a) for a in classes}
    if len(set(nodes_of.values())) != len(nodes_of):
        sys.exit("two classes share a name")

    # The literals of every enumeration: the descriptions whose type is the enumeration.
    literals = {}
    for about, decls in declarations.items():
        kind = decls[0]["type"]
        if kind in declarations and "enumeration" in stereotypes(kind):
            values = literals.setdefault(kind, [])
            if local(about).split(".", 1)[1] not in values:
                values.append(local(about).split(".", 1)[1])

    def bounds(about):
        """The loosest multiplicity the profiles declare, since a merged graph holds the data of every profile."""
        declared = [read_multiplicity(d["multiplicity"]) for d in declarations[about] if d["multiplicity"]]
        if not declared:
            return 0, 1
        lowers, uppers = [l for l, _ in declared], [u for _, u in declared]
        return min(lowers), None if None in uppers else max(uppers)

    def profiles_of(about):
        return [d["profile"] for d in declarations[about]]

    def primary(about):
        """The profile a class or property is defined in: the first that declares it other than as a description of
        a class defined elsewhere."""
        decls = declarations[about]
        return next((d for d in decls if "Description" not in d["stereotypes"]), decls[0])

    def unit_of(datatype):
        """The fixed unit of a CIM data type with its multiplier, e.g. ActivePower → MW, or None for none."""
        fixed = {local(a).split(".", 1)[1]: first(a, "fixed") for a in declarations if a.startswith(datatype + ".")}
        text = "".join(v for v in (fixed.get("multiplier"), fixed.get("unit")) if v and v != "none")
        return text or None

    def property_type(about):
        """(Neo4j type, allowed values, CIM type, unit) of an attribute."""
        datatype, enumeration = first(about, "dataType"), first(about, "range")
        if enumeration:
            if enumeration not in literals:
                sys.exit(f"{local(about)}: {local(enumeration)} is not an enumeration")
            return "STRING", literals[enumeration], local(enumeration), None
        name = local(datatype)
        kinds = stereotypes(datatype)
        if "Primitive" in kinds and name in PRIMITIVES:
            return PRIMITIVES[name], [], name, None
        if "CIMDatatype" in kinds:  # a value with a fixed unit and multiplier, typed by its value attribute
            value = first(datatype + ".value", "dataType")
            return PRIMITIVES[local(value)], [], name, unit_of(datatype)
        if "Compound" in kinds:  # a structured value, e.g. StreetAddress
            return "STRING", [], name, None
        sys.exit(f"{local(about)}: unknown data type {datatype}")

    nodes, relationships = {}, {}
    for about in classes:
        name = nodes_of[about]
        main = primary(about)
        supers = sorted({s for d in declarations[about] for s in d["superclasses"]})
        if len(supers) > 1:
            sys.exit(f"{name} has more than one superclass: {supers}")
        # CIMXML (IEC 61970-552) identifies every object by its rdf:ID, or rdf:about where a profile describes an
        # object defined in another; the class model itself only names the mRID of an IdentifiedObject.
        properties = {
            "rdfId": {
                "type": "STRING",
                "name": "rdfId",
                "description": f"The identifier of the {name}: the rdf:ID of its element in a CGMES (CIMXML) file, "
                "or the rdf:about, without its leading #, of the elements that describe it in other profiles. For "
                "an IdentifiedObject it is derived from its mRID.",
                "reference": "https://www.entsoe.eu/digital/cim/cim-for-grid-models-exchange/",
                "extensions": {"custom": {"cimType": "rdf:ID"}},
            }
        }
        constraints = {f"key_{name}": {"type": "KEY", "properties": ["rdfId"], "name": f"rdfId_{name}_key"}}

        attributes = sorted(
            a for a in declarations
            if first(a, "domain") == about and "attribute" in stereotypes(a)
        )
        for attribute in attributes:
            pid = first(attribute, "label")
            if pid in properties:
                sys.exit(f"{name}.{pid} is declared twice")
            lower, upper = bounds(attribute)
            neo4j, one_of, cim_type, unit = property_type(attribute)
            if upper is None or upper > 1:
                neo4j = f"LIST<{neo4j}>"
            kinds = stereotypes(attribute)
            prop = {
                "type": neo4j,
                "name": pid,
                "description": describe(
                    sentence(primary(attribute)["comment"]),
                    f"Multiplicity {multiplicity(lower, upper)}." if (lower, upper) != (0, 1) else "",
                    f"CIM type {cim_type}, in {unit}." if unit else "",
                ),
                "reference": primary(attribute)["reference"],
                "extensions": {
                    "custom": {
                        k: v
                        for k, v in (
                            ("cimType", cim_type),
                            ("unit", unit),
                            ("lower", lower),
                            ("upper", upper),
                            ("profiles", profiles_of(attribute)),
                            ("european", attribute.startswith(BASE + "-European#")),
                            ("deprecated", "deprecated" in kinds),
                        )
                        if v is not None and v is not False
                    }
                },
            }
            if one_of:
                prop["one_of"] = one_of
            properties[pid] = prop
            if lower >= 1:
                constraints[f"exists_{name}_{pid}"] = {
                    "type": "EXISTS",
                    "properties": [pid],
                    "name": f"{pid}_{name}_exists",
                }

        category = local(main["category"]) if main["category"] else ""
        nodes[name] = {
            "labels": {
                "identifier": name,
                **({"implied": [local(s) for s in supers]} if supers else {}),
            },
            **({"description": describe(sentence(main["comment"]))} if tidy(main["comment"]) else {}),
            "reference": main["reference"],
            "properties": properties,
            "constraints": constraints,
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (
                        ("profile", main["profile"]),
                        ("profiles", profiles_of(about)),
                        # Only the dynamics profile keeps the CIM packages; the others put every class in the profile.
                        ("package", category.removeprefix("Package_") if not category.endswith("Profile") else None),
                        ("abstract", "concrete" not in stereotypes(about)),
                        ("european", about.startswith(BASE + "-European#")),
                        ("deprecated", "deprecated" in stereotypes(about)),
                    )
                    if v is not None and v is not False
                }
            },
        }

    # Each association is declared at both ends; the end CGMES exchanges, AssociationUsed Yes, is the relationship.
    for about in sorted(a for a in declarations if first(a, "used") == "Yes"):
        source, target, inverse = first(about, "domain"), first(about, "range"), first(about, "inverse")
        if source not in nodes_of or target not in nodes_of:
            sys.exit(f"{local(about)} doesn't join two classes")
        if inverse not in declarations or first(inverse, "used") != "No":
            sys.exit(f"{local(about)}: its inverse {local(inverse or '')} isn't the unused end")
        name, target_name = nodes_of[source], nodes_of[target]
        role, inverse_role = first(about, "label"), first(inverse, "label")
        rtype = rel_type(role)
        rid = f"{name}_{rtype}_{target_name}"
        while rid in relationships:
            rid += "_2"
        (lower, upper), opposite = bounds(about), bounds(inverse)
        relationships[rid] = {
            "type": rtype,
            "from": {"node": name, **ends(lower, upper)},
            "to": {"node": target_name, **ends(*opposite)},
            "description": describe(
                sentence(primary(about)["comment"]),
                f"Each {name} has {phrase(lower, upper)} {target_name}.",
                f"The inverse role is {target_name}.{inverse_role}: each {target_name} has {phrase(*opposite)} {name}.",
            ),
            "reference": primary(about)["reference"],
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (
                        ("role", f"{name}.{role}"),
                        ("inverseRole", f"{target_name}.{inverse_role}"),
                        ("lower", lower),
                        ("upper", upper),
                        ("inverseLower", opposite[0]),
                        ("inverseUpper", opposite[1]),
                        ("profiles", profiles_of(about)),
                        ("european", about.startswith(BASE + "-European#")),
                        ("deprecated", "deprecated" in stereotypes(about)),
                    )
                    if v is not None and v is not False
                }
            },
        }

    # An association whose ends are both unused would be lost; a supertype no node was built for means a misread.
    for about in declarations:
        if first(about, "used") == "No" and first(first(about, "inverse") or about, "used") != "Yes":
            sys.exit(f"{local(about)}: neither end of the association is used")
    for node in nodes.values():
        for implied in node["labels"].get("implied", []):
            if implied not in nodes:
                sys.exit(f"superclass {implied} of {node['labels']['identifier']} is not a class")

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "id": f"cim-cgmes-{VERSION}",
        "name": "IEC CIM (CGMES 3.0)",
        "description": (
            "The IEC Common Information Model (CIM, IEC 61970 and IEC 61968) for power systems, as profiled by "
            "the Common Grid Model Exchange Standard (CGMES) 3.0, IEC 61970-600, published by ENTSO-E "
            "(https://www.entsoe.eu/digital/cim/cim-for-grid-models-exchange/). CGMES is how European transmission "
            "system operators exchange grid models: the equipment of the network and its boundaries, its topology, "
            "the steady state hypothesis and state variables of a power flow, operational limits and measurements, "
            "short circuit and dynamic models, and diagram layout and geographical location. Generated from the RDFS "
            "vocabularies of the ten CGMES 3.0 profiles (https://github.com/entsoe/application-profiles-library, tag "
            "cgmes3.0), merged into one model: each class is a node, each attribute a property, each association a "
            "relationship from the end that CGMES exchanges, and each superclass an implied label. Profiles: "
            + ", ".join(f"{titles[k]} ({k})" for k in PROFILES)
            + "."
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
    model = build(find_files(Path(sys.argv[1]) if len(sys.argv) > 1 else None))
    out = Path(__file__).parent
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(yaml(model) + "\n")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships")


if __name__ == "__main__":
    main()
