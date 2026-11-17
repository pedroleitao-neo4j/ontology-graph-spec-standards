#!/usr/bin/env python3
"""Generates the AutomationML ontology from the CAEX 3.0 XML schema and the AutomationML standard libraries.

Usage: python3 generate.py [path ...]

Each path is the CAEX schema (.xsd), a library (.aml), a zip archive or a directory holding them. Without a path, the
schema is downloaded from the AutomationML AMLEngine2.1 repository on GitHub and the libraries from automationml.org.
Writes model.json and model.yaml next to this script. Uses only the Python standard library.
"""

import io
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
COMMIT = "098106acd50ca74c10a12d2cbecdae047c1f9b4b"
XSD_PATH = "Samples/WikiSnippets/src/CAEX_ClassModel_V.3.0.xsd"
XSD_URL = f"https://raw.githubusercontent.com/AutomationML/AMLEngine2.1/{COMMIT}/{XSD_PATH}"
XSD_PAGE = f"https://github.com/AutomationML/AMLEngine2.1/blob/{COMMIT}/{XSD_PATH}"
UPLOADS = "https://www.automationml.org/wp-content/uploads"
LIBRARY_URLS = (
    f"{UPLOADS}/2021/11/Whitepaper-AutomationML-Edition-2.1.zip",  # the base libraries
    f"{UPLOADS}/2023/08/AML_Whitepaper_Part2_Semantics-Libraries.zip",  # the role class libraries
)
MAX_DESCRIPTION = 1024

XS = "{http://www.w3.org/2001/XMLSchema}"
CAEX = "{http://www.dke.de/CAEX}"

DATATYPES = {"xs:string": "STRING", "xs:dateTime": "ZONED DATETIME"}

# The two base types every CAEX element extends; they become abstract nodes, whose labels the others carry. The
# types between them and an element, e.g. SystemUnitClassType below InternalElementType, are folded into the element.
BASES = ("CAEXObject", "CAEXBasicObject")

# The organisational elements of a CAEX file: the file, its libraries and hierarchies, and their header information.
DOCUMENT = {
    "CAEXBasicObject", "CAEXObject", "CAEXFile", "SourceDocumentInformation", "ExternalReference",
    "InstanceHierarchy", "InterfaceClassLib", "RoleClassLib", "SystemUnitClassLib", "AttributeTypeLib", "Revision",
    "SourceObjectInformation",
}  # fmt: skip

# The attributes that refer to another object by its path or ID, and the nodes they refer to. The schema types them as
# strings; IEC 62424 says what they point at. An object's mirror refers to its master object by the master's ID.
REFERENCES = {
    ("InterfaceClass", "RefBaseClassPath"): ("InterfaceClass",),
    ("ExternalInterface", "RefBaseClassPath"): ("InterfaceClass", "ExternalInterface"),
    ("RoleClass", "RefBaseClassPath"): ("RoleClass",),
    ("SystemUnitClass", "RefBaseClassPath"): ("SystemUnitClass",),
    ("InternalElement", "RefBaseSystemUnitPath"): ("SystemUnitClass", "InternalElement"),
    ("RoleRequirements", "RefBaseRoleClassPath"): ("RoleClass",),
    ("SupportedRoleClass", "RefRoleClassPath"): ("RoleClass",),
    ("Attribute", "RefAttributeType"): ("AttributeType",),
    ("AttributeType", "RefAttributeType"): ("AttributeType",),
    ("InternalLink", "RefPartnerSideA"): ("ExternalInterface",),
    ("InternalLink", "RefPartnerSideB"): ("ExternalInterface",),
    ("InterfaceIDMapping", "SystemUnitInterfaceID"): ("ExternalInterface",),
    ("InterfaceIDMapping", "RoleInterfaceID"): ("ExternalInterface",),
}

# The kinds of library class, the CAEX element an object carrying the class's label is, and what a label clashing
# with another is suffixed with.
KINDS = {
    "RoleClass": ("InternalElement", "Role"),
    "InterfaceClass": ("ExternalInterface", "Interface"),
    "AttributeType": ("Attribute", "AttributeType"),
}


def words(text):
    """The words of a CamelCase name, e.g. RefBaseClassPath → Ref, Base, Class, Path, and SourceObjID → ..., ID."""
    return re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z\d]+", text)


def camel(name):
    ws = [w.lower() for w in words(name)]
    return ws[0] + "".join(w.capitalize() for w in ws[1:])


def snake(name):
    return "_".join(w.upper() for w in words(name))


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
    return {(1, 1): "exactly one", (0, 1): "at most one", (1, None): "one or more", (0, None): "zero or more"}[
        (lower, upper)
    ]


def ends(lower, upper):
    """The count constraints of a relationship end, from a multiplicity. Zero or more is unconstrained."""
    return {(1, 1): {"count": 1}, (0, 1): {"max_count": 1}, (1, None): {"min_count": 1}, (0, None): {}}[(lower, upper)]


def listed(names):
    return ", ".join(names[:-1]) + f" and {names[-1]}" if len(names) > 1 else "".join(names)


#----------------------------------
#   Reading the sources
#----------------------------------


def read_sources(paths):
    """The text of the CAEX schema, and the libraries as (file name, archive URL, root element), from the given paths
    or, without any, the default downloads."""
    files = []  # (name, bytes, archive URL)

    def add(name, data, url):
        if name.endswith(".zip"):
            archive = zipfile.ZipFile(io.BytesIO(data))
            for member in sorted(archive.namelist()):
                add(Path(member).name, archive.read(member), url)
        elif name.endswith((".xsd", ".aml")):
            files.append((name, data, url))

    def known(name):
        """The download an archive of this name came from, so a library read from a local copy links to it too."""
        return next((u for u in (XSD_URL,) + LIBRARY_URLS if u.endswith("/" + name)), None)

    if paths:
        for path in map(Path, paths):
            for file in sorted(path.rglob("*")) if path.is_dir() else [path]:
                if file.is_file():
                    add(file.name, file.read_bytes(), known(file.name))
    else:
        for url in (XSD_URL,) + LIBRARY_URLS:
            # automationml.org rejects some user agents.
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request) as response:
                add(url.rsplit("/", 1)[-1], response.read(), url)

    schemas = [data for name, data, _ in files if name.endswith(".xsd") and b'name="CAEXFile"' in data]
    if len(schemas) != 1:
        sys.exit(f"expected one CAEX 3.0 schema, found {len(schemas)}")
    libraries = [(name, url, ET.fromstring(data)) for name, data, url in sorted(files) if name.endswith(".aml")]
    return schemas[0].decode("utf-8-sig"), libraries


#----------------------------------
#   The CAEX schema
#----------------------------------


class Schema:
    """The CAEX schema's named types and groups, and what each type declares."""

    def __init__(self, text):
        self.text = text
        self.root = ET.fromstring(text.encode())
        self.types = {t.get("name"): t for t in self.root.findall(XS + "complexType")}
        self.simple = {t.get("name"): t for t in self.root.findall(XS + "simpleType")}
        self.groups = {g.get("name"): g for g in self.root.findall(XS + "group")}

    def line(self, kind, name):
        """The line of the schema declaring a named element or type, for linking to it."""
        match = re.search(rf'<xs:{kind} name="{name}"', self.text)
        return self.text.count("\n", 0, match.start()) + 1 if match else None

    def page(self, kind, name):
        line = self.line(kind, name)
        return f"{XSD_PAGE}#L{line}" if line else XSD_PAGE

    @staticmethod
    def doc(element):
        return tidy(element.findtext(f"{XS}annotation/{XS}documentation"))

    def declares(self, ctype):
        """(base type, attributes, child elements) a complex type declares itself. Each child is (element, lower,
        upper), with the lower bound zero where the child sits in a choice or an optional sequence."""
        base, attributes, children = None, [], []

        def walk(node, optional):
            nonlocal base
            for c in node:
                tag = c.tag.replace(XS, "")
                if tag in ("complexContent", "simpleContent"):
                    walk(c, optional)
                elif tag == "extension":
                    base = c.get("base")
                    walk(c, optional)
                elif tag in ("sequence", "choice"):
                    walk(c, optional or tag == "choice" or c.get("minOccurs") == "0")
                elif tag == "group":
                    walk(self.groups[c.get("ref")], optional or c.get("minOccurs") == "0")
                elif tag == "attribute":
                    attributes.append(c)
                elif tag == "element":
                    lower = 0 if optional else int(c.get("minOccurs", "1"))
                    upper = None if c.get("maxOccurs") == "unbounded" else int(c.get("maxOccurs", "1"))
                    children.append((c, lower, upper))

        walk(ctype, False)
        return base, attributes, children

    def type_of(self, element):
        """The complex type of an element: its named type, or its anonymous one. None for a simple element."""
        if element.get("type"):
            return self.types.get(element.get("type"))
        return element.find(XS + "complexType")

    def kind_of(self, element):
        """How an element is modelled: as a 'node', a 'property', or 'flatten'ed into its parent's properties."""
        ctype = self.type_of(element)
        if ctype is None:
            return "property"  # e.g. xs:string, or AdditionalInformation, which may hold anything
        base, attributes, children = self.declares(ctype)
        if ctype.find(XS + "simpleContent") is not None:
            # A text value: a property, unless it has attributes beyond its ChangeMode, e.g. SourceObjectInformation.
            return "node" if any(a.get("name") != "ChangeMode" for a in attributes) else "property"
        if base is None and not attributes and all(self.type_of(e) is None for e, _, _ in children):
            return "flatten"  # e.g. OrdinalScaledType in a Constraint, which only groups its values
        return "node"

    def chain(self, ctype):
        """The members of a type and the types it extends, down to the first of BASES, and that base's name."""
        attributes, children = [], []
        while ctype is not None:
            base, a, c = self.declares(ctype)
            attributes, children = a + attributes, c + children
            if base in BASES or base is None or base.startswith("xs:"):
                return attributes, children, base if base in BASES else None
            ctype = self.types[base]
        return attributes, children, None


def datatype(schema, attribute):
    """(Neo4j type, allowed values) of a schema attribute or simple element."""
    name = attribute.get("type")
    if name in schema.simple:  # ChangeMode
        values = [e.get("value") for e in schema.simple[name].iter(XS + "enumeration")]
        return "STRING", values
    if attribute.get("fixed"):
        return "STRING", [attribute.get("fixed")]
    if name is None:  # an anonymous restriction of xs:string, e.g. AttributeDataType, or anything
        return "STRING", []
    return DATATYPES[name], []


def build_caex(schema):
    """The nodes and relationships of the CAEX meta-model, starting from the CAEXFile root element."""
    nodes, relationships = {}, {}
    seen = {}  # node name → the type that defined it, to check that every element of a name means the same

    def identifier(name, own):
        """The id every node has, and its key; a CAEXObject's is its ID attribute."""
        if own:
            text = (
                f"The identifier of the {name}: its ID attribute, a unique identifier of the CAEX object, e.g. a "
                "UUID. Where it has none, as classes in a library often don't, one the loader assigns, e.g. its path."
            )
        elif name == "CAEXBasicObject":
            text = (
                "The identifier of the CAEX element: the ID attribute of a CAEXObject, and for any other element one "
                "the loader assigns, unique within the graph."
            )
        else:
            text = (
                f"The identifier of the {name}, which CAEX doesn't give it: one the loader assigns, unique within "
                "the graph."
            )
        return {
            "type": "STRING",
            "name": "id",
            "description": text,
            "reference": schema.page("complexType", "CAEXObject"),
            **({"extensions": {"custom": {"xsdAttribute": "ID"}}} if own else {}),
        }

    def add_property(props, constraints, node, name, element, lower, upper, xsd):
        pid = camel(name)
        neo4j, one_of = datatype(schema, element)
        if upper is None:
            neo4j = f"LIST<{neo4j}>"
        default = element.get("default")
        props[pid] = {
            "type": neo4j,
            "name": pid,
            "description": describe(
                sentence(Schema.doc(element)) or f"The {name} of the {node}.",
                f"Defaults to `{default}`." if default else "",
                f"Multiplicity {lower}..{'*' if upper is None else upper}." if (lower, upper) != (0, 1) else "",
            ),
            "reference": xsd,
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (
                        ("xsdAttribute" if element.tag == XS + "attribute" else "xsdElement", name),
                        ("xsdType", element.get("type")),
                        ("default", default),
                    )
                    if v is not None
                }
            },
        }
        if one_of:
            props[pid]["one_of"] = one_of
        if lower >= 1 and upper == 1:
            constraints[f"exists_{node}_{pid}"] = {
                "type": "EXISTS",
                "properties": [pid],
                "name": f"{pid}_{node}_exists",
            }

    def define(name, ctype, element, reference):
        """Defines the node for an element or base type, and those for the elements it contains."""
        if name in seen:
            if seen[name] is not ctype and schema.declares(ctype)[1:] != ([], []):
                sys.exit(f"element {name} is declared with two different types")
            return
        seen[name] = ctype
        if name in BASES:
            base, attributes, children = schema.declares(ctype)
            base = base if base in BASES else None
        else:
            attributes, children, base = schema.chain(ctype)
        props = {"id": identifier(name, "CAEXObject" in (name, base))}
        constraints = {f"key_{name}": {"type": "KEY", "properties": ["id"], "name": f"id_{name}_key"}}
        if ctype.find(XS + "simpleContent") is not None:  # e.g. SourceObjectInformation: its text is its value
            props["value"] = {
                "type": "STRING",
                "name": "value",
                "description": f"The text of the {name} element.",
                "reference": reference,
            }
        for attribute in attributes:
            if attribute.get("name") != "ID":
                lower = 1 if attribute.get("use") == "required" else 0
                add_property(props, constraints, name, attribute.get("name"), attribute, lower, 1, xsd=reference)
        contained = []
        for child, lower, upper in children:
            kind = schema.kind_of(child)
            if kind == "property":
                add_property(props, constraints, name, child.get("name"), child, lower, upper, xsd=reference)
            elif kind == "flatten":  # e.g. NominalScaledType/RequiredValue → nominalRequiredValue
                prefix = words(child.get("name"))[0]
                for grandchild, _, inner in schema.declares(schema.type_of(child))[2]:
                    element_name = prefix + grandchild.get("name")
                    add_property(props, constraints, name, element_name, grandchild, 0, inner, xsd=reference)
            else:
                contained.append((child, lower, upper))

        description = Schema.doc(element) if element is not None else ""
        type_name = element.get("type") if element is not None else name
        type_doc = Schema.doc(ctype)
        nodes[name] = {
            "labels": {"identifier": name, **({"implied": [base]} if base else {})},
            "description": describe(sentence(description), sentence(type_doc) if type_doc != description else "")
            or f"The {name} element of a CAEX file.",
            "reference": reference,
            "properties": props,
            "constraints": constraints,
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (
                        ("kind", "Document" if name in DOCUMENT else "Model"),
                        ("xsdType", type_name),
                        ("abstract", name in BASES or None),
                    )
                    if v is not None
                }
            },
        }

        # Each element it contains is a node of its own, which it composes.
        for child, lower, upper in contained:
            target = child.get("name")
            named = child.get("type")
            define(
                target,
                schema.type_of(child),
                child,
                schema.page("complexType", named) if named else schema.page("element", target),
            )
            rtype = "HAS_" + snake(target)
            relationships[f"{name}_{rtype}_{target}"] = {
                "type": rtype,
                "from": {"node": name, **ends(lower, upper)},
                "to": {"node": target, "max_count": 1},
                "description": describe(
                    sentence(Schema.doc(child)),
                    f"Each {name} has {phrase(lower, upper)} {target}.",
                    f"A composition: each {target} is part of at most one owner and is deleted with it.",
                ),
                "reference": reference,
                "extensions": {
                    "custom": {
                        "composition": True,
                        "xsdElement": target,
                        "lower": lower,
                        **({"upper": upper} if upper is not None else {}),
                    }
                },
            }

        # The attributes that refer to other objects, by path or ID, are relationships too.
        for attribute in attributes:
            targets = REFERENCES.get((name, attribute.get("name")), ())
            required = attribute.get("use") == "required"
            for target in targets:
                rtype = snake(re.sub(r"^Ref|(Path|ID)$", "", attribute.get("name")))
                if target == name:
                    how = "identifies by its ID: the master object the mirror object repeats"
                elif attribute.get("name").startswith("RefPartnerSide"):
                    how = "identifies by its owner's ID and its name, e.g. `788eb291-…:EnergySupply`"
                elif attribute.get("name").endswith("ID"):
                    how = "identifies by its ID"
                else:
                    how = "refers to by its path, which may start with an external file's alias and @"
                by_path = how.startswith("refers")
                # A path may refer to a class in a library that isn't loaded, so only an ID is sure to resolve.
                lower = 1 if required and len(targets) == 1 and not by_path else 0
                relationships[f"{name}_{rtype}_{target}"] = {
                    "type": rtype,
                    "from": {"node": name, **ends(lower, 1)},
                    "to": {"node": target},
                    "description": describe(
                        sentence(Schema.doc(attribute)),
                        f"Resolves the {attribute.get('name')} of the {name} to the {target} it {how}.",
                        f"Each {name} has {phrase(lower, 1)} {target}.",
                    ),
                    "reference": reference,
                    "extensions": {"custom": {"composition": False, "xsdAttribute": attribute.get("name")}},
                }

    for base in reversed(BASES):
        define(base, schema.types[base], schema.types[base], schema.page("complexType", base))
    root = schema.root.find(XS + "element")
    define(root.get("name"), schema.type_of(root), root, schema.page("element", root.get("name")))

    missing = {t for (n, _), ts in REFERENCES.items() for t in ts + (n,)} - nodes.keys()
    if missing:
        sys.exit(f"the schema has no elements {', '.join(sorted(missing))}")
    return nodes, relationships


#----------------------------------
#   The AutomationML libraries
#----------------------------------


def read_libraries(libraries):
    """Every class of the AutomationML standard libraries, keyed by its path, e.g.
    AutomationMLBaseRoleClassLib/AutomationMLBaseRole/Resource. User-defined libraries, e.g. the ISA-106 example
    that comes with the role class libraries, are left out."""
    classes, versions = {}, {}
    for file_name, url, root in libraries:
        for lib in root:
            kind = lib.tag.replace(CAEX, "").removesuffix("Lib")
            if kind not in KINDS or not lib.get("Name", "").startswith("AutomationML"):
                continue
            name = lib.get("Name")
            version = tidy(lib.findtext(CAEX + "Version"))
            if name in versions:
                sys.exit(f"{file_name}: library {name} is defined twice")
            versions[name] = version

            def walk(element, path):
                for cls in element.findall(CAEX + kind):
                    cls_path = f"{path}/{cls.get('Name')}"
                    allowed = f"{CAEX}Constraint/{CAEX}NominalScaledType/{CAEX}RequiredValue"
                    values = [tidy(v.text) for v in cls.iterfind(allowed)]
                    classes[cls_path] = {
                        "name": cls.get("Name"),
                        "kind": kind,
                        "library": name,
                        "libraryDescription": tidy(lib.findtext(CAEX + "Description")),
                        "libraryVersion": version,
                        "file": file_name,
                        "url": url,
                        "base": cls.get("RefBaseClassPath"),
                        "description": tidy(cls.findtext(CAEX + "Description")),
                        "attributes": [a.get("Name") for a in cls.findall(CAEX + "Attribute")],
                        "interfaces": [i.get("Name") for i in cls.findall(CAEX + "ExternalInterface")],
                        "attributeDataType": cls.get("AttributeDataType"),
                        "unit": cls.get("Unit"),
                        "values": values,
                    }
                    walk(cls, cls_path)

            walk(lib, name)
    return classes


def resolve(classes, path, cls):
    """The path of the class a RefBaseClassPath refers to. It may name an external file's alias before an @, e.g.
    AutomationMLBaseRoleClassLib@AutomationMLBaseRoleClassLib/AutomationMLBaseRole/Resource, and may be just a
    class's name in the same library, e.g. ControlEquipment."""
    ref = path.split("@", 1)[-1]
    if ref in classes:
        return ref
    named = [p for p, c in classes.items() if c["name"] == ref.rsplit("/", 1)[-1] and c["kind"] == cls["kind"]]
    same_library = [p for p in named if classes[p]["library"] == cls["library"]]
    if len(same_library) == 1:
        return same_library[0]
    if len(named) == 1:
        return named[0]
    sys.exit(f"{cls['library']}: can't resolve {path}")


def an(word):
    return f"an {word}" if word[0] in "AEIOU" else f"a {word}"


def build_libraries(schema, classes, taken):
    """A node for each library class: an object carries its label when it is of the class, through its
    RoleRequirements, the RefBaseClassPath of its ExternalInterface or the RefAttributeType of its Attribute."""
    counts = {}
    for cls in classes.values():
        counts[cls["name"]] = counts.get(cls["name"], 0) + 1
    labels = {}
    for path, cls in classes.items():
        clash = counts[cls["name"]] > 1 or cls["name"] in taken
        labels[path] = cls["name"] + KINDS[cls["kind"]][1] if clash else cls["name"]
    if len(set(labels.values()) | taken) != len(labels) + len(taken):
        sys.exit("library class labels clash")

    nodes = {}
    for path, cls in classes.items():
        label, element = labels[path], KINDS[cls["kind"]][0]
        base = resolve(classes, cls["base"], cls) if cls["base"] else None
        implied = labels[base] if base else element
        kind_text = {"RoleClass": "role class", "InterfaceClass": "interface class", "AttributeType": "attribute type"}[
            cls["kind"]
        ]
        how = {
            "RoleClass": "an InternalElement whose RoleRequirements refer to",
            "InterfaceClass": "an ExternalInterface whose RefBaseClassPath refers to",
            "AttributeType": "an Attribute whose RefAttributeType refers to",
        }[cls["kind"]] + f" this {kind_text}, or to one derived from it"
        library = f"the {cls['library']}" + (f" ({cls['libraryDescription']})" if cls["libraryDescription"] else "")
        props = {
            "id": {
                "type": "STRING",
                "name": "id",
                "description": f"The identifier of the {element}: its ID attribute, unique within the CAEX file, or "
                "one the loader assigns.",
                "reference": schema.page("complexType", "CAEXObject"),
            }
        }
        if cls["kind"] == "AttributeType":
            props["value"] = {
                "type": "STRING",
                "name": "value",
                "description": describe(
                    f"The value of the {cls['name']} attribute"
                    + (f", of data type {cls['attributeDataType']}." if cls["attributeDataType"] else "."),
                    f"The attribute type allows {listed([f'`{v}`' for v in cls['values']])}." if cls["values"] else "",
                ),
                "reference": schema.page("complexType", "AttributeType"),
                **({"one_of": cls["values"]} if cls["values"] else {}),
            }
        nodes[label] = {
            "labels": {"identifier": label, "implied": [implied]},
            "description": describe(
                sentence(cls["description"]),
                f"The AutomationML {kind_text} {cls['name']}, from {library} {cls['libraryVersion']}, at "
                f"{path}." + (f" It is {an(labels[base])}." if base else ""),
                f"Carried by {how}.",
                f"The {kind_text} defines the attributes {listed(cls['attributes'])}." if cls["attributes"] else "",
                f"The {kind_text} defines the external interfaces {listed(cls['interfaces'])}."
                if cls["interfaces"]
                else "",
            ),
            **({"reference": cls["url"]} if cls["url"] else {}),
            "properties": props,
            "constraints": {f"key_{label}": {"type": "KEY", "properties": ["id"], "name": f"id_{label}_key"}},
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (
                        ("kind", cls["kind"]),
                        ("library", cls["library"]),
                        ("libraryVersion", cls["libraryVersion"]),
                        ("path", path),
                        ("caexName", cls["name"] if cls["name"] != label else None),
                        ("attributes", cls["attributes"]),
                        ("interfaces", cls["interfaces"]),
                        ("attributeDataType", cls["attributeDataType"]),
                        ("unit", cls["unit"]),
                        ("file", cls["file"]),
                    )
                    if v not in (None, [], "")
                }
            },
        }
    return nodes


def build(xsd_text, libraries):
    schema = Schema(xsd_text)
    nodes, relationships = build_caex(schema)
    nodes.update(build_libraries(schema, read_libraries(libraries), set(nodes)))

    for node in nodes.values():
        for implied in node["labels"].get("implied", []):
            if implied not in nodes:
                sys.exit(f"supertype {implied} of {node['labels']['identifier']} is not a node")

    return {
        "schema": SCHEMA,
        "version": "2.1",
        "id": "automationml-2.1",
        "name": "AutomationML Edition 2.1 (CAEX 3.0)",
        "description": (
            "AutomationML (IEC 62714), published by AutomationML e.V. (https://www.automationml.org), the neutral XML "
            "data format for exchanging plant engineering data between engineering tools: the plant's hierarchy of "
            "objects, the classes they are instances of, the roles they play, their interfaces and the links between "
            "them, and their attributes. Its top-level format is CAEX 3.0 (IEC 62424:2016). Generated from the CAEX "
            "3.0 XML schema (GitHub AutomationML/AMLEngine2.1) and the AutomationML Edition 2.1 base libraries and "
            "Part 2 role class libraries (automationml.org): each CAEX element is a node, each of its XML attributes "
            "and text elements a property, each element it contains and each path or ID it refers to a relationship, "
            "and each standard role class, interface class and attribute type a node whose label the objects of that "
            "class carry."
        ),
        "nodes": nodes,
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
    model = build(*read_sources(sys.argv[1:]))
    out = Path(__file__).parent
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(yaml(model) + "\n")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships")


if __name__ == "__main__":
    main()
