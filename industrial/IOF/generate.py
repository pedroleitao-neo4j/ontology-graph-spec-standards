#!/usr/bin/env python3
"""Generates the IOF Core, Supply Chain, Maintenance, Certification and Production Planning ontology from the IOF
ontology repository.

Usage: python3 generate.py [path/to/iof/ontology]

The five entry modules are the Core, Supply Chain, Maintenance, Certification and Production Planning
ontologies of the Industrial Ontologies Foundry (IOF), at the commit of the repository's Release_202603 tag. Their owl:imports,
followed to the full closure, add the Basic Formal Ontology (BFO 2020) they're built on and the
IOF annotation vocabulary. Each import is resolved to a file through the release's own XML catalog,
catalog-v001.xml, and the files are downloaded from raw.githubusercontent.com at the pinned commit
(or read from a local checkout given as the argument). Writes model.json and model.yaml next to
this script. Uses only the Python standard library.
"""

import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

COMMIT = "0c5af080dba16489db1b5c7a432a34222524c6e9"  # the Release_202603 tag
RAW = f"https://raw.githubusercontent.com/iofoundry/ontology/{COMMIT}/"
CATALOG = "catalog-v001.xml"
IOF = "https://spec.industrialontologies.org/ontology/"
OBO = "http://purl.obolibrary.org/obo/"
ENTRY = [
    IOF + tail
    for tail in (
        "core/Core/",
        "supplychain/SupplyChain/",
        "maintenance/Maintenance/",
        "certification/Certification/",
        "productionplanning/ProductionPlanning/",
    )
]
SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
DATA = "IOF"  # whose data a node's uri is the IRI in
MAX_DESCRIPTION = 1024

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
XSD = "http://www.w3.org/2001/XMLSchema#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
AV = IOF + "annotation/"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

TYPE = RDF + "type"
SUBCLASS = RDFS + "subClassOf"
SUBPROPERTY = RDFS + "subPropertyOf"
DOMAIN = RDFS + "domain"
RANGE = RDFS + "range"
LABEL = RDFS + "label"
COMMENT = RDFS + "comment"
DEFINITION = SKOS + "definition"
NATURAL_DEFINITION = AV + "naturalLanguageDefinition"
INVERSE = OWL + "inverseOf"
EQUIVALENT = OWL + "equivalentClass"
UNIONOF = OWL + "unionOf"
INTERSECTIONOF = OWL + "intersectionOf"
ONPROPERTY = OWL + "onProperty"
ONCLASS = OWL + "onClass"
ONDATARANGE = OWL + "onDataRange"
SOME = OWL + "someValuesFrom"
ALLV = OWL + "allValuesFrom"
HASVALUE = OWL + "hasValue"
QUALIFIED = (OWL + "qualifiedCardinality", OWL + "minQualifiedCardinality", OWL + "maxQualifiedCardinality")
THING = OWL + "Thing"

# The root of the model: BFO's entity, which every class of the closure specialises and the
# unconstrained property ends stand for.
ENTITY = OBO + "BFO_0000001"

# The datatypes IOF ranges its datatype properties over, as Neo4j types. owl:rational has no
# exact Neo4j equivalent, so it is a FLOAT.
DATATYPES = {
    XSD + "string": "STRING",
    XSD + "normalizedString": "STRING",
    XSD + "token": "STRING",
    XSD + "anyURI": "STRING",
    XSD + "Name": "STRING",
    RDFS + "Literal": "STRING",
    RDF + "langString": "STRING",
    XSD + "boolean": "BOOLEAN",
    XSD + "date": "DATE",
    XSD + "dateTime": "ZONED DATETIME",
    XSD + "dateTimeStamp": "ZONED DATETIME",
    XSD + "time": "LOCAL TIME",
    XSD + "duration": "DURATION",
    XSD + "integer": "INTEGER",
    XSD + "nonNegativeInteger": "INTEGER",
    XSD + "positiveInteger": "INTEGER",
    XSD + "nonPositiveInteger": "INTEGER",
    XSD + "negativeInteger": "INTEGER",
    XSD + "long": "INTEGER",
    XSD + "int": "INTEGER",
    XSD + "short": "INTEGER",
    XSD + "byte": "INTEGER",
    XSD + "decimal": "FLOAT",
    XSD + "double": "FLOAT",
    XSD + "float": "FLOAT",
    OWL + "rational": "FLOAT",
}

# The prefixes that compact IRIs from other vocabularies, e.g. xsd:decimal.
PREFIXES = {
    "xsd": XSD,
    "rdf": RDF,
    "rdfs": RDFS,
    "owl": OWL,
    "skos": SKOS,
    "bfo": OBO,
    "iof": IOF + "construct/",
}

# The module each ontology of the closure is, by the path of its IRI below the IOF namespace, and
# the area a term's module places it in, for extensions.custom.area and the diagram.
MODULES = {
    "core/Core": "Core",
    "supplychain/SupplyChain": "SupplyChain",
    "maintenance/Maintenance": "Maintenance",
    "certification/Certification": "Certification",
    "productionplanning/ProductionPlanning": "ProductionPlanning",
    "core/meta/AnnotationVocabulary": "AnnotationVocabulary",
}
AREAS = {
    "BFO": "BFO top level",
    "Core": "Core",
    "SupplyChain": "Supply chain",
    "Maintenance": "Maintenance",
    "Certification": "Certification",
    "ProductionPlanning": "Production planning",
}


def words(text):
    """The words of a snake_case or CamelCase name, e.g. has_part → has, part; LegalPerson → Legal, Person."""
    return re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z\d]*|[a-z\d]+", text) or re.findall(r"[A-Za-z0-9]+", text)


def pascal(name):
    """A class name or label as a label, e.g. material entity → MaterialEntity."""
    return "".join(w[0].upper() + w[1:] for w in words(name))


def rel_type(name):
    return "_".join(w.upper() for w in words(name))


def article(name):
    return "an" if name[0] in "AEIOU" else "a"


def local(iri):
    return re.split(r"[/#]", iri)[-1]


def compact(iri):
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
#   Reading the ontologies
#----------------------------------


def parse_rdfxml(data, scope):
    """Reads an RDF/XML document into a subject → predicate → [values] graph.

    A value is an ("iri", iri), ("lit", text, datatype or langtag or None), ("bnode", id) or
    ("coll", [values]) tuple, as the Turtle readers of the other standards give. Blank nodes are
    named within `scope` so that the blank nodes of different modules stay apart. Covers the
    RDF/XML that IOF and BFO use: rdf:about, rdf:resource, rdf:datatype, xml:lang, typed node
    elements and rdf:parseType="Collection". Every IRI is absolute once the internal DTD entities
    are expanded, so xml:base isn't needed.
    """
    graph, counter = {}, 0

    def name(tag):
        namespace, _, local_name = tag[1:].partition("}")
        return namespace + local_name

    def node(element):
        """The subject a node element describes, with its type and properties added to the graph."""
        nonlocal counter
        subject = element.get(f"{{{RDF}}}about")
        if subject is None:
            counter += 1
            subject = f"_:{scope}b{counter}"
        po = graph.setdefault(subject, {})
        if name(element.tag) != RDF + "Description":
            po.setdefault(TYPE, []).append(("iri", name(element.tag)))
        for prop in element:
            po.setdefault(name(prop.tag), []).append(value(prop))
        return ("bnode", subject) if subject.startswith("_:") else ("iri", subject)

    def value(prop):
        if prop.get(f"{{{RDF}}}resource") is not None:
            return ("iri", prop.get(f"{{{RDF}}}resource"))
        if prop.get(f"{{{RDF}}}parseType") == "Collection":
            return ("coll", [node(child) for child in prop])
        children = list(prop)
        if children:
            return node(children[0])
        return ("lit", prop.text or "", prop.get(f"{{{RDF}}}datatype") or (f"@{prop.get(XML_LANG)}" if prop.get(XML_LANG) else None))

    for element in ET.fromstring(data):
        node(element)
    return graph


class Source:
    """The files of the import closure, read from the pinned commit of the IOF repository (or a
    local checkout) and cached in memory. An import IRI is resolved to a file by the release's XML
    catalog, which maps both the unversioned and the versioned IRI of each module, and those of
    the cached BFO, to the file in the repository."""

    def __init__(self, local=None):
        self.local = Path(local).resolve() if local else None
        self.cache = {}
        catalog = ET.fromstring(self.read(CATALOG))
        self.paths = {
            entry.get("name"): entry.get("uri").removeprefix("./")
            for entry in catalog.iter("{urn:oasis:names:tc:entity:xmlns:xml:catalog}uri")
        }

    def read(self, path):
        if path in self.cache:
            return self.cache[path]
        if self.local is not None:
            self.cache[path] = (self.local / path).read_bytes()
            return self.cache[path]
        url = RAW + path
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})) as response:
                self.cache[path] = response.read()
        except Exception as error:
            sys.exit(f"could not download {url}: {error}")
        return self.cache[path]

    def path(self, iri):
        """The file an import IRI stands for, or None if the catalog doesn't map it."""
        return self.paths.get(iri)


def module_name(ontology_iri):
    """The short name of a module, from the IRI its owl:Ontology declares, e.g. Core or BFO."""
    if ontology_iri.startswith(OBO):
        return "BFO"
    tail = re.sub(r"^\d{6}/", "", ontology_iri[len(IOF):]).rstrip("/")
    if tail not in MODULES:
        sys.exit(f"{ontology_iri}: an IOF module this generator doesn't know")
    return MODULES[tail]


def closure(source):
    """The modules the entry modules' owl:imports close over: module name → graph, in the order
    found. A module is known by the file the catalog resolves it to, since BFO is imported by
    an IRI other than the one its owl:Ontology declares."""
    modules, seen, pending = {}, set(), list(ENTRY)
    while pending:
        iri = pending.pop(0)
        path = source.path(iri)
        if path is None:
            sys.exit(f"{iri}: an import the release's catalog doesn't resolve")
        if path in seen:
            continue
        seen.add(path)
        graph = parse_rdfxml(source.read(path), f"m{len(seen)}_")
        ontology = next(s for s, po in graph.items() if ("iri", OWL + "Ontology") in po.get(TYPE, []))
        modules[module_name(ontology)] = graph
        pending += sorted(v[1] for v in graph[ontology].get(OWL + "imports", []) if v[0] == "iri")
    return modules


#----------------------------------
#   The ontologies as data
#----------------------------------


class Ontology:
    """The classes and properties of the closure, read out of the merged graph of its modules."""

    def __init__(self, modules):
        self.modules = list(modules)
        self.graph = {}
        # The module that declares each term. IOF's modules share one namespace, construct/, so a
        # term's IRI doesn't say which module it belongs to.
        self.declared_in = {}
        for module, graph in modules.items():
            for subject, po in graph.items():
                if not subject.startswith("_:") and po.get(TYPE):
                    self.declared_in.setdefault(subject, module)
                if subject in self.graph:
                    for predicate, values in po.items():
                        self.graph[subject].setdefault(predicate, []).extend(values)
                else:
                    self.graph[subject] = {p: list(v) for p, v in po.items()}

        def declared(kind):
            return {
                subject
                for subject, po in self.graph.items()
                if not subject.startswith("_:") and ("iri", kind) in po.get(TYPE, [])
            }

        deprecated = {
            subject
            for subject, po in self.graph.items()
            if any(v[0] == "lit" and v[1] == "true" for v in po.get(OWL + "deprecated", []))
        }
        # The annotation vocabulary's one class, MaturityLevel, rates the IOF's own modules, not
        # the domain, so it's left out.
        housekeeping = {c for c in declared(OWL + "Class") if self.declared_in[c] == "AnnotationVocabulary"}
        self.classes = declared(OWL + "Class") - housekeeping - deprecated
        self.data_properties = declared(OWL + "DatatypeProperty") - deprecated
        # An rdf:Property that is neither an annotation nor a datatype property relates individuals.
        self.properties = (declared(OWL + "ObjectProperty") | (declared(RDF + "Property") - self.data_properties - declared(OWL + "AnnotationProperty"))) - deprecated
        self.deprecated = sorted(deprecated & (declared(OWL + "Class") | declared(OWL + "ObjectProperty") | declared(OWL + "DatatypeProperty")))
        self.dropped = {}  # what the axioms say that the ontology can't, by construct
        if housekeeping:
            self.dropped["the annotation vocabulary's classes"] = [local(c) for c in housekeeping]

        if ENTITY not in self.classes:
            sys.exit("BFO's entity, the root of the model, isn't in the closure")

        # The PascalCase label of each class. Two classes that share one are told apart by their
        # module.
        counts = {}
        for iri in sorted(self.classes):
            counts.setdefault(pascal(self.name_of(iri)), []).append(iri)
        self.names = {}
        for name, iris in counts.items():
            if len(iris) == 1:
                self.names[iris[0]] = name
            else:
                for iri in sorted(iris, key=self.module_of):
                    self.names[iri] = name + self.module_of(iri)
        if len(set(self.names.values())) != len(self.names):
            sys.exit("two classes share a label even after their modules are appended")

        # A pair of inverse properties is declared from one side only, so the map is built in both
        # directions.
        self.inverses = {}
        for iri in sorted(self.properties):
            for inverse in self.iris(iri, INVERSE):
                if inverse in self.properties and inverse != iri:
                    self.inverses.setdefault(iri, inverse)
                    self.inverses.setdefault(inverse, iri)

    def values(self, subject, predicate):
        return self.graph.get(subject, {}).get(predicate, [])

    def iris(self, subject, predicate):
        return [v[1] for v in self.values(subject, predicate) if v[0] == "iri"]

    def text(self, subject, predicate):
        """A literal, in English where the term has one in several languages."""
        values = [v for v in self.values(subject, predicate) if v[0] == "lit" and tidy(v[1])]
        english = [v for v in values if (v[2] or "").startswith("@en")] or values
        return tidy(english[0][1]) if english else ""

    def comments(self, iri):
        """The term's definition: IOF's natural language definition, else skos:definition, which
        BFO uses, else rdfs:comment, as sentences."""
        for predicate in (NATURAL_DEFINITION, DEFINITION, COMMENT):
            for value in self.values(iri, predicate):
                if value[0] == "lit" and tidy(value[1]):
                    return [sentence(self.text(iri, predicate))]
        return []

    def said(self, iri):
        """A term as IOF and BFO write it in prose: its rdfs:label, e.g. 'has role'."""
        return self.text(iri, LABEL) or " ".join(w.lower() for w in words(local(iri)))

    def name_of(self, iri):
        """The name a term's label or type is made from: its rdfs:label, e.g. 'material entity'
        for BFO_0000040, whose local name is an opaque identifier, or 'consignor' for Shipper,
        which IOF has renamed without changing its IRI."""
        return self.said(iri)

    def property_name(self, iri):
        """The name of a datatype property: its local name, e.g. hasSimpleExpressionValue."""
        return local(iri)

    def kinds(self, iri):
        return {local(k) for k in self.iris(iri, TYPE)}

    def module_of(self, iri):
        """The module that declares a term, e.g. Core, SupplyChain or BFO."""
        return self.declared_in.get(iri, "")

    def area_of(self, iri):
        return AREAS.get(self.module_of(iri), "")

    def members(self, value, keyword):
        """The members of a blank node's union or intersection, or [] if it is neither."""
        if value[0] != "bnode":
            return []
        return next((v[1] for v in self.values(value[1], keyword) if v[0] == "coll"), [])

    def fillers(self, value):
        """The named classes a class expression stands for: a class itself, the members of a union,
        or the named members of an intersection. A restriction or complement names no class."""
        if value[0] == "iri":
            return [ENTITY if value[1] == THING else value[1]]
        union = self.members(value, UNIONOF)
        if union:
            return [c for member in union for c in self.fillers(member)]
        return [m[1] for m in self.members(value, INTERSECTIONOF) if m[0] == "iri"]

    def kept(self, prop):
        """Whether a property is the direction of its inverse pair that becomes a relationship.
        IOF and BFO name most pairs in the active and the passive voice, e.g. 'owns' and 'owned
        by', or 'has role' and 'role of'; the active one is kept. Of a pair in the same voice, the
        one that starts with 'has' is kept, e.g. 'has participant at some time' rather than
        'participates in at some time', else the one the other declares itself the owl:inverseOf,
        else the first by label."""
        inverse = self.inverses.get(prop)
        if inverse is None:
            return True
        labels = [self.said(p) for p in (prop, inverse)]
        passive = [bool(re.search(r"\b(by|of)\b", label)) for label in labels]
        if passive[0] != passive[1]:
            return not passive[0]
        having = [label.startswith("has ") for label in labels]
        if having[0] != having[1]:
            return having[0]
        declares = [inverse in self.iris(prop, INVERSE), prop in self.iris(inverse, INVERSE)]
        if declares[0] != declares[1]:
            return declares[1]
        return labels[0] < labels[1]

    def end_classes(self, prop, end, seen=None):
        """The classes at one end of a property: its own domain or range, else its inverse's other
        end, else its superproperties'. An empty result means the end is left unconstrained."""
        seen = set() if seen is None else seen
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
            if supertype in self.properties or supertype in self.data_properties:
                out |= self.end_classes(supertype, end, seen)
        return out

    def on_property(self, body):
        """The property a restriction is on, and whether it is on its anonymous inverse, e.g.
        inverse(has participant at some time). An anonymous inverse of a property that has a named
        inverse is that named property."""
        value = body[ONPROPERTY][0]
        if value[0] == "iri":
            return value[1], False
        base = next(v[1] for v in self.values(value[1], INVERSE) if v[0] == "iri")
        if base in self.inverses:
            return self.inverses[base], False
        return base, True

    def axioms(self, cls):
        """The restrictions a class's axioms place on it: those it is a subclass of, and those its
        equivalent classes are or intersect, which are necessary conditions too."""
        out = []
        for value in self.values(cls, SUBCLASS) + self.values(cls, EQUIVALENT):
            if value[0] == "bnode" and ONPROPERTY in self.graph[value[1]]:
                out.append(value)
            out += [m for m in self.members(value, INTERSECTIONOF) if m[0] == "bnode" and ONPROPERTY in self.graph[m[1]]]
        return out

    def named_supers(self, cls):
        """The named classes a class is stated to specialise: its superclasses and the named members
        of an intersection it is a subclass of or equivalent to. IOF states many superclasses inside
        an intersection, e.g. Factory ⊑ Facility ⊓ hasCapability some ProductionCapability."""
        out = [s for s in self.iris(cls, SUBCLASS) if s in self.classes]
        for value in self.values(cls, SUBCLASS) + self.values(cls, EQUIVALENT):
            out += [m[1] for m in self.members(value, INTERSECTIONOF) if m[0] == "iri" and m[1] in self.classes]
        return [s for s in dict.fromkeys(out) if s != cls]

    def supertypes(self, cls):
        """The direct named supertypes of a class. A superclass that is neither a named class, a
        restriction nor an intersection, such as a union, is dropped."""
        for value in self.values(cls, SUBCLASS):
            if value[0] == "bnode" and ONPROPERTY not in self.graph[value[1]] and not self.members(value, INTERSECTIONOF):
                self.dropped.setdefault("subclass axioms that are unions of classes or other expressions", []).append(
                    self.names[cls]
                )
        out = self.named_supers(cls)
        # Only the direct supertypes: one that another supertype already specialises adds nothing.
        return [s for s in out if not any(s in self.ancestors(o) for o in out if o != s)]

    def ancestors(self, cls, seen=None):
        seen = set() if seen is None else seen
        for s in self.named_supers(cls):
            if s not in seen:
                seen.add(s)
                self.ancestors(s, seen)
        return seen


def restriction_bounds(body):
    """The lower and upper count a restriction places, qualified or not: someValuesFrom is one or more."""
    def number(key):
        return int(body[OWL + key][0][1]) if OWL + key in body else None

    for exact, low, high in (
        ("cardinality", "minCardinality", "maxCardinality"),
        ("qualifiedCardinality", "minQualifiedCardinality", "maxQualifiedCardinality"),
    ):
        if number(exact) is not None:
            return number(exact), number(exact)
        if number(low) is not None or number(high) is not None:
            return number(low) or 0, number(high)
    return (1, None) if SOME in body else (0, None)


def build(onto):
    nodes = {}
    for iri in sorted(onto.classes, key=lambda c: onto.names[c]):
        name = onto.names[iri]
        supertypes = [onto.names[s] for s in onto.supertypes(iri)]
        if iri != ENTITY and not supertypes:
            supertypes = [onto.names[ENTITY]]  # a top class: everything is an entity
        description = describe(*onto.comments(iri))
        nodes[name] = {
            "labels": {"identifier": name, **({"implied": supertypes} if supertypes else {})},
            **({"description": description} if description else {}),
            "reference": iri,
            "properties": {
                "uri": {
                    "type": "STRING",
                    "name": "uri",
                    "description": f"The identifier of the {name} individual: its IRI in {DATA} data. Unique within a "
                    "data set; individuals that are blank nodes are given generated identifiers.",
                    "reference": "https://www.w3.org/TR/rdf11-concepts/#section-IRIs",
                }
            },
            "constraints": {f"key_{name}": {"type": "KEY", "properties": ["uri"], "name": f"uri_{name}_key"}},
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (
                        ("iri", iri),
                        ("module", onto.module_of(iri)),
                        ("area", onto.area_of(iri)),
                        ("subClassOf", [s for s in onto.iris(iri, SUBCLASS) if s not in onto.classes and s != THING]),
                        ("disjointWith", sorted(onto.names[d] for d in onto.iris(iri, OWL + "disjointWith") if d in onto.names)),
                    )
                    if v not in ("", None, [])
                }
            },
        }

    # Relationships are gathered by type and ends, so that what the domain and range say and what
    # each restriction adds end up on one relationship: its counts, and the sentences that explain
    # them.
    gathered = {}

    def relationship(prop, source, target):
        key = (prop, source, target)
        if key not in gathered:
            gathered[key] = {"from": [0, None], "to": [0, None], "notes": [], "restrictions": []}
        return gathered[key]

    def tighten(end, lower, upper):
        end[0] = max(end[0], lower)
        if upper is not None:
            end[1] = upper if end[1] is None else min(end[1], upper)

    def classes_or_root(found, prop):
        """The classes at one end of a property, or Entity where it is left unconstrained. owl:Thing
        stands for Entity too."""
        found = {ENTITY if c == THING else c for c in found}
        unknown = sorted(c for c in found if c not in onto.names)
        if unknown:
            onto.dropped.setdefault("domains, ranges or fillers outside the import closure", []).append(
                f"{local(prop)} ({', '.join(local(c) for c in unknown)})"
            )
        return sorted((c for c in found if c in onto.names), key=onto.names.get) or [ENTITY]

    for prop in sorted(onto.properties):
        if onto.kept(prop):
            for source in classes_or_root(onto.end_classes(prop, "domain"), prop):
                for target in classes_or_root(onto.end_classes(prop, "range"), prop):
                    rel = relationship(prop, source, target)
                    if "FunctionalProperty" in onto.kinds(prop):
                        tighten(rel["from"], 0, 1)
                    if "InverseFunctionalProperty" in onto.kinds(prop):
                        tighten(rel["to"], 0, 1)

    # Each restriction becomes a relationship from the restricted class, or, on the inverse of a
    # kept property, to it: someValuesFrom and the cardinalities, qualified or not, give counts at
    # the restricted end, allValuesFrom a narrower end. A restriction on a datatype property is
    # gathered instead, to become a property of the restricted class.
    restricted_data = {}  # (class, datatype property) → {"bounds": [lower, upper], "ranges": [...]}
    for cls in sorted(onto.classes, key=lambda c: onto.names[c]):
        name = onto.names[cls]
        for restriction in onto.axioms(cls):
            body = onto.graph[restriction[1]]
            used, reverse = onto.on_property(body)
            if used in onto.data_properties:
                if HASVALUE in body:
                    onto.dropped.setdefault("hasValue restrictions, which fix a value rather than a type", []).append(name)
                    continue
                entry = restricted_data.setdefault((cls, used), {"bounds": [0, None], "ranges": []})
                lower, upper = restriction_bounds(body)
                tighten(entry["bounds"], lower, upper)
                entry["ranges"] += body.get(ONDATARANGE, []) + [
                    v for k in (SOME, ALLV) for v in body.get(k, [])
                ]
                continue
            if HASVALUE in body:
                onto.dropped.setdefault("hasValue restrictions, which fix a value rather than a type", []).append(name)
                continue
            if used not in onto.properties:
                onto.dropped.setdefault("restrictions on a property that isn't kept", []).append(name)
                continue
            prop, forward = (used, True) if onto.kept(used) else (onto.inverses[used], False)
            forward = forward != reverse
            said = onto.said(used)
            far = "domain" if reverse else "range"  # the end of the property the filler is at
            if SOME in body or ALLV in body:
                value = (body.get(SOME) or body.get(ALLV))[0]
                targets = onto.fillers(value)
                union = bool(onto.members(value, UNIONOF))
                if not targets and SOME in body:
                    # A filler that names no class, e.g. a nested restriction: what the property
                    # ranges over stands for it.
                    targets = classes_or_root(onto.end_classes(used, far), used)
                    union = len(targets) > 1
                if not targets:
                    onto.dropped.setdefault("allValuesFrom restrictions whose filler names no class", []).append(name)
                    continue
                lower, upper = (1 if SOME in body and not union else 0), None
            elif any(k in body for k in QUALIFIED):
                # A qualified cardinality counts the values that are of its class, e.g. every
                # Contract has at least two contract parties.
                lower, upper = restriction_bounds(body)
                if upper == 0:
                    onto.dropped.setdefault("cardinalities of zero", []).append(name)
                    continue
                filler = (body.get(ONCLASS) or [("iri", ENTITY)])[0]
                targets = onto.fillers(filler) or classes_or_root(onto.end_classes(used, far), used)
                union = len(targets) > 1
                if union:
                    lower = 0  # only one of the union's classes need be counted
            elif {OWL + "cardinality", OWL + "minCardinality", OWL + "maxCardinality"} & body.keys():
                lower, upper = restriction_bounds(body)
                if upper == 0:
                    onto.dropped.setdefault("cardinalities of zero", []).append(name)
                    continue
                # An unqualified cardinality counts the values another restriction on the property
                # narrows, e.g. every contract has exactly one effective date, which is a Date.
                narrowed = [
                    c
                    for other in onto.axioms(cls)
                    if ("iri", used) in onto.graph[other[1]][ONPROPERTY] and ALLV in onto.graph[other[1]]
                    for c in onto.fillers(onto.graph[other[1]][ALLV][0])
                ]
                targets = [v[1] for v in body.get(ONCLASS, []) if v[0] == "iri"] or narrowed[:1] or classes_or_root(
                    onto.end_classes(used, far), used
                )
                union = False
            else:
                continue
            for target in targets:
                if target not in onto.names:
                    onto.dropped.setdefault("domains, ranges or fillers outside the import closure", []).append(
                        f"{name} ({local(target)})"
                    )
                    continue
                tname = onto.names[target]
                rel = relationship(prop, cls, target) if forward else relationship(prop, target, cls)
                tighten(rel["from" if forward else "to"], lower, upper)
                if reverse:
                    # A restriction on the anonymous inverse, read from the restricted end, e.g.
                    # every FailedState is initiated by some FailureEvent.
                    choices = " or ".join(f"{article(onto.names[t])} {onto.names[t]}" for t in targets)
                    note = (
                        f"Every {name} is reached by {phrase(lower, upper)} '{onto.said(used)}' from {choices}."
                        if lower or upper is not None
                        else f"Every '{onto.said(used)}' that reaches {article(name)} {name} is from {choices}."
                    )
                elif union:
                    choices = ", ".join(onto.names[t] for t in targets)
                    note = (
                        f"Every {name} has a '{said}' that is one of {choices}."
                        if SOME in body
                        else f"Every '{said}' of {article(name)} {name} is one of {choices}."
                    )
                elif lower or upper is not None:
                    note = f"Every {name} has {phrase(lower, upper)} '{said}' that is {article(tname)} {tname}."
                else:
                    note = f"Every '{said}' of {article(name)} {name} is {article(tname)} {tname}."
                rel["notes"].append(note)
                rel["restrictions"].append(
                    next((local(k) for k in (SOME, ALLV) if k in body), None)
                    or ("qualifiedCardinality" if any(k in body for k in QUALIFIED) else "cardinality")
                )

    relationships = {}
    for (prop, source, target), rel in sorted(gathered.items(), key=lambda g: (g[0][0], onto.names[g[0][1]], onto.names[g[0][2]])):
        rtype = rel_type(onto.name_of(prop))
        sname, tname = onto.names[source], onto.names[target]
        rid = f"{sname}_{rtype}_{tname}"
        while rid in relationships:
            rid += "_2"
        inverse = onto.inverses.get(prop)
        kinds = onto.kinds(prop)
        supers = [
            onto.name_of(s) if s in onto.properties or s in onto.data_properties else s
            for s in onto.iris(prop, SUBPROPERTY)
            if s not in (OWL + "topObjectProperty", OWL + "topDataProperty")
        ]
        relationships[rid] = {
            "type": rtype,
            "from": {"node": sname, **ends(*rel["from"])},
            "to": {"node": tname, **ends(*rel["to"])},
            "description": describe(
                *onto.comments(prop),
                f"Its inverse is '{onto.said(inverse)}'." if inverse else "",
                "Symmetric." if "SymmetricProperty" in kinds else "",
                "Transitive." if "TransitiveProperty" in kinds else "",
                *dict.fromkeys(rel["notes"]),
                f"Each {sname} has {phrase(*rel['from'])} {tname}." if rel["from"] != [0, None] and not rel["notes"] else "",
            ),
            "reference": prop,
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (
                        ("iri", prop),
                        ("module", onto.module_of(prop)),
                        ("subPropertyOf", supers),
                        ("inverseOf", onto.name_of(inverse) if inverse else None),
                        ("equivalentProperty", [onto.name_of(e) for e in onto.iris(prop, OWL + "equivalentProperty")]),
                        ("restrictions", sorted(set(rel["restrictions"]))),
                        ("functional", "FunctionalProperty" in kinds),
                        ("symmetric", "SymmetricProperty" in kinds),
                        ("transitive", "TransitiveProperty" in kinds),
                    )
                    if v not in (None, [], False)
                }
            },
        }

    def datatypes_of(values, name):
        """The Neo4j type, base datatypes and whether facets were dropped, for a list of data ranges:
        datatypes, unions of them, or datatype restrictions. None when they have no single Neo4j
        type."""
        types, bases, facets = set(), [], False
        for value in values:
            members = onto.members(value, UNIONOF) if value[0] == "bnode" else []
            for member in members or [value]:
                base = None
                if member[0] == "iri":
                    base = member[1]
                elif member[0] == "bnode":
                    base = next((v[1] for v in onto.values(member[1], OWL + "onDatatype") if v[0] == "iri"), None)
                    facets = facets or OWL + "withRestrictions" in onto.graph[member[1]]
                if base is not None:
                    bases.append(base)
                    if base in DATATYPES:
                        types.add(DATATYPES[base])
        if len(types) != 1 or any(b not in DATATYPES for b in bases):
            onto.dropped.setdefault("datatype properties whose range has no single Neo4j type", []).append(
                f"{name} ({', '.join(compact(b) for b in bases) or 'no range'})"
            )
            return None
        return types.pop(), bases, facets

    # The datatype properties, as properties of each class of their domain, and of each class a
    # restriction places them on. One that is neither given a domain nor restricted, like Supply
    # Chain's hasTextValue, is a property of Entity, as the unconstrained end of an object property is.
    node_properties = 0
    for iri in sorted(onto.data_properties, key=onto.property_name):
        name = onto.property_name(iri)
        for domain in sorted(c for c in onto.end_classes(iri, "domain") if c not in onto.names):
            onto.dropped.setdefault("domains, ranges or fillers outside the import closure", []).append(
                f"{name} ({local(domain)})"
            )
        domains = sorted(c for c in onto.end_classes(iri, "domain") if c in onto.names)
        restricting = sorted((c for (c, p) in restricted_data if p == iri), key=onto.names.get)
        if not domains and not restricting:
            domains = [ENTITY]
        # A datatype property without a range, like hasSimpleExpressionValue, holds a string.
        declared = datatypes_of(onto.values(iri, RANGE) or [("iri", RDFS + "Literal")], name)
        functional = "FunctionalProperty" in onto.kinds(iri)
        supers = [
            onto.name_of(s) if s in onto.properties or s in onto.data_properties else s
            for s in onto.iris(iri, SUBPROPERTY)
            if s not in (OWL + "topObjectProperty", OWL + "topDataProperty")
        ]
        for cls in sorted(set(domains) | set(restricting), key=onto.names.get):
            entry = restricted_data.get((cls, iri), {"bounds": [0, None], "ranges": []})
            # A restriction's data range narrows the declared one, e.g. to xsd:date.
            typed = datatypes_of(entry["ranges"], name) if entry["ranges"] else declared
            if typed is None:
                continue
            neo4j, bases, facets = typed
            if facets:
                onto.dropped.setdefault("datatype facets (owl:withRestrictions), e.g. a minimum or maximum", []).append(name)
            lower, upper = entry["bounds"]
            single = functional or upper == 1
            cname = onto.names[cls]
            node = nodes[cname]
            if name in node["properties"]:
                sys.exit(f"{cname}: two properties named {name}")
            prop = {
                "type": neo4j if single else f"LIST<{neo4j}>",
                "name": name,
                "description": describe(
                    *onto.comments(iri),
                    f"Every {cname} has {phrase(lower, upper)} '{onto.said(iri)}'." if entry["bounds"] != [0, None] else "",
                ),
                "reference": iri,
                "extensions": {
                    "custom": {
                        k: v
                        for k, v in (
                            ("iri", iri),
                            ("module", onto.module_of(iri)),
                            ("subPropertyOf", supers),
                            ("datatypes", [compact(b) for b in bases]),
                            ("functional", functional),
                            ("minCount", lower),
                            ("maxCount", upper),
                            ("fromRestriction", cls in restricting),
                        )
                        if v not in (None, [], False, 0)
                    }
                },
            }
            if not prop["description"]:
                del prop["description"]
            if lower >= 1:
                node["constraints"][f"exists_{cname}_{name}"] = {
                    "type": "EXISTS", "properties": [name], "name": f"{name}_{cname}_exists",
                }
            node["properties"][name] = prop
            node_properties += 1

    for rel in relationships.values():
        for end in (rel["from"], rel["to"]):
            if end["node"] not in nodes:
                sys.exit(f"relationship {rel['type']} points at {end['node']}, which is not a class")
    return {**META, "nodes": nodes, "relationships": relationships}, node_properties


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
    "version": "202603",
    "id": "iof-202603",
    "name": "IOF Core, Supply Chain, Maintenance, Certification and Production Planning",
    "description": (
        "The Core, Supply Chain, Maintenance, Certification and Production Planning ontologies of the Industrial "
        "Ontologies Foundry (IOF), developed by "
        "the IOF under the Open Applications Group (https://spec.industrialontologies.org) and licensed under MIT, "
        "from Release 202603. Core holds the notions common to manufacturing: agents and the roles they play, "
        "products, materials, equipment and engineered systems, planned and manufacturing processes, capabilities "
        "and functions, and the plans, specifications, identifiers and measurements that describe them. Supply "
        "Chain adds suppliers, buyers, carriers and distributors, the sourcing, shipping, storage and logistics "
        "processes between them, and the shipments, lots and locations they handle; Maintenance adds failures, "
        "failure modes and maintenance states, and the maintenance activities and work orders that answer them; "
        "Certification adds certifying bodies, attesting agents and processes, and the certificates they grant; "
        "Production Planning adds production plans and orders, process plans, operations and process steps, and "
        "the machines, tools and operators that carry them out. All are built on the Basic Formal Ontology (BFO 2020), which the closure of their owl:imports adds: each "
        "class is a node, each object property a relationship from its domain to its range (one direction per "
        "inverse pair), each datatype property a property, each class restriction a count, and each superclass "
        "an implied label."
    ),
}


def main():
    source = Source(sys.argv[1] if len(sys.argv) > 1 else None)
    modules = closure(source)
    onto = Ontology(modules)
    model, node_properties = build(onto)
    out = Path(__file__).parent
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(yaml(model) + "\n")
    print(f"{len(modules)} modules: {', '.join(onto.modules)}")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships, {node_properties} node properties")
    if onto.deprecated:
        print(f"deprecated, not kept: {', '.join(local(p) for p in onto.deprecated)}")
    for construct, where in sorted(onto.dropped.items()):
        print(f"not kept, {construct}: {', '.join(sorted(set(where)))}")


if __name__ == "__main__":
    main()
