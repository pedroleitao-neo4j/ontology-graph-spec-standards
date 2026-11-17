#!/usr/bin/env python3
"""Generates the UCO 1.5.0 ontology from the official Unified Cyber Ontology Turtle files.

Usage: python3 generate.py [path/to/UCO-1.5.0.zip | path/to/UCO]

Without a path, the 1.5.0 release is downloaded from the UCO repository on GitHub. Writes model.json and model.yaml
next to this script. Uses only the Python standard library.

The CASE generator imports this module: CASE extends UCO, and is read and built the same way.
"""

import json
import re
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

SOURCE_URL = "https://github.com/ucoProject/UCO/archive/refs/tags/1.5.0.zip"
SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
UCO = "https://ontology.unifiedcyberontology.org/uco/"
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
RANGE = RDFS + "range"
UNIONOF = OWL + "unionOf"
ONEOF = OWL + "oneOf"
EQUIVALENT = OWL + "equivalentClass"

# The XML Schema datatypes UCO uses, as Neo4j types. A dateTime is zoned: UCO's examples and tools give a timezone.
DATATYPES = {
    "string": "STRING",
    "anyURI": "STRING",
    "hexBinary": "STRING",
    "base64Binary": "STRING",
    "dateTime": "ZONED DATETIME",
    "duration": "DURATION",
    "boolean": "BOOLEAN",
    "decimal": "FLOAT",
    "integer": "INTEGER",
    "nonNegativeInteger": "INTEGER",
    "positiveInteger": "INTEGER",
    "unsignedInt": "INTEGER",
    "unsignedShort": "INTEGER",
    "byte": "INTEGER",
}

# The SHACL keywords that are read; any other on a property shape is reported, so that nothing is lost silently.
READ = {"path", "datatype", "class", "nodeKind", "minCount", "maxCount", "in", "hasValue", "or", "severity", "message",
        "description", "name"}


def words(text):
    """The words of a camelCase or space-separated name, e.g. hasFacet → has, Facet; MD5 → MD5."""
    return re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z\d]*|[a-z\d]+", text) or re.findall(r"[A-Za-z0-9]+", text)


def rel_type(name):
    return "_".join(w.upper() for w in words(name))


def local(iri):
    return re.split(r"[/#]", iri)[-1]


def namespace(iri):
    """The ontology an IRI belongs to, e.g. https://ontology.unifiedcyberontology.org/uco/core/UcoObject → core."""
    return iri.rstrip("/").rsplit("/", 2)[-2]


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


def ends(lower, upper):
    """The count constraints of a relationship end, from a multiplicity. Zero or more is unconstrained."""
    if (lower, upper) == (1, 1):
        return {"count": 1}
    if (lower, upper) == (0, 1):
        return {"max_count": 1}
    return {k: v for k, v in (("min_count", lower), ("max_count", upper)) if v}


#----------------------------------
#   Reading the ontology
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


def read_graph(files):
    """The graph of every Turtle file, merged: a term declared in several files gathers all its statements."""
    graph = {}
    for i, path in enumerate(sorted(files)):
        parse_turtle(path.read_text(), graph, f"f{i}")
    return graph


def ontology_files(source, folder):
    """The Turtle files under ontology/<folder> of a release: a downloaded or given zip archive, or a directory."""
    if not source.is_dir():
        out = Path(tempfile.mkdtemp())
        zipfile.ZipFile(source).extractall(out)
        source = out
    roots = [d for d in source.rglob(folder) if d.is_dir() and d.parent.name == "ontology"]
    if not roots:
        sys.exit(f"{source}: no ontology/{folder} directory")
    return sorted(roots[0].rglob("*.ttl"))


def download(url, name):
    path = Path(tempfile.mkdtemp()) / name
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request) as response:
        path.write_bytes(response.read())
    return path


#----------------------------------
#   The ontology as data
#----------------------------------


class Ontology:
    """The classes, properties and shapes of UCO, or of an ontology built on it such as CASE, read out of the graph."""

    def __init__(self, graph, bases):
        self.graph = graph
        self.classes = {
            s: po
            for s, po in graph.items()
            if s.startswith(bases) and ("iri", OWL + "Class") in po.get(TYPE, [])
        }
        names = {}
        for iri in self.classes:
            if local(iri) in names:
                sys.exit(f"two classes share the name {local(iri)}: {names[local(iri)]} and {iri}")
            names[local(iri)] = iri
        self.dropped = {}  # what the shapes say that the ontology can't, by SHACL keyword

    def values(self, subject, predicate):
        return self.graph.get(subject, {}).get(predicate, [])

    def iri(self, subject, predicate):
        return next((v[1] for v in self.values(subject, predicate) if v[0] == "iri"), None)

    def literal(self, subject, predicate):
        return next((v[1] for v in self.values(subject, predicate) if v[0] == "lit"), None)

    def text(self, subject, predicate):
        """A literal, in English where the term has one in several languages."""
        values = [v for v in self.values(subject, predicate) if v[0] == "lit"]
        english = [v for v in values if (v[2] or "").startswith("@en")] or values
        return tidy(english[0][1]) if english else ""

    def supertypes(self, iri):
        return [v[1] for v in self.values(iri, SUBCLASS) if v[0] == "iri" and v[1] in self.classes]

    def comment(self, iri):
        return self.text(iri, COMMENT)

    def shapes(self, iri):
        """The property shapes of a class: those of the class, which is its own node shape, and of any other node
        shape that targets it, merged by property path."""
        shapes = [s for s, po in self.graph.items() if ("iri", iri) in po.get(SH + "targetClass", []) and s != iri]
        by_path = {}
        for shape in [iri, *shapes]:
            for value in self.values(shape, SH + "property"):
                body = self.graph.get(value[1], {})
                if ("lit", "true", XSD + "boolean") in body.get(SH + "deactivated", []):
                    continue
                path = body.get(SH + "path", [None])[0]
                if not path or path[0] != "iri":
                    self.dropped.setdefault("a path other than a property", []).append(local(iri))
                    continue
                by_path.setdefault(path[1], []).append(body)
            for keyword in ("xone", "not", "sparql"):
                if SH + keyword in self.graph.get(shape, {}):
                    self.dropped.setdefault(f"sh:{keyword}", []).append(local(iri))
        return by_path

    def vocabulary(self, iri):
        """The literals of a vocabulary datatype, e.g. vocabulary:HashNameVocab, defined by an owl:oneOf."""
        for value in self.values(iri, EQUIVALENT) + [("bnode", iri)]:
            members = next((v for v in self.values(value[1], ONEOF) if v[0] == "coll"), None)
            if members:
                return [m[1] for m in members[1] if m[0] == "lit"]
        return []

    def vocabulary_of(self, prop):
        """The vocabulary a property's range names, e.g. ActionStatusTypeVocab for a range of string or it."""
        for value in self.values(prop, RANGE):
            if value[0] == "iri" and self.vocabulary(value[1]):
                return value[1]
            members = next((v for v in self.values(value[1], UNIONOF) if v[0] == "coll"), None) if value[0] == "bnode" else None
            for member in members[1] if members else []:
                if member[0] == "iri" and self.vocabulary(member[1]):
                    return member[1]
        return None

    def field(self, cls, path, bodies):
        """What the shapes of one class say about one property path, merged: its datatypes or classes, its counts,
        its values, whether it holds literals or IRIs, and the keywords that weren't read."""
        out = {"datatypes": [], "classes": [], "lower": 0, "upper": None, "one_of": None, "suggested": None,
               "kinds": set()}
        for body in bodies:
            for keyword in body:
                if keyword.startswith(SH) and keyword[len(SH):] not in READ:
                    self.dropped.setdefault(f"sh:{keyword[len(SH):]}", []).append(f"{local(cls)}.{local(path)}")
            severity = next((v[1] for v in body.get(SH + "severity", []) if v[0] == "iri"), SH + "Violation")
            out["datatypes"] += [v[1] for v in body.get(SH + "datatype", []) if v[0] == "iri"]
            for alternative in (v for v in body.get(SH + "or", []) if v[0] == "coll"):
                for member in alternative[1]:
                    out["datatypes"] += [v[1] for v in self.values(member[1], SH + "datatype") if v[0] == "iri"]
                    out["classes"] += [v[1] for v in self.values(member[1], SH + "class") if v[0] == "iri"]
            out["classes"] += [v[1] for v in body.get(SH + "class", []) if v[0] == "iri"]
            out["kinds"] |= {local(v[1]) for v in body.get(SH + "nodeKind", []) if v[0] == "iri"}
            for v in body.get(SH + "minCount", []):
                out["lower"] = max(out["lower"], int(v[1]))
            for v in body.get(SH + "maxCount", []):
                out["upper"] = int(v[1]) if out["upper"] is None else min(out["upper"], int(v[1]))
            members = next((v for v in body.get(SH + "in", []) if v[0] == "coll"), None)
            fixed = [v for v in body.get(SH + "hasValue", []) if v[0] == "lit"]
            values = [m[1] for m in members[1] if m[0] == "lit"] if members else [v[1] for v in fixed]
            if values and severity == SH + "Violation":
                out["one_of"] = values
            elif values:
                out["suggested"] = values  # an open vocabulary: other values are allowed, with an Info notice
        for datatype in out["datatypes"]:
            if not datatype.startswith(XSD) and self.vocabulary(datatype):
                out["one_of"] = self.vocabulary(datatype)
        out["datatypes"] = sorted(set(out["datatypes"]))
        out["classes"] = sorted(set(out["classes"]))
        return out

    def range_datatypes(self, prop):
        """The datatypes a property's range names, itself or as a union, e.g. xsd:string or a vocabulary."""
        out = []
        for value in self.values(prop, RANGE):
            members = next((v[1] for v in self.values(value[1], UNIONOF) if v[0] == "coll"), [value])
            out += [m[1] for m in members if m[0] == "iri" and (m[1].startswith(XSD) or self.vocabulary(m[1]))]
        return out

    def property_type(self, field, prop):
        """The Neo4j type of a literal-valued property; values of several datatypes are ANY."""
        datatypes = field["datatypes"] or self.range_datatypes(prop)
        types = set()
        for datatype in datatypes:
            if datatype.startswith(XSD):
                if local(datatype) not in DATATYPES:
                    sys.exit(f"{local(prop)}: no Neo4j type for {datatype}")
                types.add(DATATYPES[local(datatype)])
            else:  # a vocabulary of strings, or a datatype restricting a string such as pattern:PatternExpression
                types.add("STRING")
        neo4j = types.pop() if len(types) == 1 else "ANY"
        return neo4j if field["upper"] == 1 else f"LIST<{neo4j}>"


def build(onto, include, meta, ontology_of=lambda iri: "UCO"):
    """The model of the classes in `include`: each a node, each datatype-valued property shape a property, each
    class-valued one a relationship to every class it allows, and each superclass an implied label. A relationship
    to a class outside `include` is left out, and counted in the result."""
    nodes, relationships, left_out = {}, {}, []
    for iri in sorted(include, key=local):
        name = local(iri)
        properties = {
            "uri": {
                "type": "STRING",
                "name": "uri",
                "description": f"The identifier of the {name}: its IRI, the @id of the object in UCO JSON-LD. "
                "Unique within a data set; objects that are blank nodes are given generated identifiers.",
                "reference": "https://www.w3.org/TR/json-ld11/#node-identifiers",
            }
        }
        constraints = {f"key_{name}": {"type": "KEY", "properties": ["uri"], "name": f"uri_{name}_key"}}
        links = []
        for path, bodies in sorted(onto.shapes(iri).items(), key=lambda p: local(p[0])):
            field = onto.field(iri, path, bodies)
            pid = local(path)
            if field["classes"] or field["kinds"] & {"IRI", "BlankNodeOrIRI"}:
                links.append((path, field))
                continue
            if pid in properties:
                sys.exit(f"{name}: two properties named {pid}")
            vocabulary = onto.vocabulary_of(path)
            prop = {
                "type": onto.property_type(field, path),
                "name": pid,
                "description": describe(
                    sentence(onto.comment(path)),
                    f"Suggested values, from the open vocabulary {local(vocabulary) if vocabulary else ''}: "
                    + ", ".join(f"`{v}`" for v in field["suggested"]) + "."
                    if field["suggested"]
                    else "",
                    f"Holds a value of any of {', '.join(local(d) for d in field['datatypes'])}."
                    if len(field["datatypes"]) > 1
                    else "",
                ),
                "reference": path,
                "extensions": {
                    "custom": {
                        k: v
                        for k, v in (
                            ("iri", path),
                            ("datatypes", [local(d) for d in field["datatypes"]]),
                            ("vocabulary", local(vocabulary) if vocabulary else None),
                            ("suggestedValues", field["suggested"]),
                            ("minCount", field["lower"]),
                            ("maxCount", field["upper"]),
                        )
                        if v not in (None, [], 0)
                    }
                },
            }
            if not prop["description"]:
                del prop["description"]
            if field["one_of"]:
                prop["one_of"] = field["one_of"]
            properties[pid] = prop
            if field["lower"] >= 1:
                constraints[f"exists_{name}_{pid}"] = {
                    "type": "EXISTS",
                    "properties": [pid],
                    "name": f"{pid}_{name}_exists",
                }

        supertypes = [local(s) for s in onto.supertypes(iri) if s in include]
        description = describe(sentence(onto.comment(iri)))
        nodes[name] = {
            "labels": {"identifier": name, **({"implied": supertypes} if supertypes else {})},
            **({"description": description} if description else {}),
            "reference": iri,
            "properties": properties,
            "constraints": constraints,
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (
                        ("iri", iri),
                        ("ontology", ontology_of(iri)),
                        ("namespace", namespace(iri)),
                        ("disjointWith", sorted(local(d[1]) for d in onto.values(iri, OWL + "disjointWith") if d[0] == "iri")),
                    )
                    if v not in (None, [])
                }
            },
        }

        # Each class-valued property: to every class it allows, else to the class its range names, else to
        # UcoThing, the root of UCO, when it allows any IRI.
        for path, field in links:
            targets = field["classes"] or [
                v[1] for v in onto.values(path, RANGE) if v[0] == "iri" and v[1] in onto.classes
            ] or [UCO + "core/UcoThing"]
            for target in targets:
                if target not in include:
                    left_out.append(f"{name}.{local(path)} → {local(target)}")
                    continue
                rtype = rel_type(local(path))
                rid = f"{name}_{rtype}_{local(target)}"
                while rid in relationships:
                    rid += "_2"
                # A facet belongs to one object: core:hasFacet-shape forbids two objects sharing one facet.
                opposite = {"max_count": 1} if path == UCO + "core/hasFacet" else {}
                relationships[rid] = {
                    "type": rtype,
                    "from": {"node": name, **ends(field["lower"], field["upper"])},
                    "to": {"node": local(target), **opposite},
                    "description": describe(
                        sentence(onto.comment(path)),
                        f"Each {name} has {phrase(field['lower'], field['upper'])} {local(target)}.",
                        f"Each {local(target)} is the facet of at most one object." if opposite else "",
                        f"One of {len(targets)} classes the property allows." if len(targets) > 1 else "",
                    ),
                    "reference": path,
                    "extensions": {
                        "custom": {
                            k: v
                            for k, v in (
                                ("iri", path),
                                ("minCount", field["lower"]),
                                ("maxCount", field["upper"]),
                                ("unionEnds", len(targets) > 1),
                                ("blankNodes", "BlankNodeOrIRI" in field["kinds"]),
                            )
                            if v not in (None, 0, False)
                        }
                    },
                }

    for rel in relationships.values():
        for end in (rel["from"], rel["to"]):
            if end["node"] not in nodes:
                sys.exit(f"relationship {rel['type']} points at {end['node']}, which is not a class")
    return {**meta, "nodes": nodes, "relationships": relationships}, left_out


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


def write(model, out):
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(yaml(model) + "\n")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships")


def report(onto, left_out):
    for keyword, where in sorted(onto.dropped.items()):
        print(f"not kept, {keyword}: {', '.join(sorted(set(where)))}")
    if left_out:
        print(f"left out, to a class outside the model: {', '.join(left_out)}")


META = {
    "schema": SCHEMA,
    "version": "1.5.0",
    "id": "uco-1.5.0",
    "name": "UCO 1.5.0",
    "description": (
        "The Unified Cyber Ontology (UCO) 1.5.0, published by the UCO Community (https://unifiedcyberontology.org/) "
        "under the Linux Foundation's Cyber Domain Ontology project. UCO is a foundation for representing "
        "cyber-domain information: the observable objects of digital forensics and incident response (files, "
        "processes, accounts, devices, network connections, messages and over three hundred others) and the facets "
        "that characterise them, the actions performed on them and the tools that perform them, the identities, "
        "roles, locations and victims involved, and the markings, provenance and analysis that qualify them. It is "
        "written in OWL 2, with SHACL shapes that constrain each class. Generated from the 1.5.0 release Turtle "
        "files (https://github.com/ucoProject/UCO, tag 1.5.0): each class is a node, each SHACL property shape a "
        "property or, for an object-valued property, a relationship, and each superclass an implied label."
    ),
}


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else download(SOURCE_URL, "UCO-1.5.0.zip")
    onto = Ontology(read_graph(ontology_files(source, "uco") + ontology_files(source, "co")), UCO)
    model, left_out = build(onto, set(onto.classes), META)
    write(model, Path(__file__).parent)
    report(onto, left_out)


if __name__ == "__main__":
    main()
