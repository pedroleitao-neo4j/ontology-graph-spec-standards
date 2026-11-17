#!/usr/bin/env python3
"""Generates the FIBO legal modules ontology from the EDM Council FIBO repository.

Usage: python3 generate.py [path/to/fibo]

The six entry modules are FND/Law/LegalCore, FND/Law/LegalCapacity, FND/Agreements/Agreements,
FND/Agreements/Contracts, FND/Parties/Parties and BE/LegalEntities/LegalPersons, at the pinned
commit of the FIBO repository. Their owl:imports, followed to the full closure, add the FIBO
foundation modules they build on and the OMG Commons Ontology Library modules those depend on.
FIBO modules are downloaded from raw.githubusercontent.com at the pinned commit (or read from a
local checkout given as the argument); Commons modules are downloaded from their IRIs by content
negotiation. Writes model.json and model.yaml next to this script. Uses only the Python standard
library.
"""

import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

COMMIT = "33a92cd34285d532c158da97bb42add089f135d3"
RAW = f"https://raw.githubusercontent.com/edmcouncil/fibo/{COMMIT}/"
FIBO = "https://spec.edmcouncil.org/fibo/ontology/"
OMG = "https://www.omg.org/spec/Commons/"
ENTRY = [
    FIBO + tail
    for tail in (
        "FND/Law/LegalCore/",
        "FND/Law/LegalCapacity/",
        "FND/Agreements/Agreements/",
        "FND/Agreements/Contracts/",
        "FND/Parties/Parties/",
        "BE/LegalEntities/LegalPersons/",
    )
]
SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
MAX_DESCRIPTION = 1024

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
XSD = "http://www.w3.org/2001/XMLSchema#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
DCT = "http://purl.org/dc/terms/"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

TYPE = RDF + "type"
SUBCLASS = RDFS + "subClassOf"
SUBPROPERTY = RDFS + "subPropertyOf"
DOMAIN = RDFS + "domain"
RANGE = RDFS + "range"
COMMENT = RDFS + "comment"
DEFINITION = SKOS + "definition"
ABSTRACT = DCT + "abstract"
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

# The root of the model: owl:Thing, which FIBO's top classes specialise and its unconstrained
# property ends stand for.
ROOT = "Thing"

# The datatypes FIBO and Commons range their datatype properties over, as Neo4j types. A combined
# date time is Commons' union of a string, a dateTime and a dateTimeStamp, all of which carry a
# date and possibly a time; owl:rational has no exact Neo4j equivalent, so it is a FLOAT.
DATATYPES = {
    XSD + "string": "STRING",
    XSD + "normalizedString": "STRING",
    XSD + "token": "STRING",
    XSD + "anyURI": "STRING",
    XSD + "Name": "STRING",
    RDFS + "Literal": "STRING",
    RDF + "langString": "STRING",
    OMG + "TextDatatype/Text": "STRING",
    XSD + "boolean": "BOOLEAN",
    XSD + "date": "DATE",
    XSD + "dateTime": "ZONED DATETIME",
    XSD + "dateTimeStamp": "ZONED DATETIME",
    OMG + "DatesAndTimes/CombinedDateTime": "ZONED DATETIME",
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
    "dcterms": DCT,
    "cmns-dt": OMG + "DatesAndTimes/",
    "cmns-txt": OMG + "TextDatatype/",
}

# The area a term's module places it in, for extensions.custom.area and the diagram. Every module
# that is none of these is a Commons module or another support module.
AREAS = (
    ("Law and legal capacity", ("FND/Law",)),
    ("Agreements and contracts", ("FND/Agreements", "FND/Arrangements")),
    ("Parties, people and legal entities", ("FND/Parties", "FND/AgentsAndPeople", "BE/LegalEntities")),
)
SUPPORT = "Commons foundations and other support modules"


def words(text):
    """The words of a snake_case or CamelCase name, e.g. has_part → has, part; LegalPerson → Legal, Person."""
    return re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z\d]*|[a-z\d]+", text) or re.findall(r"[A-Za-z0-9]+", text)


def pascal(name):
    """A class name as a label, e.g. Legal_Person → LegalPerson."""
    return "".join(w[0].upper() + w[1:] for w in words(name))


def rel_type(name):
    return "_".join(w.upper() for w in words(name))


def spaced(name):
    """A property name as FIBO writes it in prose, e.g. hasEffectiveDate → 'has effective date'."""
    return " ".join(w.lower() for w in words(name))


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
    RDF/XML that FIBO and Commons use: rdf:about, rdf:resource, rdf:datatype, xml:lang, typed
    node elements and rdf:parseType="Collection".
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
    """The modules of the import closure, each fetched once and cached in memory: a FIBO module
    from the pinned commit of the FIBO repository (or a local checkout), a Commons module from its
    IRI by content negotiation."""

    def __init__(self, local=None):
        self.local = Path(local).resolve() if local else None
        self.cache = {}

    @staticmethod
    def normalise(iri):
        """The IRI an import stands for: some resolve through a /master/latest path."""
        return iri.replace("/master/latest", "")

    def fetch(self, iri):
        iri = self.normalise(iri)
        if iri in self.cache:
            return self.cache[iri]
        if iri.startswith(FIBO) and self.local is not None:
            path = self.local / (iri[len(FIBO):].rstrip("/") + ".rdf")
            if path.is_file():
                self.cache[iri] = path.read_bytes()
                return self.cache[iri]
        if iri.startswith(FIBO):
            url = RAW + iri[len(FIBO):].rstrip("/") + ".rdf"
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        elif iri.startswith(OMG):
            url = iri
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/rdf+xml"})
        else:
            self.cache[iri] = None  # an import from another vocabulary, which none of the closure is
            return None
        try:
            with urllib.request.urlopen(request) as response:
                self.cache[iri] = response.read()
        except Exception as error:
            sys.exit(f"could not download {url}: {error}")
        return self.cache[iri]


def closure(source):
    """The modules the entry modules' owl:imports close over: IRI → graph, in the order found."""
    modules, pending = {}, list(ENTRY)
    while pending:
        iri = source.normalise(pending.pop(0))
        if iri in modules:
            continue
        data = source.fetch(iri)
        if data is None:
            sys.exit(f"{iri}: an import outside FIBO and the OMG Commons Ontology Library")
        graph = parse_rdfxml(data, f"m{len(modules)}_")
        modules[iri] = graph
        pending += [
            source.normalise(imported)
            for imported in sorted(v[1] for v in graph.get(iri, {}).get(OWL + "imports", []) if v[0] == "iri")
            if source.normalise(imported) not in modules
        ]
    return modules


#----------------------------------
#   The ontologies as data
#----------------------------------


class Ontology:
    """The classes and properties of the closure, read out of the merged graph of its modules."""

    def __init__(self, modules):
        self.modules = sorted(modules)
        self.graph = {}
        for iri in self.modules:
            for subject, po in modules[iri].items():
                if subject in self.graph:
                    for predicate, values in po.items():
                        self.graph[subject].setdefault(predicate, []).extend(values)
                else:
                    self.graph[subject] = po

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
        self.classes = declared(OWL + "Class")
        self.data_properties = declared(OWL + "DatatypeProperty") - deprecated
        # An rdf:Property that is neither an annotation nor a datatype property relates individuals.
        self.properties = (declared(OWL + "ObjectProperty") | (declared(RDF + "Property") - self.data_properties - declared(OWL + "AnnotationProperty"))) - deprecated
        self.deprecated = sorted(deprecated)
        self.dropped = {}  # what the axioms say that the ontology can't, by construct

        # The PascalCase label of each class. Two classes that share one are told apart by their
        # module, e.g. a Party of FIBO and one of Commons.
        counts = {}
        for iri in sorted(self.classes):
            counts.setdefault(pascal(local(iri)), []).append(iri)
        self.names = {THING: ROOT}
        for name, iris in counts.items():
            if len(iris) == 1:
                self.names[iris[0]] = name
            else:
                for iri in sorted(iris, key=self.module_of):
                    self.names[iri] = name + pascal(local(self.module_of(iri)))
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
        """The term's definition: skos:definition, else rdfs:comment, else dct:abstract, as sentences."""
        for predicate in (DEFINITION, COMMENT, ABSTRACT):
            for value in self.values(iri, predicate):
                if value[0] == "lit" and tidy(value[1]):
                    return [sentence(self.text(iri, predicate))]
        return []

    def kinds(self, iri):
        return {local(k) for k in self.iris(iri, TYPE)}

    def module_of(self, iri):
        """The module a term belongs to: a FIBO family and specification, e.g. FND/Law, or a
        Commons module, e.g. Commons/Organizations."""
        owner = max((m for m in self.modules if iri.startswith(m)), key=len, default=None)
        if owner is None:
            return ""
        if owner.startswith(FIBO):
            return "/".join(owner[len(FIBO):].rstrip("/").split("/")[:-1])
        return "Commons/" + owner[len(OMG):].rstrip("/")

    def area_of(self, iri):
        module = self.module_of(iri)
        for name, prefixes in AREAS:
            if any(module == prefix or module.startswith(prefix + "/") for prefix in prefixes):
                return name
        return SUPPORT

    def members(self, value, keyword):
        """The members of a blank node's union or intersection, or [] if it is neither."""
        if value[0] != "bnode":
            return []
        return next((v[1] for v in self.values(value[1], keyword) if v[0] == "coll"), [])

    def fillers(self, value):
        """The named classes a class expression stands for: a class itself, the members of a union,
        or the named members of an intersection. A restriction or complement names no class."""
        if value[0] == "iri":
            return [value[1]]
        union = self.members(value, UNIONOF)
        if union:
            return [c for member in union for c in self.fillers(member)]
        return [m[1] for m in self.members(value, INTERSECTIONOF) if m[0] == "iri"]

    def kept(self, prop):
        """Whether a property is the direction of its inverse pair that becomes a relationship.
        FIBO names most pairs in the active and the passive voice, e.g. authorizes and
        isAuthorizedBy; the active one is kept. Of a pair in the same voice, the one the other
        declares itself the owl:inverseOf is kept."""
        inverse = self.inverses.get(prop)
        if inverse is None:
            return True
        passive = [bool(re.search(r"(By|Of|In|For)$", local(p))) for p in (prop, inverse)]
        if passive[0] != passive[1]:
            return not passive[0]
        declares = [inverse in self.iris(prop, INVERSE), prop in self.iris(inverse, INVERSE)]
        if declares[0] != declares[1]:
            return declares[1]
        return local(prop) < local(inverse)

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

    def axioms(self, cls):
        """The restrictions a class's axioms place on it: those it is a subclass of, and those its
        equivalent classes are or intersect, which are necessary conditions too."""
        out = []
        for value in self.values(cls, SUBCLASS) + self.values(cls, EQUIVALENT):
            if value[0] == "bnode" and ONPROPERTY in self.graph[value[1]]:
                out.append(value)
            out += [m for m in self.members(value, INTERSECTIONOF) if m[0] == "bnode" and ONPROPERTY in self.graph[m[1]]]
        return out

    def supertypes(self, cls):
        """The named classes a class specialises: its superclasses and the named members of an
        intersection it is equivalent to. A superclass that is a class expression is dropped."""
        out = [s for s in self.iris(cls, SUBCLASS) if s in self.classes]
        for value in self.values(cls, SUBCLASS):
            if value[0] == "bnode" and ONPROPERTY not in self.graph[value[1]]:
                self.dropped.setdefault("subclass axioms that are unions of classes or other expressions", []).append(
                    self.names[cls]
                )
        for value in self.values(cls, EQUIVALENT):
            out += [m[1] for m in self.members(value, INTERSECTIONOF) if m[0] == "iri" and m[1] in self.classes]
        out = [s for s in dict.fromkeys(out) if s != cls]
        # Only the direct supertypes: one that another supertype already specialises adds nothing.
        return [s for s in out if not any(s in self.ancestors(o) for o in out if o != s)]

    def ancestors(self, cls, seen=None):
        seen = set() if seen is None else seen
        for s in self.iris(cls, SUBCLASS):
            if s in self.classes and s not in seen:
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
    for iri in [THING, *sorted(onto.classes, key=lambda c: onto.names[c])]:
        name = onto.names[iri]
        supertypes = [onto.names[s] for s in onto.supertypes(iri)] if iri != THING else []
        if iri != THING and not supertypes:
            supertypes = [ROOT]  # a top class: everything is a Thing
        description = describe(
            *(
                onto.comments(iri)
                if iri != THING
                else [
                    "Anything at all: owl:Thing, which every class of the closure sits under. The label every node "
                    "carries, and the end of the relationships FIBO and Commons leave open to any individual."
                ]
            )
        )
        nodes[name] = {
            "labels": {"identifier": name, **({"implied": supertypes} if supertypes else {})},
            **({"description": description} if description else {}),
            "reference": iri,
            "properties": {
                "uri": {
                    "type": "STRING",
                    "name": "uri",
                    "description": f"The identifier of the {name} individual: its IRI in FIBO data. Unique within a "
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
                        ("module", onto.module_of(iri) if iri != THING else "owl"),
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
        """The classes at one end of a property, or Thing where it is left unconstrained."""
        unknown = sorted(c for c in found if c not in onto.names)
        if unknown:
            onto.dropped.setdefault("domains, ranges or fillers outside the import closure", []).append(
                f"{local(prop)} ({', '.join(local(c) for c in unknown)})"
            )
        return sorted((c for c in found if c in onto.names), key=onto.names.get) or [THING]

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
            used = next(v[1] for v in body[ONPROPERTY] if v[0] == "iri")
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
            said = spaced(local(used))
            if SOME in body or ALLV in body:
                value = (body.get(SOME) or body.get(ALLV))[0]
                targets = onto.fillers(value)
                union = bool(onto.members(value, UNIONOF))
                if not targets and SOME in body:
                    # A filler that names no class, e.g. a nested restriction: what the property
                    # ranges over stands for it.
                    targets = classes_or_root(onto.end_classes(used, "range"), used)
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
                filler = (body.get(ONCLASS) or [("iri", THING)])[0]
                targets = onto.fillers(filler) or classes_or_root(onto.end_classes(used, "range"), used)
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
                    onto.end_classes(used, "range"), used
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
                if union:
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
        rtype = rel_type(local(prop))
        sname, tname = onto.names[source], onto.names[target]
        rid = f"{sname}_{rtype}_{tname}"
        while rid in relationships:
            rid += "_2"
        inverse = onto.inverses.get(prop)
        kinds = onto.kinds(prop)
        supers = [
            local(s) if s in onto.properties or s in onto.data_properties else s
            for s in onto.iris(prop, SUBPROPERTY)
            if s not in (OWL + "topObjectProperty", OWL + "topDataProperty")
        ]
        relationships[rid] = {
            "type": rtype,
            "from": {"node": sname, **ends(*rel["from"])},
            "to": {"node": tname, **ends(*rel["to"])},
            "description": describe(
                *onto.comments(prop),
                f"FIBO also names the inverse, '{spaced(local(inverse))}'." if inverse else "",
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
                        ("inverseOf", local(inverse) if inverse else None),
                        ("equivalentProperty", [local(e) for e in onto.iris(prop, OWL + "equivalentProperty")]),
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
    # restriction places them on. One that FIBO and Commons neither give a domain nor restrict is
    # left out: its values can't be attached to a node.
    node_properties = 0
    for iri in sorted(onto.data_properties, key=local):
        name = local(iri)
        for domain in sorted(c for c in onto.end_classes(iri, "domain") if c not in onto.names):
            onto.dropped.setdefault("domains, ranges or fillers outside the import closure", []).append(
                f"{name} ({local(domain)})"
            )
        domains = sorted(c for c in onto.end_classes(iri, "domain") if c in onto.names)
        restricting = sorted((c for (c, p) in restricted_data if p == iri), key=onto.names.get)
        if not domains and not restricting:
            onto.dropped.setdefault("datatype properties without a domain or a restriction", []).append(name)
            continue
        # A datatype property without a range, like FIBO's address lines, holds a string.
        declared = datatypes_of(onto.values(iri, RANGE) or [("iri", RDFS + "Literal")], name)
        functional = "FunctionalProperty" in onto.kinds(iri)
        supers = [
            local(s) if s in onto.properties or s in onto.data_properties else s
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
                    f"Every {cname} has {phrase(lower, upper)} '{spaced(name)}'." if entry["bounds"] != [0, None] else "",
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
    "version": "2026-10",
    "id": "fibo-legal-2026-10",
    "name": "FIBO legal modules",
    "description": (
        "The legal modules of the Financial Industry Business Ontology (FIBO), developed by the EDM Council and "
        "the Object Management Group (https://spec.edmcouncil.org/fibo) and licensed under MIT. This subset covers "
        "the concepts financial agreements and the law around them are built on: the legal core of laws, jurisdictions "
        "and legal relations; legal capacity, obligations and the authority to act; agreements, contracts and their "
        "terms and parties; parties and the roles they play; and natural persons and the legal persons that are "
        "responsible for them, such as formal organizations. It is generated from the six entry modules of the FIBO "
        "repository's master branch and the modules their owl:imports close over, which adds the FIBO foundations "
        "and the OMG Commons Ontology Library they are built on: each class is a node, each object property a "
        "relationship from its domain to its range (one direction per inverse pair), each datatype property a "
        "property, each class restriction a count, and each superclass an implied label."
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
    paths = {m: (m[len(FIBO):] if m.startswith(FIBO) else "Commons/" + m[len(OMG):]).rstrip("/") for m in onto.modules}
    print(f"{len(modules)} modules: {', '.join(paths[m] for m in onto.modules)}")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships, {node_properties} node properties")
    if onto.deprecated:
        print(f"deprecated, not kept: {', '.join(local(p) for p in onto.deprecated)}")
    for construct, where in sorted(onto.dropped.items()):
        print(f"not kept, {construct}: {', '.join(sorted(set(where)))}")


if __name__ == "__main__":
    main()
