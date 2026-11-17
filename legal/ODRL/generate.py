#!/usr/bin/env python3
"""Generates the ODRL 2.2 ontology from the official W3C ODRL Version 2.2 RDF vocabulary.

Usage: python3 generate.py [path/to/ODRL22.ttl]

Without a path, the vocabulary is downloaded from the W3C. Writes model.json and model.yaml next to this script.
Uses only the Python standard library.
"""

import json
import re
import sys
import tempfile
import urllib.request
from collections import Counter
from pathlib import Path

SOURCE_URL = "https://www.w3.org/ns/odrl/2/ODRL22.ttl"
SPEC_URL = "https://www.w3.org/TR/vocab-odrl/"
SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
ODRL = "http://www.w3.org/ns/odrl/2/"
MAX_DESCRIPTION = 1024

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
XSD = "http://www.w3.org/2001/XMLSchema#"

TYPE = RDF + "type"
SUBCLASS = RDFS + "subClassOf"
SUBPROPERTY = RDFS + "subPropertyOf"
DOMAIN = RDFS + "domain"
RANGE = RDFS + "range"
LABEL = RDFS + "label"
COMMENT = RDFS + "comment"
DEFINITION = SKOS + "definition"
NOTE = SKOS + "note"
INVERSE = OWL + "inverseOf"
UNIONOF = OWL + "unionOf"
THING = OWL + "Thing"

# The root of the model: owl:Thing, which the ODRL classes without an ODRL superclass sit under, directly or through
# classes outside ODRL, e.g. Party, which is a foaf:Agent, or Action, which is a schema:Action.
ROOT = "Thing"

# The prefixes that compact IRIs from other vocabularies in extensions.custom, e.g. foaf:Agent.
PREFIXES = {
    "odrl": ODRL,
    "rdf": RDF,
    "rdfs": RDFS,
    "owl": OWL,
    "skos": SKOS,
    "xsd": XSD,
    "dct": "http://purl.org/dc/terms/",
    "schema": "http://schema.org/",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "vcard": "http://www.w3.org/2006/vcard/ns#",
    "cc": "http://creativecommons.org/ns#",
}

# The RDF datatypes ODRL ranges its properties over, as Neo4j types. An rdfs:Literal may carry a language tag and is
# a string; a class in the range stands for the IRIs of its individuals, which are strings too.
DATATYPES = {
    XSD + "string": "STRING",
    XSD + "anyURI": "STRING",
    XSD + "boolean": "BOOLEAN",
    XSD + "date": "DATE",
    XSD + "dateTime": "DATETIME",
    XSD + "integer": "INTEGER",
    XSD + "decimal": "FLOAT",
    RDFS + "Literal": "STRING",
    RDFS + "Datatype": "STRING",
}

# The area a class hierarchy belongs to, by its root: the root classes of the four areas, and where each root's own
# root-less class sits, e.g. LogicalConstraint and Operator sit with Constraint. Every other class reaches its root by
# walking its ODRL superclass.
AREA_ROOTS = {
    "Policy": "Policies and rules",
    "Rule": "Policies and rules",
    "Asset": "Assets and parties",
    "Party": "Assets and parties",
    "AssetScope": "Assets and parties",
    "PartyScope": "Assets and parties",
    "Constraint": "Constraints and operands",
    "LogicalConstraint": "Constraints and operands",
    "Operator": "Constraints and operands",
    "LeftOperand": "Constraints and operands",
    "RightOperand": "Constraints and operands",
    "ConflictTerm": "Constraints and operands",
    "UndefinedTerm": "Constraints and operands",
    "Action": "Actions",
}


def words(text):
    """The words of a snake_case or CamelCase name, e.g. LogicalConstraint → Logical, Constraint; partOf → part, Of."""
    return re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z\d]*|[a-z\d]+", text) or re.findall(r"[A-Za-z0-9]+", text)


def pascal(name):
    """A class name as a label, e.g. LogicalConstraint → LogicalConstraint."""
    return "".join(w[0].upper() + w[1:] for w in words(name))


def rel_type(name):
    return "_".join(w.upper() for w in words(name))


def spaced(name):
    """A property name as ODRL writes it in prose, e.g. partOf → 'part of'."""
    return " ".join(w.lower() for w in words(name))


def article(name):
    return "an" if name[0] in "AEIOU" else "a"


def local(iri):
    return re.split(r"[/#]", iri)[-1]


def compact(iri):
    if iri.startswith(ODRL) and local(iri):
        return "odrl:" + iri[len(ODRL):]
    for prefix, expanded in PREFIXES.items():
        if iri.startswith(expanded):
            return f"{prefix}:{iri[len(expanded):]}"
    return iri


def tidy(text):
    """Collapses whitespace."""
    return re.sub(r"\s+", " ", text).strip()


def sentence(text):
    text = tidy(text)
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
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
    numbers = {1: "one", 2: "two"}
    if lower == upper:
        return f"exactly {numbers.get(lower, lower)}"
    if lower == 0 and upper is not None:
        return f"at most {numbers.get(upper, upper)}"
    if upper is None:
        return f"{numbers.get(lower, lower)} or more"
    return f"between {lower} and {upper}"


def ends(lower, upper):
    """The count constraints of a relationship end, from a multiplicity. Zero or more is unconstrained."""
    if lower == upper and lower:
        return {"count": lower}
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
    """The classes and properties of ODRL 2.2, read out of the graph of its vocabulary."""

    def __init__(self, graph):
        self.graph = graph

        def typed(kinds):
            return {
                s: po
                for s, po in graph.items()
                if s.startswith(ODRL) and local(s) and kinds & {v[1] for v in po.get(TYPE, []) if v[0] == "iri"}
            }

        self.classes = typed({RDFS + "Class", OWL + "Class"})
        self.properties = typed({RDF + "Property", OWL + "ObjectProperty", OWL + "DatatypeProperty"})
        self.names = {iri: pascal(local(iri)) for iri in self.classes}
        self.names[THING] = ROOT
        if len(set(self.names.values())) != len(self.names):
            sys.exit("two ODRL classes share a label")
        # The individuals of the ODRL classes — the actions, left operands, operators and the like — and the SKOS
        # collections that group the vocabulary's sections: values a data set refers to by IRI, not classes.
        self.individuals = {
            s: po
            for s, po in graph.items()
            if s.startswith(ODRL) and local(s) and s not in self.classes and s not in self.properties
        }
        self.dropped = {}  # what the vocabulary says that the ontology can't, by construct

        # A pair of inverse properties is declared from one side only, so the map is built in both directions. ODRL
        # 2.2 declares none: assignee and assigneeOf and the like are counterparts in prose only.
        self.inverses = {}
        for iri, po in self.properties.items():
            inverse = next((v[1] for v in po.get(INVERSE, []) if v[0] == "iri" and v[1] in self.properties), None)
            if inverse and inverse != iri:
                self.inverses.setdefault(iri, inverse)
                self.inverses.setdefault(inverse, iri)

    def values(self, subject, predicate):
        return self.graph.get(subject, {}).get(predicate, [])

    def iris(self, subject, predicate):
        return [v[1] for v in self.values(subject, predicate) if v[0] == "iri"]

    def texts(self, iri, predicate):
        """A term's annotation, in English where it has one in several languages."""
        values = [v for v in self.values(iri, predicate) if v[0] == "lit" and tidy(v[1])]
        english = [v for v in values if (v[2] or "").startswith("@en")] or values
        return [sentence(v[1]) for v in english]

    def definitions(self, iri):
        return self.texts(iri, DEFINITION) or self.texts(iri, COMMENT)

    def notes(self, iri):
        return self.texts(iri, NOTE)

    def label(self, iri):
        values = [v for v in self.values(iri, LABEL) if v[0] == "lit"]
        return tidy(values[0][1]) if values else local(iri)

    def kinds(self, iri):
        return {local(k) for k in self.iris(iri, TYPE)}

    def deprecated(self, iri):
        return any(v[0] == "lit" and v[1] == "true" for v in self.values(iri, OWL + "deprecated"))

    def members(self, value, keyword):
        """The members of a blank node's union, or [] if it is none."""
        if value[0] != "bnode":
            return []
        return next((v[1] for v in self.values(value[1], keyword) if v[0] == "coll"), [])

    def kept(self, prop):
        """Whether a property is the direction of its inverse pair that becomes a relationship. ODRL 2.2 declares no
        owl:inverseOf, so every property is kept."""
        inverse = self.inverses.get(prop)
        if inverse is None:
            return True
        passive = [bool(re.search(r"_(by|of|in|for)$", local(p))) for p in (prop, inverse)]
        if passive[0] != passive[1]:
            return not passive[0]
        declares = [inverse in self.iris(prop, INVERSE), prop in self.iris(inverse, INVERSE)]
        if declares[0] != declares[1]:
            return declares[1]
        return local(prop) < local(inverse)

    def end_classes(self, prop, end, seen=None):
        """The classes at one end of a property: its own domain or range, else its inverse's other end, else its
        superproperties'. An empty result means ODRL leaves that end unconstrained. The function properties, e.g.
        attributingParty, take their ends from :function this way."""
        seen = seen or set()
        if prop in seen:
            return set()
        seen.add(prop)
        values = self.values(prop, DOMAIN if end == "domain" else RANGE)
        if values:
            return {c for v in values for c in self.fillers(v)}
        inverse = self.inverses.get(prop)
        if inverse:
            values = self.values(inverse, RANGE if end == "domain" else DOMAIN)
            if values:
                return {c for v in values for c in self.fillers(v)}
        out = set()
        for supertype in self.iris(prop, SUBPROPERTY):
            if supertype in self.properties:
                out |= self.end_classes(supertype, end, seen)
        return out

    def fillers(self, value):
        """The named classes a class expression stands for: a class itself, or the members of a union. A restriction
        or complement names no class, and gives []."""
        if value[0] == "iri":
            return [value[1]]
        union = self.members(value, UNIONOF)
        if union:
            return [c for member in union for c in self.fillers(member)]
        return []

    def supertypes(self, cls):
        """The ODRL classes a class specialises."""
        return [s for s in self.iris(cls, SUBCLASS) if s in self.classes]

    def external_supertypes(self, cls):
        """The classes outside ODRL a class specialises, e.g. Action a schema:Action; for Party, the union of the
        agent classes of schema.org, FOAF and vCard."""
        return [c for value in self.values(cls, SUBCLASS) for c in self.fillers(value) if c not in self.classes]

    def area(self, cls):
        """The area a class belongs to, by walking its superclasses to one of the area roots."""
        if cls == THING:
            return ROOT
        name = local(cls)
        if name in AREA_ROOTS:
            return AREA_ROOTS[name]
        supertypes = self.supertypes(cls)
        return self.area(supertypes[0]) if supertypes else sys.exit(f"{name}: no area")


def build(onto):
    nodes = {}
    for iri in [THING, *sorted(onto.classes, key=local)]:
        name = onto.names[iri]
        implied, external, disjoint = [], [], []
        if iri == THING:
            description = (
                "Anything at all: owl:Thing. ODRL leaves most of its classes without a superclass — Policy, Rule, "
                "Asset and the constraint classes stand alone, and the ones that do specialise classes outside ODRL: "
                "a Party is a foaf:Agent, an Action a schema:Action. Each of these roots carries the Thing label, "
                "making one tree of the model."
            )
        else:
            implied = [onto.names[s] for s in onto.supertypes(iri)] or [ROOT]
            external = [compact(s) for s in onto.external_supertypes(iri)]
            disjoint = sorted(onto.names[d] for d in onto.iris(iri, OWL + "disjointWith") if d in onto.names)
            description = describe(
                *onto.definitions(iri),
                *onto.notes(iri),
                "Deprecated." if onto.deprecated(iri) else "",
                f"Specialises {' and '.join(external)}." if external else "",
            )
        nodes[name] = {
            "labels": {"identifier": name, **({"implied": implied} if implied else {})},
            **({"description": description} if description else {}),
            "reference": iri,
            "properties": {
                "uri": {
                    "type": "STRING",
                    "name": "uri",
                    "description": f"The identifier of the {name} individual: its IRI in ODRL data. Unique within "
                    "a data set; individuals that are blank nodes are given generated identifiers.",
                    "reference": "https://www.w3.org/TR/rdf11-concepts/#section-IRIs",
                }
            },
            "constraints": {f"key_{name}": {"type": "KEY", "properties": ["uri"], "name": f"uri_{name}_key"}},
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (
                        ("iri", iri),
                        ("area", onto.area(iri)),
                        ("subClassOf", external),
                        ("disjointWith", disjoint),
                        ("deprecated", onto.deprecated(iri)),
                    )
                    if v not in (None, [], False)
                }
            },
        }

    relationships, left_out, as_properties = {}, [], []

    def add_property(node_name, prop, neo4j_type, description, custom):
        properties_of = nodes[node_name]["properties"]
        if local(prop) in properties_of:
            sys.exit(f"{node_name}: two properties named {local(prop)}")
        properties_of[local(prop)] = {
            "type": f"LIST<{neo4j_type}>" if "FunctionalProperty" not in onto.kinds(prop) else neo4j_type,
            "name": local(prop),
            **({"description": description} if description else {}),
            "reference": prop,
            "extensions": {"custom": custom},
        }

    def described(prop, *more):
        return describe(*onto.definitions(prop), *onto.notes(prop), *more)

    def neo4j_type(ranges):
        """The single Neo4j type of a property's range: a datatype as mapped, a class as the strings of the IRIs of
        its individuals, and no range at all as the strings of the IRIs it holds."""
        if not ranges:
            return "STRING"
        types = set()
        for r in ranges:
            if r in onto.classes:
                types.add("STRING")
            elif r in DATATYPES:
                types.add(DATATYPES[r])
            else:
                sys.exit(f"{local(r)}: no Neo4j type")
        if len(types) != 1:
            sys.exit(f"a range of several types: {sorted(compact(r) for r in ranges)}")
        return types.pop()

    for prop in sorted(onto.properties, key=local):
        name = local(prop)
        if not onto.kept(prop):
            continue
        domains = sorted(onto.end_classes(prop, "domain"), key=local)
        if not domains:
            left_out.append(name)
            continue
        ranges = onto.end_classes(prop, "range")
        targets = sorted((r for r in ranges if r in onto.classes), key=local)
        kinds = onto.kinds(prop)
        supers = [local(s) for s in onto.iris(prop, SUBPROPERTY) if s in onto.properties]
        inverse = onto.inverses.get(prop)
        union_ends = len(domains) > 1 or len(targets) > 1
        if "DatatypeProperty" in kinds or not targets:
            # A property without a class range, or a datatype property: its values are IRIs or literals, held as
            # strings on each class of its domain.
            extra = (
                "Holds the IRI of the datatype of the value, e.g. xsd:date."
                if ranges == {RDFS + "Datatype"}
                else f"Holds the IRI of {'the' if 'FunctionalProperty' in kinds else 'each'} resource it refers to, "
                "which ODRL leaves unconstrained."
                if not ranges
                else "Holds the value, or the IRI of one of the RightOperand individuals ODRL defines."
            )
            for domain in domains:
                if domain not in onto.classes:
                    sys.exit(f"{name}: domain {domain} is not a class")
                add_property(
                    onto.names[domain],
                    prop,
                    neo4j_type(ranges),
                    described(prop, extra, "Deprecated." if onto.deprecated(prop) else ""),
                    {
                        k: v
                        for k, v in (
                            ("iri", prop),
                            ("subPropertyOf", supers),
                            ("inverseOf", local(inverse) if inverse else None),
                            ("datatypes", sorted(compact(r) for r in ranges)),
                            ("unionEnds", union_ends),
                            ("deprecated", onto.deprecated(prop)),
                        )
                        if v not in (None, [], False)
                    },
                )
            as_properties.append(name)
            continue
        for domain in domains:
            if domain not in onto.classes:
                sys.exit(f"{name}: domain {domain} is not a class")
            for target in targets:
                rtype = rel_type(name)
                sname, tname = onto.names[domain], onto.names[target]
                rid = f"{sname}_{rtype}_{tname}"
                while rid in relationships:
                    rid += "_2"
                relationships[rid] = {
                    "type": rtype,
                    "from": {
                        "node": sname,
                        **({"max_count": 1} if "FunctionalProperty" in kinds else {}),
                    },
                    "to": {"node": tname, **({"max_count": 1} if "InverseFunctionalProperty" in kinds else {})},
                    "description": described(
                        prop,
                        "Transitive." if "TransitiveProperty" in kinds else "",
                        "Deprecated." if onto.deprecated(prop) else "",
                    ),
                    "reference": prop,
                    "extensions": {
                        "custom": {
                            k: v
                            for k, v in (
                                ("iri", prop),
                                ("subPropertyOf", supers),
                                ("inverseOf", local(inverse) if inverse else None),
                                ("unionEnds", union_ends),
                                ("transitive", "TransitiveProperty" in kinds),
                                ("deprecated", onto.deprecated(prop)),
                            )
                            if v not in (None, [], False)
                        }
                    },
                }

    for rel in relationships.values():
        for end in (rel["from"], rel["to"]):
            if end["node"] not in nodes:
                sys.exit(f"relationship {rel['type']} points at {end['node']}, which is not a class")
    return {**META, "nodes": nodes, "relationships": relationships}, as_properties, left_out


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


META = {
    "schema": SCHEMA,
    "version": "2.2",
    "id": "odrl-2.2",
    "name": "ODRL 2.2",
    "description": (
        "ODRL 2.2, the Open Digital Rights Language vocabulary published by the W3C in the ODRL Vocabulary and "
        "Expression 2.2 Recommendation of 15 February 2018 (https://www.w3.org/TR/vocab-odrl/), alongside the ODRL "
        "Information Model 2.2 it expresses. ODRL is a policy expression language: a machine-readable way to state "
        "what may and may not be done with content and services, and what must be done in return. A Policy — an "
        "Agreement, Offer, Request, Ticket, Assertion, Privacy policy or Set — holds Permissions, Prohibitions and "
        "Duties; each Rule grants one Action over a target Asset to Parties in functional roles such as assignee and "
        "assigner, and is refined by Constraints and Logical Constraints over Operators and left and right operands, "
        "with conflict and undefined-term strategies at the Policy level. It is used for digital licensing and usage "
        "policies across sectors, and extended by the community profiles built on the ODRL Core Vocabulary. Generated "
        "from the ODRL Version 2.2 RDF vocabulary: each class is a node, each object property a relationship from its "
        "domain to its range (one per class of a union), each datatype property and each property without a class "
        "range a node property, and each superclass an implied label. The individuals ODRL defines — the actions, "
        "left operands, operators and the like — are values a data set refers to by IRI, not nodes."
    ),
}


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else download(SOURCE_URL, "ODRL22.ttl")
    graph = {}
    parse_turtle(source.read_text(), graph, "f0")
    onto = Ontology(graph)
    model, as_properties, left_out = build(onto)
    out = Path(__file__).parent
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(yaml(model) + "\n")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships")
    counts = Counter()
    for po in onto.individuals.values():
        for value in po.get(TYPE, []):
            if value[0] == "iri" and value[1] in onto.classes:
                counts[local(value[1])] += 1
    print(
        f"{sum(counts.values())} individuals of the ODRL classes not modelled, values a data set refers to by IRI: "
        + ", ".join(f"{n} {c}" for c, n in sorted(counts.items(), key=lambda i: -i[1]))
    )
    collections = sum(
        1 for po in onto.individuals.values() if SKOS + "Collection" in {v[1] for v in po.get(TYPE, []) if v[0] == "iri"}
    )
    if collections:
        print(f"{collections} SKOS collections that group the vocabulary's sections, not modelled")
    if as_properties:
        print(f"to anything, and so properties holding IRIs or values: {', '.join(as_properties)}")
    if left_out:
        print(f"left out, no domain: {', '.join(sorted(left_out))}")


if __name__ == "__main__":
    main()
