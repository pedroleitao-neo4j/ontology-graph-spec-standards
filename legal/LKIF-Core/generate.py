#!/usr/bin/env python3
"""Generates the LKIF Core 1.1 ontology from the official LKIF Core Turtle files.

Usage: python3 generate.py [path/to/lkif-core.zip | path/to/lkif-core]

Without a path, the pinned commit of the LKIF Core repository is downloaded from GitHub. Writes model.json and
model.yaml next to this script. Uses only the Python standard library.
"""

import json
import re
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

COMMIT = "1958d940c4157678c7f5445b07b35e093e918f31"
SOURCE_URL = f"https://github.com/RinkeHoekstra/lkif-core/archive/{COMMIT}.zip"
BROWSE = f"https://github.com/RinkeHoekstra/lkif-core/blob/{COMMIT}/"
SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
LKIF = "http://www.estrellaproject.org/lkif-core/"
ENTRY = "lkif-core"  # the module whose imports make up LKIF Core; lkif-extended adds the two framework modules
MAX_DESCRIPTION = 1024

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
XSD = "http://www.w3.org/2001/XMLSchema#"

TYPE = RDF + "type"
SUBCLASS = RDFS + "subClassOf"
SUBPROPERTY = RDFS + "subPropertyOf"
DOMAIN = RDFS + "domain"
RANGE = RDFS + "range"
COMMENT = RDFS + "comment"
INVERSE = OWL + "inverseOf"
EQUIVALENT = OWL + "equivalentClass"
UNIONOF = OWL + "unionOf"
INTERSECTIONOF = OWL + "intersectionOf"
ONPROPERTY = OWL + "onProperty"
ONCLASS = OWL + "onClass"
SOME = OWL + "someValuesFrom"
ALLV = OWL + "allValuesFrom"
THING = OWL + "Thing"

# The root of the model: owl:Thing, which LKIF's top classes specialise and many of its properties range over.
ROOT = "Thing"


def words(text):
    """The words of a snake_case or CamelCase name, e.g. Legal_Document → Legal, Document; actor_in → actor, in."""
    return re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z\d]*|[a-z\d]+", text) or re.findall(r"[A-Za-z0-9]+", text)


def pascal(name):
    """A class name as a label, e.g. Legal_Document → LegalDocument."""
    return "".join(w[0].upper() + w[1:] for w in words(name))


def rel_type(name):
    return "_".join(w.upper() for w in words(name))


def spaced(name):
    """A property name as LKIF writes it in prose, e.g. actor_in → 'actor in'."""
    return name.replace("_", " ")


def article(name):
    return "an" if name[0] in "AEIOU" else "a"


def local(iri):
    return re.split(r"[/#]", iri)[-1]


def module(iri):
    """The module an IRI belongs to, e.g. http://www.estrellaproject.org/lkif-core/norm.owl#Norm → norm."""
    return iri[len(LKIF):].split(".owl", 1)[0] if iri.startswith(LKIF) else "owl"


def tidy(text):
    """Collapses whitespace, and drops the stray backslash some comments end with."""
    return re.sub(r"\s+", " ", text).strip().rstrip("\\").strip()


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


def read_prefixes(text):
    return {m[0]: m[1] for m in re.findall(r"@prefix\s+([\w-]*):\s+<([^>]*)>", text)}


def module_files(source):
    """The Turtle files of the modules LKIF Core imports, from its entry module down: a downloaded or given zip
    archive, or a directory."""
    if not source.is_dir():
        out = Path(tempfile.mkdtemp())
        zipfile.ZipFile(source).extractall(out)
        source = out
    entry = next(source.rglob(f"{ENTRY}.ttl"), None)
    if entry is None:
        sys.exit(f"{source}: no {ENTRY}.ttl")
    files, pending = {}, [ENTRY]
    while pending:
        name = pending.pop()
        if name in files:
            continue
        files[name] = entry.parent / f"{name}.ttl"
        text = files[name].read_text()
        imports = re.search(r"owl:imports\s+(.*?)\s*[;.]\s*$", text, re.S | re.M)
        pending += re.findall(re.escape(LKIF) + r"([\w-]+)\.owl", imports.group(1)) if imports else []
    return files


def declarations(files):
    """Where each term is declared in its own module's file: IRI → 'file.ttl#Lline', for the reference links."""
    out = {}
    for name, path in files.items():
        text = path.read_text()
        prefixes = read_prefixes(text)
        for number, line in enumerate(text.splitlines(), 1):
            match = re.match(r"(<[^>]+>|[\w-]*:[\w-]+)\s+a\s", line)
            if not match:
                continue
            subject = match.group(1)
            if subject.startswith("<"):
                iri = subject[1:-1]
            else:
                prefix, _, local_name = subject.partition(":")
                iri = prefixes[prefix] + local_name
            if module(iri) == name:
                out.setdefault(iri, f"{path.name}#L{number}")
    return out


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
    """The classes and properties of LKIF Core, read out of the merged graph of its modules."""

    def __init__(self, graph):
        self.graph = graph

        def named(kind):
            return {
                s: po
                for s, po in graph.items()
                if s.startswith(LKIF) and ("iri", kind) in po.get(TYPE, [])
            }

        self.classes = named(OWL + "Class")
        self.properties = named(OWL + "ObjectProperty")
        self.data_properties = named(OWL + "DatatypeProperty")
        self.names = {iri: pascal(local(iri)) for iri in self.classes}
        self.names[THING] = ROOT
        if len(set(self.names.values())) != len(self.names):
            sys.exit("two LKIF classes share a label")
        self.dropped = {}  # what the class axioms say that the ontology can't, by construct

        # A pair of inverse properties is declared from one side only, so the map is built in both directions.
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

    def comments(self, iri):
        return [sentence(v[1]) for v in self.values(iri, COMMENT) if v[0] == "lit" and tidy(v[1])]

    def kinds(self, iri):
        return {local(k) for k in self.iris(iri, TYPE)}

    def members(self, value, keyword):
        """The members of a blank node's union or intersection, or [] if it is neither."""
        if value[0] != "bnode":
            return []
        return next((v[1] for v in self.values(value[1], keyword) if v[0] == "coll"), [])

    def kept(self, prop):
        """Whether a property is the direction of its inverse pair that becomes a relationship. LKIF names most
        pairs in the active and the passive voice, e.g. actor and actor_in; the active one is kept. Of a pair in
        the same voice, e.g. bears and medium, the one the other declares itself the owl:inverseOf is kept."""
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
        superproperties'. An empty result means LKIF leaves that end unconstrained."""
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
        """The named classes a class expression stands for: a class itself, the members of a union, or the named
        members of an intersection, which an individual of it is an instance of. A restriction or complement names
        no class, and gives []."""
        if value[0] == "iri":
            return [value[1]]
        union = self.members(value, UNIONOF)
        if union:
            return [c for member in union for c in self.fillers(member)]
        return [m[1] for m in self.members(value, INTERSECTIONOF) if m[0] == "iri"]

    def axioms(self, cls):
        """The restrictions a class's axioms place on it: those it is a subclass of, and those its equivalent
        classes are or intersect, which are necessary conditions too."""
        out = []
        for value in self.values(cls, SUBCLASS) + self.values(cls, EQUIVALENT):
            if value[0] == "bnode" and ONPROPERTY in self.graph[value[1]]:
                out.append(value)
            out += [m for m in self.members(value, INTERSECTIONOF) if m[0] == "bnode" and ONPROPERTY in self.graph[m[1]]]
        return out

    def supertypes(self, cls):
        """The named classes a class specialises: its superclasses, the named members of an intersection it is
        equivalent to, and every union it is a member of an equivalent of."""
        out = [s for s in self.iris(cls, SUBCLASS) if s in self.classes]
        for value in self.values(cls, EQUIVALENT):
            out += [m[1] for m in self.members(value, INTERSECTIONOF) if m[0] == "iri"]
        for other in self.classes:
            for value in self.values(other, EQUIVALENT):
                if ("iri", cls) in self.members(value, UNIONOF):
                    out.append(other)
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

    def equivalents(self, cls):
        """The named classes a class is equivalent to, in either direction."""
        out = [e for e in self.iris(cls, EQUIVALENT) if e in self.classes]
        out += [o for o in self.classes if cls in self.iris(o, EQUIVALENT)]
        return sorted(set(out) - {cls}, key=local)

    def union_of(self, cls):
        return next((self.fillers(v) for v in self.values(cls, EQUIVALENT) if self.members(v, UNIONOF)), [])


def build(onto, refs):
    def reference(iri):
        return BROWSE + refs[iri] if iri in refs else iri

    nodes = {}
    for iri in [THING, *sorted(onto.classes, key=local)]:
        name = onto.names[iri]
        supertypes = [onto.names[s] for s in onto.supertypes(iri)] if iri != THING else []
        if iri != THING and not supertypes:
            supertypes = [ROOT]  # a top class: everything is a Thing
        equivalents = [onto.names[e] for e in onto.equivalents(iri)]
        union = [onto.names[u] for u in onto.union_of(iri)]
        description = describe(
            *(onto.comments(iri) if iri != THING else [
                "Anything at all: owl:Thing, which every LKIF class specialises. The label every node carries, and "
                "the end of the relationships LKIF leaves open to any individual, e.g. what a role is played by."
            ]),
            f"Equivalent to {' and '.join(equivalents)}." if equivalents else "",
            f"Equivalent to the union of {', '.join(union[:-1])} and {union[-1]}." if union else "",
        )
        nodes[name] = {
            "labels": {"identifier": name, **({"implied": supertypes} if supertypes else {})},
            **({"description": description} if description else {}),
            "reference": reference(iri),
            "properties": {
                "uri": {
                    "type": "STRING",
                    "name": "uri",
                    "description": f"The identifier of the {name} individual: its IRI in LKIF data. Unique within "
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
                        ("module", module(iri)),
                        ("lkifName", local(iri) if local(iri) != name else None),
                        ("equivalentTo", equivalents),
                        ("unionOf", union),
                        ("disjointWith", sorted(onto.names[d] for d in onto.iris(iri, OWL + "disjointWith") if d in onto.names)),
                    )
                    if v not in (None, [])
                }
            },
        }

    # Relationships are gathered by type and ends, so that what the domain and range say and what each
    # restriction adds end up on one relationship: its counts, and the sentences that explain them.
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

    def classes_or_root(found):
        return sorted(found, key=local) if found else [THING]

    for prop in onto.properties:
        if onto.kept(prop):
            for source in classes_or_root(onto.end_classes(prop, "domain")):
                for target in classes_or_root(onto.end_classes(prop, "range")):
                    rel = relationship(prop, source, target)
                    if "FunctionalProperty" in onto.kinds(prop):
                        tighten(rel["from"], 0, 1)
                    if "InverseFunctionalProperty" in onto.kinds(prop):
                        tighten(rel["to"], 0, 1)

    # Each restriction becomes a relationship from the restricted class, or, on the inverse of a kept property,
    # to it: someValuesFrom and the cardinalities give counts at the restricted end, allValuesFrom a narrower end.
    for cls in onto.classes:
        name = onto.names[cls]
        for restriction in onto.axioms(cls):
            body = onto.graph[restriction[1]]
            used = next(v[1] for v in body[ONPROPERTY] if v[0] == "iri")
            prop, forward = (used, True) if onto.kept(used) else (onto.inverses[used], False)
            said = spaced(local(used))
            if SOME in body or ALLV in body:
                value = (body.get(SOME) or body.get(ALLV))[0]
                targets = onto.fillers(value)
                union = bool(onto.members(value, UNIONOF))
                if not targets and SOME in body:
                    targets = sorted(onto.end_classes(used, "range"), key=local) or [THING]
                    union = len(targets) > 1
                if not targets:
                    onto.dropped.setdefault("allValuesFrom a class expression without a named class", []).append(name)
                    continue
                lower, upper = (1 if SOME in body and not union else 0), None
            elif {OWL + "cardinality", OWL + "minCardinality", OWL + "maxCardinality"} & body.keys():
                number = lambda k: int(body[OWL + k][0][1]) if OWL + k in body else None
                lower = number("cardinality") if number("cardinality") is not None else number("minCardinality") or 0
                upper = number("cardinality") if number("cardinality") is not None else number("maxCardinality")
                if upper == 0:
                    onto.dropped.setdefault("a cardinality of zero", []).append(name)
                    continue
                # An unqualified cardinality counts the values another restriction on the property narrows, e.g.
                # the two direct parts of a Transaction, every one of which is an Action.
                narrowed = [
                    c
                    for other in onto.axioms(cls)
                    if ("iri", used) in onto.graph[other[1]][ONPROPERTY] and ALLV in onto.graph[other[1]]
                    for c in onto.fillers(onto.graph[other[1]][ALLV][0])
                ]
                targets = [v[1] for v in body.get(ONCLASS, []) if v[0] == "iri"] or narrowed[:1] or sorted(
                    onto.end_classes(used, "range"), key=local
                ) or [THING]
                union = False
            else:
                onto.dropped.setdefault("a restriction of another kind", []).append(name)
                continue
            for target in targets:
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
                rel["restrictions"].append(next((local(k) for k in (SOME, ALLV) if k in body), "cardinality"))

    relationships = {}
    for (prop, source, target), rel in sorted(gathered.items(), key=lambda g: (local(g[0][0]), onto.names[g[0][1]], onto.names[g[0][2]])):
        rtype = rel_type(local(prop))
        sname, tname = onto.names[source], onto.names[target]
        rid = f"{sname}_{rtype}_{tname}"
        while rid in relationships:
            rid += "_2"
        inverse = onto.inverses.get(prop)
        kinds = onto.kinds(prop)
        supers = [local(s) for s in onto.iris(prop, SUBPROPERTY) if s in onto.properties]
        relationships[rid] = {
            "type": rtype,
            "from": {"node": sname, **ends(*rel["from"])},
            "to": {"node": tname, **ends(*rel["to"])},
            "description": describe(
                *onto.comments(prop),
                f"LKIF also names the inverse, '{spaced(local(inverse))}'." if inverse else "",
                "Symmetric." if "SymmetricProperty" in kinds else "",
                "Transitive." if "TransitiveProperty" in kinds else "",
                *dict.fromkeys(rel["notes"]),
                f"Each {sname} has {phrase(*rel['from'])} {tname}." if rel["from"] != [0, None] and not rel["notes"] else "",
            ),
            "reference": reference(prop),
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (
                        ("iri", prop),
                        ("module", module(prop)),
                        ("inverseOf", local(inverse) if inverse else None),
                        ("subPropertyOf", supers),
                        ("equivalentProperty", [local(e) for e in onto.iris(prop, OWL + "equivalentProperty")]),
                        ("symmetric", "SymmetricProperty" in kinds),
                        ("transitive", "TransitiveProperty" in kinds),
                        ("functional", "FunctionalProperty" in kinds),
                        ("restrictions", sorted(set(rel["restrictions"]))),
                    )
                    if v not in (None, [], False)
                }
            },
        }

    for rel in relationships.values():
        for end in (rel["from"], rel["to"]):
            if end["node"] not in nodes:
                sys.exit(f"relationship {rel['type']} points at {end['node']}, which is not a class")
    return {**META, "nodes": nodes, "relationships": relationships}


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
    "version": "1.1",
    "id": "lkif-core-1.1",
    "name": "LKIF Core 1.1",
    "description": (
        "LKIF Core 1.1, the core legal ontology of the Legal Knowledge Interchange Format, developed by the University "
        "of Amsterdam, the University of Bologna and Fraunhofer FOKUS in the European ESTRELLA project "
        "(IST-2004-027665) and maintained by Rinke Hoekstra (https://github.com/RinkeHoekstra/lkif-core) under CC BY "
        "4.0. It is a library of OWL modules for the concepts legal knowledge is built on: norms as qualifications of "
        "what is allowed, disallowed or obliged; legal sources such as statutes, regulations, contracts and precedents; "
        "rights and powers after Hohfeld and Sartor; legal persons, public bodies and public acts; legal and social "
        "roles; and the commonsense layers beneath them, from propositions, beliefs and communicated attitudes to "
        "actions, agents, processes, places, time and parthood. Generated from the Turtle files of the twelve modules "
        "LKIF Core imports: each class is a node, each object property a relationship from its domain to its range "
        "(one direction per inverse pair), each class restriction a relationship or a count, and each superclass an "
        "implied label."
    ),
}


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else download(SOURCE_URL, "lkif-core.zip")
    files = module_files(source)
    graph = {}
    for i, path in enumerate(sorted(files.values())):
        parse_turtle(path.read_text(), graph, f"f{i}")
    onto = Ontology(graph)
    if onto.data_properties:
        sys.exit(f"datatype properties aren't read: {', '.join(local(p) for p in onto.data_properties)}")
    model = build(onto, declarations(files))
    out = Path(__file__).parent
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(yaml(model) + "\n")
    print(f"{len(files)} modules: {', '.join(sorted(files))}")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships")
    for construct, where in sorted(onto.dropped.items()):
        print(f"not kept, {construct}: {', '.join(sorted(set(where)))}")


if __name__ == "__main__":
    main()
