#!/usr/bin/env python3
"""Generates the Common Core Ontologies (CCO) 2.2 ontology from the CCO repository.

Usage: python3 generate.py [path/to/CommonCoreOntologies]

The entry module is the All Core Ontology, which imports the eleven CCO modules, at the commit of the repository's
v2.2 tag. Their owl:imports, followed to the full closure, add the Basic Formal Ontology (BFO 2020) they're built
on. Each import is resolved to a file through the catalog beside the entry module, and the files are downloaded
from raw.githubusercontent.com at the pinned commit (or read from a local checkout given as the argument). CCO is
written in OWL on BFO 2020, as the Industrial Ontologies Foundry's ontologies are, so building reuses the IOF
generator in ../../industrial/IOF; reading the Turtle files is done here. Writes model.json and model.yaml next to
this script. Uses only the Python standard library.
"""

import importlib.util
import json
import posixpath
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

# The IOF generator, whose reading of BFO-based OWL CCO shares; loaded without leaving a __pycache__ behind.
sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location(
    "iof_generate", Path(__file__).resolve().parent.parent.parent / "industrial" / "IOF" / "generate.py"
)
iof = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(iof)

COMMIT = "0bc7d33e1bc09fd4693366119ab4e03cb0340042"  # the v2.2 tag
RAW = f"https://raw.githubusercontent.com/CommonCoreOntology/CommonCoreOntologies/{COMMIT}/"
ENTRY = "src/cco-merged/AllCoreOntology.ttl"
CATALOG = "src/cco-merged/catalog-v001.xml"
CCO = "https://www.commoncoreontologies.org/"
CURATED_IN = CCO + "ont00001760"  # 'is curated in ontology': the module a term belongs to
XSD = iof.XSD

# The area each module places its terms in, for extensions.custom.area and the diagram's four colours.
AREAS = {
    "BFO": "BFO top level",
    "AgentOntology": "Agents, events and time",
    "EventOntology": "Agents, events and time",
    "TimeOntology": "Agents, events and time",
    "ArtifactOntology": "Artifacts and facilities",
    "FacilityOntology": "Artifacts and facilities",
    "InformationEntityOntology": "Information, qualities, units and places",
    "QualityOntology": "Information, qualities, units and places",
    "UnitsOfMeasureOntology": "Information, qualities, units and places",
    "CurrencyUnitOntology": "Information, qualities, units and places",
    "GeospatialOntology": "Information, qualities, units and places",
    "ExtendedRelationOntology": "Information, qualities, units and places",
}

META = {
    "schema": iof.SCHEMA,
    "version": "2.2",
    "id": "cco-2.2",
    "name": "Common Core Ontologies 2.2",
    "description": (
        "The Common Core Ontologies (CCO) 2.2, a mid-level ontology published by the CCO Governance Board "
        "(https://github.com/CommonCoreOntology/CommonCoreOntologies) under the BSD 3-Clause licence, and directed as "
        "a baseline standard for ontology development across the US Department of Defense and Intelligence "
        "Community. Its eleven modules hold the classes common to data in many domains: agents, persons, "
        "organizations and their roles; acts, events and processes; temporal intervals and instants; artifacts, "
        "with their functions, models and specifications; facilities; information content entities and the "
        "information bearing entities that carry them; qualities, realizable entities and process profiles; units "
        "of measure and currencies; sites and spatial regions; and the relations between them. Built on the Basic "
        "Formal Ontology (BFO 2020), which the closure of their owl:imports adds: each class is a node, each object "
        "property a relationship from its domain to its range (one direction per inverse pair), each datatype "
        "property a property, each class restriction a count, and each superclass an implied label."
    ),
}


def words(text):
    return re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z\d]*|[a-z\d]+", text) or re.findall(r"[A-Za-z0-9]+", text)


#----------------------------------
#   Reading Turtle
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
        elif c.isdigit() or (c in "+-" and text[i + 1].isdigit()):
            j = i + 1
            while j < n and (text[j].isdigit() or text[j] in ".eE+-"):
                j += 1
            yield ("num", text[i:j])
            i = j
        else:
            yield ("punct", c)
            i += 1


def parse_turtle(text, scope, base=""):
    """Reads a Turtle file into a subject → predicate → [values] graph.

    A value is an ("iri", iri), ("lit", text, datatype or langtag or None), ("bnode", id) or ("coll", [values])
    tuple, as the IOF generator's RDF/XML reader gives; a blank node property list becomes its own subject, named
    within `scope` so that the blank nodes of different modules stay apart, and a collection is kept as a single
    value. Relative IRIs are resolved against @base, or else `base`.
    """
    graph = {}
    toks = list(reversed(list(tokens(text))))
    prefixes, counter = {}, 0

    def peek():
        return toks[-1] if toks else (None, None)

    def take():
        return toks.pop()

    def expand(name):
        prefix, _, local_name = name.partition(":")
        return prefixes[prefix] + local_name

    def absolute(iri):
        return iri if re.match(r"[a-z][a-z0-9+.-]*:", iri) else base + iri

    def term():
        nonlocal counter
        kind, value = take()
        if kind == "iri":
            return ("iri", absolute(value))
        if kind == "name":
            if value in ("true", "false"):
                return ("lit", value, XSD + "boolean")
            return ("iri", expand(value))
        if kind == "num":
            return ("lit", value, XSD + ("integer" if re.fullmatch(r"[+-]?\d+", value) else "decimal" if "e" not in value.lower() else "double"))
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
            predicate = iof.TYPE if (kind, value) == ("name", "a") else absolute(value) if kind == "iri" else expand(value)
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
            prefixes[name[1].rstrip(":")] = absolute(iri[1])
            assert take() == ("punct", ".")
        elif (kind, value) == ("at", "base"):
            base = take()[1]
            assert take() == ("punct", ".")
        else:
            toks.append((kind, value))
            subject = term()
            if peek() != ("punct", "."):  # a named subject: its predicates and objects follow
                predicate_object_list(subject[1])
            assert take() == ("punct", ".")
    return graph


class Source:
    """The files of the import closure, read from the pinned commit of the CCO repository (or a local checkout)
    and cached in memory. An import IRI is resolved to a file by the catalog beside the entry module."""

    def __init__(self, local=None):
        self.local = Path(local).resolve() if local else None
        self.cache = {}
        catalog = ET.fromstring(self.read(CATALOG))
        folder = posixpath.dirname(CATALOG)
        self.paths = {
            entry.get("name"): posixpath.normpath(posixpath.join(folder, entry.get("uri")))
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


def module_name(ontology_iri):
    """The short name of a module, from the IRI its owl:Ontology declares, e.g. AgentOntology or BFO."""
    if ontology_iri.startswith(iof.OBO):
        return "BFO"
    if not ontology_iri.startswith(CCO):
        sys.exit(f"{ontology_iri}: a module this generator doesn't know")
    return ontology_iri[len(CCO):].strip("/")


def ontology_of(graph):
    return next(s for s, po in graph.items() if ("iri", iof.OWL + "Ontology") in po.get(iof.TYPE, []))


def closure(source):
    """The modules the All Core Ontology's owl:imports close over: module name → graph, in the order found. The
    All Core Ontology itself has no content of its own, so it isn't one of them."""
    entry = parse_turtle(source.read(ENTRY).decode(), "entry_")
    modules, seen = {}, set()
    pending = sorted(v[1] for v in entry[ontology_of(entry)].get(iof.OWL + "imports", []) if v[0] == "iri")
    while pending:
        iri = pending.pop(0)
        path = source.paths.get(iri)
        if path is None:
            sys.exit(f"{iri}: an import the catalog doesn't resolve")
        if path in seen:
            continue
        seen.add(path)
        graph = parse_turtle(source.read(path).decode(), f"m{len(seen)}_")
        ontology = ontology_of(graph)
        modules[module_name(ontology)] = graph
        pending += sorted(v[1] for v in graph[ontology].get(iof.OWL + "imports", []) if v[0] == "iri")
    return modules


class Ontology(iof.Ontology):
    """The IOF generator's reading of the closure, with CCO's own conventions: a term's module is the one its
    'is curated in ontology' annotation names, and a datatype property whose IRI is an opaque identifier, e.g.
    ont00001771, is named by its label, e.g. hasDateValue."""

    def __init__(self, modules):
        super().__init__(modules)
        for iri in list(self.declared_in):
            curated = [v[1] for v in self.values(iri, CURATED_IN) if v[0] in ("iri", "lit")]
            if curated:
                self.declared_in[iri] = module_name(curated[0])
        self.individuals = {
            module: sorted(s for s, po in graph.items() if ("iri", iof.OWL + "NamedIndividual") in po.get(iof.TYPE, []))
            for module, graph in modules.items()
        }

    def property_name(self, iri):
        name = iof.local(iri)
        if not re.fullmatch(r"ont\d+", name):
            return name
        parts = words(self.said(iri))
        return parts[0].lower() + "".join(w[0].upper() + w[1:] for w in parts[1:])


def main():
    source = Source(sys.argv[1] if len(sys.argv) > 1 else None)
    iof.AREAS = AREAS
    iof.META = META
    iof.DATA = "CCO"

    modules = closure(source)
    unknown = [module for module in modules if module not in AREAS]
    if unknown:
        sys.exit(f"modules without an area: {', '.join(unknown)}")
    onto = Ontology(modules)
    model, node_properties = iof.build(onto)

    out = Path(__file__).parent
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(iof.yaml(model) + "\n")
    print(f"{len(modules)} modules: {', '.join(onto.modules)}")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships, {node_properties} node properties")
    if onto.deprecated:
        print(f"deprecated, not kept: {', '.join(onto.said(p) for p in onto.deprecated)}")
    individuals = {module: len(iris) for module, iris in onto.individuals.items() if iris}
    if individuals:
        print("named individuals, not kept: " + ", ".join(f"{n} in {module}" for module, n in individuals.items()))
    for construct, where in sorted(onto.dropped.items()):
        print(f"not kept, {construct}: {', '.join(sorted(set(where)))}")


if __name__ == "__main__":
    main()
