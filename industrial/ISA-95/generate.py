#!/usr/bin/env python3
"""Generates the ISA-95 ontology from MESA International's B2MML V0700 XML schemas.

Usage: python3 generate.py [path/to/B2MML-BatchML.zip | path/to/B2MML-BatchML | path/to/Schema]

Without a path, the schemas are downloaded from the B2MML-BatchML repository on GitHub. Writes model.json and
model.yaml next to this script. Uses only the Python standard library.
"""

import json
import re
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

COMMIT = "6b051863c3e249a1c0d3db464d472795dcf854d9"  # tag V7.00.00
SOURCE_URL = f"https://github.com/MESAInternational/B2MML-BatchML/archive/{COMMIT}.zip"
SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
BLOB = f"https://github.com/MESAInternational/B2MML-BatchML/blob/{COMMIT}/Schema"
MAX_DESCRIPTION = 1024
XS = "{http://www.w3.org/2001/XMLSchema}"

# The schemas of the B2MML messaging infrastructure rather than of the ISA-95 object models: business object document
# confirmations, error messages, and the profiles a system publishes of the transactions and master data it supports.
INFRASTRUCTURE = (
    "B2MML-ConfirmBOD.xsd",
    "B2MML-ErrorMessage.xsd",
    "B2MML-TransactionProfile.xsd",
    "B2MML-MasterDataProfile.xsd",
)

# The ISA-95 model each schema belongs to, which colours the diagram.
AREAS = {
    "Resources": (
        "Personnel", "Equipment", "PhysicalAsset", "Material", "OperationalLocation", "OperationsTest",
        "ResourceRelationshipNetwork",
    ),
    "Operations": (
        "ProcessSegment", "OperationsDefinition", "OperationsSchedule", "OperationsPerformance",
        "OperationsPerformanceTypes", "OperationsCapability", "OperationsEvent",
    ),
    "Work": (
        "WorkDefinition", "WorkSchedule", "WorkPerformance", "WorkCapability", "WorkAlert", "WorkCalendar",
        "WorkRecord", "WorkflowSpecification", "InformationObject",
    ),
    "Common": ("Common",),
}

XSD_TYPES = {
    "string": "STRING",
    "normalizedString": "STRING",
    "token": "STRING",
    "language": "STRING",
    "anyURI": "STRING",
    "base64Binary": "STRING",
    "hexBinary": "STRING",
    "dateTime": "ZONED DATETIME",
    "date": "DATE",
    "time": "LOCAL TIME",
    "duration": "DURATION",
    "decimal": "FLOAT",
    "double": "FLOAT",
    "float": "FLOAT",
    "integer": "INTEGER",
    "int": "INTEGER",
    "long": "INTEGER",
    "nonNegativeInteger": "INTEGER",
    "positiveInteger": "INTEGER",
    "boolean": "BOOLEAN",
}

# Structured value types, which have no identity of their own: each becomes properties of the object that holds it,
# named after the element that holds it, e.g. Value → value, valueDataType, valueUnitOfMeasure and valueKey.
VALUE_TYPES = {
    "ValueType": {"ValueString": "", "DataType": "DataType", "UnitOfMeasure": "UnitOfMeasure", "Key": "Key"},
    "QuantityValueType": {"QuantityString": "", "DataType": "DataType", "UnitOfMeasure": "UnitOfMeasure", "Key": "Key"},
    "SpatialDefinitionType": {"Value": "", "Format": "Format", "SRID": "SRID", "SRIDAuthority": "SRIDAuthority"},
    "ResourceLocationType": {"Location": "", "LocationType": "Type"},
}
# The ID references whose name doesn't spell out the object they refer to, and the misspelling some of them carry.
REFERENCE_ALIASES = {
    "OperationalClass": "OperationalLocationClass",
    "OperationalClassProperty": "OperationalLocationClassProperty",
    "OperationsRecordSpecification": "OperationsRecordSpecTemplate",
    "FromWSNode": "WorkflowSpecificationNode",
    "ToWSNode": "WorkflowSpecificationNode",
}
MISSPELLINGS = {"Defintion": "Definition"}
# The roles an ID reference can name before or after the object it refers to, e.g. EquipmentClassBaseID.
REFERENCE_ROLES = (r"^Dependent", r"Base$", r"Source$", r"Pattern$")

HIERARCHY_SCOPE = "HierarchyScopeType"
INFORMATION_OBJECT = "InformationObjectType"
ASSET_MAPPING = "EquipmentAssetMappingType"


def words(text):
    """The words of a CamelCase name, keeping acronyms whole, e.g. SRIDAuthority → SRID, Authority."""
    return re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z\d]+|[A-Z]+|\d+", text)


def camel(name):
    ws = [w.lower() for w in words(name)]
    return ws[0] + "".join(w.capitalize() for w in ws[1:])


def spaced(name):
    """A name as words in lower case, keeping acronyms, e.g. OpEquipmentActual → op equipment actual."""
    return " ".join(w if w.isupper() and len(w) > 1 else w.lower() for w in words(name))


def rel_type(name):
    return "HAS_" + "_".join(w.upper() for w in words(name))


def tidy(text):
    return re.sub(r"\s+", " ", text or "").strip()


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
    return f"between {lower} and {'*' if upper is None else upper}"


def multiplicity(lower, upper):
    return f"{lower}..{'*' if upper is None else upper}"


def ends(lower, upper):
    """The count constraints of a relationship end, from a multiplicity. Zero or more is unconstrained."""
    if (lower, upper) == (1, 1):
        return {"count": 1}
    if (lower, upper) == (0, 1):
        return {"max_count": 1}
    if (lower, upper) == (0, None):
        return {}
    return {k: v for k, v in (("min_count", lower), ("max_count", upper)) if v}


def node_of(type_name):
    """The node a B2MML type becomes, e.g. EquipmentType → Equipment, ResourceNetworkConnectionTypeType →
    ResourceNetworkConnectionType."""
    return type_name[: -len("Type")] if type_name.endswith("Type") else type_name


#----------------------------------
#   Reading the schemas
#----------------------------------


class Schemas:
    """The named types and groups of the B2MML schemas, where each is declared, and its documentation."""

    def __init__(self, files):
        self.types, self.groups, self.elements, self.file_of, self.lines = {}, {}, {}, {}, {}
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.lines[path.name] = text.splitlines()
            root = ET.fromstring(text)
            for child in root:
                name = child.get("name")
                if child.tag in (XS + "complexType", XS + "simpleType"):
                    self.types[name] = child
                elif child.tag == XS + "group":
                    self.groups[name] = child
                elif child.tag == XS + "element":
                    self.elements[name] = child
                else:
                    continue
                self.file_of[(child.tag, name)] = path.name

    def file(self, type_name):
        node = self.types[type_name]
        return self.file_of[(node.tag, type_name)]

    def line(self, file, pattern, after=0):
        """The first line of a file at or after a line that matches a pattern, 1-based; 0 if there is none."""
        regex = re.compile(pattern)
        for i, text in enumerate(self.lines[file][after:], start=after + 1):
            if regex.search(text):
                return i
        return 0

    def type_line(self, type_name):
        file = self.file(type_name)
        return self.line(file, rf'(complexType|simpleType)\s+name\s*=\s*"{type_name}"')

    def link(self, file, line):
        return f"{BLOB}/{file}" + (f"#L{line}" if line else "")

    def documentation(self, type_name):
        """The documentation of a type, or of the global element of the same name, e.g. EquipmentClass."""
        for node in (self.types.get(type_name), self.elements.get(node_of(type_name))):
            if node is not None:
                docs = [tidy(d.text) for d in node.findall(f"{XS}annotation/{XS}documentation") if tidy(d.text)]
                if docs:
                    return " ".join(docs)
        return ""

    def is_complex(self, type_name):
        node = self.types.get(type_name)
        return node is not None and node.tag == XS + "complexType" and node.find(XS + "simpleContent") is None

    def simple(self, type_name):
        """(Neo4j type, enumeration values, XSD base type) of a simple type or a complex type with simple content,
        following its restrictions and extensions down to the XSD type it is built on."""
        if type_name.startswith("xsd:"):
            base = type_name[4:]
            if base not in XSD_TYPES:
                sys.exit(f"unmapped XSD type {type_name}")
            return XSD_TYPES[base], [], base
        node = self.types.get(type_name)
        if node is None:
            sys.exit(f"unknown type {type_name}")
        derivation = next(
            (d for d in node.iter() if d.tag in (XS + "restriction", XS + "extension") and d.get("base")), None
        )
        if derivation is None:
            sys.exit(f"{type_name} is neither a restriction nor an extension")
        neo4j, values, base = self.simple(derivation.get("base"))
        own = [e.get("value") for e in derivation.findall(XS + "enumeration")]
        return neo4j, list(dict.fromkeys(own)) or values, base

    def content(self, type_name):
        """The elements of a complex type, in order: (name, type, lower, upper, group), with an upper of None meaning
        unbounded. Choices make each of their elements optional; groups other than the extension hooks are expanded,
        and the element records the group it came from."""
        out = []

        def walk(node, optional=False, many=False, group=None):
            for child in node:
                tag = child.tag[len(XS):]
                if tag in ("sequence", "choice"):
                    walk(
                        child,
                        optional or tag == "choice" or child.get("minOccurs") == "0",
                        many or child.get("maxOccurs") == "unbounded",
                        group,
                    )
                elif tag == "group" and child.get("ref"):
                    if child.get("ref").startswith("Extended:"):
                        continue  # the empty hooks through which users extend B2MML
                    walk(self.groups[child.get("ref")], optional, many, child.get("ref"))
                elif tag == "element":
                    lower = 0 if optional else int(child.get("minOccurs", "1"))
                    upper = child.get("maxOccurs", "1")
                    upper = None if many or upper == "unbounded" else int(upper)
                    if child.get("type") is None:
                        sys.exit(f"{type_name}.{child.get('name')} has an anonymous type")
                    out.append((child.get("name"), child.get("type"), lower, upper, group))

        walk(self.types[type_name])
        return out


def read_schemas(source):
    """The B2MML schema files: from a downloaded or given zip archive, a clone of the repository, or its Schema
    directory. The BatchML schemas and the extension hooks are left out."""
    if not source.is_dir():
        out = Path(tempfile.mkdtemp())
        zipfile.ZipFile(source).extractall(out)
        source = out
    root = source if list(source.glob("B2MML-*.xsd")) else next(
        (d for d in source.rglob("Schema") if list(d.glob("B2MML-*.xsd"))), None
    )
    if root is None:
        sys.exit(f"{source}: no B2MML schemas found")
    return [p for p in sorted(root.glob("B2MML-*.xsd")) if "Extensions" not in p.name]


#----------------------------------
#   The ISA-95 model as data
#----------------------------------


def build(files):
    schemas = Schemas(files)

    def area_of(file):
        stem = file[len("B2MML-"): -len(".xsd")]
        return next(area for area, stems in AREAS.items() if stem in stems)

    def is_message(type_name):
        """A transaction verb wrapper, e.g. ProcessEquipmentType, holds an application area and a data area."""
        return any(e.get("name") == "ApplicationArea" for e in schemas.types[type_name].iter(XS + "element"))

    objects = sorted(
        t
        for t in schemas.types
        if schemas.is_complex(t)
        and schemas.file(t) not in INFRASTRUCTURE
        and not t.startswith("Trans")
        and t not in VALUE_TYPES
        and t not in (HIERARCHY_SCOPE, INFORMATION_OBJECT, ASSET_MAPPING)
        and not is_message(t)
    )
    names = {node_of(t) for t in objects}
    # The objects an information object can be, those of its choice that are B2MML objects; the BatchML ones aren't.
    information_objects = [t for _, t, *_ in schemas.content(INFORMATION_OBJECT) if t in objects]
    by_lower = {n.lower(): n for n in names}

    def referenced(element, etype):
        """The node an ID reference refers to, e.g. EquipmentClassID → EquipmentClass, MaterialSublotID →
        MaterialSubLot, EquipmentClassBaseID → EquipmentClass or SegmentRequirementID → OpSegmentRequirement (B2MML
        prefixes the ISA-95 segment objects with Op), or None when it can't be told which object it is."""
        if not element.endswith("ID") or etype not in ("IdentifierType", "DescriptionType"):
            return None
        base = element[:-2]
        for wrong, right in MISSPELLINGS.items():
            base = base.replace(wrong, right)
        candidates = [base] + [re.sub(role, "", base) for role in REFERENCE_ROLES if re.search(role, base)]
        for candidate in candidates:
            candidate = REFERENCE_ALIASES.get(candidate, candidate)
            for name in (candidate, "Op" + candidate):
                if name.lower() in by_lower:
                    return by_lower[name.lower()]
        return None

    def property_of(element, b2mml_type, lower, upper, description, reference):
        """A property for a simple-typed element: a list when it repeats, with the values of an enumeration."""
        neo4j, values, _ = schemas.simple(b2mml_type)
        if upper is None or upper > 1:
            neo4j = f"LIST<{neo4j}>"
        prop = {
            "type": neo4j,
            "name": camel(element),
            "description": describe(
                sentence(description),
                f"Multiplicity {multiplicity(lower, upper)}." if (lower, upper) != (0, 1) else "",
            ),
            "reference": reference,
            "extensions": {
                "custom": {"lower": lower, **({"upper": upper} if upper is not None else {}), "b2mmlType": b2mml_type}
            },
        }
        if values:
            prop["one_of"] = values
        return prop

    def element_line(type_name, element, group):
        """The line an element is declared on, in its type or in the group it came from."""
        if group:
            file = schemas.file_of[(XS + "group", group)]
            start = schemas.line(file, rf'group\s+name\s*=\s*"{group}"')
        else:
            file, start = schemas.file(type_name), schemas.type_line(type_name)
        return file, schemas.line(file, rf'element\s+name\s*=\s*"{element}"', start)

    nodes, relationships = {}, {}

    def add_relationship(rid, rel):
        while rid in relationships:
            rid += "_2"
        relationships[rid] = rel

    for type_name in objects:
        name = node_of(type_name)
        file = schemas.file(type_name)
        properties, constraints = {}, {}
        groups = []

        for element, etype, lower, upper, group in schemas.content(type_name):
            if group and group not in groups:
                groups.append(group)
            efile, eline = element_line(type_name, element, group)
            reference = schemas.link(efile, eline)
            custom = {"lower": lower, **({"upper": upper} if upper is not None else {})}

            if element == "ID" and etype == "IdentifierType":
                properties["id"] = {
                    "type": "STRING",
                    "name": "id",
                    "description": f"The identifier of the {name}, unique within its scope.",
                    "reference": reference,
                    "extensions": {"custom": {**custom, "b2mmlType": etype}},
                }
                constraints[f"key_{name}"] = {"type": "KEY", "properties": ["id"], "name": f"id_{name}_key"}

            elif etype in objects or etype == INFORMATION_OBJECT:
                target = node_of(etype)
                rtype = rel_type(element)
                add_relationship(
                    f"{name}_{rtype}_{target}",
                    {
                        "type": rtype,
                        "from": {"node": name, **ends(lower, upper)},
                        "to": {"node": target, "max_count": 1},
                        "description": describe(
                            f"The {spaced(element)} of the {name}. Each {name} has {phrase(lower, upper)} {target}.",
                            f"A composition: each {target} is part of at most one owner and is deleted with it.",
                            "The information object is one of the ISA-95 objects; ExternalReferenceID, the "
                            "alternative B2MML allows to it, is the externalReferenceId property."
                            if etype == INFORMATION_OBJECT
                            else "",
                        ),
                        "reference": reference,
                        "extensions": {"custom": {"composition": True, "element": element, **custom}},
                    },
                )

            elif etype == HIERARCHY_SCOPE:
                rtype = rel_type(element)
                add_relationship(
                    f"{name}_{rtype}_Equipment",
                    {
                        "type": rtype,
                        "from": {"node": name, **ends(lower, upper)},
                        "to": {"node": "Equipment"},
                        "description": describe(
                            f"Where the {name} fits within the role-based equipment hierarchy: the Equipment "
                            f"its hierarchy scope identifies. Each {name} has {phrase(lower, upper)} hierarchy scope.",
                            sentence(schemas.documentation(HIERARCHY_SCOPE)),
                        ),
                        "reference": reference,
                        "extensions": {"custom": {"composition": False, "element": element, **custom}},
                    },
                )

            elif etype == ASSET_MAPPING:
                # An association between a piece of equipment and the physical asset that implements it for a time.
                mapping_line = schemas.type_line(ASSET_MAPPING)
                rel_properties = {}
                for part, ptype, plower, pupper, _ in schemas.content(ASSET_MAPPING):
                    if part in ("EquipmentID", "PhysicalAssetID"):
                        continue  # the ends of the relationship
                    pline = schemas.line("B2MML-Common.xsd", rf'element\s+name\s*=\s*"{part}"', mapping_line)
                    if ptype == HIERARCHY_SCOPE:
                        rel_properties["hierarchyScope"] = {
                            "type": "STRING",
                            "name": "hierarchyScope",
                            "description": "The ID of the Equipment that identifies where the mapping fits within "
                            "the role-based equipment hierarchy.",
                            "reference": schemas.link("B2MML-Common.xsd", pline),
                            "extensions": {"custom": {"lower": plower, "upper": pupper, "b2mmlType": ptype}},
                        }
                    else:
                        rel_properties[camel(part)] = property_of(
                            part,
                            ptype,
                            plower,
                            pupper,
                            f"The {spaced(part)} of the mapping",
                            schemas.link("B2MML-Common.xsd", pline),
                        )
                add_relationship(
                    f"{name}_{rel_type(element)}_PhysicalAsset",
                    {
                        "type": rel_type(element),
                        "from": {"node": name, **ends(lower, upper)},
                        "to": {"node": "PhysicalAsset"},
                        "description": describe(
                            f"A physical asset that implements the {name} for a time: the EquipmentAssetMapping "
                            "between them, identified by their IDs.",
                            f"Each {name} has {phrase(lower, upper)} such mappings.",
                        ),
                        "reference": schemas.link("B2MML-Common.xsd", mapping_line),
                        "properties": rel_properties,
                        "extensions": {"custom": {"composition": False, "element": element, **custom}},
                    },
                )

            elif etype in VALUE_TYPES:
                for part, ptype, plower, pupper, _ in schemas.content(etype):
                    suffix = VALUE_TYPES[etype][part]
                    pname = element + suffix
                    # A part is as optional and as repeated as the value that holds it.
                    plower = plower if lower else 0
                    pupper = upper if upper != 1 else pupper
                    prop = property_of(
                        pname,
                        ptype,
                        plower,
                        pupper,
                        f"The {spaced(element)} of the {name}"
                        + (f": its {spaced(part)}" if suffix else "")
                        + (f". The parts of a repeated {element} are listed in the same order" if pupper != 1 else ""),
                        reference,
                    )
                    prop["extensions"]["custom"]["b2mmlType"] = f"{etype}.{part}"
                    properties[camel(pname)] = prop
                    if (plower, pupper) == (1, 1):
                        constraints[f"exists_{name}_{camel(pname)}"] = {
                            "type": "EXISTS",
                            "properties": [camel(pname)],
                            "name": f"{camel(pname)}_{name}_exists",
                        }

            elif referenced(element, etype):
                target = referenced(element, etype)
                role = element[:-2]
                for wrong, right in MISSPELLINGS.items():
                    role = role.replace(wrong, right)
                rtype = rel_type(role)
                add_relationship(
                    f"{name}_{rtype}_{target}",
                    {
                        "type": rtype,
                        "from": {"node": name, **ends(lower, upper)},
                        "to": {"node": target},
                        "description": describe(
                            f"The {target} the {name} refers to by its {element}, the ID of the {target}. Each "
                            f"{name} refers to {phrase(lower, upper)} {target}."
                        ),
                        "reference": reference,
                        "extensions": {"custom": {"composition": False, "element": element, **custom}},
                    },
                )

            elif not schemas.is_complex(etype):
                pid = camel(element)
                if pid in properties:
                    sys.exit(f"{type_name}: {element} is declared twice")
                doc = schemas.documentation(etype) if etype not in ("IdentifierType", "DescriptionType") else ""
                properties[pid] = property_of(
                    element, etype, lower, upper, f"The {spaced(element)} of the {name}", reference
                )
                if doc:
                    properties[pid]["description"] = describe(properties[pid]["description"], sentence(doc))
                if (lower, upper) == (1, 1):
                    constraints[f"exists_{name}_{pid}"] = {
                        "type": "EXISTS",
                        "properties": [pid],
                        "name": f"{pid}_{name}_exists",
                    }

            else:
                sys.exit(f"{type_name}.{element}: unmapped type {etype}")

        if "id" not in properties:
            sys.exit(f"{type_name} has no ID")
        documentation = schemas.documentation(type_name)
        nodes[name] = {
            "labels": {
                "identifier": name,
                **({"implied": ["InformationObject"]} if type_name in information_objects else {}),
            },
            "description": describe(
                sentence(documentation) or f"An ISA-95 {spaced(name)}.",
                f"Exchanged in B2MML as {type_name}, declared in {file}.",
            ),
            "reference": schemas.link(file, schemas.type_line(type_name)),
            "properties": properties,
            "constraints": constraints,
            "extensions": {
                "custom": {
                    "model": area_of(file),
                    "schema": file,
                    "b2mmlType": type_name,
                    **({"groups": groups} if groups else {}),
                }
            },
        }

    # An information object is any one of the ISA-95 objects a record entry can hold, so it is a label they all carry.
    info_file = schemas.file(INFORMATION_OBJECT)
    nodes["InformationObject"] = {
        "labels": {"identifier": "InformationObject"},
        "description": describe(
            "An ISA-95 object held in a work or operations record entry: any one of the "
            f"{len(information_objects)} objects B2MML's InformationObjectType offers a choice of, each of which "
            "carries this label too.",
            f"Exchanged in B2MML as {INFORMATION_OBJECT}, declared in {info_file}.",
        ),
        "reference": schemas.link(info_file, schemas.type_line(INFORMATION_OBJECT)),
        "properties": {
            "id": {
                "type": "STRING",
                "name": "id",
                "description": "The identifier of the object, unique among the objects of its own kind.",
                "reference": schemas.link(info_file, schemas.type_line(INFORMATION_OBJECT)),
                "extensions": {"custom": {"lower": 1, "upper": 1, "b2mmlType": "IdentifierType"}},
            }
        },
        "constraints": {
            "exists_InformationObject_id": {
                "type": "EXISTS",
                "properties": ["id"],
                "name": "id_InformationObject_exists",
            }
        },
        "extensions": {
            "custom": {"model": area_of(info_file), "schema": info_file, "b2mmlType": INFORMATION_OBJECT, "abstract": True}
        },
    }

    for rel in relationships.values():
        for end in (rel["from"], rel["to"]):
            if end["node"] not in nodes:
                sys.exit(f"relationship {rel['type']} points at {end['node']}, which is not an object")

    return {
        "schema": SCHEMA,
        "version": "7.00.00",
        "id": "isa-95-b2mml-7.00.00",
        "name": "ISA-95 (B2MML V0700)",
        "description": (
            "The ANSI/ISA-95 (IEC 62264) enterprise-control system integration object models, as MESA "
            "International's Business To Manufacturing Markup Language (B2MML) V0700 implements them "
            "(https://github.com/MESAInternational/B2MML-BatchML, tag V7.00.00), based on ISA-95.00.02-2018, "
            "ISA-95.00.04-2018 and ISA-95.00.05-2018. It covers the resources manufacturing operations use (personnel, "
            "equipment, physical assets, material, operational locations and their tests), the operations models "
            "(process segments, operations definitions, schedules, performance, capability and events), and the "
            "work models of operations management (work definitions, schedules, performance, capability, alerts, "
            "calendars, records and workflow specifications). Generated from the B2MML XML schemas: each object "
            "type is a node, each simple-typed element a property, each nested object a composition and each ID "
            "reference to another object a relationship."
        ),
        "nodes": dict(sorted(nodes.items())),
        "relationships": relationships,
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
    if len(sys.argv) > 1:
        source = Path(sys.argv[1])
    else:
        source = Path(tempfile.mkdtemp()) / "B2MML-BatchML.zip"
        with urllib.request.urlopen(SOURCE_URL) as response:
            source.write_bytes(response.read())
    model = build(read_schemas(source))
    out = Path(__file__).parent
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(yaml(model) + "\n")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships")


if __name__ == "__main__":
    main()
