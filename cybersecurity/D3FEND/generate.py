#!/usr/bin/env python3
"""Generates the MITRE D3FEND ontology from the official D3FEND Turtle file.

Usage: python3 generate.py [path/to/d3fend.ttl]

Without a path, D3FEND 1.6.0 is downloaded from MITRE. Writes model.json and model.yaml next to this
script. Uses only the Python standard library.

D3FEND's classes are the content of its knowledge graph, e.g. the defensive technique File Hashing or the digital
artifact File, rather than a schema: each class is also an individual. So the ontology describes the graph that holds
that knowledge base: each D3FEND class becomes a node, labelled by the category it falls in, e.g. DefensiveTechnique
or DigitalArtifact, and each D3FEND relation becomes a relationship between the categories it links.
"""

import json
import re
import sys
import tempfile
import urllib.request
from collections import Counter, deque
from pathlib import Path

SOURCE_URL = "https://d3fend.mitre.org/ontologies/d3fend/1.6.0/d3fend.ttl"
SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
D3F = "http://d3fend.mitre.org/ontologies/d3fend.owl#"
MAX_DESCRIPTION = 1024

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
XSD = "http://www.w3.org/2001/XMLSchema#"

TYPE = RDF + "type"
SUBCLASS = RDFS + "subClassOf"
SUBPROPERTY = RDFS + "subPropertyOf"
LABEL = RDFS + "label"
INVERSE = OWL + "inverseOf"
UNIONOF = OWL + "unionOf"
ONPROPERTY = OWL + "onProperty"
SOME = OWL + "someValuesFrom"
ALLV = OWL + "allValuesFrom"

# The categories of the knowledge base, each a node label: the D3FEND class at its root, the area of the diagram it
# is drawn in, and whether its nodes are D3FEND classes or the individuals of its classes. Relationships are drawn
# between the categories with endpoint True; the others are finer labels a node carries as well, e.g. a File is
# also a DigitalArtifact.
CATEGORIES = [
    # label, root class, area, holds, endpoint, implied labels
    ("DefensiveTactic", "DefensiveTactic", "Defensive", "class", True, []),
    ("DefensiveTechnique", "DefensiveTechnique", "Defensive", "class", True, []),
    ("AnalyticTechnique", "AnalyticTechnique", "Defensive", "class", True, []),
    ("AnalyticalPurpose", "AnalyticalPurpose", "Defensive", "class", True, []),
    ("OffensiveTactic", "OffensiveTactic", "Offensive", "class", True, []),
    ("OffensiveTechnique", "OffensiveTechnique", "Offensive", "class", True, []),
    ("ATTACKICSTechnique", "ATTACKICSTechnique", "Offensive", "class", True, []),
    ("ATTACKMobileTechnique", "ATTACKMobileTechnique", "Offensive", "class", True, []),
    ("ATLASTechnique", "ATLASTechnique", "Offensive", "class", True, []),
    ("SPARTATechnique", "SPARTATechnique", "Offensive", "class", True, []),
    ("Weakness", "Weakness", "Offensive", "class", True, []),
    ("DigitalArtifact", "DigitalArtifact", "Core", "class", True, ["Artifact"]),
    ("PhysicalArtifact", "PhysicalArtifact", "Core", "class", True, ["Artifact"]),
    ("Artifact", "Artifact", "Core", "class", True, []),
    ("File", "File", "Core", "class", False, ["DigitalArtifact"]),
    ("Software", "Software", "Core", "class", False, ["DigitalArtifact"]),
    ("Process", "Process", "Core", "class", False, ["DigitalArtifact"]),
    ("NetworkTraffic", "NetworkTraffic", "Core", "class", False, ["DigitalArtifact"]),
    ("NetworkNode", "NetworkNode", "Core", "class", False, ["DigitalArtifact"]),
    ("Event", "Event", "Core", "class", True, []),
    ("Agent", "Agent", "Core", "class", True, []),
    ("Sensor", "Sensor", "Core", "class", True, []),
    ("TechniqueReference", "TechniqueReference", "Knowledge base", "individual", True, []),
    ("ExternalControl", "ExternalControl", "Knowledge base", "individual", True, []),
    ("ControlCatalog", "ControlCatalog", "Knowledge base", "individual", True, []),
    ("ATTACKEnterpriseMitigation", "ATTACKEnterpriseMitigation", "Knowledge base", "individual", True, []),
    ("ATTACKEnterpriseDataSource", "ATTACKEnterpriseDataSource", "Knowledge base", "individual", True, []),
]
BASE = "D3FENDClass"  # the label every node that is a D3FEND class carries

# The framework an offensive tactic or technique comes from, by the D3FEND class it falls under.
FRAMEWORKS = [
    ("ATTACKEnterpriseThing", "ATT&CK Enterprise"),
    ("ATTACKICSThing", "ATT&CK ICS"),
    ("ATTACKMobileThing", "ATT&CK Mobile"),
    ("ATLASThing", "ATLAS"),
    ("SPARTAThing", "SPARTA"),
]

# The annotations kept as properties, by property name; others are left out. Each lands on the categories whose
# nodes carry it, or on D3FENDClass when nodes of several class categories do.
ANNOTATIONS = {
    "name": LABEL,
    "definition": D3F + "definition",
    "d3fendId": D3F + "d3fend-id",
    "attackId": D3F + "attack-id",
    "cweId": D3F + "cwe-id",
    "capecId": D3F + "capec-id",
    "kbArticle": D3F + "kb-article",
    "synonyms": D3F + "synonym",
    "prefLabel": SKOS + "prefLabel",
    "altLabels": SKOS + "altLabel",
    "comment": RDFS + "comment",
    "d3fendComment": D3F + "d3fend-comment",
    "seeAlso": RDFS + "seeAlso",
    "isDefinedBy": RDFS + "isDefinedBy",
    "deprecated": OWL + "deprecated",
    "displayOrder": D3F + "display-order",
    "displayPriority": D3F + "display-priority",
    "title": D3F + "kb-reference-title",
    "abstract": D3F + "kb-abstract",
    "authors": D3F + "kb-author",
    "organization": D3F + "kb-organization",
    "mitreAnalysis": D3F + "kb-mitre-analysis",
    "link": D3F + "has-link",
    "releaseDate": D3F + "release-date",
    "controlName": D3F + "control-name",
    "contributor": D3F + "contributor",
    "published": D3F + "published",
    "version": D3F + "version",
    "archivedAt": D3F + "archived-at",
}
# Annotations whose values are many by nature, kept as lists even where a node has one; the others are single
# values, and where D3FEND gives a node more than one, e.g. two labels for a CWE weakness, the first is kept.
LISTS = {"synonyms", "altLabels", "seeAlso", "isDefinedBy", "comment"}
NEO4J_TYPES = {
    XSD + "dateTime": "ZONED DATETIME",
    XSD + "boolean": "BOOLEAN",
    XSD + "integer": "INTEGER",
    XSD + "int": "INTEGER",
    XSD + "nonNegativeInteger": "INTEGER",
}


def local(iri):
    return iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def words(text):
    """The words of a D3FEND relation name, e.g. may-be-associated-with → may, be, associated, with."""
    return re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z\d]*|[a-z\d]+", text)


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


def article(name):
    return "an" if name[0] in "AEIO" else "a"


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
            if text[i : i + 3] == c * 3:  # a triple-quoted string, which may span lines and escape its quotes
                j = i + 3
                while text[j : j + 3] != c * 3:
                    j += 2 if text[j] == "\\" else 1
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
    toks = deque(tokens(text))
    prefixes, graph, counter = {}, {}, 0

    def peek():
        return toks[0] if toks else (None, None)

    def take():
        return toks.popleft()

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
            toks.appendleft((kind, value))
            subject = term()
            if peek() != ("punct", "."):  # a named subject: its predicates and objects follow
                predicate_object_list(subject[1])
            assert take() == ("punct", ".")
    return graph


def read_prefixes(text):
    return {m[0]: m[1] for m in re.findall(r"@prefix\s+([\w-]*):\s+<([^>]*)>", text)}


#----------------------------------
#   The D3FEND knowledge graph as data
#----------------------------------


class KB:
    """The D3FEND classes, individuals and relations, and the categories each class and individual falls in."""

    def __init__(self, graph):
        self.graph = graph

        def typed(kind):
            return {s for s, po in graph.items() if s.startswith(D3F) and ("iri", kind) in po.get(TYPE, [])}

        self.classes = typed(OWL + "Class")
        self.relations = typed(OWL + "ObjectProperty")
        self.supers = {c: [v[1] for v in graph[c].get(SUBCLASS, []) if v[0] == "iri" and v[1] in self.classes] for c in self.classes}
        self.ancestors = {}
        self.individuals = {
            s
            for s, po in graph.items()
            if s.startswith(D3F) and s not in self.classes and any(v[1] in self.classes for v in po.get(TYPE, []))
        }
        missing = [root for _, root, *_ in CATEGORIES if D3F + root not in self.classes]
        if missing:
            sys.exit(f"the categories {', '.join(missing)} are not D3FEND classes")

    def above(self, c):
        """A class and every class above it."""
        if c not in self.ancestors:
            self.ancestors[c] = {c}  # a placeholder, in case of a cycle
            out = {c}
            for s in self.supers[c]:
                out |= self.above(s)
            self.ancestors[c] = out
        return self.ancestors[c]

    def types(self, iri):
        """The D3FEND classes an individual is typed by; a class is its own type."""
        if iri in self.classes:
            return [iri]
        return [v[1] for v in self.graph[iri].get(TYPE, []) if v[1] in self.classes]

    def labels(self, iri, holds):
        """The categories a class or individual falls in, holding classes or individuals, finest first."""
        above = set().union(*(self.above(t) for t in self.types(iri))) if self.types(iri) else set()
        return [label for label, root, _, h, *_ in CATEGORIES if h == holds and D3F + root in above]

    def endpoints(self, iri):
        """The categories a class or individual is linked as: those its relationships are drawn between, leaving
        out any another of them implies, e.g. Artifact for a DigitalArtifact. A class that falls in none is a
        D3FENDClass."""
        is_individual_category = bool(self.labels(iri, "individual"))
        found = [l for l in self.labels(iri, "individual" if is_individual_category else "class") if ENDPOINT[l]]
        implied = {i for l in found for i in IMPLIED[l]}
        found = [l for l in found if l not in implied]
        return found or ([] if is_individual_category else [BASE])

    def is_node(self, iri):
        """Whether a class or individual is a node: a class outside the individual categories, whose classes are
        the kinds of their individuals, or an individual in one of them."""
        if iri in self.classes:
            return not self.labels(iri, "individual")
        return iri in self.individuals and bool(self.labels(iri, "individual"))

    def text(self, iri, predicate):
        values = [v for v in self.graph[iri].get(predicate, []) if v[0] == "lit"]
        return tidy(values[0][1]) if values else ""

    def name(self, iri):
        return self.text(iri, LABEL) or local(iri)


ENDPOINT = {label: endpoint for label, _, _, _, endpoint, _ in CATEGORIES}
ROOT = {label: D3F + root for label, root, *_ in CATEGORIES}
HOLDS = {label: holds for label, _, _, holds, *_ in CATEGORIES}
IMPLIED = {label: implied for label, *_, implied in CATEGORIES}


def links_of(kb):
    """Every (subject, relation, object, how) link between two nodes: asserted directly, e.g. FileHashReputationAnalysis
    analyzes FileHash, or by a someValuesFrom or allValuesFrom restriction on the subject's class. Returns the links
    and those that touch something that is not a node."""
    links, dropped = set(), Counter()
    for s, po in kb.graph.items():
        if not s.startswith(D3F):
            continue
        for p, values in po.items():
            if p in kb.relations:
                for v in values:
                    if v[0] == "iri":
                        links.add((s, p, v[1], "asserted"))
        if s not in kb.classes:
            continue
        for restriction in (v for v in po.get(SUBCLASS, []) if v[0] == "bnode"):
            body = kb.graph[restriction[1]]
            p = next((v[1] for v in body.get(ONPROPERTY, []) if v[0] == "iri"), None)
            qualifier = next((q for q in (SOME, ALLV) if q in body), None)
            if p not in kb.relations or qualifier is None:
                continue
            value = body[qualifier][0]
            members = [value[1]] if value[0] == "iri" else [
                m[1] for c in kb.graph.get(value[1], {}).get(UNIONOF, []) if c[0] == "coll" for m in c[1] if m[0] == "iri"
            ]
            for o in members:
                links.add((s, p, o, local(qualifier)))
    kept = set()
    for s, p, o, how in links:
        if (s in kb.classes or kb.is_node(s)) and (o in kb.classes or kb.is_node(o)):
            kept.add((s, p, o, how))
        else:
            dropped[local(p)] += 1
    return kept, dropped


def build(graph, prefixes):
    kb = KB(graph)
    version = next((v[1] for s, po in graph.items() if ("iri", OWL + "Ontology") in po.get(TYPE, []) for v in po.get(OWL + "versionInfo", []) if v[0] == "lit"), "")
    released = next((v[1][:10] for s, po in graph.items() if ("iri", OWL + "Ontology") in po.get(TYPE, []) for v in po.get(D3F + "release-date", []) if v[0] == "lit"), "")

    members = {label: [] for label, *_ in CATEGORIES}
    members[BASE] = []
    for iri in sorted(kb.classes | kb.individuals):
        if not kb.is_node(iri):
            continue
        holds = "class" if iri in kb.classes else "individual"
        for label in kb.labels(iri, holds):
            members[label].append(iri)
        if holds == "class":
            members[BASE].append(iri)
    skipped_individuals = sorted(kb.name(i) for i in kb.individuals if not kb.is_node(i))

    def examples(iris, count=3):
        named = sorted((kb.name(i) for i in iris), key=lambda n: (len(n), n))
        return ", ".join(named[:count])

    def framework(iri):
        above = set().union(*(kb.above(t) for t in kb.types(iri)))
        return next((name for root, name in FRAMEWORKS if D3F + root in above), None)

    # The annotations each node carries, as property values, and the categories they land on.
    values = {}  # (node iri, property name) → [values]
    for iri in members[BASE] + [i for label, _, _, h, *_ in CATEGORIES if h == "individual" for i in members[label]]:
        for name, predicate in ANNOTATIONS.items():
            found = [v for v in graph[iri].get(predicate, []) if v[0] in ("lit", "iri")]
            if found:
                values[(iri, name)] = found

    def property_type(name, found):
        datatypes = {v[2] if v[0] == "lit" else None for v in found}
        types = {NEO4J_TYPES.get(d) or ("BOOLEAN" if d == RDF + "boolean" else "STRING") for d in datatypes}
        neo4j = types.pop() if len(types) == 1 else "STRING"
        if neo4j == "ZONED DATETIME" and not any(re.search(r"(Z|[+-]\d\d:\d\d)$", v[1]) for v in found):
            neo4j = "LOCAL DATETIME"  # D3FEND writes these dates without a time zone
        return f"LIST<{neo4j}>" if name in LISTS else neo4j

    def annotation_description(name):
        predicate = ANNOTATIONS[name]
        text = kb.text(predicate, D3F + "definition") if predicate in graph else ""
        text = re.sub(r"^x [\w-]+ y: ", "", text)
        return sentence(text) if text else ""

    homes = {}  # property name → the labels it is a property of
    for (iri, name), found in values.items():
        if iri in kb.classes:
            classes = [l for l in kb.labels(iri, "class") if ENDPOINT[l]] or [BASE]
            homes.setdefault(name, {"class": set(), "individual": set()})["class"].update(classes)
        else:
            homes.setdefault(name, {"class": set(), "individual": set()})["individual"].update(kb.labels(iri, "individual"))
    placed = {}
    for name, where in homes.items():
        on = set(where["individual"])
        if len(where["class"]) == 1 and where["class"] != {BASE}:
            on |= where["class"]
        elif where["class"]:
            on.add(BASE)
        for label in on:
            placed.setdefault(label, []).append(name)

    PROPERTY_TEXT = {
        "name": "The name of the {thing}: its rdfs:label in D3FEND, e.g. `{example}`.",
        "definition": "The definition of the {thing} in D3FEND.",
        "d3fendId": "The D3FEND identifier of a defensive technique or tactic, e.g. `D3-FH` for File Hashing.",
        "attackId": "The ATT&CK, ATLAS or SPARTA identifier of the {thing}, e.g. `T1003`.",
        "cweId": "The CWE identifier of the weakness, e.g. `CWE-79`.",
        "kbArticle": "The knowledge base article on the {thing}, in Markdown: how it works, its considerations and so on.",
        "synonyms": "Equivalent terms for the {thing}.",
        "prefLabel": "The preferred display label of the {thing}.",
        "altLabels": "Alternative labels of the {thing}.",
        "comment": "Notes on the {thing}: its rdfs:comment in D3FEND.",
        "seeAlso": "Related resources: the rdfs:seeAlso links of the {thing}, as IRIs or text.",
        "isDefinedBy": "Where the {thing} is defined: its rdfs:isDefinedBy links, e.g. a WordNet or vendor documentation IRI.",
        "deprecated": "Whether D3FEND deprecates the {thing}: owl:deprecated.",
        "title": "The title of the referenced work.",
        "abstract": "The abstract of the {thing}, or of the work it references.",
        "authors": "The authors of the referenced work.",
        "organization": "The organization that created or owns the referenced work.",
        "mitreAnalysis": "MITRE's analysis of the referenced work, as it bears on the techniques it is a reference of.",
        "link": "The link to the {thing}.",
        "capecId": "The CAPEC identifier of the attack pattern the {thing} corresponds to, e.g. `CAPEC-553`.",
        "d3fendComment": "A public note the D3FEND team has written on the {thing}, e.g. on how it maps to D3FEND.",
        "displayOrder": "The position the {thing} is listed in among others of its kind, in D3FEND's displays.",
        "displayPriority": "The priority of the {thing} in D3FEND's displays.",
        "releaseDate": "The release date of the {thing}, as text, e.g. `May 18, 2021`.",
        "controlName": "The name of the control or control enhancement, e.g. `Account Management | Automated System Account Management`.",
        "contributor": "The IRI of the organization that contributed the {thing}.",
        "published": "The date the {thing} was published.",
        "version": "The version of the {thing}, e.g. `2022-04-05` or `5`.",
        "archivedAt": "The link to the published {thing}.",
    }

    def property_of(label, name):
        found = [v for (i, n), vs in values.items() if n == name for v in vs]
        thing = {"TechniqueReference": "reference", "ExternalControl": "control", "ControlCatalog": "catalog"}.get(
            label, "class" if label == BASE else label
        )
        example = next((v[1] for (i, n), vs in values.items() if n == name and i in members[label] for v in vs[:1]), "")
        text = PROPERTY_TEXT.get(name, "").format(thing=thing, example=tidy(str(example))[:60])
        several = sum(1 for (i, n), vs in values.items() if n == name and len(vs) > 1 and i in members[label])
        if several and name not in LISTS:
            text += f" D3FEND gives {several} of them more than one; the first is kept."
        return {
            "type": property_type(name, found),
            "name": name,
            "description": describe(text or annotation_description(name) or f"The {local(ANNOTATIONS[name])} of the {thing}."),
            "reference": ANNOTATIONS[name],
            "extensions": {"custom": {"iri": ANNOTATIONS[name]}},
        }

    def uri_property(label):
        return {
            "type": "STRING",
            "name": "uri",
            "description": f"The IRI of the {'D3FEND class' if HOLDS.get(label, 'class') == 'class' else 'individual'} the node stands for, e.g. "
            f"`{(members[label] or [D3F])[0]}`. Unique within the knowledge base.",
            "reference": "https://www.w3.org/TR/rdf11-concepts/#section-IRIs",
        }

    nodes = {}
    for label, root, area, holds, endpoint, implied in [(BASE, None, "Core", "class", True, [])] + CATEGORIES:
        iris = members[label]
        if holds == "class" and label != BASE and not implied:
            implied = [BASE]  # every class category is a D3FENDClass, directly or through the label it implies
        properties = {"uri": uri_property(label)}
        if holds == "individual":
            kinds = sorted({local(t) for i in iris for t in kb.types(i)})
            properties["kind"] = {
                "type": "STRING",
                "name": "kind",
                "description": f"The D3FEND class the {label} is an individual of, e.g. `{kinds[0]}`.",
                "reference": D3F + root,
                "one_of": kinds,
            }
        if label in ("OffensiveTactic", "OffensiveTechnique", "ATTACKICSTechnique", "ATTACKMobileTechnique", "ATLASTechnique", "SPARTATechnique", "ATTACKEnterpriseMitigation", "ATTACKEnterpriseDataSource"):
            names = sorted({framework(i) for i in iris} - {None})
            properties["framework"] = {
                "type": "STRING",
                "name": "framework",
                "description": "The threat model the node comes from, by the D3FEND class it falls under, e.g. "
                "ATT&CK Enterprise for a class under ATTACKEnterpriseThing.",
                "reference": D3F + "ExternalThreatModelThing",
                "one_of": names,
            }
        for name in ANNOTATIONS:
            if name in placed.get(label, []):
                properties[name] = property_of(label, name)
        if label == BASE:
            definition = "A class of the D3FEND knowledge base: a defensive or offensive tactic or technique, a digital or physical artifact, an event, a weakness or any other concept D3FEND defines."
            what = (
                f"Every node that stands for a D3FEND class carries this label, {len(iris)} in D3FEND {version}; "
                "the label of its category, e.g. DefensiveTechnique, says what kind of class it is. Classes in no "
                "category, e.g. Vulnerability or Capability, carry this label alone."
            )
        else:
            definition = kb.text(D3F + root, D3F + "definition")
            kind = "classes under" if holds == "class" else "individuals of the classes under"
            what = f"Holds the {len(iris)} D3FEND {kind} {root} in D3FEND {version}, e.g. {examples(iris)}."
        nodes[label] = {
            "labels": {"identifier": label, **({"implied": implied} if implied else {})},
            "description": describe(sentence(definition), what),
            "reference": D3F + (root or "D3FENDThing"),
            "properties": properties,
            "constraints": {f"key_{label}": {"type": "KEY", "properties": ["uri"], "name": f"uri_{label}_key"}},
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (
                        ("iri", D3F + root if root else None),
                        ("area", area),
                        ("holds", "classes" if holds == "class" else "individuals"),
                        ("count", len(iris)),
                    )
                    if v is not None
                }
            },
        }

    # The relations, one direction per inverse pair: the direction D3FEND asserts more often, e.g. kb-reference over
    # kb-reference-of, with the links asserted the other way turned around.
    links, dropped = links_of(kb)
    used = Counter(p for _, p, _, _ in links)
    inverses = {}
    for p in kb.relations:
        for v in graph[p].get(INVERSE, []):
            if v[1] in kb.relations:
                inverses.setdefault(p, v[1])
                inverses.setdefault(v[1], p)
    canonical = {}
    for p in kb.relations:
        q = inverses.get(p)
        canonical[p] = p if q is None or (used[p], local(q)) > (used[q], local(p)) else q
    turned = set()
    for s, p, o, how in links:
        if canonical[p] == p:
            turned.add((s, p, o, how))
        else:
            turned.add((o, canonical[p], s, f"inverse {how}"))

    # A link with a class that isn't a node at one end, e.g. a restriction on the class TechniqueReference, whose
    # individuals are the nodes, is a statement about the category rather than a link in the data.
    used_relations = {p for _, p, _, _ in turned}
    narrower = {p: [q for q in used_relations if p in {v[1] for v in graph[q].get(SUBPROPERTY, [])}] for p in kb.relations}
    grouped, statements = {}, {}
    for s, p, o, how in sorted(turned):
        for a in kb.endpoints(s):
            for b in kb.endpoints(o):
                stated_on_root = how.endswith("someValuesFrom") and (s == ROOT.get(a) if how == "someValuesFrom" else o == ROOT.get(b))
                if not (kb.is_node(s) and kb.is_node(o)):
                    if stated_on_root:
                        statements.setdefault((p, a, b), how)
                    continue
                entry = grouped.setdefault((p, a, b), {"pairs": set(), "how": Counter(), "from": False, "to": False, "stated": False})
                entry["pairs"].add((s, o))
                entry["how"][how] += 1
                if stated_on_root:  # a restriction on the root class of a category of classes, which is a node
                    entry["stated"] = a if how == "someValuesFrom" else b

    # A restriction on the root class of a category of individuals requires a link of each of them, unless D3FEND
    # links them by narrower relations, e.g. related for semantic-relation; then it is told in the node's description.
    told = {}
    for (p, a, b), how in sorted(statements.items()):
        entry = grouped.get((p, a, b))
        subject, target = (a, b) if how == "someValuesFrom" else (b, a)
        linked = {pair[0 if how == "someValuesFrom" else 1] for pair in entry["pairs"]} if entry else set()
        unlinked = len(set(members[subject]) - linked)
        if entry and not narrower[p] and not unlinked:
            entry["from" if how == "someValuesFrom" else "to"] = True
            continue
        verb = kb.name(p) if how == "someValuesFrom" else kb.name(inverses[p]) if p in inverses else f"is the object of {kb.name(p)} from"
        alternatives = sorted(kb.name(q) for q in narrower[p] if (q, a, b) in grouped)
        told.setdefault(subject, []).append(
            f"D3FEND states that every {subject} {verb} some {target}"
            + (f", which it links by {', '.join(alternatives)}." if alternatives else ".")
            + (f" {unlinked} of them have no such link, so the ontology doesn't require one." if entry and not narrower[p] and unlinked else "")
        )

    def flags(p):
        kinds = {v[1] for v in graph[p].get(TYPE, [])}
        return OWL + "TransitiveProperty" in kinds, OWL + "SymmetricProperty" in kinds, OWL + "FunctionalProperty" in kinds

    relationships = {}
    for (p, a, b), entry in sorted(grouped.items(), key=lambda e: (rel_type(local(e[0][0])), e[0][1], e[0][2])):
        name = kb.name(p)
        inverse = inverses.get(p)
        transitive, symmetric, functional = flags(p)
        pairs = sorted(entry["pairs"], key=lambda pair: (kb.name(pair[0]), kb.name(pair[1])))
        definition = re.sub(r"^x [\w-]+ y: ", "", kb.text(p, D3F + "definition"))
        sample = "; ".join(f"{kb.name(s)} {name} {kb.name(o)}" for s, o in pairs[:3])
        rid = f"{a}_{rel_type(name)}_{b}"
        relationships[rid] = {
            "type": rel_type(name),
            "from": {"node": a, **({"min_count": 1} if entry["from"] else {})},
            "to": {"node": b, **({"min_count": 1} if entry["to"] else {})},
            "description": describe(
                sentence(definition) if definition else f"The D3FEND relation '{name}'.",
                f"Every {a} {name} some {b}." if entry["from"] else "",
                (f"Every {b} {kb.name(inverse)} some {a}." if inverse else f"Every {b} is the object of {name} from some {a}.")
                if entry["to"]
                else "",
                f"D3FEND restricts the class {entry['stated']} itself, so the classes below it have such a link "
                "through their SUBCLASS_OF path rather than directly." if entry["stated"] else "",
                f"Links {len(pairs)} pair{'s' if len(pairs) != 1 else ''} in D3FEND {version}, e.g. {sample}.",
                f"The inverse D3FEND relation is '{kb.name(inverse)}'." if inverse else "",
                "Transitive." if transitive else "",
                "Symmetric." if symmetric else "",
            ),
            "reference": p,
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (
                        ("iri", p),
                        ("definite", not kb.name(p).startswith("may-")),  # D3FEND names its possible relations may-…
                        ("links", len(pairs)),
                        ("asserted", entry["how"]["asserted"] + entry["how"]["inverse asserted"]),
                        ("restrictions", sum(n for h, n in entry["how"].items() if "ValuesFrom" in h)),
                        ("inverseOf", kb.name(inverse) if inverse else None),
                        ("subPropertyOf", [kb.name(v[1]) for v in graph[p].get(SUBPROPERTY, []) if v[1] in kb.relations]),
                        ("transitive", transitive),
                        ("symmetric", symmetric),
                        ("functional", functional),
                    )
                    if v not in (None, [], False, 0)
                }
            },
        }

    # The class hierarchy, between the classes themselves.
    subclass_pairs = [(c, s) for c in members[BASE] for s in kb.supers[c] if kb.is_node(s)]
    relationships[f"{BASE}_SUBCLASS_OF_{BASE}"] = {
        "type": "SUBCLASS_OF",
        "from": {"node": BASE},
        "to": {"node": BASE},
        "description": describe(
            "x subclass of y: the D3FEND class x is a subclass of y (rdfs:subClassOf), so everything that holds for y "
            "holds for x too; e.g. a relation D3FEND states for File Analysis holds for File Hashing.",
            f"Links {len(subclass_pairs)} pairs in D3FEND {version}; {sum(1 for c in members[BASE] if len(kb.supers[c]) > 1)} classes have more than one superclass.",
        ),
        "reference": SUBCLASS,
        "extensions": {"custom": {"iri": SUBCLASS, "definite": True, "links": len(subclass_pairs)}},
    }

    for label, texts in told.items():
        nodes[label]["description"] = describe(nodes[label]["description"], *texts)

    for rel in relationships.values():
        for end in (rel["from"], rel["to"]):
            if end["node"] not in nodes:
                sys.exit(f"relationship {rel['type']} points at {end['node']}, which is not a node")

    model = {
        "schema": SCHEMA,
        "version": version,
        "id": f"d3fend-{version}",
        "name": f"MITRE D3FEND {version}",
        "description": (
            f"MITRE D3FEND {version} (released {released}), a knowledge graph of cybersecurity countermeasures "
            "(https://d3fend.mitre.org/), funded by the NSA Cybersecurity Directorate and managed by MITRE. D3FEND "
            "relates the defensive techniques that counter cyber attacks, and the tactics they serve, to the digital "
            "artifacts they analyze, harden, isolate, deceive with, evict or restore, and to the offensive techniques "
            "of MITRE ATT&CK, ATLAS and SPARTA that act on the same artifacts; it maps them to CWE weaknesses, NIST "
            "SP 800-53 and DISA CCI controls, ATT&CK mitigations and the references that ground them. D3FEND's "
            "classes are the content of the knowledge graph, so each becomes a node, labelled by its category, e.g. "
            "DefensiveTechnique or DigitalArtifact, and also D3FENDClass. Its references, controls and catalogs, "
            "which D3FEND holds as individuals, are nodes too. Each D3FEND relation, asserted or stated by a "
            "restriction, is a relationship between the categories it links, and rdfs:subClassOf is SUBCLASS_OF. "
            "Generated from the D3FEND Turtle file."
        ),
        "nodes": nodes,
        "relationships": relationships,
    }
    return model, dropped, skipped_individuals


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
        source = Path(tempfile.mkdtemp()) / "d3fend.ttl"
        request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request) as response:
            source.write_bytes(response.read())
    text = source.read_text()
    model, dropped, skipped = build(parse_turtle(text), read_prefixes(text))
    out = Path(__file__).parent
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(yaml(model) + "\n")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships")
    if skipped:
        print(f"{len(skipped)} example individuals left out, e.g. {', '.join(skipped[:5])}")
    if dropped:
        print(f"links to or from them left out: {sum(dropped.values())} ({', '.join(f'{k} {v}' for k, v in dropped.most_common())})")


if __name__ == "__main__":
    main()
