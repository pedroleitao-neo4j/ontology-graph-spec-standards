#!/usr/bin/env python3
"""Writes a Cypher script for ontologies in the graph spec format: the model's constraints, then sample data.

Usage: python3 cypher.py [FOLDER ...]

For each folder given, or every folder below this script that holds both a model.json and a sample.json but no
crosswalk.json, whose Cypher scripts crosswalk.py writes, reads the
model and the sample data, checks the data against the model and writes model.cypher beside them. The script creates
the model's constraints, then merges the sample nodes and relationships, so it can be run more than once.

The sample data, sample.json, describes a scenario in the standard's domain:

    {
      "scenario": "The GDPR, as published in the Official Journal ...",   what the data describes, in prose
      "nodes": {
        "gdpr": {                                          a node, by an id local to this file
          "node": "LegalResource",                         the model node it is, or a list of them for a node of
                                                           several kinds; the node carries their labels and the
                                                           labels they imply
          "properties": {"uri": "...", "date_document": "2016-04-27"}
        }, ...
      },
      "relationships": [
        ["gdpr", "TYPE_DOCUMENT", "regulation"],           a relationship from one node to another, by type,
        ["consolidated", "CONSOLIDATES", "gdpr", {...}]    with its properties, if any, last
      ],
      "open": {                                            model relationships, by id, whose minimum counts the
        "TemporalOccurrence_IMMEDIATELY_AFTER_...": "..."  data leaves open, and why: e.g. that no finite data
      }                                                    can meet them; optional
    }

Every node must be a model node, carrying the labels it implies. Its properties must be ones the model defines for
one of its labels, of their type, in their one_of and matching their pattern, and the key and existing properties of
every label it carries must be there, with no key repeated. Every relationship must be one the model defines between
a label of its start and a label of its end, and the counts at both ends must hold for every node of the data, but
for the minimum counts of the relationships the data leaves open. Values
are JSON: a DATE, ZONED DATETIME, LOCAL DATETIME or DURATION as its ISO 8601 string, e.g. "2016-04-27", and a list
type as a list. Uses only the Python standard library.
"""

import json
import re
import sys
import textwrap
from collections import Counter, defaultdict
from pathlib import Path

IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# The Cypher function that makes each temporal type from its ISO 8601 string, and the pattern the string must match
TEMPORAL = {
    "DATE": ("date", r"\d{4}-\d{2}-\d{2}"),
    "ZONED DATETIME": ("datetime", r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})"),
    "LOCAL DATETIME": ("localdatetime", r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?"),
    "DURATION": ("duration", r"-?P(?=\d|T\d)(\d+Y)?(\d+M)?(\d+W)?(\d+D)?(T(\d+H)?(\d+M)?(\d+(\.\d+)?S)?)?"),
}


def name(identifier):
    """A label, type, property or constraint name, quoted if it needs to be."""
    return identifier if IDENTIFIER.fullmatch(identifier) else "`" + identifier.replace("`", "``") + "`"


def string(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'"


def literal(value, kind):
    """The Cypher literal of a sample value of a property type."""
    if kind.startswith("LIST<"):
        return "[" + ", ".join(literal(item, kind[5:-1]) for item in value) + "]"
    if kind in TEMPORAL:
        return f"{TEMPORAL[kind][0]}({string(value)})"
    if kind == "FLOAT":
        return repr(float(value))
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return string(value)
    if isinstance(value, list):
        return "[" + ", ".join(literal(item, "ANY") for item in value) + "]"
    return repr(value)


def map_literal(values, definitions):
    return "{" + ", ".join(f"{name(key)}: {literal(value, definitions[key]['type'])}" for key, value in values.items()) + "}"


def type_errors(value, definition):
    """What is wrong with a sample value for a property definition, if anything."""
    kind = definition["type"]
    if kind.startswith("LIST<"):
        if not isinstance(value, list):
            return [f"{value!r} isn't a list"]
        return [error for item in value for error in type_errors(item, {**definition, "type": kind[5:-1]})]
    if kind == "ANY":
        return []
    if kind == "STRING" and not isinstance(value, str):
        return [f"{value!r} isn't a string"]
    if kind == "INTEGER" and (isinstance(value, bool) or not isinstance(value, int)):
        return [f"{value!r} isn't an integer"]
    if kind == "FLOAT" and (isinstance(value, bool) or not isinstance(value, (int, float))):
        return [f"{value!r} isn't a number"]
    if kind == "BOOLEAN" and not isinstance(value, bool):
        return [f"{value!r} isn't a boolean"]
    if kind in TEMPORAL and not (isinstance(value, str) and re.fullmatch(TEMPORAL[kind][1], value)):
        return [f"{value!r} isn't an ISO 8601 {kind.lower()}"]
    if "one_of" in definition and value not in definition["one_of"]:
        return [f"{value!r} isn't one of {', '.join(definition['one_of'])}"]
    if "pattern" in definition and isinstance(value, str):
        try:
            pattern = re.compile(definition["pattern"])
        except re.error:
            return []  # a pattern in a regex dialect Python doesn't read
        if not pattern.fullmatch(value):
            return [f"{value!r} doesn't match {definition['pattern']}"]
    return []


def labels_of(model, kinds):
    """The labels of a node of the given model nodes: theirs, then every label those imply, most specific first."""
    labelled, labels = by_label(model), []

    def add(label):
        if label in labels:
            return
        labels.append(label)
        node = labelled.get(label, {})
        for implied in node.get("labels", {}).get("implied", []):
            add(implied)

    for kind in kinds:
        add(model["nodes"][kind]["labels"].get("identifier", kind))
    return labels


def by_label(model):
    return {node["labels"].get("identifier", key): node for key, node in model["nodes"].items()}


def node_key(model, kind):
    """The properties of the key a node of a model node is merged on."""
    for constraint in model["nodes"][kind].get("constraints", {}).values():
        if constraint["type"] in ("KEY", "UNIQUE"):
            return constraint["properties"]
    return []


def check(model, sample):
    """Every way the sample data breaks the model."""
    errors = []
    nodes, labelled = model["nodes"], by_label(model)
    labels = {}
    for local, node in sample["nodes"].items():
        kinds = node["node"] if isinstance(node["node"], list) else [node["node"]]
        unknown = [kind for kind in kinds if kind not in nodes]
        if unknown:
            errors.append(f"node {local}: {', '.join(unknown)} isn't a node of the model")
            continue
        labels[local] = labels_of(model, kinds)
        definitions = {}
        for label in labels[local]:  # most specific first, so a subclass's definition of a property wins
            for key, definition in labelled.get(label, {}).get("properties", {}).items():
                definitions.setdefault(key, definition)
        values = node.get("properties", {})
        for key, value in values.items():
            if key not in definitions:
                errors.append(f"node {local}: {key} isn't a property of {', '.join(labels[local])}")
            else:
                errors.extend(f"node {local}: {key}: {error}" for error in type_errors(value, definitions[key]))
        for label in labels[local]:
            for constraint in labelled.get(label, {}).get("constraints", {}).values():
                missing = [key for key in constraint["properties"] if key not in values]
                if missing and constraint["type"] in ("KEY", "EXISTS"):
                    errors.append(f"node {local}: {label} must have {', '.join(missing)}")
        if not node_key(model, kinds[0]):
            errors.append(f"node {local}: {kinds[0]} has no key to merge it on")
    seen = {}
    for local, node in sample["nodes"].items():
        for label in labels.get(local, []):
            for constraint in labelled.get(label, {}).get("constraints", {}).values():
                if constraint["type"] in ("KEY", "UNIQUE"):
                    values = node.get("properties", {})
                    if all(key in values for key in constraint["properties"]):
                        key = (label, tuple(constraint["properties"]), json.dumps([values[k] for k in constraint["properties"]]))
                        if key in seen:
                            errors.append(f"nodes {seen[key]} and {local} have the same {label} key")
                        seen[key] = local

    counts = defaultdict(Counter)  # model relationship id -> end ("from", local) or ("to", local) -> count
    pairs = Counter()
    for index, relationship in enumerate(sample["relationships"]):
        start, kind, end = relationship[:3]
        where = f"relationship {index} ({start})-[:{kind}]->({end})"
        if start not in labels or end not in labels:
            errors.append(f"{where}: {start if start not in labels else end} isn't a node of the data")
            continue
        matches = [
            (key, defined) for key, defined in model["relationships"].items()
            if defined["type"] == kind
            and nodes[defined["from"]["node"]]["labels"].get("identifier") in labels[start]
            and nodes[defined["to"]["node"]]["labels"].get("identifier") in labels[end]
        ]
        if not matches:
            errors.append(f"{where}: the model has no {kind} between {', '.join(labels[start])} and {', '.join(labels[end])}")
            continue
        for key, _ in matches:
            counts[key][("from", start)] += 1
            counts[key][("to", end)] += 1
        definitions = {}
        for _, defined in matches:
            definitions.update(defined.get("properties", {}))
        values = relationship[3] if len(relationship) > 3 else {}
        for key, value in values.items():
            if key not in definitions:
                errors.append(f"{where}: {key} isn't a property of {kind}")
            else:
                errors.extend(f"{where}: {key}: {error}" for error in type_errors(value, definitions[key]))
        for _, defined in matches:
            for constraint in defined.get("constraints", {}).values():
                missing = [key for key in constraint["properties"] if key not in values]
                if missing and constraint["type"] in ("KEY", "EXISTS"):
                    errors.append(f"{where}: {kind} must have {', '.join(missing)}")
        pair = (start, kind, end, json.dumps(rel_key(model, kind, values)))
        if pairs[pair]:
            errors.append(f"{where}: repeated, and would be merged into one")
        pairs[pair] += 1

    open_ends = sample.get("open", {})
    errors.extend(f"open: {key} isn't a relationship of the model" for key in open_ends if key not in model["relationships"])
    for key, defined in model["relationships"].items():
        for end in ("from", "to"):
            bounds = defined[end]
            low = None if key in open_ends else bounds.get("count", bounds.get("min_count"))
            high = bounds.get("count", bounds.get("max_count"))
            if low is None and high is None:
                continue
            label = nodes[defined[end]["node"]]["labels"].get("identifier")
            for local in sample["nodes"]:
                if label not in labels.get(local, []):
                    continue
                count = counts[key][(end, local)]
                if (low is not None and count < low) or (high is not None and count > high):
                    other = nodes[defined["to" if end == "from" else "from"]["node"]]["labels"].get("identifier")
                    pattern = f"-[:{defined['type']}]->(:{other})" if end == "from" else f"<-[:{defined['type']}]-(:{other})"
                    allowed = f"exactly {low}" if low == high else f"at least {low}" if high is None else f"at most {high}" if low is None else f"{low} to {high}"
                    errors.append(f"node {local}: has {count} {pattern}, but must have {allowed}")
    return errors


def rel_key(model, kind, values):
    for defined in model["relationships"].values():
        if defined["type"] == kind:
            for constraint in defined.get("constraints", {}).values():
                if constraint["type"] in ("KEY", "UNIQUE"):
                    return {key: values[key] for key in constraint["properties"] if key in values}
    return {}


def comment(text, width=118):
    return "\n".join(textwrap.wrap(text, width, initial_indent="// ", subsequent_indent="// ")) if text else "//"


def schema(model):
    """The statements creating the model's constraints."""
    lines, names = [], set()

    def unique(proposed):
        candidate, suffix = proposed, 2
        while candidate in names:
            candidate, suffix = f"{proposed}_{suffix}", suffix + 1
        names.add(candidate)
        return name(candidate)

    for key, node in model["nodes"].items():
        label = name(node["labels"].get("identifier", key))
        for constraint_id, constraint in node.get("constraints", {}).items():
            properties = constraint["properties"]
            if constraint["type"] == "EXISTS":
                for prop in properties:
                    constraint_name = constraint.get("name") if len(properties) == 1 else None
                    lines.append(f"CREATE CONSTRAINT {unique(constraint_name or f'{prop}_{key}_exists')} IF NOT EXISTS "
                                 f"FOR (n:{label}) REQUIRE n.{name(prop)} IS NOT NULL;")
                continue
            target = ", ".join(f"n.{name(prop)}" for prop in properties)
            target = target if len(properties) == 1 else f"({target})"
            requirement = {"KEY": "IS NODE KEY", "UNIQUE": "IS UNIQUE"}.get(constraint["type"])
            if requirement is None:
                continue  # property types are checked by the data, not a constraint
            lines.append(f"CREATE CONSTRAINT {unique(constraint.get('name') or f'{constraint_id}_{key}')} IF NOT EXISTS "
                         f"FOR (n:{label}) REQUIRE {target} {requirement};")
    done = set()
    for relationship in model["relationships"].values():
        kind = relationship["type"]
        for constraint_id, constraint in relationship.get("constraints", {}).items():
            properties = constraint["properties"]
            if (kind, constraint["type"], tuple(properties)) in done:
                continue
            done.add((kind, constraint["type"], tuple(properties)))
            if constraint["type"] == "EXISTS":
                for prop in properties:
                    lines.append(f"CREATE CONSTRAINT {unique(f'{prop}_{kind}_exists')} IF NOT EXISTS "
                                 f"FOR ()-[r:{name(kind)}]-() REQUIRE r.{name(prop)} IS NOT NULL;")
                continue
            requirement = {"KEY": "IS RELATIONSHIP KEY", "UNIQUE": "IS UNIQUE"}.get(constraint["type"])
            if requirement is None:
                continue
            target = ", ".join(f"r.{name(prop)}" for prop in properties)
            target = target if len(properties) == 1 else f"({target})"
            proposed = constraint.get("name") or f"{'_'.join(properties)}_{kind}_{constraint['type'].lower()}"
            lines.append(f"CREATE CONSTRAINT {unique(proposed)} IF NOT EXISTS "
                         f"FOR ()-[r:{name(kind)}]-() REQUIRE {target} {requirement};")
    return lines


def data(model, sample):
    """The statements merging the sample nodes and relationships."""
    labelled, lines = by_label(model), []
    matchers, definitions_of = {}, {}
    for local, node in sample["nodes"].items():
        kinds = node["node"] if isinstance(node["node"], list) else [node["node"]]
        labels = labels_of(model, kinds)
        definitions = {}
        for label in labels:  # most specific first, so a subclass's definition of a property wins
            for key, definition in labelled[label].get("properties", {}).items():
                definitions.setdefault(key, definition)
        definitions_of[local] = definitions
        values = node.get("properties", {})
        key = node_key(model, kinds[0])
        matchers[local] = f"{name(labels[0])} {map_literal({k: values[k] for k in key}, definitions)}"
        rest = {k: v for k, v in values.items() if k not in key}
        sets = [f"n:{':'.join(name(label) for label in labels[1:])}"] if labels[1:] else []
        if rest:
            sets.append(f"n += {map_literal(rest, definitions)}")
        lines.append(f"MERGE (n:{matchers[local]})" + (f" SET {', '.join(sets)}" if sets else "") + ";")
    lines.append("")
    for relationship in sample["relationships"]:
        start, kind, end = relationship[:3]
        values = relationship[3] if len(relationship) > 3 else {}
        definitions = {}
        for defined in model["relationships"].values():
            if defined["type"] == kind:
                for key, definition in defined.get("properties", {}).items():
                    definitions.setdefault(key, definition)
        key = rel_key(model, kind, values)
        rest = {k: v for k, v in values.items() if k not in key}
        variable = "r" if rest else ""
        merged = f"(a)-[{variable}:{name(kind)}{' ' + map_literal(key, definitions) if key else ''}]->(b)"
        line = f"MATCH (a:{matchers[start]}), (b:{matchers[end]}) MERGE {merged}"
        if rest:
            line += f" SET r += {map_literal(rest, definitions)}"
        lines.append(line + ";")
    return lines


def write(folder):
    model = json.loads((folder / "model.json").read_text())
    sample = json.loads((folder / "sample.json").read_text())
    errors = check(model, sample)
    if errors:
        print(f"{folder}: {len(errors)} problems with sample.json", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return False
    edition = "Enterprise Edition, for its node key and property existence constraints"
    text = "\n".join([
        f"// {model['name']}: the graph model and sample data",
        "//",
        "// Generated by ../../cypher.py from model.json and sample.json. Edit those and regenerate, rather than this file.",
        "//",
        comment(sample["scenario"]),
        "//",
        *[line for key, reason in sample.get("open", {}).items()
          for line in (comment(f"The data leaves the minimum counts of {key} open: {reason}"), "//")],
        comment(f"Run it against an empty database of Neo4j 5 or later, {edition}, e.g. with cypher-shell -f "
                "model.cypher. It merges every node and relationship, so it can be run again."),
        "",
        "// The model: its constraints",
        "",
        *schema(model),
        "",
        "// The sample data",
        "",
        *data(model, sample),
        "",
    ])
    (folder / "model.cypher").write_text(text)
    print(f"{folder / 'model.cypher'}: {len(sample['nodes'])} nodes, {len(sample['relationships'])} relationships")
    return True


def main():
    here = Path(__file__).resolve().parent
    folders = [Path(arg).resolve() for arg in sys.argv[1:]] or sorted(
        path.parent for path in here.rglob("sample.json")
        if (path.parent / "model.json").exists() and not (path.parent / "crosswalk.json").exists())
    results = [write(folder) for folder in folders]
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
