#!/usr/bin/env python3
"""Generates the DEXPI 2.0.1 ontology from the official DEXPI Specification 2.0.1 model sources.

Usage: python3 generate.py [path/to/Specification-V2.0.1.zip | path/to/spec/src/model]

Without a path, the model sources are downloaded from the DEXPI Specification repository on GitLab. Writes model.json
and model.yaml next to this script. Uses only the Python standard library.
"""

import ast
import json
import re
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

SOURCE_URL = "https://gitlab.com/dexpi/Specification/-/archive/V2.0.1/Specification-V2.0.1.zip"
SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
HTML = "https://dexpi.org/specification/2.0.1/html"
XSD = HTML + "/_static/DEXPI_XML_Schema_doc/schemas/DEXPI_XML_Schema_xsd/complexTypes/Object.html"
MAX_DESCRIPTION = 1024

# The constructors of the model DSL, and what they declare.
CLASS_KINDS = ("CONCRETE_CLASS", "ABSTRACT_CLASS")
VALUE_KINDS = ("AGGREGATED_DATA_TYPE", "ABSTRACT_DATA_TYPE")  # structured value types, not classes
MEMBER_KINDS = ("DATA_PROPERTY", "COMPOSITION_PROPERTY", "REFERENCE_PROPERTY")
LITERAL_KINDS = ("ENUMERATION_LITERAL", "SINGLETON_VALUE")
ENUM_KINDS = ("ENUMERATION", "SINGLETON_TYPE")
PARAM_KINDS = ("DATA_TYPE_PARAMETER",)

BUILTINS = {
    "String": "STRING",
    "AnyURI": "STRING",
    "Double": "FLOAT",
    "Integer": "INTEGER",
    "UnsignedByte": "INTEGER",
    "Boolean": "BOOLEAN",
    "DateTime": "ZONED DATETIME",
    "Undefined": "ANY",
}

ODS_NS = {
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}


def words(text):
    """The words of a CamelCase or space-separated name, e.g. PipingNetworkSystem → Piping, Network, System."""
    return re.findall(r"[A-Z][a-z\d]*|[A-Z]+|[a-z\d]+", text) or re.findall(r"[A-Za-z0-9]+", text)


def camel(name):
    ws = [w.lower() for w in words(name)]
    return ws[0] + "".join(w.capitalize() for w in ws[1:])


def rel_type(name):
    return "HAS_" + "_".join(w.upper() for w in words(name))


def tidy(text):
    """Collapses whitespace and normalises the doubled quotes the model sources use."""
    return re.sub(r"\s+", " ", text.replace("''", "'")).strip()


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
    if lower == upper:
        return f"exactly {lower}"
    return f"between {lower} and {'*' if upper is None else upper}"


def multiplicity(lower, upper):
    return f"{lower}..{'*' if upper is None else upper}"


#----------------------------------
#   Reading the model sources
#----------------------------------


def dotted(node):
    """The dotted name of an Attribute or Name expression, e.g. PIPING.PipingComponent."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def plain(node):
    """A keyword argument's plain value: a constant, or the dotted name of a reference like DEXPI_RDL.NOTE."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.Attribute, ast.Name)):
        return dotted(node)
    return None


def resolve(path, aliases):
    """A dotted name with its leading alias replaced by the model, package or template model it stands for."""
    parts = path.split(".")
    return ".".join([aliases.get(parts[0], parts[0])] + parts[1:])


def declared_list(kw, aliases):
    """The resolved entries of a list keyword argument, e.g. superTypes or templates."""
    return [resolve(dotted(e), aliases) for e in kw.value.elts] if isinstance(kw.value, ast.List) else []


def read_sources(files):
    """Every element and member the model DSL declares, keyed by its qualified name, e.g. Plant.Piping.PipingComponent.

    The sources alias their packages behind short module-level names, e.g. PIPING = Plant.Piping; those aliases are
    file-local, so every reference is resolved to its qualified name while the file is still being read.
    """
    declarations = {}
    for path in sorted(files):
        aliases = {}
        tree = ast.parse(path.read_text())

        # Pass one: what each short module-level name stands for, and which packages and template models exist.
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, (ast.Call, ast.Attribute, ast.Name)):
                continue
            if isinstance(node.value, ast.Call):
                kind = dotted(node.value.func)
                if kind in ("MODEL", "TEMPLATE_MODEL"):
                    name_kw = next((k for k in node.value.keywords if k.arg == "name"), None)
                    target = plain(name_kw.value) if name_kw is not None else None
                elif kind == "PACKAGE":
                    # An X.Y = Z.W = PACKAGE() chain names the package after its Z.W target, e.g. Core.Diagram.
                    attrs = [t for t in node.targets if isinstance(t, ast.Attribute)]
                    target = resolve(dotted(attrs[0]), aliases) if attrs else None
                else:
                    target = None  # e.g. DEFAULT_MULTI_UNDEF_QUALIF_CHECK = 'Check multiplicity, ...'
            else:
                target = resolve(dotted(node.value), aliases)
            if not target or not isinstance(target, str):
                continue
            for t in node.targets:
                if isinstance(t, ast.Name):
                    aliases[t.id] = target
                else:  # the package target of a chain, e.g. Core.Diagram in DIAGRAM = Core.Diagram = PACKAGE()
                    declarations.setdefault(resolve(dotted(t), aliases), {"kind": "PACKAGE", "kw": {}})

        # Pass two: the elements and members the DSL declares, with their references resolved.
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                continue
            kind = dotted(node.value.func)
            if kind not in CLASS_KINDS + VALUE_KINDS + MEMBER_KINDS + LITERAL_KINDS + ENUM_KINDS + PARAM_KINDS:
                continue
            kw = {k.arg: k for k in node.value.keywords if k.arg}
            type_base = type_param = None
            type_undefined = False
            if "type" in kw:  # a type is a name, optionally parameterised, and possibly in union with Undefined
                expr = kw["type"].value
                if isinstance(expr, ast.BinOp):  # e.g. BUILTIN.Undefined | PHYSICAL_QUANTITIES.PhysicalQuantity[...]
                    type_undefined = "Undefined" in (render(expr.left), render(expr.right))
                    expr = expr.right if render(expr.left) == "Undefined" else expr.left
                if isinstance(expr, ast.Subscript):  # e.g. Core.QualifiedValue[{'Type': <physical quantity>}]
                    expr, type_param = expr.value, expr.slice
                type_base = resolve(dotted(expr), aliases) if dotted(expr) else None
            for t in node.targets:
                if not isinstance(t, ast.Attribute):
                    continue
                fq = resolve(dotted(t), aliases)
                if fq in declarations and declarations[fq]["kind"] != "PACKAGE":
                    sys.exit(f"{path.name}: {fq} is declared twice")
                declarations[fq] = {
                    "kind": kind,
                    "kw": kw,
                    "superTypes": declared_list(kw.get("superTypes"), aliases) if "superTypes" in kw else [],
                    "templates": declared_list(kw.get("templates"), aliases) if "templates" in kw else [],
                    "type_base": type_base,
                    "type_param": type_param,
                    "type_undefined": type_undefined,
                }
    return declarations


def read_enumerations(files, declarations):
    """The literals of every enumeration: those the DSL declares, and those its .ods spreadsheets define."""
    literals = {}
    for fq, decl in declarations.items():
        if decl["kind"] in ENUM_KINDS:
            literals[fq] = []
        elif decl["kind"] in LITERAL_KINDS:
            literals.setdefault(".".join(fq.split(".")[:-1]), []).append(fq.split(".")[-1])
    for path in sorted(files):
        if path.suffix != ".ods" or "enumeration" not in path.name:
            continue  # the unit-of-measure spreadsheet defines unit data types, not enumerations
        package = f"{'Plant' if 'plant' in path.name.lower() else 'Process'}.Enumerations"
        root = ET.fromstring(zipfile.ZipFile(path).read("content.xml"))
        name = None
        for row in root.findall(".//table:table-row", ODS_NS):
            cells = []
            for cell in row.findall("table:table-cell", ODS_NS):
                text = "".join(p.text or "" for p in cell.findall(".//text:p", ODS_NS))
                cells += [text] * int(cell.get(f"{{{ODS_NS['table']}}}number-columns-repeated", "1"))
            if cells and cells[0]:
                name = cells[0]
            elif name and len(cells) > 1 and cells[1]:
                literals.setdefault(f"{package}.{name}", []).append(cells[1])
    return literals


def read_model(source):
    """The model sources: a downloaded or given zip archive, an extracted repository, or its src/model directory."""
    if source.is_dir():
        root = source if (source / "Core.py").exists() or not (source / "src").is_dir() else next(
            (d for d in source.rglob("src/model") if d.is_dir()), source
        )
        return sorted(root.rglob("*.py")), sorted(root.rglob("*.ods"))
    out = Path(tempfile.mkdtemp())
    zipfile.ZipFile(source).extractall(out)
    root = next((d for d in out.rglob("src/model") if d.is_dir()), out)
    return sorted(root.rglob("*.py")), sorted(root.rglob("*.ods"))


#----------------------------------
#   The DEXPI model as data
#----------------------------------


def render(expr):
    """A data type expression as the specification writes it, e.g. PhysicalQuantity with UnitType → LengthUnit."""
    if isinstance(expr, ast.BinOp):
        left, right = render(expr.left), render(expr.right)
        if left == "Undefined":
            return right
        if right == "Undefined":
            return left
        return f"{left} | {right}"
    if isinstance(expr, ast.Dict):  # the {'Type': <type>} a QualifiedValue is parameterised with
        return ", ".join(f"{render(k)} → {render(v)}" for k, v in zip(expr.keys, expr.values))
    if isinstance(expr, ast.Subscript):  # e.g. PhysicalQuantity[{'UnitType': LengthUnit}]
        pairs = zip(expr.slice.keys, expr.slice.values) if isinstance(expr.slice, ast.Dict) else []
        entries = ", ".join(f"{render(k)} → {render(v)}" for k, v in pairs)
        return f"{render(expr.value)} with {entries}"
    if isinstance(expr, ast.Constant):
        return str(expr.value)
    return dotted(expr).split(".")[-1]  # BUILTIN.Undefined → Undefined, PHYSICAL_QUANTITIES.LengthUnit → LengthUnit


def example(expr):
    """An exampleValue expression as short text, e.g. PhysicalQuantity(Value=40.0, Unit=...Metre) → 40.0 Metre."""
    if isinstance(expr, ast.Constant):
        value = expr.value
        return "" if value is None else (value.isoformat(sep=" ") if hasattr(value, "isoformat") else str(value))
    if isinstance(expr, (ast.Attribute, ast.Name)):
        return dotted(expr).split(".")[-1]
    if isinstance(expr, ast.List):
        return ", ".join(example(e) for e in expr.elts)
    if isinstance(expr, ast.Call):
        name = dotted(expr.func).split(".")[-1]
        kw = {k.arg: k for k in expr.keywords if k.arg}
        if name in ("PhysicalQuantity", "PhysicalQuantityVector") and "Value" in kw:
            value = example(kw["Value"].value)
            unit = example(kw["Unit"].value) if "Unit" in kw else ""
            return f"{value} {unit}".strip()
        if name == "QualifiedValue" and "Value" in kw:
            return example(kw["Value"].value)
        if name == "MultiLanguageString" and "SingleLanguageStrings" in kw:
            strings = kw["SingleLanguageStrings"].value
            strings = strings.elts if isinstance(strings, ast.List) else [strings]
            return "; ".join(example(s) for s in strings)
        if name == "SingleLanguageString" and "Value" in kw:
            language = example(kw["Language"].value) if "Language" in kw else ""
            return f"{language}: {example(kw['Value'].value)}".strip()
        return ", ".join(f"{k}={example(kw[k].value)}" for k in kw)
    return tidy(ast.unparse(expr))


def clean(text, owner, self_name):
    """A description in reStructuredText, as plain English: the roles become names, the placeholders text."""

    def role(match):
        content = match.group(1)
        if "<" in content:  # e.g. `Notes <Core.Note>`: the part before the angle bracket is what is displayed
            return content[: content.index("<")].strip()
        return content.lstrip("~!").strip().rsplit(".", 1)[-1]  # e.g. `~Core.Note` → Note

    def placeholder(match):
        who, part = match.group(1), match.group(2)
        return part or (self_name if who == "SELF" else owner)

    text = re.sub(r":[\w:.-]+:`([^`]*)`", role, text)
    text = re.sub(r"``([^`]*)``", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"<!?(OWNER|SELF)(?:\.([A-Za-z0-9_]+))?>", placeholder, text)
    return tidy(text)


def page(fq):
    """The specification page of an element, e.g. Plant.Piping.PipingComponent → models/Plant/Piping/PipingComponent."""
    parts = fq.split(".")
    return f"{HTML}/models/{'/'.join(parts[:-1])}/{parts[-1]}.html"


def anchor(fq):
    return f"{page(fq.rsplit('.', 1)[0])}#sp:{fq.lower()}"


def element(decl, name, default=None):
    return plain(decl["kw"][name].value) if name in decl["kw"] else default


def description_of(decl, owner, self_name):
    """A declaration's description as plain English; description=AUTO means the specification generates it from
    the reference data library, so there is nothing to clean."""
    text = element(decl, "description", "")
    return "" if text in (None, "AUTO") else clean(text, owner, self_name)


def ends(lower, upper):
    """The count constraints of a relationship end, from a multiplicity. Zero or more is unconstrained."""
    if (lower, upper) == (1, 1):
        return {"count": 1}
    if (lower, upper) == (0, 1):
        return {"max_count": 1}
    if (lower, upper) == (0, None):
        return {}
    return {k: v for k, v in (("min_count", lower), ("max_count", upper)) if v or v is not None}


def build(py_files, ods_files):
    declarations = read_sources(py_files)
    literals = read_enumerations(ods_files, declarations)

    classes = {fq: d for fq, d in declarations.items() if d["kind"] in CLASS_KINDS}
    values = {fq for fq, d in declarations.items() if d["kind"] in VALUE_KINDS}
    parameters = {fq for fq, d in declarations.items() if d["kind"] in PARAM_KINDS}

    def members_of(fq, *kinds):
        prefix = fq + "."
        return [(name, d) for name, d in declarations.items() if name.startswith(prefix) and d["kind"] in kinds]

    def node_of(fq):
        return fq.split(".")[-1]

    def property_type(decl, fq):
        """(Neo4j type, allowed values, a sentence about the DEXPI type, the DEXPI type as text) of a data property."""
        text = render(decl["kw"]["type"].value)
        base = decl["type_base"]
        one_of, type_sentence = [], ""
        if base.startswith("BUILTIN.") and base.split(".")[-1] in BUILTINS:
            neo4j = BUILTINS[base.split(".")[-1]]
        elif base in literals:
            one_of = [camel(l) for l in literals[base]]
            neo4j = "STRING"
        elif base in parameters:  # QualifiedValue.Value, whose type is the QualifiedValue's type parameter
            neo4j, type_sentence = "ANY", "May hold a value of any DEXPI data type."
        elif base in values:  # a structured value type such as MultiLanguageString or PhysicalQuantity
            neo4j, type_sentence = "STRING", f"Values of DEXPI type {text}."
        else:
            sys.exit(f"{fq}: unknown data type {base}")
        if element(decl, "upper") is None and neo4j != "ANY":  # a multi-valued property is a list
            neo4j = f"LIST<{neo4j}>"
        return neo4j, one_of, type_sentence, (f"Undefined | {text}" if decl["type_undefined"] else text)

    nodes, relationships = {}, {}
    for fq, decl in classes.items():
        name = node_of(fq)
        module, package = fq.split(".")[0], fq.rsplit(".", 1)[0]
        # The class model has no identifiers; the exchange format identifies each object by its id attribute.
        properties = {
            "id": {
                "type": "STRING",
                "name": "id",
                "description": f"The identifier of the {name}: the id attribute of its Object element in a DEXPI "
                "XML exchange file. Unique within that file.",
                "reference": XSD,
                "extensions": {"custom": {"dexpiType": "ID"}},
            }
        }
        constraints = {f"key_{name}": {"type": "KEY", "properties": ["id"], "name": f"id_{name}_key"}}

        # The members the class declares, then the template properties it applies, under its own name.
        own = members_of(fq, *MEMBER_KINDS)
        applied = [
            (fq + "." + node_of(t), declarations[t])
            for t in decl["templates"]
            if t in declarations and declarations[t]["kind"] in MEMBER_KINDS
        ]

        for member, mdecl in [(m, d) for m, d in own + applied if d["kind"] == "DATA_PROPERTY"]:
            member_name = member.rsplit(".", 1)[-1]
            pid = camel(member_name)
            if pid in properties:
                continue  # the class's own property of the same name wins
            lower, upper = element(mdecl, "lower", 0), element(mdecl, "upper", 1)
            neo4j, one_of, type_sentence, dexpi = property_type(mdecl, member)
            example_text = tidy(example(mdecl["kw"]["exampleValue"].value)) if "exampleValue" in mdecl["kw"] else ""
            prop = {
                "type": neo4j,
                "name": pid,
                "description": describe(
                    sentence(description_of(mdecl, name, member_name)),
                    f"Multiplicity {multiplicity(lower, upper)}." if (lower, upper) != (0, 1) else "",
                    f"e.g. `{example_text}`." if example_text else "",
                    type_sentence if "String" not in type_sentence else "",
                ),
                "reference": anchor(member),
                "extensions": {
                    "custom": {
                        k: v
                        for k, v in (
                            ("rdl", element(mdecl, "rdl")),
                            ("lower", lower),
                            ("upper", upper),
                            ("dexpiType", dexpi),
                            ("isOrdered", element(mdecl, "isOrdered")),
                            ("isUnique", element(mdecl, "isUnique")),
                        )
                        if v is not None
                    }
                },
            }
            if one_of:
                prop["one_of"] = one_of
            properties[pid] = prop
            if (lower, upper) == (1, 1):
                constraints[f"exists_{name}_{pid}"] = {
                    "type": "EXISTS",
                    "properties": [pid],
                    "name": f"{pid}_{name}_exists",
                }

        nodes[name] = {
            "labels": {
                "identifier": name,
                **({"implied": [node_of(s) for s in decl["superTypes"]]} if decl["superTypes"] else {}),
            },
            **(
                {"description": describe(description_of(decl, name, name))}
                if description_of(decl, name, name)
                else {}
            ),
            "reference": page(fq),
            "properties": properties,
            "constraints": constraints,
            "extensions": {
                "custom": {
                    k: v
                    for k, v in (
                        ("module", module),
                        ("package", package),
                        ("abstract", decl["kind"] == "ABSTRACT_CLASS"),
                        ("rdl", element(decl, "rdl")),
                        ("templates", [node_of(t) for t in decl["templates"]]),
                    )
                    if v not in (None, False, [])
                }
            },
        }

        # Composition and reference properties, the class's own and those of the templates it applies.
        for member, mdecl in [(m, d) for m, d in own + applied if d["kind"] in MEMBER_KINDS[1:]]:
            member_name = member.rsplit(".", 1)[-1]
            target = mdecl["type_base"]
            if target not in classes:
                sys.exit(f"{member}: {target} is not a class")
            rtype = rel_type(member_name)
            rid = f"{name}_{rtype}_{node_of(target)}"
            while rid in relationships:
                rid += "_2"
            lower, upper = element(mdecl, "lower", 0), element(mdecl, "upper", 1)
            declared = element(mdecl, "oppositeLower"), element(mdecl, "oppositeUpper")
            composition = mdecl["kind"] == "COMPOSITION_PROPERTY"
            opposite = (0, 1) if composition else declared  # a part belongs to at most one owner
            # A count constrains the nodes at its end: the owner's multiplicity bounds the relationships each owner
            # starts, and the opposite multiplicity those each target ends.
            relationships[rid] = {
                "type": rtype,
                "from": {"node": name, **ends(lower, upper)},
                "to": {"node": node_of(target), **(ends(*opposite) if opposite != (None, None) else {})},
                "description": describe(
                    sentence(description_of(mdecl, name, member_name)),
                    f"Each {name} has {phrase(lower, upper)} {node_of(target)}."
                    + (
                        f" Each {node_of(target)} has {phrase(*opposite)} {name}."
                        if opposite != (None, None) and not composition
                        else ""
                    ),
                    f"A composition: each {node_of(target)} is part of at most one owner and is deleted with it."
                    if composition
                    else "",
                ),
                "reference": anchor(member),
                "extensions": {
                    "custom": {
                        k: v
                        for k, v in (
                            ("composition", mdecl["kind"] == "COMPOSITION_PROPERTY"),
                            ("rdl", element(mdecl, "rdl")),
                            ("lower", lower),
                            ("upper", upper),
                            ("oppositeLower", declared[0]),
                            ("oppositeUpper", declared[1]),
                            ("typeParameter", render(mdecl["type_param"]) if mdecl["type_param"] is not None else None),
                            ("isOrdered", element(mdecl, "isOrdered")),
                        )
                        if v is not None
                    }
                },
            }

    # A supertype or relationship target that no node was built for means the sources were misread.
    for node in nodes.values():
        for implied in node["labels"].get("implied", []):
            if implied not in nodes:
                sys.exit(f"supertype {implied} of {node['labels']['identifier']} is not a class")
    for rel in relationships.values():
        for end in (rel["from"], rel["to"]):
            if end["node"] not in nodes:
                sys.exit(f"relationship {rel['type']} points at {end['node']}, which is not a class")

    return {
        "schema": SCHEMA,
        "version": "2.0.1",
        "id": "dexpi-2.0.1",
        "name": "DEXPI 2.0.1",
        "description": (
            "The DEXPI (Data Exchange in the Process Industry) P&ID Specification 2.0.1 class model, published by "
            "the DEXPI Initiative (https://dexpi.org/specifications/). DEXPI standardises the exchange of piping and "
            "instrumentation diagram data between engineering tools: the conceptual model of a plant and its process "
            "(equipment, piping, instrumentation, plant structure, process steps and connections), the quantities "
            "and properties that describe them, and the diagrams and graphical elements that represent them. "
            "Generated from the specification's model sources (https://gitlab.com/dexpi/Specification, tag "
            "V2.0.1): each class is a node, each data property a property, each composition or reference property a "
            "relationship from the owning class to its target, and each supertype an implied label."
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
    if len(sys.argv) > 1:
        source = Path(sys.argv[1])
    else:
        source = Path(tempfile.mkdtemp()) / "Specification-V2.0.1.zip"
        # GitLab rejects some user agents.
        request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request) as response:
            source.write_bytes(response.read())
    model = build(*read_model(source))
    out = Path(__file__).parent
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(yaml(model) + "\n")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships")


if __name__ == "__main__":
    main()
