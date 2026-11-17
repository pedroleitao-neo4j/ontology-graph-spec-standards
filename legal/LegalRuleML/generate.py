#!/usr/bin/env python3
"""Generates the LegalRuleML 1.0 ontology from the official RDFS modules of the OASIS LegalRuleML Core
Specification.

Usage: python3 generate.py [path/to/modules]

Without a path, the twelve RDFS modules of LegalRuleML Core Specification Version 1.0 (OASIS Standard,
30 August 2021) are downloaded from the OASIS docs site; a path is a directory holding a <module>.rdf file
for each module. Writes model.json and model.yaml next to this script. Uses only the Python standard
library.
"""

import json
import re
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SPEC = "https://docs.oasis-open.org/legalruleml/legalruleml-core-spec/v1.0/os/rdfs/"
MODULES = [
    "alternative", "context", "defeasible", "deontic", "legaltemporal", "metadata-actor",
    "metadata-jurisdiction-authority", "rulemm", "source", "statement", "upper", "wrapper",
]
SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
LRMLMM = "http://docs.oasis-open.org/legalruleml/ns/v1.0/metamodel#"
RULEMM = "http://docs.oasis-open.org/legalruleml/ns/v1.0/rule-metamodel#"
LRMLV = "http://docs.oasis-open.org/legalruleml/ns/v1.0/vocab#"
NAMESPACES = (LRMLMM, RULEMM, LRMLV)
MAX_DESCRIPTION = 1024

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
XSD = "http://www.w3.org/2001/XMLSchema#"
XMLBASE = "{http://www.w3.org/XML/1998/namespace}base"

TYPE = RDF + "type"
SUBCLASS = RDFS + "subClassOf"
SUBPROPERTY = RDFS + "subPropertyOf"
DOMAIN = RDFS + "domain"
RANGE = RDFS + "range"
LABEL = RDFS + "label"
COMMENT = RDFS + "comment"
INVERSE = OWL + "inverseOf"
DISJOINT = OWL + "disjointWith"

# The datatypes the modules range properties over, as Neo4j types. An rdfs:Literal or rdfs:XMLLiteral is a
# string; the two range values the modules write unprefixed, 'rdfs:Literal' and 'rdfs:XMLLiteral', are these.
DATATYPES = {
    XSD + "date": "DATE",
    XSD + "string": "STRING",
    XSD + "anyURI": "STRING",
    RDFS + "Literal": "STRING",
    RDFS + "XMLLiteral": "STRING",
}
BARE = {"rdfs:Literal": RDFS + "Literal", "rdfs:XMLLiteral": RDFS + "XMLLiteral"}

# The prefixes that compact IRIs from other vocabularies in extensions.custom, e.g. dcterms:created.
PREFIXES = {
    "lrmlmm": LRMLMM,
    "rulemm": RULEMM,
    "lrmlv": LRMLV,
    "dcterms": "http://purl.org/dc/terms/",
    "frbr": "http://purl.org/vocab/frbr/core#",
    "rdf": RDF,
    "rdfs": RDFS,
    "owl": OWL,
    "xs": XSD,
}

# The area of the diagram the terms of each module are coloured by: four areas.
AREAS = {
    "rulemm": "Rules and statements",
    "statement": "Rules and statements",
    "wrapper": "Rules and statements",
    "upper": "Rules and statements",
    "deontic": "Deontic and defeasible",
    "defeasible": "Deontic and defeasible",
    "alternative": "Deontic and defeasible",
    "source": "Sources, authorities and time",
    "legaltemporal": "Sources, authorities and time",
    "metadata-actor": "Sources, authorities and time",
    "metadata-jurisdiction-authority": "Sources, authorities and time",
    "context": "Context",
}


def words(text):
    """The words of a snake_case or CamelCase name, e.g. refID → ref, ID; LegalSource → Legal, Source."""
    return re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z\d]*|[a-z\d]+", text)


def rel_type(name):
    return "_".join(w.upper() for w in words(name))


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


def joined(names):
    """A list of names as prose, e.g. 'A, B and C'."""
    return ", ".join(names[:-1]) + f" and {names[-1]}" if len(names) > 1 else names[0]


#----------------------------------
#   Reading the ontology
#----------------------------------


def parse_rdfxml(path):
    """Reads an RDF/XML module into a subject → predicate → [values] graph, in the order the file declares its
    terms.

    A value is an ("iri", iri), ("lit", text, datatype or None) or ("bnode", id) tuple, as the Turtle readers
    of the other standards give; a nested node element becomes the named node it is about, or a blank node.
    Covers the RDF/XML the LegalRuleML modules use: rdf:about, rdf:resource, rdf:datatype and typed node
    elements. The modules set xml:base to the namespace without the '#', while terms are referenced as
    '#Name', so relative IRIs are resolved against xml:base here, which ElementTree does not do; and the two
    range values the modules write as unprefixed names, rdfs:Literal and rdfs:XMLLiteral, are those literals.
    """
    graph, counter = {}, 0
    root = ET.parse(path).getroot()
    base = root.get(XMLBASE) or ""

    def resolve(ref):
        if ref in BARE:
            return BARE[ref]
        return base + ref if ref.startswith("#") else ref

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
        subject = resolve(subject)
        po = graph.setdefault(subject, {})
        if name(element.tag) != RDF + "Description":
            po.setdefault(TYPE, []).append(("iri", name(element.tag)))
        for prop in element:
            po.setdefault(name(prop.tag), []).append(value(prop))
        return ("bnode", subject) if subject.startswith(":b") else ("iri", subject)

    def value(prop):
        if prop.get(f"{{{RDF}}}resource") is not None:
            return ("iri", resolve(prop.get(f"{{{RDF}}}resource")))
        children = list(prop)
        if children:
            return node(children[0])
        return ("lit", prop.text or "", prop.get(f"{{{RDF}}}datatype"))

    for element in root:
        node(element)
    return graph


#----------------------------------
#   The LegalRuleML metamodel as data
#----------------------------------


class Term:
    """One LegalRuleML term: a class or a property, with every module that declares it, in module order.

    Several terms are declared in more than one module: 'applies' is repeated in six modules for diagramming
    purposes, and Comment, LegalRuleMLDocument, Scope, Statement and Statements are declared twice. The
    declarations are merged: the module of a term is the first that declares it with a label or a comment,
    which picks its defining module, e.g. context for 'applies'; its annotations are the first non-empty
    ones; and its superclasses and superproperties are the union of every declaration.
    """

    def __init__(self, iri, declarations):
        self.iri = iri
        self.declarations = declarations
        defined = [m for m, po in declarations if po.get(LABEL) or po.get(COMMENT)]
        self.module = defined[0] if defined else declarations[0][0]
        self.name = local(iri)

    def values(self, predicate):
        return [v for _, po in self.declarations for v in po.get(predicate, [])]

    def iris(self, predicate):
        """A term's IRI values, once each: declarations repeated across modules repeat their values."""
        return list(dict.fromkeys(v[1] for v in self.values(predicate) if v[0] == "iri"))

    @property
    def kinds(self):
        return {v[1] for v in self.values(TYPE) if v[0] == "iri"}

    def text(self, predicate):
        """A term's first non-empty literal. 'TBD' is a placeholder, not a description, so it is passed over."""
        for v in self.values(predicate):
            if v[0] == "lit" and tidy(v[1]) and tidy(v[1]) != "TBD":
                return tidy(v[1])
        return ""

    @property
    def functional(self):
        return OWL + "FunctionalProperty" in self.kinds

    @property
    def inverse_functional(self):
        return OWL + "InverseFunctionalProperty" in self.kinds

    @property
    def description_text(self):
        """A term's comment, else its label with the first letter capitalised; empty when it has neither."""
        comment = self.text(COMMENT)
        if comment:
            return sentence(comment)
        label = self.text(LABEL)
        return sentence(label) if label else ""


def terms_of(modules, kind):
    """The terms of one kind, rdfs:Class or rdf:Property, that the modules declare in a LegalRuleML namespace,
    each with the (module, properties) list of its declarations, in module order."""
    out = {}
    for module, graph in modules:
        for iri, po in graph.items():
            if iri.startswith(NAMESPACES) and ("iri", kind) in po.get(TYPE, []):
                out.setdefault(iri, []).append((module, po))
    return out


def individuals_of(modules, classes):
    """The individuals each modelled class is declared to have, e.g. lrmlv:InForce of LegalStatus, which are
    not themselves classes or properties."""
    out = {}
    for _, graph in modules:
        for iri, po in graph.items():
            if iri in classes or not iri.startswith(NAMESPACES):
                continue
            kinds = {v[1] for v in po.get(TYPE, []) if v[0] == "iri"}
            for cls in kinds & set(classes):
                out.setdefault(cls, []).append(iri)
    return {cls: sorted(iris) for cls, iris in out.items()}


def names_of(classes):
    """The node name of each class: its local name. Two classes of the RuleML metamodel, Wrapper and
    XMLLiteralWrapper, share their local names with classes of the LegalRuleML metamodel, so the RuleML ones
    are prefixed, e.g. RuleMLWrapper for rule-metamodel#Wrapper; sorted by IRI, the LegalRuleML metamodel
    namespace comes first and keeps the plain names."""
    names = {}
    for iri in sorted(classes):
        name = local(iri)
        if name in names.values():
            name = ("RuleML" if iri.startswith(RULEMM) else "Vocab") + name
        names[iri] = name
    if len(set(names.values())) != len(names):
        sys.exit("two LegalRuleML classes share a name")
    return names


def supertypes(term, classes):
    """The named classes a class specialises, superclasses that another superclass already specialises left
    out."""
    out = []
    for supertype in term.iris(SUBCLASS):
        if supertype in classes and supertype != term.iri and supertype not in out:
            out.append(supertype)

    def ancestors(iri, seen=None):
        seen = set() if seen is None else seen
        for supertype in classes[iri].iris(SUBCLASS):
            if supertype in classes and supertype not in seen:
                seen.add(supertype)
                ancestors(supertype, seen)
        return seen

    return [s for s in out if not any(s in ancestors(o) for o in out if o != s)]


def custom_of(term, properties, **more):
    """The extensions.custom a term's node, relationship or property carries."""
    def subproperty(iri):
        return local(iri) if iri in properties else compact(iri)

    return {
        k: v
        for k, v in (
            ("iri", term.iri),
            ("module", term.module),
            ("subPropertyOf", [subproperty(s) for s in term.iris(SUBPROPERTY)]),
            ("inverseOf", [local(i) for i in term.iris(INVERSE)]),
            ("functional", term.functional),
            *more.items(),
        )
        if v not in ("", None, [], False)
    }


def end(term, which, properties, seen=None):
    """The classes at one end of a property: its own domain or range, else its superproperties'. Returns the
    IRIs and the chain of superproperties they come through, outermost first, or [] when the property declares
    them itself. An empty result means LegalRuleML leaves that end unconstrained, and no superproperty fills
    it in."""
    seen = seen or set()
    if term.iri in seen:
        return [], []
    seen.add(term.iri)
    own = term.iris(DOMAIN if which == "domain" else RANGE)
    if own:
        return own, []
    for superproperty in term.iris(SUBPROPERTY):
        if superproperty in properties:
            found, chain = end(properties[superproperty], which, properties, seen)
            if found:
                return found, [superproperty, *chain]
    return [], []


def unmodelled(iri):
    """Why a range that is neither a class of the modules nor a literal datatype is not modelled."""
    if iri.startswith(NAMESPACES):
        return f"{compact(iri)}, which the modules reference but do not declare"
    return f"{compact(iri)}, from another vocabulary"


def build(modules):
    classes = {iri: Term(iri, declarations) for iri, declarations in terms_of(modules, RDFS + "Class").items()}
    properties = {iri: Term(iri, declarations) for iri, declarations in terms_of(modules, RDF + "Property").items()}
    individuals = individuals_of(modules, classes)
    names = names_of(classes)

    nodes = {}
    for iri in sorted(classes, key=lambda i: names[i]):
        term, name = classes[iri], names[iri]
        implied = [names[s] for s in supertypes(term, classes)]
        external = [compact(s) for s in term.iris(SUBCLASS) if s not in classes]
        disjoint = sorted(names[d] for d in term.iris(DISJOINT) if d in classes)
        values = individuals.get(iri, [])
        value_names = [f"`{local(v)}`" for v in values]
        uri = {
            "type": "STRING",
            "name": "uri",
            "description": describe(
                f"The identifier of the {name}: its IRI in LegalRuleML data. Unique within a data set; resources "
                "that are blank nodes are given generated identifiers.",
                f"One of the {len(values)} values LegalRuleML defines, whose IRIs are the allowed values of "
                f"`uri`: {joined(value_names)}."
                if values
                else "",
            ),
            "reference": "https://www.w3.org/TR/rdf11-concepts/#section-IRIs",
        }
        if values:
            uri["one_of"] = values
        description = describe(
            term.description_text,
            f"One of the {len(values)} values LegalRuleML defines: {joined(value_names)}."
            if values and not all(v in term.text(COMMENT) for v in value_names)
            else "",
        )
        nodes[name] = {
            "labels": {"identifier": name, **({"implied": implied} if implied else {})},
            **({"description": description} if description else {}),
            "reference": iri,
            "properties": {"uri": uri},
            "constraints": {f"key_{name}": {"type": "KEY", "properties": ["uri"], "name": f"uri_{name}_key"}},
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (
                        ("iri", iri),
                        ("module", term.module),
                        ("area", AREAS[term.module]),
                        ("lrmlName", local(iri) if local(iri) != name else None),
                        ("subClassOf", external),
                        ("disjointWith", disjoint),
                    )
                    if v not in ("", None, [])
                }
            },
        }

    relationships, node_properties, left_out = {}, [], []

    def relationship(term, from_name, to_name, description, custom):
        rid = f"{from_name}_{rel_type(term.name)}_{to_name}"
        while rid in relationships:
            rid += "_2"
        relationships[rid] = {
            "type": rel_type(term.name),
            "from": {"node": from_name, **({"max_count": 1} if term.functional else {})},
            "to": {"node": to_name, **({"max_count": 1} if term.inverse_functional else {})},
            "description": description,
            "reference": term.iri,
            "extensions": {"custom": custom},
        }

    def inherited_note(which, chain):
        """How a property's undeclared end is filled in: by the superproperty that declares it, e.g.
        'hasCollection', reached through the superproperties that specialise it in turn."""
        if len(chain) == 1:
            return f"Its {which} is not declared: it comes from its superproperty '{local(chain[0])}'."
        return (
            f"Its {which} is not declared: it comes from '{local(chain[-1])}', reached through "
            + joined([f"'{local(c)}'" for c in chain[:-1]]) + "."
        )

    for iri in sorted(properties, key=local):
        term = properties[iri]
        domains, domain_chain = end(term, "domain", properties)
        ranges, range_chain = end(term, "range", properties)
        inherited = [which for which, chain in (("domain", domain_chain), ("range", range_chain)) if chain]
        description = describe(
            term.description_text,
            inherited_note("domain", domain_chain) if domain_chain else "",
            inherited_note("range", range_chain) if range_chain else "",
        )
        if not domains:
            left_out.append((term.name, "no domain" if ranges else "neither domain nor range"))
            continue
        if not all(d in classes for d in domains):
            left_out.append((term.name, unmodelled(next(d for d in domains if d not in classes))))
            continue
        if not ranges:
            left_out.append((term.name, "no range"))
            continue
        if all(r in DATATYPES for r in ranges):
            types = {DATATYPES[r] for r in ranges}
            if len(types) != 1:
                sys.exit(f"{term.name}: no single Neo4j type for {ranges}")
            neo4j = types.pop()
            for domain in domains:
                node = nodes[names[domain]]
                if term.name in node["properties"]:
                    sys.exit(f"{names[domain]}: two properties named {term.name}")
                node["properties"][term.name] = {
                    "type": neo4j if term.functional else f"LIST<{neo4j}>",
                    "name": term.name,
                    **({"description": description} if description else {}),
                    "reference": term.iri,
                    "extensions": {
                        "custom": custom_of(
                            term,
                            properties,
                            datatypes=["xsd:" + local(r) if r.startswith(XSD) else compact(r) for r in ranges],
                            inheritedEnds=inherited,
                        )
                    },
                }
                node_properties.append(f"{names[domain]}.{term.name}")
            continue
        if not all(r in classes for r in ranges):
            left_out.append((term.name, unmodelled(next(r for r in ranges if r not in classes))))
            continue
        for domain in domains:
            for range_ in ranges:
                relationship(
                    term,
                    names[domain],
                    names[range_],
                    description,
                    custom_of(term, properties, inheritedEnds=inherited),
                )

    for rel in relationships.values():
        for end_node in (rel["from"], rel["to"]):
            if end_node["node"] not in nodes:
                sys.exit(f"relationship {rel['type']} points at {end_node['node']}, which is not a class")
    for name, node in nodes.items():
        for implied in node["labels"].get("implied", []):
            if implied not in nodes:
                sys.exit(f"{name}: implied label {implied} is not a class")

    model = {
        **META,
        "nodes": nodes,
        "relationships": dict(sorted(relationships.items())),
    }
    report = [
        f"{len(modules)} modules: {', '.join(module for module, _ in modules)}",
        f"{len(nodes)} nodes, {len(model['relationships'])} relationships",
        f"properties: {', '.join(sorted(node_properties))}" if node_properties else "",
        f"renamed for a shared name: "
        + joined(sorted(
            f"{names[iri]} ({compact(iri)})" for iri in classes if names[iri] != local(iri)
        )) if any(names[iri] != local(iri) for iri in classes) else "",
        *(f"left out, {name} ({reason})" for name, reason in left_out),
    ]
    return model, [line for line in report if line]


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
    "version": "1.0",
    "id": "legalruleml-1.0",
    "name": "LegalRuleML 1.0",
    "description": (
        "The RDFS metamodel of LegalRuleML 1.0, an OASIS Standard of 30 August 2021 published by the OASIS "
        "LegalRuleML Technical Committee (https://www.oasis-open.org/committees/legalruleml/). LegalRuleML is a "
        "language for legal rules: the deontic specifications, e.g. obligations, prohibitions, permissions, "
        "rights and the suborder lists that chain them, that legal sources give rise to; the defeasible rules, "
        "strengths and overrides that resolve conflicts between them; and the statements, sources, references, "
        "authorities, jurisdictions, actors, roles and times they are stated in, hold for and are applied in. "
        "It extends RuleML with features specific to legal norms, guidelines and policies, and is a companion "
        "to Akoma Ntoso, which it follows in identifying the documents rules are found in. Generated from the "
        "twelve RDFS modules of the Core Specification: each class is a node, each property whose domain and "
        "range are classes of the modules a relationship from its domain to its range, each property with a "
        "literal range a property of its domain, and each superclass an implied label."
    ),
}


def main():
    if len(sys.argv) > 1:
        folder = Path(sys.argv[1])
    else:
        folder = Path(tempfile.mkdtemp())
        for module in MODULES:
            request = urllib.request.Request(SPEC + module + ".rdf", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request) as response:
                (folder / f"{module}.rdf").write_bytes(response.read())
    modules = []
    for module in MODULES:
        path = folder / f"{module}.rdf"
        if not path.is_file():
            sys.exit(f"{path}: not found")
        modules.append((module, parse_rdfxml(path)))
    model, report = build(modules)
    out = Path(__file__).parent
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(yaml(model) + "\n")
    print("\n".join(report))


if __name__ == "__main__":
    main()
