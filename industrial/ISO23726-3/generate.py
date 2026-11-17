#!/usr/bin/env python3
"""Generates the ISO 23726-3 (IDO) ontology from the official IDO Turtle file published by PCA.

Usage: python3 generate.py [path/to/LIS-14-for-FDIS.ttl]

Without a path, the IDO 4.2 (FDIS) file is downloaded from the POSC Caesar Association. Writes model.json and
model.yaml next to this script. Uses only the Python standard library.
"""

import json
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

SOURCE_URL = "https://stfilestorepca.blob.core.windows.net/files/LIS-14-for-FDIS.ttl"
SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
LIS = "http://rds.posccaesar.org/ontology/lis14/rdl/"
MAX_DESCRIPTION = 1024

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
IOF = "https://spec.industrialontologies.org/ontology/core/meta/AnnotationVocabulary/"

TYPE = RDF + "type"
SUBCLASS = RDFS + "subClassOf"
SUBPROPERTY = RDFS + "subPropertyOf"
DOMAIN = RDFS + "domain"
RANGE = RDFS + "range"
LABEL = RDFS + "label"
SEEALSO = RDFS + "seeAlso"
INVERSE = OWL + "inverseOf"
UNIONOF = OWL + "unionOf"
ONPROPERTY = OWL + "onProperty"
SOME = OWL + "someValuesFrom"
ALLV = OWL + "allValuesFrom"
LITERAL = RDFS + "Literal"
CHAIN = OWL + "propertyChainAxiom"


def words(text):
    """The words of a CamelCase or space-separated name, e.g. hasParticipant → has, Participant; datumUOM →
    datum, UOM."""
    return re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z\d]*|[a-z\d]+", text) or re.findall(r"[A-Za-z0-9]+", text)


def spaced(name):
    """A CamelCase name as IDO writes it in prose, e.g. hasParticipant → 'has participant', datumUOM → 'datum UOM'."""
    return " ".join(w if w.isupper() and len(w) <= 4 else w.lower() for w in words(name))


def article(name):
    """'a' or 'an' before a class name; a U is a 'yoo' sound, so 'a UnitOfMeasure'."""
    return "an" if name[0] in "AEIO" else "a"


def rel_type(name):
    return "_".join(w.upper() for w in words(name))


def tidy(text):
    """Collapses whitespace and normalises the doubled quotes the annotations use."""
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
    text = tidy(text).rstrip(".")
    return f"e.g. `{text}`." if text and "`" not in text else ""


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


def parse_turtle(text):
    """Reads the ontology as a subject → predicate → [values] graph, in the order the file declares its terms.

    A value is an ("iri", iri), ("lit", text, datatype or langtag or None), ("bnode", id) or ("coll", [values])
    tuple; a blank node property list becomes its own subject, and a collection is kept as a single value.
    """
    toks = list(tokens(text))
    prefixes, graph, counter = {}, {}, 0

    def peek():
        return toks[0] if toks else (None, None)

    def take():
        return toks.pop(0)

    def expand(name):
        prefix, _, local = name.partition(":")
        return prefixes[prefix] + local

    def term():
        nonlocal counter
        kind, value = take()
        if kind == "iri":
            return ("iri", value)
        if kind == "name":
            if value in ("true", "false"):
                return ("lit", value, RDF + "boolean")
            return ("iri", expand(value))
        if kind == "num":
            xsd = "http://www.w3.org/2001/XMLSchema#"
            return ("lit", value, xsd + ("integer" if re.fullmatch(r"[+-]?\d+", value) else "double"))
        if (kind, value) == ("punct", "["):
            counter += 1
            subject = f":b{counter}"
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
            toks.insert(0, (kind, value))
            subject = term()
            if peek() != ("punct", "."):  # a named subject: its predicates and objects follow
                predicate_object_list(subject[1])
            assert take() == ("punct", ".")
    return graph


def read_prefixes(text):
    return {m[0]: m[1] for m in re.findall(r"@prefix\s+([\w-]*):\s+<([^>]*)>", text)}


#----------------------------------
#   The IDO ontology as data
#----------------------------------


class Term:
    """One IDO term: a class or a property, with its annotations read out of the graph."""

    def __init__(self, iri, po, prefixes):
        self.iri = iri
        self.po = po
        self.name = self.text(LABEL) or iri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
        self.kinds = {v[1] for v in po.get(TYPE, []) if v[0] == "iri"}
        self.definition = self.text(IOF + "naturalLanguageDefinition")
        self.example = self.text(SKOS + "example")
        self.iso15926 = next((v[1] for v in po.get(SEEALSO, []) if v[0] == "lit" and "ISO 15926" in v[1]), "")
        self.seeAlso = [compact(v[1], prefixes) for v in po.get(SEEALSO, []) if v[0] == "iri"]
        self.primary = bool(self.definition or self.example)

    def text(self, predicate):
        values = [v for v in self.po.get(predicate, []) if v[0] == "lit"]
        return tidy(values[0][1]) if values else ""

    def texts(self, predicate):
        return [tidy(v[1]) for v in self.po.get(predicate, []) if v[0] == "lit"]


def compact(iri, prefixes):
    """An IRI in the compact form the ontology writes it in, e.g. obo:BFO_0000015."""
    for prefix, expanded in sorted(prefixes.items(), key=lambda p: -len(p[1])):
        if prefix and iri.startswith(expanded):
            return f"{prefix}:{iri[len(expanded):]}"
    return f"<{iri}>"


def classes_of(value, graph):
    """The classes a domain or range value stands for: one class, or the members of a union."""
    if value[0] == "iri":
        return [value[1]]
    members = next((v for v in graph[value[1]].get(UNIONOF, []) if v[0] == "coll"), None)
    if members is None:
        sys.exit(f"a domain or range is neither a class nor a union of classes: {value}")
    return [m[1] for m in members[1] if m[0] == "iri"]


def root_of(term, classes):
    """The top of a class's superclass chain: Object, Temporal, Dependent, Actual or Specified."""
    names = [v[1] for v in term.po.get(SUBCLASS, []) if v[0] == "iri"]
    return root_of(classes[names[0]], classes) if names else term.name


def end_classes(term, end, properties, graph, seen=None):
    """The classes at one end of a property: its own domain or range, else its inverse's other end, else its
    superproperties'. An empty result means IDO leaves that end unconstrained."""
    seen = seen or set()
    if term.iri in seen:
        return set()
    seen.add(term.iri)
    values = term.po.get(DOMAIN if end == "domain" else RANGE, [])
    if values:
        return {c for v in values for c in classes_of(v, graph)}
    inverse = next((v[1] for v in term.po.get(INVERSE, []) if v[0] == "iri"), None)
    if inverse and inverse in properties:
        values = properties[inverse].po.get(RANGE if end == "domain" else DOMAIN, [])
        if values:
            return {c for v in values for c in classes_of(v, graph)}
    ends = set()
    for supertype in (v[1] for v in term.po.get(SUBPROPERTY, []) if v[0] == "iri"):
        if supertype in properties:
            ends |= end_classes(properties[supertype], end, properties, graph, seen)
    return ends


def build(graph, prefixes):
    def iri_terms(kind):
        return {
            iri: Term(iri, po, prefixes)
            for iri, po in graph.items()
            if iri.startswith(LIS) and kind in {v[1] for v in po.get(TYPE, []) if v[0] == "iri"}
        }

    classes, properties = iri_terms(OWL + "Class"), iri_terms(OWL + "ObjectProperty")
    data_properties = iri_terms(OWL + "DatatypeProperty")
    if len({c.name for c in classes.values()}) != len(classes):
        sys.exit("two IDO classes share a label")
    for term in classes.values():
        for supertype in (v[1] for v in term.po.get(SUBCLASS, []) if v[0] == "iri"):
            if supertype not in classes:
                sys.exit(f"supertype {supertype} of {term.name} is not an IDO class")

    nodes = {}
    for iri, term in classes.items():
        implied = [classes[v[1]].name for v in term.po.get(SUBCLASS, []) if v[0] == "iri"]
        alt_labels = term.texts(SKOS + "altLabel")
        description = describe(
            sentence(term.definition),
            f"Renders {term.iso15926}." if term.iso15926 else "",
            example(term.example),
            *[sentence(note) for note in term.texts(SKOS + "scopeNote")],
            *[sentence(note) for note in term.texts(IOF + "explanatoryNote")],
            *[sentence(note) for note in term.texts(IOF + "usageNote")],
        )
        nodes[term.name] = {
            "labels": {"identifier": term.name, **({"implied": implied} if implied else {})},
            **({"aliases": alt_labels} if alt_labels else {}),
            **({"description": description} if description else {}),
            "reference": term.iri,
            "properties": {
                "uri": {
                    "type": "STRING",
                    "name": "uri",
                    "description": f"The identifier of the {term.name} individual: its IRI in IDO data. Unique "
                    "within a data set; individuals that are blank nodes in IDO are given generated identifiers.",
                    "reference": "https://www.w3.org/TR/rdf11-concepts/#section-IRIs",
                }
            },
            "constraints": {
                f"key_{term.name}": {"type": "KEY", "properties": ["uri"], "name": f"uri_{term.name}_key"}
            },
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (
                        ("iri", term.iri),
                        ("root", root_of(term, classes)),
                        ("iso15926", term.iso15926),
                        (
                            "disjointWith",
                            [classes[d[1]].name for d in term.po.get(OWL + "disjointWith", []) if d[1] in classes],
                        ),
                        ("seeAlso", term.seeAlso),
                    )
                    if v not in ("", None, [])
                }
            },
        }

    relationships = {}

    def relationship(from_name, to_name, term, description, counts=None, custom=None):
        rid = f"{from_name}_{rel_type(term.name)}_{to_name}"
        while rid in relationships:
            rid += "_2"
        relationships[rid] = {
            "type": rel_type(term.name),
            "from": {"node": from_name, **(counts or {})},
            "to": {"node": to_name},
            "description": description,
            "reference": term.iri,
            "extensions": {"custom": {k: v for k, v in (custom or {}).items() if v not in ("", None, [], False)}},
        }

    # A pair of inverse properties is declared from one side only, so the inverse map is built in both directions.
    inverses = {}
    for term in properties.values():
        inverse = next((v[1] for v in term.po.get(INVERSE, []) if v[0] == "iri" and v[1] in properties), None)
        if inverse:
            inverses.setdefault(term.iri, inverse)
            inverses.setdefault(inverse, term.iri)

    def emit(term):
        """One relationship per domain/range pair the property allows, union ends included."""
        domains = sorted(end_classes(term, "domain", properties, graph))
        ranges = sorted(end_classes(term, "range", properties, graph))
        if not domains or not ranges:
            return False
        inverse = inverses.get(term.iri)
        inverse_label = properties[inverse].name if inverse else ""
        functional = OWL + "FunctionalProperty" in term.kinds
        symmetric = OWL + "SymmetricProperty" in term.kinds
        subproperties = [
            properties[s].name for s in (v[1] for v in term.po.get(SUBPROPERTY, [])) if s in properties
        ]
        chains = [
            [properties[m[1]].name for m in c[1] if m[0] == "iri" and m[1] in properties]
            for c in term.po.get(CHAIN, [])
            if c[0] == "coll"
        ]
        description = describe(
            sentence(term.definition),
            f"The inverse IDO relation is '{spaced(inverse_label)}'." if inverse_label else "",
            f"Symmetric: x '{spaced(term.name)}' y if and only if y '{spaced(term.name)}' x." if symmetric else "",
            f"Renders {term.iso15926}." if term.iso15926 else "",
            example(term.example),
            *[sentence(note) for note in term.texts(SKOS + "scopeNote")],
            *[sentence(note) for note in term.texts(IOF + "usageNote")],
        )
        for domain in domains:
            for range_ in ranges:
                relationship(
                    classes[domain].name,
                    classes[range_].name,
                    term,
                    description,
                    {"max_count": 1} if functional else None,
                    {
                        "inverseOf": inverse_label,
                        "subPropertyOf": subproperties,
                        "symmetric": symmetric,
                        "functional": functional,
                        "propertyChains": chains,
                        "iso15926": term.iso15926,
                        "unionEnds": len(domains) > 1 or len(ranges) > 1,
                    },
                )
        return True

    # One relationship per property, in the direction IDO annotates: for each inverse pair, the property that
    # carries the definition and example; symmetric properties, which declare no inverse, as they are.
    handled, skipped = set(), []
    for iri, term in properties.items():
        if id(term) in handled:
            continue  # this property lost its inverse pair, which was emitted in the other direction
        inverse = inverses.get(iri)
        if inverse:
            pair = (term, properties[inverse])
            winner = next((p for p in pair if p.primary and not pair[1 - pair.index(p)].primary), None)
            if winner is None:
                winner = next((p for p in pair if p.definition), pair[0])
            handled.add(id(pair[1 - pair.index(winner)]))  # the loser skips its own visit
            if winner is not term:
                continue
        if not emit(term):
            skipped.append(term.name)

    # The restrictions a class places on a property: someValuesFrom becomes a required relationship to the
    # restricted class, allValuesFrom one to the narrower class, and a someValuesFrom of a literal a required
    # property.
    for iri, term in classes.items():
        for restriction in (v for v in term.po.get(SUBCLASS, []) if v[0] == "bnode"):
            body = graph[restriction[1]]
            prop = next((v[1] for v in body.get(ONPROPERTY, []) if v[0] == "iri"), None)
            if prop not in properties and prop not in data_properties:
                sys.exit(f"a restriction on {term.name} names {prop}, which is not an IDO property")
            qualifier = next((q for q in (SOME, ALLV) if q in body), None)
            if qualifier is None:
                continue
            value = body[qualifier][0]
            if value[0] == "lit" or value == ("iri", LITERAL):
                # A required data property, e.g. datumValue on ScalarQuantityDatum. The property is declared on a
                # superclass, so the requirement is stated in the description rather than an EXISTS constraint,
                # which in this format must name a property of its own node.
                pid = (properties.get(prop) or data_properties.get(prop)).name
                node = nodes[term.name]
                node["description"] = describe(
                    node["description"],
                    f"Every {term.name} has a '{spaced(pid)}': the property is declared on "
                    f"{node['labels']['implied'][0]}."
                    if node["labels"].get("implied")
                    else f"Every {term.name} has a '{spaced(pid)}'.",
                )
                continue
            if value[1] not in classes:
                sys.exit(f"a restriction on {term.name} names {value[1]}, which is not an IDO class")
            prop_term = properties.get(prop) or data_properties.get(prop)
            exactly = OWL + "FunctionalProperty" in prop_term.kinds
            target = classes[value[1]].name
            requirement = (
                f"Every {term.name} has {'exactly one' if exactly else 'at least one'} "
                f"'{spaced(prop_term.name)}' that is {article(target)} {target}."
                if qualifier == SOME
                else f"Every '{spaced(prop_term.name)}' of {article(term.name)} {term.name} "
                f"is {article(target)} {target}."
            )
            relationship(
                term.name,
                classes[value[1]].name,
                prop_term,
                describe(
                    requirement,
                    f"Renders {prop_term.iso15926}." if prop_term.iso15926 else "",
                    example(prop_term.example),
                ),
                {"count": 1} if qualifier == SOME and exactly else {"min_count": 1} if qualifier == SOME else None,
                {"restriction": qualifier.rsplit("#", 1)[-1], "iso15926": prop_term.iso15926},
            )

    # The data properties, on the classes IDO declares them for. IDO gives them no datatype: a value may be any
    # RDF literal, and the annotations recommend datatypes per use.
    for iri, term in data_properties.items():
        for domain in sorted(end_classes(term, "domain", properties, graph)):
            nodes[classes[domain].name]["properties"][term.name] = {
                "type": "ANY",
                "name": term.name,
                "description": describe(
                    sentence(term.definition),
                    f"Renders {term.iso15926}." if term.iso15926 else "",
                    example(term.example),
                    *[sentence(note) for note in term.texts(IOF + "usageNote")],
                ),
                "reference": term.iri,
                "extensions": {
                    "custom": {
                        k: v
                        for k, v in (
                            ("iri", term.iri),
                            ("functional", OWL + "FunctionalProperty" in term.kinds),
                            ("seeAlso", term.seeAlso),
                        )
                        if v not in ("", None, [], False)
                    }
                },
            }

    # A domain, range or restriction that names a class no node was built for means the ontology was misread.
    for rel in relationships.values():
        for end in (rel["from"], rel["to"]):
            if end["node"] not in nodes:
                sys.exit(f"relationship {rel['type']} points at {end['node']}, which is not a class")

    model = {
        "schema": SCHEMA,
        "version": "4.2",
        "id": "ido-4.2",
        "name": "ISO 23726-3 (IDO) 4.2",
        "description": (
            "The Industrial Data Ontology (IDO), published as ISO 23726-3 by the POSC Caesar Association "
            "(https://www.posccaesar.org/). IDO is a W3C OWL 2 ontology for industrial data in all life-cycle "
            "phases of industrial assets and processes, and the OWL rendering of the ISO 15926-2 data model, "
            "previously deployed as ISO TR 15926-14 (https://rds.posccaesar.org/ontology/lis14/). It provides the "
            "top-level vocabulary for building reference data libraries (RDLs) and asset models: the objects a "
            "plant is made of (physical, informational and organisational) and their parts, connections and "
            "locations; the activities that take place in it and the temporal regions they occupy; the qualities "
            "and potentials those objects bear, and the datums and units of measure that quantify them; and the "
            "'implements' relation that pairs a designed asset with its actual counterpart. Generated from the IDO "
            "4.2 FDIS Turtle file: each owl:Class is a node, each object property a relationship from its domain "
            "to its range (one direction per inverse pair), each datatype property a property, and each "
            "superclass an implied label."
        ),
        "nodes": nodes,
        "relationships": relationships,
    }
    return model, skipped


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
        source = Path(sys.argv[1])
    else:
        source = Path(tempfile.mkdtemp()) / "LIS-14-for-FDIS.ttl"
        # The file store rejects Python's default user agent.
        request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request) as response:
            source.write_bytes(response.read())
    text = source.read_text()
    model, skipped = build(parse_turtle(text), read_prefixes(text))
    out = Path(__file__).parent
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(yaml(model) + "\n")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships")
    if skipped:
        print(f"left unconstrained by IDO, and so without a relationship: {', '.join(skipped)}")


if __name__ == "__main__":
    main()
