#!/usr/bin/env python3
"""Generates the Akoma Ntoso ontology from the OASIS LegalDocML Akoma Ntoso Version 1.0 XML schema.

Usage: python3 generate.py [path/to/akomantoso30.xsd]

Without a path, the schema is downloaded from the OASIS document repository. Writes model.json and model.yaml next to
this script. Uses only the Python standard library.
"""

import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SPECS = "https://docs.oasis-open.org/legaldocml/akn-core/v1.0/os/part2-specs"
SOURCE_URL = f"{SPECS}/schemas/akomantoso30.xsd"
DOCS = f"{SPECS}/os-part2-specs_xsd_"  # the specification's page for each declaration, e.g. …Element_act.html
NAMING = "https://docs.oasis-open.org/legaldocml/akn-nc/v1.0/os/akn-nc-v1.0-os.html"  # the naming convention
SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
MAX_DESCRIPTION = 1024

XS = "{http://www.w3.org/2001/XMLSchema}"
AKN = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}"

XSD_TYPES = {
    "string": "STRING",
    "anyURI": "STRING",
    "boolean": "BOOLEAN",
    "integer": "INTEGER",
    "dateTime": "ZONED DATETIME",
    "duration": "DURATION",
}

# The elements that become nodes, by the area of the diagram they are drawn in. Every other element is either a value
# (VALUES), or left out: presentational markup and generic text structure, through which what it contains is
# attached to the nearest node above it.
AREAS = {
    "Document": (
        "akomaNtoso", "act", "bill", "amendment", "amendmentList", "debate", "debateReport", "doc",
        "documentCollection", "judgment", "officialGazette", "portion", "statement", "components", "component",
        "attachments", "attachment", "documentRef", "componentRef", "coverPage", "preface", "preamble", "header",
        "body", "mainBody", "judgmentBody", "debateBody", "amendmentBody", "collectionBody", "portionBody",
        "conclusions",
    ),
    "Metadata": (
        "meta", "identification", "FRBRWork", "FRBRExpression", "FRBRManifestation", "FRBRItem", "FRBRauthor",
        "FRBRtranslation", "publication", "classification", "keyword", "lifecycle", "eventRef", "workflow", "step",
        "analysis", "activeModifications", "passiveModifications", "textualMod", "meaningMod", "scopeMod",
        "forceMod", "efficacyMod", "legalSystemMod", "source", "destination", "force", "efficacy", "application",
        "duration", "condition", "previous", "old", "new", "domain", "restrictions", "restriction", "judicial",
        "result", "supports", "isAnalogTo", "applies", "extends", "restricts", "derogates", "contrasts",
        "overrules", "dissentsFrom", "putsInQuestion", "distinguishes", "parliamentary", "quorumVerification",
        "voting", "recount", "quorum", "count", "mappings", "mapping", "otherReferences", "implicitReference",
        "alternativeReference", "otherAnalysis", "temporalData", "temporalGroup", "timeInterval", "references",
        "notes", "note", "proprietary", "presentation",
    ),
    "Structure": (
        "clause", "section", "part", "paragraph", "chapter", "title", "article", "book", "tome", "division", "list",
        "point", "indent", "alinea", "rule", "subrule", "proviso", "subsection", "subpart", "subparagraph",
        "subchapter", "subtitle", "subdivision", "subclause", "sublist", "level", "transitional", "hcontainer",
        "intro", "content", "wrapUp", "recitals", "recital", "citations", "citation", "longTitle", "formula",
        "administrationOfOath", "rollCall", "prayers", "oralStatements", "writtenStatements", "personalStatements",
        "ministerialStatements", "resolutions", "nationalInterest", "declarationOfVote", "communication",
        "petitions", "papers", "noticesOfMotion", "questions", "address", "proceduralMotions", "pointOfOrder",
        "adjournment", "debateSection", "speechGroup", "speech", "question", "answer", "introduction",
        "background", "arguments", "remedies", "motivation", "decision", "amendmentHeading", "amendmentContent",
        "amendmentReference", "amendmentJustification",
    ),
    "Reference": (
        "TLCPerson", "TLCOrganization", "TLCConcept", "TLCObject", "TLCEvent", "TLCLocation", "TLCProcess",
        "TLCRole", "TLCTerm", "TLCReference", "original", "passiveRef", "activeRef", "jurisprudence",
        "hasAttachment", "attachmentOf", "ref", "mref", "rref", "mod", "mmod", "rmod", "quotedText",
        "quotedStructure", "vote", "opinion", "date", "time", "person", "organization", "concept", "object",
        "event", "location", "process", "role", "term", "quantity", "def", "entity", "docType", "docTitle",
        "docNumber", "docProponent", "docDate", "legislature", "session", "shortTitle", "docAuthority",
        "docPurpose", "docCommittee", "docIntroducer", "docStage", "docStatus", "docJurisdiction", "docketNumber",
        "courtType", "neutralCitation", "party", "judge", "lawyer", "signature", "argument", "affectedDocument",
        "relatedDocument", "change", "noteRef", "authorialNote",
    ),
}  # fmt: skip

# The elements that hold a single value, which become properties of the element that holds them: the attribute that
# holds the value, or None for the element's text, and the other attributes kept with it.
VALUES = {
    "FRBRthis": ("value", ()),
    "FRBRuri": ("value", ()),
    "FRBRalias": ("value", ("name",)),
    "FRBRdate": ("date", ("name",)),
    "FRBRcountry": ("value", ()),
    "FRBRsubtype": ("value", ()),
    "FRBRnumber": ("value", ()),
    "FRBRname": ("value", ()),
    "FRBRprescriptive": ("value", ()),
    "FRBRauthoritative": ("value", ()),
    "FRBRversionNumber": ("value", ()),
    "FRBRlanguage": ("language", ()),
    "FRBRformat": ("value", ()),
    "FRBRmasterExpression": ("href", ()),
    "num": (None, ()),
    "heading": (None, ()),
    "subheading": (None, ()),
}

# The labels that group elements: those of an element group of the schema, every element of which carries the label;
# those of a complex type, carried by every element of that type or a type extending it; and unions of other labels.
GROUP_LABELS = {
    "documentType": "Document",
    "hierElements": "Hierarchy",
    "speechSection": "SpeechSection",
    "ANcontainers": "DebateContainer",
    "judgmentBlock": "JudgmentBlock",
    "amendmentBlock": "AmendmentBlock",
    "TLCs": "TLC",
    "docRefs": "DocRef",
    "inlineCM": "InlineElement",
    "ANsemanticInline": "SemanticInline",
    "ANtitleInline": "TitleInline",
    "ANheaderInline": "HeaderInline",
    "amendmentInline": "AmendmentInline",
}
TYPE_LABELS = {
    "coreProperties": "FRBRLevel",
    "modificationType": "Modification",
    "judicialArgumentType": "JudicialArgument",
    "periodType": "Period",
    "subFlowStructure": "SubFlow",
}
ATTRIBUTE_LABELS = {
    "ContentElement": (
        ("corereq", "coreopt", "corereqreq"),
        "An element of a document's content, which has the core attributes all such elements have: its "
        "identifiers (eId, wId and GUID), the elements of the references section it refers to (refersTo), the time "
        "interval it is in force or in efficacy (period), its status, its language and the element it is an "
        "alternative to.",
    ),
}
UNION_LABELS = {
    "Agent": (
        ("TLCPerson", "TLCOrganization"),
        "An agent: a person or an organization of the references section, which the attributes typed agentRef, "
        "e.g. by, source, to and empoweredBy, refer to.",
        "Simple_Type_agentRef",
    ),
    "RefItem": (
        ("TLC", "DocRef"),
        "An entry of the references section: a top-level class of the Akoma Ntoso ontology (a TLC), or a reference "
        "to another document (a DocRef). It is what the refersTo attribute of an element points at, and what the "
        "references element contains.",
        "Complex_Type_refItems",
    ),
}

# The simple types of the attributes that refer to other elements by `#` and an eId, and the nodes they refer to.
# References by eIdRef or wIdRef may point at any element, and stay properties only.
REFERENCE_TYPES = {
    "agentRef": ("Agent",),
    "roleRef": ("TLCRole",),
    "conceptRef": ("TLCConcept",),
    "referenceRef": ("RefItem",),
    "eventRefRef": ("EventRef",),
    "temporalGroupRef": ("TemporalGroup",),
    "voteRef": ("Quorum", "Count"),
}
# Attributes of the general anyURI type that the specification says refer to a particular element.
HREFS = {
    ("noteRef", "href"): ("Note",),
    ("FRBRauthor", "href"): ("Agent",),
}
REL_NAMES = {"href": "LINKS_TO"}

# Attribute groups left out: HTML presentation attributes, and the hook for attributes of other namespaces.
SKIPPED_GROUPS = ("HTMLattrs", "core")
SKIPPED_ATTRIBUTES = ("xml:space", "xml:id")


def words(text):
    """The words of a camelCase name, keeping acronyms whole, e.g. FRBRWork → FRBR, Work; FRBRthis → FRBR, this;
    TLCPerson → TLC, Person; eventRef → event, Ref."""
    return re.findall(r"FRBR|[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z\d]+|[A-Z]+|\d+", text)


def label(name):
    """The label of an element, e.g. eventRef → EventRef, FRBRauthor → FRBRAuthor."""
    return "".join(w[0].upper() + w[1:] for w in words(name))


def camel(name):
    if name == "xml:lang":
        return "lang"
    ws = words(name)
    return ws[0].lower() + "".join(w[0].upper() + w[1:] for w in ws[1:])


def snake(name):
    return "_".join(w.upper() for w in words(name))


def spaced(name):
    return " ".join(w if w.isupper() and len(w) > 1 else w.lower() for w in words(name))


def tidy(text):
    return re.sub(r"\s+", " ", text or "").strip()


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


def listed(names):
    return ", ".join(names[:-1]) + f" and {names[-1]}" if len(names) > 1 else "".join(names)


def page(kind, name):
    """The specification's page for a declaration, e.g. Element act or Attribute_Group corereq."""
    return f"{DOCS}{kind}_{name}.html"


#----------------------------------
#   Reading the schema
#----------------------------------


class Schema:
    """The Akoma Ntoso schema's elements, types and groups, and what each element declares."""

    def __init__(self, text):
        self.root = ET.fromstring(text)
        self.elements, self.types, self.simple, self.groups, self.attribute_groups = {}, {}, {}, {}, {}
        for child in self.root:
            table = {
                XS + "element": self.elements,
                XS + "complexType": self.types,
                XS + "simpleType": self.simple,
                XS + "group": self.groups,
                XS + "attributeGroup": self.attribute_groups,
            }.get(child.tag)
            if table is not None:
                table[child.get("name")] = child

    @staticmethod
    def doc(node):
        """The comment of a declaration's documentation, which the schema writes as type, name and comment."""
        if node is None:
            return ""
        documentation = node.find(f"{XS}annotation/{XS}documentation")
        if documentation is None:
            return ""
        comment = documentation.find(AKN + "comment")
        return tidy(comment.text if comment is not None else documentation.text)

    def type_of(self, name):
        element = self.elements[name]
        return self.types[element.get("type")] if element.get("type") else element.find(XS + "complexType")

    def bases(self, name):
        """The named complex types an element's type is or extends, nearest first."""
        out, ctype = [], self.type_of(name)
        if self.elements[name].get("type"):
            out.append(self.elements[name].get("type"))
        while ctype is not None:
            extension = next((e for e in ctype.iter(XS + "extension")), None)
            if extension is None or extension.get("base") not in self.types:
                break
            out.append(extension.get("base"))
            ctype = self.types[extension.get("base")]
        return out

    def documentation(self, name):
        """The documentation of an element, else of the type it is declared with."""
        own = self.doc(self.elements[name])
        if own:
            return own
        return self.doc(self.types.get(self.elements[name].get("type")))

    def particles(self, name, labelled):
        """What an element's type contains, in order: ("element", name, lower, upper) for each element, and
        ("group", name, lower, upper) for each group in `labelled`, whose elements carry a label of their own. Other
        groups are expanded. An upper of None means unbounded; a choice makes each of its members optional."""
        out = []

        def walk(node, optional, many):
            for child in node:
                tag = child.tag[len(XS):]
                if tag in ("complexContent", "simpleContent"):
                    walk(child, optional, many)
                elif tag == "extension":
                    if child.get("base") in self.types:
                        walk(self.types[child.get("base")], optional, many)
                    walk(child, optional, many)
                elif tag in ("sequence", "choice"):
                    walk(
                        child,
                        optional or tag == "choice" or child.get("minOccurs") == "0",
                        many or child.get("maxOccurs") == "unbounded",
                    )
                elif tag == "group":
                    group = self.groups[child.get("ref")]
                    if child.get("ref") in labelled:
                        top = next(iter(group))  # the group's choice or sequence
                        lower = 0 if optional or child.get("minOccurs") == "0" or top.get("minOccurs") == "0" else 1
                        unbounded = many or "unbounded" in (child.get("maxOccurs"), top.get("maxOccurs"))
                        out.append(("group", child.get("ref"), lower, None if unbounded else 1))
                    else:
                        walk(
                            group,
                            optional or child.get("minOccurs") == "0",
                            many or child.get("maxOccurs") == "unbounded",
                        )
                elif tag == "element":
                    lower = 0 if optional else int(child.get("minOccurs", "1"))
                    upper = None if many or child.get("maxOccurs") == "unbounded" else int(child.get("maxOccurs", "1"))
                    out.append(("element", child.get("ref"), lower, upper))

        walk(self.type_of(name), False, False)
        return out

    def group_members(self, group):
        """Every element of a group, through the groups it refers to."""
        out = []
        for child in self.groups[group].iter():
            if child.tag == XS + "element":
                out.append(child.get("ref"))
            elif child.tag == XS + "group" and child.get("ref"):
                out += self.group_members(child.get("ref"))
        return list(dict.fromkeys(out))

    def attributes(self, name):
        """The attributes of an element: (attribute, the attribute group declaring it or None, required)."""
        out = []

        def walk(node, group):
            for child in node:
                tag = child.tag[len(XS):]
                if tag in ("complexContent", "simpleContent"):
                    walk(child, group)
                elif tag == "extension":
                    if child.get("base") in self.types:
                        walk(self.types[child.get("base")], group)
                    walk(child, group)
                elif tag == "attributeGroup":
                    ref = child.get("ref")
                    if ref not in SKIPPED_GROUPS:
                        walk(self.attribute_groups[ref], ref)
                elif tag == "attribute":
                    if (child.get("name") or child.get("ref")) not in SKIPPED_ATTRIBUTES:
                        out.append((child, group, child.get("use") == "required"))

        walk(self.type_of(name), None)
        names = [a.get("name") or a.get("ref") for a, _, _ in out]
        if len(names) != len(set(names)):
            sys.exit(f"{name} declares an attribute twice: {names}")
        return out

    def attribute_groups_of(self, name):
        """Every attribute group an element's type uses, directly or through other groups and base types."""
        out = set()

        def walk(node):
            for child in node.iter():
                if child.tag == XS + "attributeGroup" and child.get("ref") and child.get("ref") not in out:
                    out.add(child.get("ref"))
                    walk(self.attribute_groups[child.get("ref")])
                elif child.tag == XS + "extension" and child.get("base") in self.types:
                    walk(self.types[child.get("base")])

        walk(self.type_of(name))
        return out

    def datatype(self, attribute):
        """(Neo4j type, enumeration values, simple type name, whether it is a list) of an attribute."""
        name = attribute.get("type")
        if attribute.get("ref") == "xml:lang":
            return "STRING", [], "xml:lang", False
        if name is None:  # an anonymous type: a list of references, or a union of a date and a dateTime
            simple = attribute.find(XS + "simpleType")
            inner = simple.find(f"{XS}list/{XS}simpleType/{XS}restriction")
            if inner is not None:
                return "STRING", [], inner.get("base"), True
            if simple.find(XS + "union") is not None:
                return "STRING", [], simple.find(XS + "union").get("memberTypes"), False
            sys.exit(f"unmapped anonymous type of {attribute.get('name')}")
        if name.startswith("xsd:"):
            return XSD_TYPES[name[4:]], [], name, False
        restriction = self.simple[name].find(XS + "restriction")
        values = [e.get("value") for e in restriction.findall(XS + "enumeration")]
        return "STRING", values, name, False


def read_schema(path):
    if path:
        return Path(path).read_bytes()
    with urllib.request.urlopen(urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})) as r:
        return r.read()


#----------------------------------
#   The model
#----------------------------------


def build(text):
    schema = Schema(text)
    area_of = {name: area for area, names in AREAS.items() for name in names}
    for name in list(area_of) + list(VALUES):
        if name not in schema.elements:
            sys.exit(f"the schema has no element {name}")
    kept = set(area_of)

    # The labels, their members and where they come from.
    members, label_ref, label_doc = {}, {}, {}
    for group, name in GROUP_LABELS.items():
        members[name] = {e for e in schema.group_members(group) if e in kept}
        label_ref[name] = page("Element_Group", group)
        label_doc[name] = Schema.doc(schema.groups[group])
    for ctype, name in TYPE_LABELS.items():
        members[name] = {e for e in kept if ctype in schema.bases(e)}
        label_ref[name] = page("Complex_Type", ctype)
        label_doc[name] = Schema.doc(schema.types[ctype])
    for name, (groups, doc) in ATTRIBUTE_LABELS.items():
        members[name] = {e for e in kept if schema.attribute_groups_of(e) & set(groups)}
        label_ref[name] = page("Attribute_Group", groups[0])
        label_doc[name] = doc
    by_label = {label(e): {e} for e in kept}
    for name, (parts, doc, ref) in UNION_LABELS.items():
        members[name] = set().union(*(members.get(p) or by_label[p] for p in parts))
        label_ref[name], label_doc[name] = f"{DOCS}{ref}.html", doc
    for name, elements in members.items():
        if len(elements) < 2:
            sys.exit(f"label {name} has fewer than two elements")

    def parents(elements, exclude=None):
        """The smallest labels whose elements include all of these."""
        holders = [n for n, m in members.items() if n != exclude and elements <= m and m != elements]
        return sorted(n for n in holders if not any(members[o] < members[n] for o in holders))

    implied = {name: parents(m, name) for name, m in members.items()}
    for element in kept:
        implied[label(element)] = parents({element})
    depth = {}

    def depth_of(name):
        if name not in depth:
            depth[name] = 1 + max((depth_of(p) for p in implied[name]), default=-1)
        return depth[name]

    for name in implied:
        depth_of(name)

    def area_of_label(name):
        """The area most of a label's elements are in."""
        areas = [area_of[e] for e in members[name]]
        return max(AREAS, key=areas.count)

    # What each element contains, as (target label, lower, upper, the elements left out it is reached through).
    labelled = set(GROUP_LABELS)

    def reached(name, seen):
        """The nodes reached through an element left out. The elements of a labelled group that are left out, e.g.
        the presentational inlines b and i, aren't followed: their content is the group's content again."""
        out = []
        for kind, ref, _, _ in schema.particles(name, labelled):
            out += reach(kind, ref, seen)
        return out

    def reach(kind, ref, seen):
        if kind == "group":
            return [GROUP_LABELS[ref]]
        if ref in kept:
            return [label(ref)]
        if ref in VALUES or ref in seen:
            return []
        seen.add(ref)
        return reached(ref, seen)

    # Through the text structure that is left out, e.g. paragraphs, lists, tables and generic blocks, only the inline
    # elements are followed: the structural elements a generic block may hold, e.g. an intro in a blockContainer,
    # aren't related to the element above it.
    inlines = {"InlineElement"} | {label(e) for e in members["InlineElement"]}
    inlines |= {n for n in members if members[n] <= members["InlineElement"]}

    def contents(name):
        out = {}

        def add(target, lower, upper, through):
            if target in out:
                l0, u0, t0 = out[target]
                out[target] = (min(l0, lower), None, t0 | through)
            else:
                out[target] = (lower, upper, set(through))

        for kind, ref, lower, upper in schema.particles(name, labelled):
            if kind == "group":
                add(GROUP_LABELS[ref], lower, upper, set())
            elif ref in kept:
                add(label(ref), lower, upper, set())
            elif ref not in VALUES:
                for target in reached(ref, {ref}):
                    if target in inlines:
                        add(target, 0, None, {ref})
        # A label's elements reached one by one, each of them, are the label.
        for name_, elements in sorted(members.items(), key=lambda m: -len(m[1])):
            targets = {label(e) for e in elements}
            if name_ not in out and targets <= out.keys():
                lower = 0
                upper = None if any(out[t][1] != 1 for t in targets) or len(targets) > 1 else 1
                through = set().union(*(out[t][2] for t in targets))
                for t in targets:
                    del out[t]
                out[name_] = (lower, upper, through)
        return out

    # Each element: its properties and the relationships its attributes and contents give it.
    nodes, props, rels = {}, {}, {}
    for element in sorted(kept, key=label):
        name = label(element)
        own, links = {}, {}
        for attribute, group, required in schema.attributes(element):
            attr = attribute.get("name") or attribute.get("ref")
            neo4j, values, simple, many = schema.datatype(attribute)
            ref = page("Attribute_Group", group) if group else page("Element", element)
            doc = Schema.doc(attribute) or Schema.doc(schema.attribute_groups.get(group))
            targets = REFERENCE_TYPES.get(simple, ()) or HREFS.get((element, attr), ())
            own[camel(attr)] = {
                "type": f"LIST<{neo4j}>" if many else neo4j,
                "doc": doc,
                "reference": ref,
                "required": required,
                "one_of": values,
                "custom": {"xsdAttribute": attr, "xsdType": simple, "attributeGroup": group},
                "refersTo": targets,
            }
            for target in targets:
                rtype = REL_NAMES.get(attr, snake(attr))
                links[(rtype, target)] = {
                    "lower": 1 if required else 0,
                    "upper": None if many else 1,
                    "composition": False,
                    "attribute": attr,
                    "simple": simple,
                    "doc": doc,
                    "reference": ref,
                    "union": len(targets),
                }
        for kind, ref, lower, upper in schema.particles(element, labelled):
            if kind != "element" or ref not in VALUES:
                continue
            main, extra = VALUES[ref]
            value_attrs = {(a.get("name")): a for a, _, _ in schema.attributes(ref)}
            for attr in ([main] if main else [None]) + list(extra):
                pid = camel(ref) if attr == main else camel(ref + attr[0].upper() + attr[1:])
                if attr is None:
                    neo4j, simple = "STRING", "mixed text"
                    doc = Schema.documentation(schema, ref)
                else:
                    neo4j, _, simple, _ = schema.datatype(value_attrs[attr])
                    doc = Schema.documentation(schema, ref) if attr == main else (
                        f"The {attr} of the {ref}: " + Schema.doc(schema.attribute_groups.get(attr))
                    )
                own[pid] = {
                    "type": neo4j if upper == 1 else f"LIST<{neo4j}>",
                    "doc": doc,
                    "reference": page("Element", ref),
                    "required": lower >= 1 and upper == 1,
                    "one_of": [],
                    "custom": {"xsdElement": ref, "xsdAttribute": attr, "xsdType": simple, "lower": lower,
                               "upper": upper},
                    "refersTo": (),
                }
        for target, (lower, upper, through) in contents(element).items():
            links[("HAS_" + snake(target), target)] = {
                "lower": lower,
                "upper": upper,
                "composition": True,
                "through": sorted(through),
                "reference": page("Element", element),
            }
        props[name], rels[name] = own, links
        nodes[name] = {"element": element, "area": area_of[element]}

    # What every element carrying a label has, it has through the label: each property and relationship all of a
    # label's elements have moves to the label, the most general labels first. Where the elements differ in whether
    # it is required, the label has it as optional, and the elements that require it keep their own.
    for name in sorted(members, key=lambda n: (depth[n], n)):
        leaves = sorted(label(e) for e in members[name])
        props[name], rels[name] = {}, {}
        for pid in list(props[leaves[0]]):
            versions = [props[leaf].get(pid) for leaf in leaves]
            if None in versions or any(not alike(v, versions[0], ("type", "one_of")) for v in versions):
                continue
            required = all(v["required"] for v in versions)
            matching = [v for v in versions if v["required"] == required]
            # The attribute groups declaring it may describe it differently, e.g. idreq and idopt: the most common.
            docs = [v["doc"] for v in matching]
            props[name][pid] = next(v for v in matching if v["doc"] == max(docs, key=docs.count))
            for leaf, v in zip(leaves, versions):
                if v["required"] == required:
                    del props[leaf][pid]
        for key in list(rels[leaves[0]]):
            versions = [rels[leaf].get(key) for leaf in leaves]
            if None in versions or any(not alike(v, versions[0], ("composition", "upper", "attribute")) for v in versions):
                continue
            lower = min(v["lower"] for v in versions)
            through = sorted(set().union(*(v.get("through", []) for v in versions)))
            rels[name][key] = {**next(v for v in versions if v["lower"] == lower), "through": through}
            for leaf, v in zip(leaves, versions):
                if v["lower"] == lower:
                    del rels[leaf][key]
        nodes[name] = {"label": True, "area": area_of_label(name)}

    return render(schema, nodes, props, rels, members, implied, label_ref, label_doc)


def alike(a, b, keys):
    return all(a.get(k) == b.get(k) for k in keys)


def render(schema, nodes, props, rels, members, implied, label_ref, label_doc):
    """The model, in the graph spec format."""
    out_nodes, out_rels = {}, {}
    for name in sorted(nodes):
        node = nodes[name]
        is_label = node.get("label", False)
        element = node.get("element")
        if is_label:
            carriers = sorted(label(e) for e in members[name])
            description = describe(
                sentence(label_doc[name]),
                f"A label carried by {listed(carriers)}.",
            )
            reference = label_ref[name]
        else:
            description = sentence(schema.documentation(element)) or f"The {element} element of an Akoma Ntoso document."
            reference = page("Element", element)
        properties = {
            "uri": {
                "type": "STRING",
                "name": "uri",
                "description": (
                    f"The identifier of the {name}: an IRI unique across documents. For a document, its "
                    "expression IRI, e.g. /akn/ke/act/2010-08-27/1/eng@; for an element within a document, the "
                    "document's IRI followed by # and the element's eId, or where it has none its wId, GUID or an "
                    "identifier the loader assigns."
                    if name != "Document" and name not in [label(e) for e in members["Document"]]
                    else f"The identifier of the {name}: its FRBR Expression IRI, e.g. /akn/ke/act/2010-08-27/1/eng@, "
                    "unique across documents."
                ),
                "reference": NAMING,
            }
        }
        constraints = {f"key_{name}": {"type": "KEY", "properties": ["uri"], "name": f"uri_{name}_key"}}
        for pid, p in props[name].items():
            refs = [r for r in p["refersTo"]]
            properties[pid] = {
                "type": p["type"],
                "name": pid,
                "description": describe(
                    sentence(p["doc"]) or f"The {pid} of the {name}.",
                    f"Resolved to the {listed(refs)} it identifies by the {spaced(pid)} relationship."
                    if refs
                    else "",
                    f"One of {listed([f'`{v}`' for v in p['one_of']])}." if p["one_of"] and len(p["one_of"]) <= 12 else "",
                ),
                "reference": p["reference"],
                "extensions": {"custom": {k: v for k, v in p["custom"].items() if v is not None}},
            }
            if p["one_of"]:
                properties[pid]["one_of"] = p["one_of"]
            if p["required"]:
                constraints[f"exists_{name}_{pid}"] = {
                    "type": "EXISTS",
                    "properties": [pid],
                    "name": f"{pid}_{name}_exists",
                }
        out_nodes[name] = {
            "labels": {"identifier": name, **({"implied": implied[name]} if implied[name] else {})},
            "description": description,
            "reference": reference,
            "properties": properties,
            "constraints": constraints,
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (
                        ("area", node["area"]),
                        ("xsdElement", element),
                        ("xsdType", schema.elements[element].get("type") if element else None),
                        ("abstract", True if is_label else None),
                    )
                    if v is not None
                }
            },
        }

        for (rtype, target), r in sorted(rels[name].items()):
            rid = f"{name}_{rtype}_{target}"
            if r["composition"]:
                through = r.get("through", [])
                description = describe(
                    f"Each {name} contains {phrase(r['lower'], r['upper'])} {target}"
                    + (f", within {listed(through[:4])}{' and others' if len(through) > 4 else ''}, which "
                       f"aren't nodes." if through else "."),
                    f"A composition: each {target} is part of at most one owner.",
                )
                to = {"node": target, "max_count": 1}
                custom = {"composition": True, "lower": r["lower"], **({"upper": r["upper"]} if r["upper"] is not None else {}),
                          **({"through": through} if through else {})}
            else:
                description = describe(
                    sentence(r["doc"]),
                    f"Resolves the {r['attribute']} attribute of the {name}, # followed by an eId, to the "
                    f"{target} it identifies.",
                    f"Each {name} refers to {phrase(r['lower'], r['upper'])} {target}"
                    + (f", or to one of the {r['union'] - 1} other kinds of element the attribute allows." if r["union"] > 1 else "."),
                )
                to = {"node": target}
                custom = {"composition": False, "xsdAttribute": r["attribute"], "xsdType": r["simple"]}
            out_rels[rid] = {
                "type": rtype,
                "from": {"node": name, **ends(r["lower"], r["upper"])},
                "to": to,
                "description": description,
                "reference": r["reference"],
                "extensions": {"custom": custom},
            }

    for rel in out_rels.values():
        for end in (rel["from"], rel["to"]):
            if end["node"] not in out_nodes:
                sys.exit(f"relationship {rel['type']} points at {end['node']}, which is not a node")
    return {
        "schema": SCHEMA,
        "version": "1.0",
        "id": "akoma-ntoso-1.0",
        "name": "Akoma Ntoso 1.0",
        "description": (
            "Akoma Ntoso Version 1.0 (OASIS LegalDocML), the OASIS Standard of 29 August 2018 for the XML "
            "representation of parliamentary, legislative and judiciary documents: acts, bills, amendments, debates, "
            "judgments, official gazettes and other documents, their structure down to articles and paragraphs, their "
            "FRBR identification, lifecycle, workflow and analysis metadata, and the people, organizations, concepts "
            "and other documents their text refers to. Generated from the Akoma Ntoso 3.0 XML schema "
            "(akomantoso30.xsd): each legal element is a node, each attribute and each value element a property, each "
            "element contained and each attribute referring to another element by its eId a relationship, and each "
            "element group a label its elements also carry."
        ),
        "nodes": out_nodes,
        "relationships": out_rels,
    }


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
    model = build(read_schema(sys.argv[1] if len(sys.argv) > 1 else None))
    out = Path(__file__).parent
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(yaml(model) + "\n")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships")


if __name__ == "__main__":
    main()
