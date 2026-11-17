#!/usr/bin/env python3
"""Generates the Asset Administration Shell (AAS) 3.2 ontology from the official IDTA metamodel schemas.

Usage: python3 generate.py [path/to/aas-specs-metamodel-3.2.0.zip | path/to/aas-specs-metamodel]

Without a path, the v3.2.0 release is downloaded from the IDTA aas-specs-metamodel repository on GitHub. Writes
model.json and model.yaml next to this script. Uses only the Python standard library.
"""

import json
import re
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

SOURCE_URL = "https://github.com/admin-shell-io/aas-specs-metamodel/archive/refs/tags/v3.2.0.zip"
SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
AAS = "https://admin-shell.io/aas/3/2/"
SITE = "https://industrialdigitaltwin.io/aas-specifications"
SPEC = SITE + "/IDTA-01001/v3.2"
IEC61360 = SITE + "/IDTA-01003-a/v3.2/specification.html"
UOM = SITE + "/IDTA-01003-b/v3.1/specification.html"
MAX_DESCRIPTION = 1024

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
SH = "http://www.w3.org/ns/shacl#"
XSD = "http://www.w3.org/2001/XMLSchema#"

TYPE = RDF + "type"
SUBCLASS = RDFS + "subClassOf"
LABEL = RDFS + "label"
COMMENT = RDFS + "comment"
ONEOF = OWL + "oneOf"

# The XML Schema datatypes the shapes use, as Neo4j types. A Blob's base64Binary content is kept as its text.
DATATYPES = {"string": "STRING", "boolean": "BOOLEAN", "base64Binary": "STRING"}

# The pattern most strings carry, which only excludes characters XML can't hold; any other pattern is kept.
XML_CHARACTERS = r"^([\x09\x0a\x0d\x20-\ud7ff\ue000-\ufffd]|\ud800[\udc00-\udfff]|[\ud801-\udbfe][\udc00-\udfff]|\udbff[\udc00-\udfff])*$"

# The lists the specification marks <<ordered>>: the keys of a reference and the elements of a submodel element list.
ORDERED = {AAS + "Reference/keys", AAS + "SubmodelElementList/value"}

# Where the classes the Part 1 pages don't define are specified: the data specification templates (Parts 3a and 3b)
# and the language string types, which Part 1 describes as data types.
PAGES = {
    "AbstractLangString": (f"{SPEC}/spec-metamodel/datatypes.html#LangStringSet", "datatypes"),
    "LangStringNameType": (f"{SPEC}/spec-metamodel/datatypes.html#MultiLanguageNameType", "datatypes"),
    "LangStringTextType": (f"{SPEC}/spec-metamodel/datatypes.html#MultiLanguageTextType", "datatypes"),
    "EmbeddedDataSpecification": (f"{SPEC}/spec-metamodel/common.html#HasDataSpecification", "common"),
    "DataSpecificationIec61360": (f"{IEC61360}#DataSpecificationIec61360", "data-specifications"),
    "LangStringPreferredNameTypeIec61360": (f"{IEC61360}#PreferredNameTypeIec61360", "data-specifications"),
    "LangStringShortNameTypeIec61360": (f"{IEC61360}#ShortNameTypeIec61360", "data-specifications"),
    "LangStringDefinitionTypeIec61360": (f"{IEC61360}#DefinitionTypeIec61360", "data-specifications"),
    "LevelType": (f"{IEC61360}#LevelType", "data-specifications"),
    "ValueList": (f"{IEC61360}#ValueList", "data-specifications"),
    "ValueReferencePair": (f"{IEC61360}#ValueReferencePair", "data-specifications"),
    "DataSpecificationUom": (f"{UOM}#_data_specification_unit_of_measurement_template_specification", "data-specifications"),
    "LangStringUom": (f"{UOM}#LangStringSetUoM", "data-specifications"),
    "LangStringDefinitionTypeUom": (f"{UOM}#DefinitionTypeUoM", "data-specifications"),
}


def rel_type(label):
    """A relationship type from an attribute's label, e.g. has specific asset IDs → HAS_SPECIFIC_ASSET_IDS. A label
    that is already a verb phrase loses its has, e.g. has is case of → IS_CASE_OF."""
    words = label.split()
    if words[:1] == ["has"] and words[1:2] in (["is"], ["refers"]):
        words = words[1:]
    return "_".join(w.upper() for w in words)


def local(iri):
    return re.split(r"[/#]", iri)[-1]


def tidy(text):
    """Collapses whitespace."""
    return re.sub(r"\s+", " ", text).strip()


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
    return f"between {lower} and {'any number' if upper is None else upper}"


def multiplicity(lower, upper):
    return f"{lower}..{'*' if upper is None else upper}"


def ends(lower, upper):
    """The count constraints of a relationship end, from a multiplicity. Zero or more is unconstrained."""
    if (lower, upper) == (1, 1):
        return {"count": 1}
    if (lower, upper) == (0, 1):
        return {"max_count": 1}
    return {k: v for k, v in (("min_count", lower), ("max_count", upper)) if v}


#----------------------------------
#   Reading the schemas
#----------------------------------

ESCAPES = {"t": "\t", "n": "\n", "r": "\r", '"': '"', "'": "'", "\\": "\\", "b": "\b", "f": "\f"}


def tokens(text):
    """The Turtle tokens of the file: IRIs, names, literals, numbers and punctuation."""
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c == "#":
            while i < n and text[i] != "\n":
                i += 1
        elif c == "<":
            j = text.index(">", i)
            yield ("iri", text[i + 1 : j])
            i = j + 1
        elif c in "\"'":
            if text[i : i + 3] == c * 3:  # a triple-quoted string, which may span lines
                j = text.index(c * 3, i + 3)
                body, i = text[i + 3 : j], j + 3
            else:
                body, j = "", i + 1
                while text[j] != c:
                    if text[j] == "\\":  # an escaped character stays in the body for the decoder
                        body += text[j : j + 2]
                        j += 2
                    else:
                        body += text[j]
                        j += 1
                i = j + 1
            out, k = "", 0
            while k < len(body):
                if body[k] == "\\" and k + 1 < len(body) and body[k + 1] in ESCAPES:
                    out += ESCAPES[body[k + 1]]
                    k += 2
                elif body[k] == "\\" and body[k + 1 : k + 2] == "u":
                    out += chr(int(body[k + 2 : k + 6], 16))
                    k += 6
                else:
                    out += body[k]
                    k += 1
            yield ("lit", out)
        elif c == "@":
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] == "-"):
                j += 1
            yield ("at", text[i + 1 : j])
            i = j
        elif text[i : i + 2] == "^^":
            yield ("punct", "^^")
            i += 2
        elif c.isalpha() or c in "_:":
            j = i
            while j < n and (text[j].isalnum() or text[j] in "_-.:%"):
                j += 1
            while j > i and text[j - 1] == ".":  # a statement dot is not part of a name
                j -= 1
            yield ("name", text[i:j])
            i = j
            while i < n and text[i] == ".":  # emit the statement dots the name swallowed
                yield ("punct", ".")
                i += 1
        elif c.isdigit() or (c == "-" and text[i + 1].isdigit()):
            j = i + 1
            while j < n and (text[j].isdigit() or text[j] in ".eE+-"):
                j += 1
            yield ("num", text[i:j])
            i = j
        else:
            yield ("punct", c)
            i += 1


def parse_turtle(text, graph, scope):
    """Reads a Turtle file into a subject → predicate → [values] graph, merging with the files read before it.

    A value is an ("iri", iri), ("lit", text, datatype or langtag or None), ("bnode", id) or ("coll", [values])
    tuple; a blank node property list becomes its own subject, named within `scope` so that the blank nodes of
    different files stay apart, and a collection is kept as a single value.
    """
    toks = list(reversed(list(tokens(text))))
    prefixes, counter = {}, 0

    def peek():
        return toks[-1] if toks else (None, None)

    def take():
        return toks.pop()

    def expand(name):
        prefix, _, local_name = name.partition(":")
        return prefixes[prefix] + local_name

    def term():
        nonlocal counter
        kind, value = take()
        if kind == "iri":
            return ("iri", value)
        if kind == "name":
            if value in ("true", "false"):
                return ("lit", value, XSD + "boolean")
            return ("iri", expand(value))
        if kind == "num":
            return ("lit", value, XSD + ("integer" if re.fullmatch(r"[+-]?\d+", value) else "double"))
        if (kind, value) == ("punct", "["):
            counter += 1
            subject = f"_:{scope}b{counter}"
            if peek() == ("punct", "]"):
                take()
            else:
                predicate_object_list(subject)
                assert take() == ("punct", "]")
            return ("bnode", subject)
        if (kind, value) == ("punct", "("):
            items = []
            while peek() != ("punct", ")"):
                items.append(term())
            take()
            return ("coll", items)
        if kind == "lit":
            nxt = peek()
            if nxt[0] == "at":
                take()
                return ("lit", value, f"@{nxt[1]}")
            if nxt == ("punct", "^^"):
                take()
                return ("lit", value, term()[1])
            return ("lit", value, None)
        sys.exit(f"unexpected token {kind} {value}")

    def predicate_object_list(subject):
        while True:
            kind, value = take()
            predicate = TYPE if (kind, value) == ("name", "a") else value if kind == "iri" else expand(value)
            while True:
                graph.setdefault(subject, {}).setdefault(predicate, []).append(term())
                if peek() == ("punct", ","):
                    take()
                else:
                    break
            if peek() == ("punct", ";"):
                while peek() == ("punct", ";"):
                    take()
                if peek() in (("punct", "."), ("punct", "]"), ("punct", ")")):
                    return
                continue
            return

    while toks:
        kind, value = take()
        if (kind, value) == ("at", "prefix"):
            name, iri = take(), take()
            prefixes[name[1].rstrip(":")] = iri[1]
            assert take() == ("punct", ".")
        elif (kind, value) == ("at", "base"):
            take()
            assert take() == ("punct", ".")
        else:
            toks.append((kind, value))
            subject = term()
            if peek() != ("punct", "."):  # a named subject: its predicates and objects follow
                predicate_object_list(subject[1])
            assert take() == ("punct", ".")
    return graph


def read_sources(source):
    """The RDF ontology and SHACL shapes, the JSON schema and the Part 1 documentation pages of a release: a
    downloaded or given zip archive, or a directory."""
    if not source.is_dir():
        out = Path(tempfile.mkdtemp())
        zipfile.ZipFile(source).extractall(out)
        source = out
    found = {}
    for name in ("rdf-ontology.ttl", "shacl-schema.ttl", "aas.json"):
        paths = sorted(p for p in source.rglob(name) if "examples" not in p.parts)
        if not paths:
            sys.exit(f"{source}: no {name}")
        found[name] = paths[0]
    pages = next((d for d in source.rglob("pages") if d.parent.parent.parent.name == "IDTA-01001"), None)
    if pages is None:
        sys.exit(f"{source}: no IDTA-01001 documentation pages")
    graph = {}
    for i, name in enumerate(("rdf-ontology.ttl", "shacl-schema.ttl")):
        parse_turtle(found[name].read_text(), graph, f"f{i}")
    return graph, json.loads(found["aas.json"].read_text())["definitions"], pages


def read_pages(pages):
    """Where Part 1 specifies each class: the page whose class table names it, e.g. Submodel → core.html#Submodel,
    and the page's section, e.g. core."""
    out = {}
    for path in sorted(pages.rglob("*.adoc")):
        for name in re.findall(r"h\|Class:\s*3\+e\|\[\[(\w+)\]\]", path.read_text()):
            page = path.relative_to(pages).with_suffix(".html").as_posix()
            out[name] = (f"{SPEC}/{page}#{name}", path.stem)
    return out


def download(url, name):
    path = Path(tempfile.mkdtemp()) / name
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request) as response:
        path.write_bytes(response.read())
    return path


#----------------------------------
#   The metamodel as data
#----------------------------------


def build(graph, definitions, pages):
    def values(subject, predicate):
        return graph.get(subject, {}).get(predicate, [])

    def iris(subject, predicate):
        return [v[1] for v in values(subject, predicate) if v[0] == "iri"]

    def text(subject, predicate):
        found = [v[1] for v in values(subject, predicate) if v[0] == "lit"]
        return tidy(found[0]) if found else ""

    classes = sorted(
        (s for s, po in graph.items() if s.startswith(AAS) and ("iri", OWL + "Class") in po.get(TYPE, [])), key=local
    )
    # An enumeration is a class of individuals; its values are those the JSON and XML exchange formats write, e.g.
    # xs:boolean for aas:DataTypeDefXsd/Boolean.
    enumerations = {c: definitions[local(c)]["enum"] for c in classes if values(c, ONEOF)}
    kinds = [c for c in classes if c not in enumerations]

    # The node shape of each class, and the classes the specification makes abstract: their shapes reject instances.
    shapes = {iris(s, SH + "targetClass")[0]: s for s in graph if iris(s, SH + "targetClass")}
    abstract = {c for c, s in shapes.items() if values(s, SH + "sparql")}
    where = read_pages(pages)

    def field(path, body):
        """What a property shape says: its datatype or class, its counts and its string length and pattern."""
        number = lambda keyword: int(values(body, SH + keyword)[0][1]) if values(body, SH + keyword) else None
        pattern = next((v[1] for v in values(body, SH + "pattern")), None)
        return {
            "datatype": next(iter(iris(body, SH + "datatype")), None),
            "class": next(iter(iris(body, SH + "class")), None),
            "lower": number("minCount") or 0,
            "upper": number("maxCount"),
            "minLength": number("minLength"),
            "maxLength": number("maxLength"),
            "pattern": pattern if pattern != XML_CHARACTERS else None,
        }

    nodes, relationships = {}, {}
    for iri in kinds:
        name = local(iri)
        if name not in where and name not in PAGES:
            sys.exit(f"{name}: no page in the specification")
        page, section = where.get(name) or PAGES[name]
        # AAS identifies an Identifiable globally by its id, and a Referable by its idShort within its parent; other
        # elements have no identity of their own. Every node gets a key a loader sets, so that nodes can be matched.
        properties = {
            "uid": {
                "type": "STRING",
                "name": "uid",
                "description": f"The identifier of the {name} node in the graph, set by the loader: not part of the "
                "AAS metamodel. For an Identifiable, its id; for a Referable within one, e.g. a submodel element, "
                "the Identifiable's id followed by the element's idShort path; for any other element, e.g. a "
                "Reference or a Key, an identifier generated from its parent's uid and its position.",
                "extensions": {"custom": {"addedByOntology": True}},
            }
        }
        constraints = {f"key_{name}": {"type": "KEY", "properties": ["uid"], "name": f"uid_{name}_key"}}
        links = []
        for body in [v[1] for v in values(shapes.get(iri, ""), SH + "property")]:
            path = iris(body, SH + "path")[0]
            f = field(path, body)
            if f["class"] in kinds:
                links.append((path, f))
                continue
            pid = local(path)
            if f["class"] in enumerations:
                neo4j, one_of, aas_type = "STRING", enumerations[f["class"]], local(f["class"])
            elif f["datatype"] and f["datatype"].startswith(XSD) and local(f["datatype"]) in DATATYPES:
                neo4j, one_of, aas_type = DATATYPES[local(f["datatype"])], [], f"xs:{local(f['datatype'])}"
            else:
                sys.exit(f"{name}.{pid}: no Neo4j type for {f['datatype'] or f['class']}")
            lower, upper = f["lower"], f["upper"]
            prop = {
                "type": neo4j if upper == 1 else f"LIST<{neo4j}>",
                "name": pid,
                "description": describe(
                    sentence(text(path, COMMENT)),
                    f"Multiplicity {multiplicity(lower, upper)}." if (lower, upper) != (0, 1) else "",
                    f"Values of AAS enumeration {aas_type}." if one_of else "",
                ),
                "reference": page,
                "extensions": {
                    "custom": {
                        k: v
                        for k, v in (
                            ("iri", path),
                            ("aasType", aas_type),
                            ("lower", lower),
                            ("upper", upper),
                            ("minLength", f["minLength"]),
                            ("maxLength", f["maxLength"]),
                            ("pattern", f["pattern"]),
                        )
                        if v is not None
                    }
                },
            }
            if one_of:
                prop["one_of"] = one_of
            properties[pid] = prop
            if (iri, pid) == (AAS + "Identifiable", "id"):
                # The id of an Identifiable is globally unique; the key also makes it exist.
                constraints[f"key_{name}_id"] = {"type": "KEY", "properties": ["id"], "name": f"id_{name}_key"}
            elif lower >= 1:
                constraints[f"exists_{name}_{pid}"] = {
                    "type": "EXISTS",
                    "properties": [pid],
                    "name": f"{pid}_{name}_exists",
                }

        supertypes = [local(s) for s in iris(iri, SUBCLASS) if s in kinds]
        nodes[name] = {
            "labels": {"identifier": name, **({"implied": supertypes} if supertypes else {})},
            **({"description": describe(sentence(text(iri, COMMENT)))} if text(iri, COMMENT) else {}),
            "reference": page,
            "properties": properties,
            "constraints": constraints,
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (("iri", iri), ("section", section), ("abstract", iri in abstract))
                    if v not in (None, False)
                }
            },
        }

        # Every class-valued attribute is a composition: an AAS environment is a tree, in which each element belongs
        # to one parent, and elements elsewhere in it are pointed at through a Reference.
        for path, f in sorted(links, key=lambda link: local(link[0])):
            target = local(f["class"])
            rtype = rel_type(text(path, LABEL) or f"has {local(path)}")
            rid = f"{name}_{rtype}_{target}"
            lower, upper = f["lower"], f["upper"]
            ordered = path in ORDERED
            relationships[rid] = {
                "type": rtype,
                "from": {"node": name, **ends(lower, upper)},
                "to": {"node": target, "max_count": 1},
                **(
                    {
                        "properties": {
                            "index": {
                                "type": "INTEGER",
                                "name": "index",
                                "description": f"The position of the {target} in the {name}'s list, from 0. The "
                                "specification orders this list; a relationship has no order of its own.",
                            }
                        }
                    }
                    if ordered
                    else {}
                ),
                "description": describe(
                    sentence(text(path, COMMENT)),
                    f"Each {name} has {phrase(lower, upper)} {target}.",
                    f"A composition: each {target} is part of at most one owner.",
                    "The list is ordered, by the index property." if ordered else "",
                ),
                "reference": page,
                "extensions": {
                    "custom": {
                        k: v
                        for k, v in (
                            ("iri", path),
                            ("composition", True),
                            ("lower", lower),
                            ("upper", upper),
                            ("isOrdered", ordered or None),
                        )
                        if v is not None
                    }
                },
            }

    # The element a model reference points at, which AAS gives only as a path of keys.
    relationships["Reference_RESOLVES_TO_Referable"] = {
        "type": "RESOLVES_TO",
        "from": {"node": "Reference", "max_count": 1},
        "to": {"node": "Referable"},
        "description": "The element a model reference identifies, resolved from its keys: the Identifiable its "
        "first key names, and the Referable the following keys name within it. Not part of the AAS metamodel: "
        "added by the ontology, so that references can be followed in the graph. Each Reference has at most one; "
        "an external reference, or a model reference to an element outside the graph, has none.",
        "reference": f"{SPEC}/spec-metamodel/referencing.html#Reference",
        "extensions": {"custom": {"composition": False, "addedByOntology": True}},
    }

    for node in nodes.values():
        for implied in node["labels"].get("implied", []):
            if implied not in nodes:
                sys.exit(f"superclass {implied} of {node['labels']['identifier']} is not a class")
    for rel in relationships.values():
        for end in (rel["from"], rel["to"]):
            if end["node"] not in nodes:
                sys.exit(f"relationship {rel['type']} points at {end['node']}, which is not a class")

    return {
        "schema": SCHEMA,
        "version": "3.2.0",
        "id": "aas-3.2.0",
        "name": "Asset Administration Shell 3.2",
        "description": (
            "The Asset Administration Shell (AAS) metamodel 3.2, specified by the Industrial Digital Twin Association "
            "(IDTA) in IDTA-01001 Part 1 and standardised as IEC 63278-1. The AAS is the standardised digital twin of "
            "Industrie 4.0: an asset administration shell describes an asset (its kind and identifiers) through "
            "submodels, each made of submodel elements (properties, ranges, files, blobs, collections, lists, "
            "entities, relationships, operations, capabilities and events), whose semantics are given by concept "
            "descriptions and IEC 61360 data specifications, and which point at each other through references. "
            "Generated from the RDF ontology and SHACL shapes of the IDTA metamodel schemas "
            "(https://github.com/admin-shell-io/aas-specs-metamodel, tag v3.2.0): each class is a node, each "
            "attribute of a primitive or enumeration type a property, each attribute of a class type a composition "
            "relationship, and each superclass an implied label."
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
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else download(SOURCE_URL, "aas-specs-metamodel-3.2.0.zip")
    model = build(*read_sources(source))
    out = Path(__file__).parent
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(yaml(model) + "\n")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships")


if __name__ == "__main__":
    main()
