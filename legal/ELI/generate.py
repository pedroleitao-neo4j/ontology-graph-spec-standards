#!/usr/bin/env python3
"""Generates the ELI 1.4 ontology from the official ELI ontology file published by the Publications Office of the EU.

Usage: python3 generate.py [path/to/eli.owl]

Without a path, the ELI ontology (RDF/XML) is downloaded from the Publications Office. Writes model.json and model.yaml
next to this script. Uses only the Python standard library.
"""

import json
import re
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SOURCE_URL = "https://op.europa.eu/documents/3938058/11669184/eli.owl/"
SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
ELI = "http://data.europa.eu/eli/ontology#"
MAX_DESCRIPTION = 1024

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
XSD = "http://www.w3.org/2001/XMLSchema#"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

TYPE = RDF + "type"
SUBCLASS = RDFS + "subClassOf"
SUBPROPERTY = RDFS + "subPropertyOf"
DOMAIN = RDFS + "domain"
RANGE = RDFS + "range"
LABEL = RDFS + "label"
COMMENT = RDFS + "comment"
INVERSE = OWL + "inverseOf"
UNIONOF = OWL + "unionOf"
ONPROPERTY = OWL + "onProperty"
THING = OWL + "Thing"
CONCEPT = SKOS + "Concept"
SPECIFIC = ELI + "specificPropertyOf"

# The datatypes ELI ranges its datatype properties over, as Neo4j types. An rdfs:Literal may carry a language tag, e.g.
# a title in French, and is a string.
DATATYPES = {
    XSD + "date": "DATE",
    XSD + "string": "STRING",
    XSD + "anyURI": "STRING",
    RDFS + "Literal": "STRING",
}

# The prefixes that compact IRIs from other vocabularies in extensions.custom, e.g. dcterms:publisher.
PREFIXES = {
    "dcterms": "http://purl.org/dc/terms/",
    "frbroo": "http://iflastandards.info/ns/fr/frbr/frbroo/",
    "crm": "http://www.cidoc-crm.org/cidoc-crm/",
    "authority": "http://publications.europa.eu/resource/authority/",
    "skos": SKOS,
    "rdfs": RDFS,
    "owl": OWL,
}

# The FRBR level, or kind, of each class's hierarchy root, and so the area a card is coloured by.
LEVELS = {"Work": "Work", "Expression": "Expression", "Manifestation": "Manifestation", "Agent": "Agent",
          "Concept": "Concept"}


def words(text):
    """The words of a snake_case or CamelCase name, e.g. is_part_of → is, part, of; LegalResource → Legal, Resource."""
    return re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z\d]*|[a-z\d]+", text)


def rel_type(name):
    return "_".join(w.upper() for w in words(name))


def spaced(name):
    return " ".join(w.lower() for w in words(name))


def local(iri):
    return re.split(r"[/#]", iri)[-1]


def compact(iri):
    if iri.startswith(ELI):
        return "eli:" + iri[len(ELI):]
    for prefix, expanded in PREFIXES.items():
        if iri.startswith(expanded):
            return f"{prefix}:{iri[len(expanded):]}"
    return iri


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


def article(name):
    return "an" if name[0] in "AEIOU" else "a"


#----------------------------------
#   Reading the ontology
#----------------------------------


def parse_rdfxml(path):
    """Reads an RDF/XML file into a subject → predicate → [values] graph, in the order the file declares its terms.

    A value is an ("iri", iri), ("lit", text, datatype or langtag or None), ("bnode", id) or ("coll", [values])
    tuple, as the Turtle readers of the other standards give. A nested node element becomes a blank node, or the
    named node it is about, and an rdf:parseType="Collection" a single collection value. Covers the RDF/XML that
    ELI uses: rdf:about, rdf:resource, rdf:datatype, xml:lang, typed node elements and collections.
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
            subject = f":b{counter}"
        po = graph.setdefault(subject, {})
        if name(element.tag) != RDF + "Description":
            po.setdefault(TYPE, []).append(("iri", name(element.tag)))
        for prop in element:
            po.setdefault(name(prop.tag), []).append(value(prop))
        return ("bnode", subject) if subject.startswith(":b") else ("iri", subject)

    def value(prop):
        if prop.get(f"{{{RDF}}}resource") is not None:
            return ("iri", prop.get(f"{{{RDF}}}resource"))
        if prop.get(f"{{{RDF}}}parseType") == "Collection":
            return ("coll", [node(child) for child in prop])
        children = list(prop)
        if children:
            return node(children[0])
        datatype = prop.get(f"{{{RDF}}}datatype")
        lang = prop.get(XML_LANG)
        return ("lit", prop.text or "", datatype or (f"@{lang}" if lang else None))

    for element in ET.parse(path).getroot():
        node(element)
    return graph


#----------------------------------
#   The ELI ontology as data
#----------------------------------


class Term:
    """One ELI term: a class, a property or an individual, with its annotations read out of the graph."""

    def __init__(self, iri, po):
        self.iri = iri
        self.po = po
        self.name = local(iri)
        self.kinds = {v[1] for v in po.get(TYPE, []) if v[0] == "iri"}
        self.comment = self.text(COMMENT)

    def text(self, predicate):
        """A literal, in English where the term has one in several languages."""
        values = [v for v in self.po.get(predicate, []) if v[0] == "lit"]
        english = [v for v in values if (v[2] or "").startswith("@en")] or values
        return tidy(english[0][1]) if english else ""

    def iris(self, predicate):
        return [v[1] for v in self.po.get(predicate, []) if v[0] == "iri"]

    @property
    def functional(self):
        return OWL + "FunctionalProperty" in self.kinds

    @property
    def deprecated(self):
        return any(v[0] == "lit" and v[1] == "true" for v in self.po.get(OWL + "deprecated", []))


def classes_of(value, graph):
    """The classes or datatypes a domain or range value stands for: one, or the members of a union."""
    if value[0] == "iri":
        return [value[1]]
    members = next((v for v in graph[value[1]].get(UNIONOF, []) if v[0] == "coll"), None)
    if members is None:
        sys.exit(f"a domain or range is neither a class nor a union of classes: {value}")
    return [m[1] for m in members[1] if m[0] == "iri"]


def end_classes(term, end, properties, graph):
    """The classes at one end of a property: its own domain or range, else its inverse's other end. An empty
    result means ELI leaves that end unconstrained."""
    values = term.po.get(DOMAIN if end == "domain" else RANGE, [])
    if values:
        return sorted({c for v in values for c in classes_of(v, graph)})
    for inverse in inverses_of(term, properties):
        values = properties[inverse].po.get(RANGE if end == "domain" else DOMAIN, [])
        if values:
            return sorted({c for v in values for c in classes_of(v, graph)})
    return []


def inverses_of(term, properties):
    """The inverse of a property, declared on either side: ELI declares most pairs from one side only."""
    out = [i for i in term.iris(INVERSE) if i in properties]
    out += [p.iri for p in properties.values() if term.iri in p.iris(INVERSE) and p.iri not in out]
    return out


def root_of(term, classes):
    """The top of a class's ELI superclass chain, e.g. Work for LegalResourceSubdivision; Concept for the classes
    of ELI's concept schemes, which specialise skos:Concept."""
    supertypes = [s for s in term.iris(SUBCLASS) if s in classes]
    return root_of(classes[supertypes[0]], classes) if supertypes else term.name


def schemes_of(term, graph):
    """The concept schemes a concept class is defined by, from its owl:equivalentClass, e.g. eli:InForceTable."""
    out = []

    def walk(value):
        if value[0] == "coll":
            for member in value[1]:
                walk(member)
        elif value[0] == "bnode":
            body = graph[value[1]]
            if ("iri", SKOS + "inScheme") in body.get(ONPROPERTY, []):
                out.extend(v[1] for v in body.get(OWL + "hasValue", []) if v[0] == "iri")
            for key in (OWL + "intersectionOf", UNIONOF):
                for member in body.get(key, []):
                    walk(member)

    for value in term.po.get(OWL + "equivalentClass", []):
        walk(value)
    return out


def winner_of(pair):
    """Which property of an inverse pair becomes the relationship: the functional one, e.g. realizes over
    is_realized_by; else the one ELI defines rather than describing as the inverse of the other, e.g. is_part_of over
    has_part; else the active one rather than the one ending in _by, e.g. amends over amended_by; else the one that
    declares the pair."""
    a, b = pair
    for test in (
        lambda t: t.functional,
        lambda t: not t.comment.lower().startswith("inverse of"),
        lambda t: not t.name.endswith("_by"),
        lambda t: bool(t.iris(INVERSE)),
    ):
        if test(a) != test(b):
            return a if test(a) else b
    return a


def build(graph):
    def terms(kind):
        return {
            iri: Term(iri, po)
            for iri, po in graph.items()
            if iri.startswith(ELI) and kind in {v[1] for v in po.get(TYPE, []) if v[0] == "iri"}
        }

    classes, properties = terms(OWL + "Class"), terms(OWL + "ObjectProperty")
    data_properties = terms(OWL + "DatatypeProperty")
    individuals = terms(OWL + "NamedIndividual")
    individuals.update(
        (iri, Term(iri, po))
        for iri, po in graph.items()
        if OWL + "NamedIndividual" in {v[1] for v in po.get(TYPE, []) if v[0] == "iri"} and iri not in individuals
    )

    # skos:Concept is the one class from another vocabulary that is a node: ELI's concept classes, e.g. InForce,
    # specialise it, and eli:is_about ranges over it.
    classes[CONCEPT] = Term(CONCEPT, {
        COMMENT: [("lit", "An idea or notion; a unit of thought, from a concept scheme such as an authority table "
                   "or a thesaurus (SKOS). ELI's concept classes, e.g. InForce or ResourceType, are concepts of "
                   "their scheme, and eli:is_about takes concepts from any scheme, e.g. EuroVoc.", "@en")],
    })
    classes[CONCEPT].name = "Concept"
    if len({c.name for c in classes.values()}) != len(classes):
        sys.exit("two ELI classes share a name")

    nodes = {}
    for iri, term in classes.items():
        implied = [classes[s].name for s in term.iris(SUBCLASS) if s in classes]
        external = [compact(s) for s in term.iris(SUBCLASS) if s not in classes]
        schemes = schemes_of(term, graph)
        members = [i for i in individuals.values() if iri in i.kinds and iri != CONCEPT]
        # A scheme that ELI declares with all its concepts, e.g. eli:InForceTable, is closed; one whose concepts are
        # only examples, e.g. eli:FormatTypeTable, is open, and its concepts are suggested values.
        closed = (
            bool(members)
            and all(s.startswith(ELI) for s in schemes)
            and all(set(m.iris(SKOS + "inScheme")) & set(schemes) for m in members)
            and all(m.iris(SKOS + "topConceptOf") or m.iris(SKOS + "broader") for m in members)
        )
        values = sorted(m.iri for m in members)
        labels = {m.iri: m.text(SKOS + "prefLabel") for m in members}
        uri = {
            "type": "STRING",
            "name": "uri",
            "description": describe(
                f"The identifier of the {term.name}: its IRI."
                + (
                    " For a legal resource or expression, its ELI, e.g. http://data.europa.eu/eli/reg/2016/679/oj."
                    if root_of(term, classes) in ("Work", "Expression")
                    else " For a concept, its IRI in its scheme, e.g. "
                    "http://publications.europa.eu/resource/authority/language/FRA."
                    if root_of(term, classes) == "Concept"
                    else ""
                )
                + " Unique within a data set; resources that are blank nodes are given generated identifiers.",
                "One of the concepts ELI defines: " + ", ".join(f"`{labels[v]}` ({compact(v)})" for v in values) + "."
                if closed
                else "",
            ),
            "reference": "https://www.w3.org/TR/rdf11-concepts/#section-IRIs",
        }
        if closed:
            uri["one_of"] = values
        description = describe(
            sentence(term.comment),
            f"A concept of {' or '.join(compact(s) for s in schemes)}."
            if schemes and not all(s in term.comment or compact(s) in term.comment for s in schemes)
            else "",
            "Suggested concepts, which ELI gives as examples rather than a closed list: "
            + ", ".join(f"`{labels[v] or local(v)}`" for v in values)
            + "; their IRIs are in extensions.custom.suggestedValues."
            if values and not closed
            else "",
        )
        nodes[term.name] = {
            "labels": {"identifier": term.name, **({"implied": implied} if implied else {})},
            **({"description": description} if description else {}),
            "reference": iri,
            "properties": {"uri": uri},
            "constraints": {f"key_{term.name}": {"type": "KEY", "properties": ["uri"], "name": f"uri_{term.name}_key"}},
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (
                        ("iri", iri),
                        ("level", LEVELS[root_of(term, classes)]),
                        ("subClassOf", external),
                        ("conceptSchemes", [compact(s) for s in schemes]),
                        ("suggestedValues", values if not closed else []),
                        ("versionInfo", [tidy(v[1]) for v in term.po.get(OWL + "versionInfo", []) if v[0] == "lit"]),
                    )
                    if v not in ("", None, [])
                }
            },
        }
    nodes["Concept"]["properties"]["prefLabel"] = {
        "type": "LIST<STRING>",
        "name": "prefLabel",
        "description": "The preferred labels of the concept, at most one per language, e.g. `in force` for "
        "eli:InForce-inForce. Taken from the concept scheme, e.g. an EU authority table.",
        "reference": SKOS + "prefLabel",
        "extensions": {"custom": {"iri": SKOS + "prefLabel"}},
    }

    relationships, as_properties, left_out = {}, [], []

    def custom_of(term, **more):
        return {
            k: v
            for k, v in (
                ("iri", term.iri),
                ("specificPropertyOf", [compact(i) for i in term.iris(SPECIFIC)]),
                ("subPropertyOf", [
                    (classes.get(s) or properties.get(s) or data_properties.get(s) or Term(s, {})).name
                    if s.startswith(ELI) else compact(s)
                    for s in term.iris(SUBPROPERTY) if s not in (OWL + "topObjectProperty", OWL + "topDataProperty")
                ]),
                ("functional", term.functional),
                ("originalName", term.text(ELI + "originalName")),
                *more.items(),
            )
            if v not in ("", None, [], False)
        }

    def add_property(node_name, term, neo4j_type, description, custom):
        properties_of = nodes[node_name]["properties"]
        if term.name in properties_of:
            sys.exit(f"{node_name}: two properties named {term.name}")
        prop = {
            "type": neo4j_type if term.functional else f"LIST<{neo4j_type}>",
            "name": term.name,
            "description": description,
            "reference": term.iri,
            "extensions": {"custom": custom},
        }
        if not description:
            del prop["description"]
        properties_of[term.name] = prop

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
            "extensions": {"custom": custom or {}},
        }

    def described(term, *more):
        return describe(
            sentence(term.comment),
            *more,
            "See also " + ", ".join(compact(s) for s in term.iris(RDFS + "seeAlso")) + "."
            if term.iris(RDFS + "seeAlso")
            else "",
        )

    def emit(term):
        """One relationship per domain/range pair the property allows, union ends included; to owl:Thing, which
        isn't a node, a property holding the IRI instead."""
        domains = end_classes(term, "domain", properties, graph)
        ranges = end_classes(term, "range", properties, graph)
        if not domains:
            left_out.append(f"{term.name} (no domain)")
            return
        inverses = [properties[i].name for i in inverses_of(term, properties)]
        inverse_text = (
            f"The inverse ELI property is '{inverses[0]}'." if inverses and inverses[0] not in term.comment else ""
        )
        if not ranges or ranges == [THING]:
            for domain in domains:
                add_property(
                    classes[domain].name,
                    term,
                    "STRING",
                    described(
                        term,
                        f"Holds the IRI of {'the resource' if term.functional else 'each resource'} it refers to, "
                        "which ELI allows to be anything" + (", not only an ELI resource." if ranges else "."),
                        inverse_text,
                    ),
                    custom_of(term, inverseOf=inverses[0] if inverses else "", unionEnds=len(domains) > 1),
                )
            as_properties.append(term.name)
            return
        for domain in domains:
            for range_ in ranges:
                if range_ not in classes:
                    sys.exit(f"{term.name} ranges over {range_}, which is not a class")
                relationship(
                    classes[domain].name,
                    classes[range_].name,
                    term,
                    described(term, inverse_text),
                    {"max_count": 1} if term.functional else None,
                    custom_of(
                        term,
                        inverseOf=inverses[0] if inverses else "",
                        unionEnds=len(domains) > 1 or len(ranges) > 1,
                    ),
                )

    # One relationship per inverse pair, in the direction winner_of picks; deprecated properties are left out.
    handled = set()
    for iri, term in properties.items():
        if iri in handled:
            continue
        if term.deprecated:
            left_out.append(f"{term.name} (deprecated)")
            continue
        inverses = inverses_of(term, properties)
        if inverses:
            pair = (term, properties[inverses[0]])
            winner = winner_of(pair)
            handled.update(t.iri for t in pair)
            if winner is not term:
                emit(winner)
                continue
        emit(term)

    # The restrictions a class places on a property, e.g. every Format has exactly one format: a relationship of its
    # own from the restricted class, with its counts.
    for iri, term in classes.items():
        for restriction in (v for v in term.po.get(SUBCLASS, []) if v[0] == "bnode"):
            body = graph[restriction[1]]
            prop = properties[next(v[1] for v in body.get(ONPROPERTY, []) if v[0] == "iri")]
            exact = next((int(v[1]) for v in body.get(OWL + "cardinality", []) if v[0] == "lit"), None)
            if exact != 1:
                sys.exit(f"a restriction on {term.name} other than a cardinality of one: {body}")
            for range_ in end_classes(prop, "range", properties, graph):
                target = classes[range_].name
                relationship(
                    term.name,
                    target,
                    prop,
                    describe(f"Every {term.name} has exactly one '{spaced(prop.name)}', {article(target)} {target}.",
                             sentence(prop.comment)),
                    {"count": 1},
                    custom_of(prop, restriction="cardinality 1"),
                )

    # The datatype properties, on each class of their domain.
    for iri, term in data_properties.items():
        ranges = end_classes(term, "range", properties, graph) or [RDFS + "Literal"]
        types = {DATATYPES[r] for r in ranges if r in DATATYPES}
        if len(types) != 1 or any(r not in DATATYPES for r in ranges):
            sys.exit(f"{term.name}: no single Neo4j type for {ranges}")
        neo4j = types.pop()
        domains = end_classes(term, "domain", properties, graph)
        for domain in domains:
            add_property(
                classes[domain].name,
                term,
                neo4j,
                described(term),
                custom_of(
                    term,
                    datatypes=[compact(r) if not r.startswith(XSD) else "xsd:" + local(r) for r in ranges],
                    unionEnds=len(domains) > 1,
                ),
            )

    for rel in relationships.values():
        for end in (rel["from"], rel["to"]):
            if end["node"] not in nodes:
                sys.exit(f"relationship {rel['type']} points at {end['node']}, which is not a class")

    model = {
        "schema": SCHEMA,
        "version": "1.4",
        "id": "eli-1.4",
        "name": "ELI 1.4",
        "description": (
            "The European Legislation Identifier (ELI) ontology 1.4, published by the Publications Office of the "
            "European Union (https://op.europa.eu/en/web/eu-vocabularies/eli). ELI is the EU's framework for "
            "identifying legislation with persistent URIs and describing it with shared metadata, adopted by the "
            "Council conclusions of 2012 and used by the EU institutions and Member States to publish legislation "
            "as linked data. Built on the FRBR model, it describes legal resources (acts and their subdivisions, "
            "e.g. articles) as works; their versions in a language and at a point in time as legal expressions; "
            "and their published files as formats. Between them run the relations of the legislative corpus: "
            "amendment, repeal, consolidation, transposition, citation and so on; and from them the agents that "
            "pass and publish them and the authority-table concepts that classify them. Generated from the ELI 1.4 "
            "OWL file: each ELI class is a node, each object property a relationship from its domain to its range "
            "(one direction per inverse pair), each datatype property a property, and each superclass an implied "
            "label."
        ),
        "nodes": nodes,
        "relationships": relationships,
    }
    return model, as_properties, left_out


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
        source = Path(tempfile.mkdtemp()) / "eli.owl"
        # The Publications Office rejects Python's default user agent.
        request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request) as response:
            source.write_bytes(response.read())
    model, as_properties, left_out = build(parse_rdfxml(source))
    out = Path(__file__).parent
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(yaml(model) + "\n")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships")
    if as_properties:
        print(f"to any resource, and so properties holding IRIs: {', '.join(as_properties)}")
    if left_out:
        print(f"left out: {', '.join(left_out)}")


if __name__ == "__main__":
    main()
