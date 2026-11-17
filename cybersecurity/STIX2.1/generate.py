#!/usr/bin/env python3
"""Generates the STIX 2.1 ontology from the OASIS STIX 2.1 JSON schemas, the OASIS STIX validator's relationship
table and the STIX 2.1 specification.

Usage: python3 generate.py [SCHEMAS [VALIDATOR [SPECIFICATION]]]

SCHEMAS is the cti-stix2-json-schemas repository: an archive, a clone or its schemas directory. VALIDATOR is the
cti-stix-validator repository: an archive, a clone or its stix2validator/v21/enums.py. SPECIFICATION is the STIX 2.1
OASIS Standard as HTML. Each one left out is downloaded. Writes model.json and model.yaml next to this script. Uses
only the Python standard library.
"""

import ast
import html
import json
import posixpath
import re
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

SCHEMAS_COMMIT = "9af1db41b7b86c06324f899649ae83480134f66e"
SCHEMAS_URL = f"https://github.com/oasis-open/cti-stix2-json-schemas/archive/{SCHEMAS_COMMIT}.zip"
SCHEMAS_PAGE = f"https://github.com/oasis-open/cti-stix2-json-schemas/blob/{SCHEMAS_COMMIT}/schemas"
VALIDATOR_URL = "https://github.com/oasis-open/cti-stix-validator/archive/refs/tags/v3.3.2.zip"
SPEC_URL = "https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html"
SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
MAX_DESCRIPTION = 1024

# The schema files of the objects that become nodes, by category. A bundle is a container, not an object, and a
# relationship object becomes a relationship.
CATEGORIES = {"sdos": "SDO", "observables": "SCO", "sros": "SRO", "common": "Meta"}
META = ("marking-definition", "language-content", "extension-definition")

# The labels every SDO and every SCO also carries: they stand for "any SDO" and "any SCO" where a reference allows
# one, and hold the common references and relationships declared once for all of them.
UMBRELLAS = {
    "SDO": ("StixDomainObject", "Any STIX Domain Object (SDO): a higher-level intelligence object, such as an Attack "
            "Pattern, Malware or Threat Actor. Every SDO node also carries this label."),
    "SCO": ("StixCyberObservableObject", "Any STIX Cyber-observable Object (SCO): a fact observed on a system or "
            "network, such as a File, Process or IPv4 Address. Every SCO node also carries this label."),
}

# The structured types that have no Neo4j property type, by schema file or definition. They are kept as JSON text.
STRUCTURED = {
    "hashes-type": "hashes",
    "dictionary": "dictionary",
    "external-reference": "external-reference",
    "kill-chain-phase": "kill-chain-phase",
    "granular-marking": "granular-marking",
    "extension": "extension",
}

# The references whose targets neither the validator nor the schema patterns name, from the specification's tables of
# embedded relationships: (object type or None for any, property) → target types.
SPEC_TARGETS = {
    (None, "created_by_ref"): ["identity"],
    (None, "object_marking_refs"): ["marking-definition"],
    ("malware", "sample_refs"): ["file", "artifact"],
    ("file", "contains_refs"): ["<SCO>"],
    ("malware-analysis", "analysis_sco_refs"): ["<SCO>"],
    ("grouping", "object_refs"): ["<SDO>", "<SCO>", "sighting", "relationship"],
    ("note", "object_refs"): ["<SDO>", "<SCO>", "sighting", "relationship"],
    ("opinion", "object_refs"): ["<SDO>", "<SCO>", "sighting", "relationship"],
    ("report", "object_refs"): ["<SDO>", "<SCO>", "sighting", "relationship"],
    ("sighting", "sighting_of_ref"): ["<SDO>"],
    # The schema's pattern leaves out artifact, which the specification allows: "SCO or SRO".
    ("observed-data", "object_refs"): ["<SCO>", "sighting", "relationship"],
}

# The specification's names for the open vocabularies whose validator constants are abbreviated.
VOCABULARY_NAMES = {"hash-algo-ov": "hash-algorithm-ov"}

# The SRO properties that the relationship's type and ends stand for, so the graph relationship doesn't repeat them.
SRO_ENDS = ("type", "relationship_type", "source_ref", "target_ref")


def words(text):
    return re.findall(r"[A-Za-z0-9]+", text)


def pascal(stix_type):
    """A STIX type as a label, e.g. attack-pattern → AttackPattern, ipv4-addr → Ipv4Addr."""
    return "".join(w[0].upper() + w[1:] for w in words(stix_type))


def upper(name):
    """A STIX name as a relationship type, e.g. created_by_ref → CREATED_BY_REF, attributed-to → ATTRIBUTED_TO."""
    return "_".join(w.upper() for w in words(name))


def tidy(text):
    return re.sub(r"\s+", " ", text.replace("​", "").replace("\xa0", " ")).strip()


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


def a(name):
    return "an" if name[0].lower() in "aeio" else "a"


#----------------------------------
#   Reading the sources
#----------------------------------


def download(url, name):
    path = Path(tempfile.mkdtemp()) / name
    # GitHub and OASIS reject some user agents.
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request) as response:
        path.write_bytes(response.read())
    return path


def read_schemas(source):
    """Every schema, keyed by its path below schemas/, e.g. sdos/malware.json."""
    if source.is_dir():
        root = source if (source / "common").is_dir() else next(d for d in source.rglob("schemas") if d.is_dir())
        return {p.relative_to(root).as_posix(): json.loads(p.read_text()) for p in sorted(root.rglob("*.json"))}
    schemas = {}
    with zipfile.ZipFile(source) as archive:
        for name in sorted(archive.namelist()):
            match = re.search(r"/schemas/((?:common|sdos|sros|observables)/[^/]+\.json)$", name)
            if match:
                schemas[match.group(1)] = json.loads(archive.read(name))
    return schemas


def read_enums(source):
    """The lists and tables of the validator's stix2validator/v21/enums.py, read without running it."""
    if source.is_dir():
        text = next(source.rglob("v21/enums.py")).read_text()
    elif source.suffix == ".py":
        text = source.read_text()
    else:
        with zipfile.ZipFile(source) as archive:
            text = archive.read(next(n for n in archive.namelist() if n.endswith("v21/enums.py"))).decode()
    return {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in ast.parse(text).body
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
    }


def cell_text(fragment):
    return tidy(html.unescape(re.sub(r"<[^>]+>", "", fragment)))


def read_spec(source):
    """The specification's section anchors, by normalised heading, and the rows of its relationship tables."""
    text = source.read_bytes().decode("windows-1252", errors="replace")
    headings = []
    for match in re.finditer(r"<h([1-4])[^>]*>(.*?)</h\1>", text, re.S):
        anchor = re.search(r'name="(_[^"]+)"', match.group(0))
        title = cell_text(match.group(2))
        number = re.match(r"([\d.]+)\s+(.*)", title)
        if anchor and number:
            headings.append((match.start(), number.group(1), number.group(2), anchor.group(1)))
    anchors, relationships = {}, {}
    for (start, number, title, anchor), following in zip(headings, headings[1:] + [(len(text), "", "", "")]):
        anchors.setdefault(normalise(title), (number, anchor))
        if title != "Relationships":
            continue
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", text[start : following[0]], re.S):
            cells = [cell_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
            if len(cells) != 4 or cells[0] in ("Source", "—"):
                continue
            sources, types, targets = ([t.strip() for t in c.split(",")] for c in cells[:3])
            for source_type in sources:
                for relationship_type in types:
                    relationships.setdefault((source_type, relationship_type), []).append(
                        (targets, cells[3], len(sources) == 1, number.rsplit(".", 1)[0])
                    )
    # The section of an object holds its Relationships subsection, if it has one.
    sections = {}
    for _, number, title, anchor in headings:
        if title == "Relationships":
            sections[number.rsplit(".", 1)[0]] = anchor
    return anchors, sections, relationships


def normalise(title):
    """A heading or STIX type, comparable, e.g. 'Autonomous System (AS) Object' and autonomous-system."""
    title = re.sub(r"\([^)]*\)|\bObject$", "", title).replace("addr", "address")
    return re.sub(r"[^a-z0-9]", "", title.lower()).replace("addressess", "address")


#----------------------------------
#   Reading the schemas
#----------------------------------


class Schemas:
    """The schemas, with their $refs resolved and the properties of an object collected from all its parts."""

    def __init__(self, schemas):
        self.schemas = schemas

    def resolve(self, ref, file):
        """The (file, schema) a $ref points at, e.g. ../common/core.json from sdos/malware.json."""
        path, _, pointer = ref.partition("#")
        target = posixpath.normpath(posixpath.join(posixpath.dirname(file), path)) if path else file
        schema = self.schemas[target]
        for part in [p for p in pointer.split("/") if p]:
            schema = schema[part]
        return target, schema

    def collect(self, schema, file, conditional=False):
        """The properties of an object: name → [(schema, file, conditional)], and the names it requires.

        A part is conditional when it is one branch of a oneOf or anyOf; a property is required when the object
        requires it outright, or every branch of a oneOf or anyOf does.
        """
        props, required = {}, set(schema.get("required", []))
        if "$ref" in schema:
            p, r = self.collect(*reversed(self.resolve(schema["$ref"], file)), conditional)
            merge(props, p)
            required |= r
        for name, prop in schema.get("properties", {}).items():
            props.setdefault(name, []).append((prop, file, conditional))
        for part in schema.get("allOf", []):
            p, r = self.collect(part, file, conditional)
            merge(props, p)
            required |= r
        for key in ("oneOf", "anyOf"):
            if key in schema:
                branches = [self.collect(b, file, True) for b in schema[key]]
                for p, _ in branches:
                    merge(props, p)
                required |= set.intersection(*(r for _, r in branches))
        return props, required

    def type_of(self, schema, file):
        """(Neo4j type, STIX type as text, pattern, enumerated values) of a property schema, or None if it has none."""
        if "$ref" in schema:
            target, sub = self.resolve(schema["$ref"], file)
            name = schema["$ref"].rsplit("/", 1)[-1].removesuffix(".json")
            if name in STRUCTURED:
                return "STRING", STRUCTURED[name], None, None
            if name == "timestamp":
                return "ZONED DATETIME", "timestamp", None, None
            if name in ("identifier", "hex", "binary"):
                return "STRING", name, sub.get("pattern") if name != "identifier" else None, None
            if name == "url-regex":
                return "STRING", "url", None, None
            found = self.type_of(sub, target)
            if found and found[1] == "dictionary":
                return "STRING", name, None, None  # a named structured type, e.g. windows-pe-optional-header-type
            return found
        for part in schema.get("allOf", []):
            found = self.type_of(part, file)
            if found:
                return found
        kind = schema.get("type")
        if kind == "array":
            item = self.type_of(schema.get("items", {}), file) or ("STRING", "string", None, None)
            if item[0].startswith("LIST") or item[1] not in ("string", "integer", "number", "boolean", "timestamp",
                                                             "identifier", "hex", "binary", "url"):
                return "STRING", f"list of {item[1]}", None, None
            return f"LIST<{item[0]}>", f"list of {item[1]}", None, item[3]
        if kind == "object":
            return "STRING", "dictionary", None, None
        scalar = {"string": "STRING", "integer": "INTEGER", "number": "FLOAT", "boolean": "BOOLEAN"}.get(kind)
        if scalar:
            return scalar, kind, schema.get("pattern"), schema.get("enum")
        return None


def merge(into, props):
    for name, occurrences in props.items():
        into.setdefault(name, []).extend(occurrences)


def patterns(schema, negated=False):
    """The (pattern, negated) pairs a reference schema restricts its identifiers with, nested parts included."""
    out = []
    if isinstance(schema, dict):
        if "pattern" in schema:
            out.append((schema["pattern"], negated))
        for key, value in schema.items():
            if key in ("items", "allOf", "anyOf", "oneOf", "not"):
                for part in value if isinstance(value, list) else [value]:
                    out += patterns(part, negated or key == "not")
    return out


def types_in(pattern):
    """The STIX types an identifier pattern names, e.g. ^(identity|location)-- → identity, location."""
    match = re.match(r"^\^\(?([a-z0-9|\-]+?)\)?(?:--)?(?:\.\+\$|\$)?$", pattern.replace("--|", "|").replace("--)", ")"))
    return match.group(1).replace("--", "").split("|") if match else []


#----------------------------------
#   The STIX model as data
#----------------------------------


def build(schemas, enums, spec):
    anchors, sections, spec_relationships = spec
    schemas = Schemas(schemas)

    objects = {}  # STIX type → (category, file)
    for file in schemas.schemas:
        folder, name = file.split("/")[0], file.split("/")[1].removesuffix(".json")
        if folder in ("sdos", "observables") or name == "sighting" or name in META:
            objects[name] = (CATEGORIES[folder], file)
    by_category = {c: sorted(t for t, (cat, _) in objects.items() if cat == c) for c in CATEGORIES.values()}
    if sorted(enums["TYPES"]) != sorted(set(by_category["SDO"]) | {"bundle", "relationship", "sighting", *META}):
        sys.exit("the validator and the schemas list different STIX object types")
    if sorted(enums["OBSERVABLE_TYPES"]) != by_category["SCO"]:
        sys.exit("the validator and the schemas list different observable types")

    def label(stix_type):
        return UMBRELLAS[stix_type[1:4]][0] if stix_type.startswith("<") else pascal(stix_type)

    def section(stix_type):
        """(number, anchor) of the specification section of an object type, e.g. 4.11 for malware."""
        found = anchors.get(normalise(stix_type))
        if not found:
            sys.exit(f"no section of the specification describes {stix_type}")
        return found

    def link(anchor):
        return f"{SPEC_URL}#{anchor}"

    common_section = anchors[normalise("Common Properties")][1]
    common_relationships = anchors[normalise("Common Relationships")][1]

    # The open vocabularies the validator lists, by the object type and property that use them.
    vocabularies = {}
    for constant, uses in enums.items():
        if constant.endswith("_USES") and isinstance(uses, dict) and constant[:-5] + "_OV" in enums:
            for stix_type, props in uses.items():
                for prop in props:
                    vocabularies[(stix_type, prop)] = (constant[:-5].lower().replace("_", "-") + "-ov",
                                                       enums[constant[:-5] + "_OV"])

    def property_of(stix_type, name, occurrences, required, reference):
        """A property of a node or relationship, from every place the schemas declare it."""
        unconditional = [o for o in occurrences if not o[2]] or occurrences
        typed = [schemas.type_of(schema, file) for schema, file, _ in unconditional]
        typed = [t for t in typed if t] or [t for t in (schemas.type_of(s, f) for s, f, _ in occurrences) if t]
        if not typed:
            sys.exit(f"{stix_type}.{name} has no type")
        neo4j, stix, pattern, _ = typed[0]
        if all(o[2] for o in occurrences):  # declared only in branches of a oneOf or anyOf
            pattern = None
            stix = "identifier" if name == "id" else " or ".join(sorted({t[1] for t in typed}))
        enums_seen = [t[3] for t in typed]
        one_of = sorted({v for e in enums_seen for v in e}) if all(enums_seen) and neo4j == "STRING" else []
        texts = [s.get("description", "") for s, _, c in occurrences if s.get("description") and not c]
        texts = texts or [s.get("description", "") for s, _, c in occurrences if s.get("description")]
        text = texts[-1] if texts else ""
        if name == "id" and all(o[2] for o in occurrences):  # e.g. marking-definition, whose id only its TLP branch describes
            text = schemas.schemas["common/core.json"]["properties"]["id"]["description"]
        vocabulary = vocabularies.get((stix_type, name))
        named = re.search(r"[Oo]pen [Vv]ocab(?:ulary)?\s*-\s*([a-z0-9-]+)", text)
        if named and vocabulary and named.group(1).endswith("-ov"):
            vocabulary = (named.group(1), vocabulary[1])
        if vocabulary:
            vocabulary = (VOCABULARY_NAMES.get(vocabulary[0], vocabulary[0]), vocabulary[1])
        bounds = [(k, s[k]) for s, _, _ in unconditional for k in ("minimum", "maximum") if k in s]
        if name == "id":
            pattern = schemas.schemas["common/identifier.json"]["pattern"].replace(
                "^[a-z][a-z0-9-]+[a-z0-9]--", f"^{stix_type}--"
            )
        deprecated = name in enums.get("DEPRECATED_PROPERTIES", {}).get(stix_type, [])
        prop = {
            "type": neo4j,
            "name": name,
            "description": describe(
                sentence(re.sub(r"\s*[Oo]pen [Vv]ocab(?:ulary)?\s*-\s*[a-z0-9-]+\.?", "", text)),
                "Required." if required else "",
                "Deprecated." if deprecated else "",
                " ".join(f"{'At least' if k == 'minimum' else 'At most'} {v}." for k, v in bounds),
                f"STIX type {stix}, as JSON text." if neo4j == "STRING" and stix not in (
                    "string", "identifier", "hex", "binary", "url") else "",
                f"Open vocabulary {vocabulary[0]}: {', '.join(vocabulary[1])}." if vocabulary else "",
            ),
            "reference": reference,
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (
                        ("stixType", stix),
                        ("required", required),
                        ("deprecated", deprecated),
                        ("openVocabulary", vocabulary[0] if vocabulary else None),
                        ("suggestedValues", vocabulary[1] if vocabulary else None),
                        *bounds,
                    )
                    if v not in (None, False)
                }
            },
        }
        if name == "type":
            prop["one_of"] = [stix_type]
        elif one_of:
            prop["one_of"] = one_of
        elif pattern:
            prop["pattern"] = pattern
        return prop

    def targets_of(stix_type, name, occurrences):
        """The STIX types a reference may point at: the validator's, else the schema's patterns, else the
        specification's. <SDO> and <SCO> stand for any of them."""
        refs = enums["OBSERVABLE_PROP_REFS"].get(stix_type, {})
        if isinstance(refs.get(name), list):
            return refs[name]
        for key in ((stix_type, name), (None, name)):
            if key in SPEC_TARGETS:
                return SPEC_TARGETS[key]
        found = [(t, neg) for schema, _, _ in occurrences for p, neg in patterns(schema) for t in types_in(p)]
        positive = [t for t, neg in found if not neg]
        if positive:
            return sorted(set(positive))
        negative = {t for t, neg in found if neg}
        if negative:
            every = ["<SDO>", "<SCO>", "sighting", "relationship", *META]
            return [t for t in every if t not in negative]
        sys.exit(f"{stix_type}.{name}: no target types")

    def collapse(types):
        """Target types with every SDO or every SCO replaced by its umbrella."""
        types = set(types)
        for category in ("SDO", "SCO"):
            if set(by_category[category]) <= types:
                types = (types - set(by_category[category])) | {f"<{category}>"}
        return sorted(types, key=lambda t: (not t.startswith("<"), t))

    nodes, relationships = {}, {}

    def relationship(from_type, rel_type, to_type, description, reference, counts=None, custom=None, props=None,
                     constraints=None):
        from_name, to_name = label(from_type), label(to_type)
        rid = f"{from_name}_{rel_type}_{to_name}"
        if rid in relationships:
            sys.exit(f"two relationships {rid}")
        relationships[rid] = {
            "type": rel_type,
            "from": {"node": from_name, **(counts or {})},
            "to": {"node": to_name},
            **({"properties": props} if props else {}),
            **({"constraints": constraints} if constraints else {}),
            "description": description,
            "reference": reference,
            "extensions": {"custom": {k: v for k, v in (custom or {}).items() if v not in (None, False, [], "")}},
        }

    def reference_relationships(stix_type, from_type, name, occurrences, required, reference, owner, custom=None):
        """One relationship per target type of a reference property, named after the property."""
        targets = targets_of(stix_type, name, occurrences)
        dropped = "relationship" in targets
        targets = collapse(t for t in targets if t != "relationship")
        many = name.endswith("_refs")
        texts = [s.get("description", "") for s, _, _ in occurrences if s.get("description")]
        if many:
            counts = {"min_count": 1} if required and len(targets) == 1 else None
        else:
            counts = {"count": 1} if required and len(targets) == 1 else {"max_count": 1}
        kinds = ", ".join(label(t) for t in targets)
        for target in targets:
            relationship(
                from_type,
                upper(name),
                target,
                describe(
                    sentence(texts[-1]) if texts else "",
                    f"The {name} property of {owner}, "
                    + ("a list of identifiers" if many else "an identifier")
                    + (f" of {kinds} objects." if len(targets) > 1 else f" of {a(kinds)} {kinds}.")
                    + (" Required." if required else ""),
                    "It may also name STIX relationship objects, which the graph holds as relationships, not nodes."
                    if dropped else "",
                ),
                reference,
                counts,
                {"property": name, "list": many, "required": required, "unionEnds": len(targets) > 1, **(custom or {})},
            )

    # The objects: one node each, with the common properties of core.json or cyber-observable-core.json folded in.
    common_refs = ("created_by_ref", "object_marking_refs")
    for stix_type, (category, file) in sorted(objects.items()):
        name = pascal(stix_type)
        schema = schemas.schemas[file]
        props, required = schemas.collect(schema, file)
        number, anchor = section(stix_type)
        reference = link(anchor)
        properties, constraints = {}, {}
        for prop, occurrences in props.items():
            if prop.endswith(("_ref", "_refs")):
                continue
            # A property from core.json or cyber-observable-core.json links to the common properties section.
            own = any(f == file for _, f, _ in occurrences)
            properties[prop] = property_of(stix_type, prop, occurrences, prop in required,
                                           reference if own else link(common_section))
            if prop in required and prop != "id":
                constraints[f"exists_{name}_{prop}"] = {"type": "EXISTS", "properties": [prop],
                                                        "name": f"{prop}_{name}_exists"}
        properties = {"id": properties.pop("id"), **properties}
        constraints = {f"key_{name}": {"type": "KEY", "properties": ["id"], "name": f"id_{name}_key"}, **constraints}
        nodes[name] = {
            "labels": {"identifier": name, **({"implied": [UMBRELLAS[category][0]]} if category in UMBRELLAS else {})},
            "description": describe(sentence(schema.get("description", ""))),
            "reference": reference,
            "properties": properties,
            "constraints": constraints,
            "extensions": {"custom": {"stixType": stix_type, "category": category, "section": number,
                                      "schema": f"{SCHEMAS_PAGE}/{file}"}},
        }
        for prop, occurrences in props.items():
            if not prop.endswith(("_ref", "_refs")):
                continue
            if category in UMBRELLAS and prop in common_refs and not any(f == file for _, f, _ in occurrences):
                continue  # drawn once, from the umbrella
            reference_relationships(stix_type, stix_type, prop, occurrences, prop in required, reference,
                                    f"{a(name)} {name}")

        # References inside the predefined extensions and embedded types, e.g. archive-ext's contains_refs.
        for path, prop, targets in nested(enums["OBSERVABLE_PROP_REFS"].get(stix_type, {}), []):
            where = path[-1]
            found = find_property(schema, prop, where) or find_property(schema, prop, "")
            for target in collapse(targets):
                relationship(
                    stix_type,
                    upper(prop),
                    target,
                    describe(
                        sentence(found.get("description", "")) if found else "",
                        f"The {prop} property of the {where} "
                        + ("extension" if path[0] == "extensions" else "entries")
                        + f" of {a(name)} {name}, "
                        + ("a list of identifiers" if prop.endswith("_refs") else "an identifier")
                        + f" of {a(label(target))} {label(target)}.",
                    ),
                    reference,
                    None if prop.endswith("_refs") else {"max_count": 1},
                    {"property": prop, "list": prop.endswith("_refs"), "embeddedIn": ".".join(path)},
                )

    # The umbrellas, and the common references every SDO or SCO has.
    for category, (name, text) in UMBRELLAS.items():
        nodes[name] = {
            "labels": {"identifier": name},
            "description": text,
            "reference": link(anchors[normalise("STIX Domain Objects" if category == "SDO"
                                                else "STIX Cyber-observable Objects")][1]),
            "properties": {
                "id": {
                    "type": "STRING",
                    "name": "id",
                    "description": f"The identifier of the {'SDO' if category == 'SDO' else 'SCO'}, e.g. "
                    + ("malware--31b940d4-6f7f-459a-80ea-9c1f17b5891b." if category == "SDO"
                       else "file--fb0419a8-f09c-57f8-be64-71a80417591c."),
                    "reference": link(anchors[normalise("Object IDs and References")][1]),
                    "pattern": schemas.schemas["common/identifier.json"]["pattern"],
                    "extensions": {"custom": {"stixType": "identifier", "required": True}},
                }
            },
            "constraints": {f"key_{name}": {"type": "KEY", "properties": ["id"], "name": f"id_{name}_key"}},
            "extensions": {"custom": {"category": category, "abstract": True}},
        }
        core = "common/core.json" if category == "SDO" else "common/cyber-observable-core.json"
        props, required = schemas.collect(schemas.schemas[core], core)
        for prop in common_refs:
            if prop in props:
                reference_relationships(f"<{category}>", f"<{category}>", prop, props[prop], prop in required,
                                        link(common_section), f"every {category}")

    # The relationship objects (SROs): one graph relationship per source, type and target the validator allows,
    # carrying the relationship object's own properties.
    sro_props, sro_required = schemas.collect(schemas.schemas["sros/relationship.json"], "sros/relationship.json")
    sro_reference = link(section("relationship")[1])
    properties, constraints = {}, {}
    for prop, occurrences in sro_props.items():
        if prop in SRO_ENDS:
            continue
        properties[prop] = property_of("relationship", prop, occurrences, prop in sro_required, sro_reference)
        if prop.endswith(("_ref", "_refs")):  # a relationship can't point at a node, so the identifiers are kept
            properties[prop]["description"] = describe(
                properties[prop]["description"],
                "Kept as identifiers: a relationship can't itself point at a node.",
            )
        if prop in sro_required and prop != "id":
            constraints[f"exists_{prop}"] = {"type": "EXISTS", "properties": [prop]}
    properties = {"id": properties.pop("id"), **properties}
    constraints = {"key_id": {"type": "KEY", "properties": ["id"]}, **constraints}

    def spec_description(source, rel, target):
        """The specification's description of a relationship, preferring a row about this source alone."""
        rows = spec_relationships.get((source, rel), [])
        matching = [
            (alone, text)
            for targets, text, alone, _ in rows
            if target in targets or (target in by_category["SCO"] and "<All STIX Cyber-observable Objects>" in targets)
        ]
        return sorted(matching, key=lambda m: not m[0])[0][1] if matching else ""

    def sro(source, rel, target, text, reference, custom):
        relationship(
            source,
            upper(rel),
            target,
            describe(
                sentence(text),
                f"Stored in STIX as a relationship object with relationship_type '{rel}', source_ref "
                f"{a(label(source))} {label(source)} and target_ref {a(label(target))} {label(target)}.",
            ),
            reference,
            None,
            {"relationshipType": rel, "relationshipObject": True, **custom},
            json.loads(json.dumps(properties)),
            json.loads(json.dumps(constraints)),
        )

    # The validator's table, with the relationships the specification defines in the source's own section that the
    # validator leaves out, e.g. malware targets vulnerability.
    allowed = {}
    for source, table in enums["RELATIONSHIPS"].items():
        for rel, targets in table.items():
            for target in [targets] if isinstance(targets, str) else targets:
                # The validator lists vulnerability impacts 'tools'; the specification's type is tool.
                allowed.setdefault((source, rel), {}).setdefault("tool" if target == "tools" else target, set()).add(
                    "validator" if target != "tools" else "validator (as 'tools')"
                )
    for (source, rel), rows in spec_relationships.items():
        for targets, _, _, number in rows:
            if source in objects and number == section(source)[0]:
                for target in targets:
                    if target == "<All STIX Cyber-observable Objects>":
                        for sco in by_category["SCO"]:
                            allowed.setdefault((source, rel), {}).setdefault(sco, set()).add("specification")
                    elif target in objects:
                        allowed.setdefault((source, rel), {}).setdefault(target, set()).add("specification")

    for (source, rel), targets in sorted(allowed.items()):
        for target in collapse(targets):
            members = by_category[target[1:4]] if target.startswith("<") else [target]
            text = next((spec_description(source, rel, t) for t in members if spec_description(source, rel, t)), "")
            if not text:
                text = "Listed by the OASIS STIX validator; the STIX 2.1 specification doesn't define it."
            number = section(source)[0]
            sro(source, rel, target, text, link(sections.get(number, section(source)[1])),
                {"definedBy": sorted(set.intersection(*(targets[t] for t in members)))})

    # The common relationships any two objects may have: derived-from and duplicate-of between objects of the same
    # type, and related-to between any two.
    for rel in enums["COMMON_RELATIONSHIPS"]:
        pairs = [("<SDO>", "<SDO>"), ("<SCO>", "<SCO>")]
        if rel == "related-to":
            pairs += [("<SDO>", "<SCO>"), ("<SCO>", "<SDO>")]
        for source, target in pairs:
            text = {
                "derived-from": "The information in the target object is based on information from the source "
                "object. Both objects are of the same type.",
                "duplicate-of": "The referenced source and target objects are semantically duplicates of each other. "
                "Both objects are of the same type.",
                "related-to": "Asserts a non-specific relationship between two objects. Used when no other "
                "relationship type is suitable.",
            }[rel]
            sro(source, rel, target, text, link(common_relationships), {"common": True, "definedBy": ["specification"]})

    for rel in relationships.values():
        for end in (rel["from"], rel["to"]):
            if end["node"] not in nodes:
                sys.exit(f"relationship {rel['type']} points at {end['node']}, which is not a node")

    nodes = dict(sorted(nodes.items(), key=lambda n: (list(CATEGORIES.values()).index(
        n[1]["extensions"]["custom"]["category"]), n[0])))
    return {
        "schema": SCHEMA,
        "version": "2.1",
        "id": "stix-2.1",
        "name": "STIX 2.1",
        "description": (
            "STIX (Structured Threat Information Expression) 2.1, the OASIS Standard language and serialisation "
            "format for exchanging cyber threat intelligence (https://docs.oasis-open.org/cti/stix/v2.1/os/"
            "stix-v2.1-os.html). STIX describes threat intelligence as a graph: STIX Domain Objects (SDOs) such as "
            "attack patterns, campaigns, indicators, malware, threat actors and vulnerabilities; STIX "
            "Cyber-observable Objects (SCOs) such as files, processes, network traffic and IP addresses; STIX "
            "Relationship Objects (SROs) that connect them; and meta objects for data markings, translations and "
            "extensions. Generated from the OASIS STIX 2.1 JSON schemas (https://github.com/oasis-open/"
            f"cti-stix2-json-schemas, commit {SCHEMAS_COMMIT}), the relationship table of the OASIS STIX "
            "validator 3.3.2 and the specification itself: each object type is a node, each property a property, "
            "each _ref or _refs property a relationship named after it, and each relationship type the "
            "specification defines between two object types a relationship carrying the relationship object's "
            "properties."
        ),
        "nodes": nodes,
        "relationships": relationships,
    }


def nested(refs, path):
    """The (path, property, targets) of each reference the validator lists inside an extension or embedded type."""
    for key, value in refs.items():
        if isinstance(value, dict):
            yield from nested(value, path + [key])
        elif path:
            yield path, key, value


def find_property(schema, prop, within):
    """The schema of a property declared under a key containing `within`, e.g. contains_refs under ^archive-ext$."""

    def search(node, inside):
        if isinstance(node, dict):
            if inside and prop in node.get("properties", {}):
                return node["properties"][prop]
            for key, value in node.items():
                found = search(value, inside or within in key)
                if found:
                    return found
        elif isinstance(node, list):
            for value in node:
                found = search(value, inside)
                if found:
                    return found
        return None

    return search(schema, False)


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
    args = [Path(arg) for arg in sys.argv[1:4]]
    schemas = args[0] if len(args) > 0 else download(SCHEMAS_URL, "cti-stix2-json-schemas.zip")
    validator = args[1] if len(args) > 1 else download(VALIDATOR_URL, "cti-stix-validator-3.3.2.zip")
    spec = args[2] if len(args) > 2 else download(SPEC_URL, "stix-v2.1-os.html")
    model = build(read_schemas(schemas), read_enums(validator), read_spec(spec))
    out = Path(__file__).parent
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(yaml(model) + "\n")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships")


if __name__ == "__main__":
    main()
