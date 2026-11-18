#!/usr/bin/env python3
"""Builds crosswalks between ontologies in the graph spec format: how their classes map, and data linking them.

Usage: python3 crosswalk.py [FOLDER ...]

For each folder given, or every folder below this script that holds a crosswalk.json, reads the crosswalk, the models
and sample data of the standards it joins, and the crosswalk's own sample.json, checks them and writes beside them:

    model.json, model.yaml   the crosswalk as a graph spec model: the nodes it maps, from every standard, and a
                             relationship for each mapping, linking the data of one standard to the other's
    diagram.json             how visualise.py draws model.json as model.svg, one area per standard
    mappings.sssom.tsv       the mappings in the Simple Standard for Sharing Ontological Mappings
    model.cypher             a Cypher script loading every standard's constraints and sample data, the crosswalk's
                             extra data and the links between them into one database

Standards share many labels, e.g. Person or Role, with keys and meanings of their own, and relationship types, e.g.
USES, so in a crosswalk every label and relationship type of a standard is namespaced by its prefix, as neosemantics
does: Tag in CFIHOS becomes cfihos__Tag and USES in STIX stix__USES. Only the links the crosswalk adds go unprefixed.

The crosswalk, crosswalk.json:

    {
      "id": "plant-engineering",
      "name": "Plant engineering: CFIHOS 2.0 and DEXPI 2.0.1",
      "description": "...",                                what the crosswalk joins, and why, in prose
      "standards": {                                         the standards it joins, by a prefix of its own
        "cfihos": "industrial/CFIHOS2.0",                    for each, the folder of the standard, from here
        "dexpi": "industrial/DEXPI"
      },
      "mappings": [
        {
          "subject": "cfihos:Tag",                           a node of one standard,
          "predicate": "closeMatch",                         how it maps, as SKOS does: exactMatch, closeMatch,
                                                             broadMatch (the object is broader), narrowMatch or
                                                             relatedMatch
          "object": "dexpi:TaggedPlantItem",                 to a node of another
          "link": "SAME_AS",                                 the relationship from a subject node to an object node
                                                             in data; SAME_AS when they describe the same thing,
                                                             the default but for relatedMatch, which is RELATED_TO
          "properties": {"tagName": "tagName"},              properties of the subject and object that hold the
                                                             same value, which every linked pair must agree on
          "comment": "...",                                  why the nodes map, and where they differ
          "source": "https://..."                            where the mapping comes from, if anyone publishes it
        }, ...
      ]
    }

The sample data, sample.json, is in the format cypher.py describes, but for the ids it uses: the data of every
standard is included, each node by its prefix and its id in that standard's sample.json, e.g. "cfihos:tag-P-2001A".
The crosswalk's sample.json adds the links, by their types, and, where the standards' samples don't describe the same
things, nodes of either standard, by its prefix and node name, e.g. {"node": "dexpi:CentrifugalPump"}, with
relationships of their standard by prefix and type, e.g. "dexpi:ASSEMBLY". Every link must join nodes of two
standards that a mapping joins, and the nodes it links must agree on the properties the mapping names. Uses only
the Python standard library.
"""

import json
import sys
from pathlib import Path

import cypher

HERE = Path(__file__).resolve().parent
SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
REPOSITORY = "https://github.com/pedroleitao-neo4j/ontology-graph-spec-standards/blob/main/"
PREDICATES = ("exactMatch", "closeMatch", "broadMatch", "narrowMatch", "relatedMatch")
SEPARATOR = "__"


def qualified(prefix, name):
    return f"{prefix}{SEPARATOR}{name}"


def namespaced(model, prefix, title):
    """The model with its node names, labels, relationship ids and types and constraint names prefixed."""
    nodes = {}
    for key, node in model["nodes"].items():
        node = json.loads(json.dumps(node))
        labels = node["labels"]
        labels["identifier"] = qualified(prefix, labels.get("identifier", key))
        if "implied" in labels:
            labels["implied"] = [qualified(prefix, label) for label in labels["implied"]]
        for constraint in node.get("constraints", {}).values():
            if "name" in constraint:
                constraint["name"] = qualified(prefix, constraint["name"])
        node.setdefault("extensions", {}).setdefault("custom", {})["standard"] = title
        nodes[qualified(prefix, key)] = node
    relationships = {}
    for key, relationship in model["relationships"].items():
        relationship = json.loads(json.dumps(relationship))
        relationship["type"] = qualified(prefix, relationship["type"])
        for end in ("from", "to"):
            relationship[end]["node"] = qualified(prefix, relationship[end]["node"])
        for constraint in relationship.get("constraints", {}).values():
            if "name" in constraint:
                constraint["name"] = qualified(prefix, constraint["name"])
        relationships[qualified(prefix, key)] = relationship
    return nodes, relationships


def split(reference, prefixes, what):
    """The prefix and name of a reference such as cfihos:Tag."""
    prefix, _, rest = reference.partition(":")
    if not rest or prefix not in prefixes:
        raise ValueError(f"{what} {reference!r} isn't prefix:name, with one of the prefixes {', '.join(prefixes)}")
    return prefix, rest


def link_of(mapping):
    return mapping.get("link") or ("RELATED_TO" if mapping["predicate"] == "relatedMatch" else "SAME_AS")


def mapping_id(mapping, prefixes):
    subject, obj = (qualified(*split(mapping[end], prefixes, end)) for end in ("subject", "object"))
    return f"{subject}_{link_of(mapping)}_{obj}"


def load(folder):
    """The crosswalk, the standards it joins, and its combined model and sample data, or the problems with them."""
    crosswalk = json.loads((folder / "crosswalk.json").read_text())
    errors, models, nodes, relationships = [], {}, {}, {}
    sample = {"scenario": "", "nodes": {}, "relationships": [], "open": {}}
    scenarios = []
    for prefix, path in crosswalk["standards"].items():
        if SEPARATOR in prefix or not cypher.IDENTIFIER.fullmatch(prefix):
            errors.append(f"prefix {prefix!r} must be an identifier without {SEPARATOR}")
        standard = HERE / path
        model = json.loads((standard / "model.json").read_text())
        models[prefix] = model
        more_nodes, more_relationships = namespaced(model, prefix, model["name"])
        nodes.update(more_nodes)
        relationships.update(more_relationships)
        if (standard / "sample.json").exists():
            own = json.loads((standard / "sample.json").read_text())
            scenarios.append(f"{model['name']}: {own['scenario']}")
            for local, node in own["nodes"].items():
                kinds = node["node"] if isinstance(node["node"], list) else [node["node"]]
                sample["nodes"][f"{prefix}:{local}"] = {**node, "node": [qualified(prefix, kind) for kind in kinds]}
            for start, kind, end, *rest in own["relationships"]:
                sample["relationships"].append([f"{prefix}:{start}", qualified(prefix, kind), f"{prefix}:{end}", *rest])
            for key, reason in own.get("open", {}).items():
                sample["open"][qualified(prefix, key)] = reason

    prefixes = list(crosswalk["standards"])
    links = {}
    for index, mapping in enumerate(crosswalk["mappings"]):
        where = f"mapping {index} ({mapping.get('subject')} {mapping.get('predicate')} {mapping.get('object')})"
        try:
            (subject_prefix, subject), (object_prefix, obj) = (
                split(mapping[end], prefixes, end) for end in ("subject", "object"))
        except (KeyError, ValueError) as error:
            errors.append(f"{where}: {error}")
            continue
        if subject_prefix == object_prefix:
            errors.append(f"{where}: maps two nodes of the same standard")
        if mapping["predicate"] not in PREDICATES:
            errors.append(f"{where}: the predicate must be one of {', '.join(PREDICATES)}")
        missing = [f"{p}:{n}" for p, n in ((subject_prefix, subject), (object_prefix, obj)) if n not in models[p]["nodes"]]
        if missing:
            errors.append(f"{where}: {', '.join(missing)} isn't a node of its standard")
            continue
        for end, (prefix, name) in (("subject", (subject_prefix, subject)), ("object", (object_prefix, obj))):
            known = properties_of(nodes, qualified(prefix, name))
            for key in (mapping.get("properties", {}) if end == "subject" else mapping.get("properties", {}).values()):
                if key not in known:
                    errors.append(f"{where}: {key} isn't a property of {prefix}:{name}")
        key = mapping_id(mapping, prefixes)
        if key in links:
            errors.append(f"{where}: repeats a mapping between the same nodes by the same link")
        links[key] = mapping
        relationships[key] = {
            "type": link_of(mapping),
            "from": {"node": qualified(subject_prefix, subject)},
            "to": {"node": qualified(object_prefix, obj)},
        }

    extra = json.loads((folder / "sample.json").read_text()) if (folder / "sample.json").exists() else {}
    if extra.get("scenario"):
        scenarios.insert(0, extra["scenario"])
    for local, node in extra.get("nodes", {}).items():
        if local in sample["nodes"]:
            errors.append(f"node {local}: already a node of a standard's sample data")
            continue
        try:
            ends = [split(kind, prefixes, f"node {local}")
                    for kind in (node["node"] if isinstance(node["node"], list) else [node["node"]])]
        except ValueError as error:
            errors.append(str(error))
            continue
        if any(prefix != local.partition(":")[0] for prefix, _ in ends):
            errors.append(f"node {local}: its id must start with the prefix of its standard, e.g. {ends[0][0]}:{local}")
            continue
        sample["nodes"][local] = {**node, "node": [qualified(*end) for end in ends]}
    link_types = {relationship["type"] for key, relationship in relationships.items() if key in links}
    for start, kind, end, *rest in extra.get("relationships", []):
        if kind not in link_types:
            try:
                kind = qualified(*split(kind, prefixes, "relationship type"))
            except ValueError as error:
                errors.append(f"relationship ({start})-[:{kind}]->({end}): {error}, or a link")
                continue
        sample["relationships"].append([start, kind, end, *rest])
    for key, reason in extra.get("open", {}).items():
        try:
            sample["open"][qualified(*split(key, prefixes, "open relationship"))] = reason
        except ValueError as error:
            errors.append(str(error))
    sample["scenario"] = " ".join(scenarios)
    combined = {"name": crosswalk["name"], "nodes": nodes, "relationships": relationships}
    return crosswalk, models, combined, sample, links, errors


def properties_of(nodes, key):
    """Every property a node of the model node has, its own and those of the labels it implies."""
    labelled = cypher.by_label({"nodes": nodes})
    known = set()
    for label in cypher.labels_of({"nodes": nodes}, [key]):
        known.update(labelled.get(label, {}).get("properties", {}))
    return known


def disagreements(combined, sample, links):
    """Every pair of linked nodes whose values differ for a property their mapping says they share."""
    errors, labelled = [], {}
    for local, node in sample["nodes"].items():
        labelled[local] = cypher.labels_of(combined, node["node"])
    for start, kind, end, *_ in sample["relationships"]:
        for key, mapping in links.items():
            defined = combined["relationships"][key]
            if (defined["type"] != kind or start not in labelled or end not in labelled
                    or defined["from"]["node"] not in labelled[start] or defined["to"]["node"] not in labelled[end]):
                continue
            ours, theirs = sample["nodes"][start].get("properties", {}), sample["nodes"][end].get("properties", {})
            for subject_key, object_key in mapping.get("properties", {}).items():
                if subject_key in ours and object_key in theirs and ours[subject_key] != theirs[object_key]:
                    errors.append(f"link ({start})-[:{kind}]->({end}): {subject_key} {ours[subject_key]!r} isn't "
                                  f"{object_key} {theirs[object_key]!r}, as {mapping['subject']} "
                                  f"{mapping['predicate']} {mapping['object']} says it is")
    link_types = {combined["relationships"][key]["type"] for key in links}
    for start, kind, end, *_ in sample["relationships"]:
        if kind in link_types and start.partition(":")[0] == end.partition(":")[0]:
            errors.append(f"link ({start})-[:{kind}]->({end}): joins two nodes of the same standard")
    return errors


def crosswalk_model(crosswalk, models, combined, links):
    """The crosswalk as a graph spec model: the nodes its mappings join and a relationship for each mapping."""
    prefixes = list(crosswalk["standards"])
    mapped = {}
    for mapping in links.values():
        for end in ("subject", "object"):
            prefix, name = split(mapping[end], prefixes, end)
            mapped[qualified(prefix, name)] = None
    nodes = {}
    for prefix in prefixes:  # by standard, in the order the crosswalk lists them
        for key in combined["nodes"]:
            if key in mapped and key.startswith(prefix + SEPARATOR):
                node = json.loads(json.dumps(combined["nodes"][key]))
                implied = [label for label in node["labels"].get("implied", []) if label in mapped]
                labelled = cypher.by_label(combined)
                for label in cypher.labels_of(combined, [key])[1:]:  # inherit the properties of the labels left out
                    if label not in mapped:
                        for name, definition in labelled[label].get("properties", {}).items():
                            node.setdefault("properties", {}).setdefault(name, definition)
                node["labels"] = {"identifier": node["labels"]["identifier"], **({"implied": implied} if implied else {})}
                node["extensions"] = {"custom": {"standard": models[prefix]["name"]}}
                nodes[key] = node
    relationships = {}
    for key, mapping in links.items():
        relationship = combined["relationships"][key]
        shared = mapping.get("properties", {})
        description = (f"{mapping['subject']} skos:{mapping['predicate']} {mapping['object']}. "
                       f"{mapping.get('comment', '')}".strip())
        if shared:
            description += " Linked nodes share " + ", ".join(
                f"{a} and {b}" if a != b else a for a, b in shared.items()) + "."
        relationships[key] = {
            "type": relationship["type"],
            "from": {"node": relationship["from"]["node"]},
            "to": {"node": relationship["to"]["node"]},
            "description": description,
            **({"reference": mapping["source"]} if mapping.get("source") else {}),
            "extensions": {"custom": {
                "predicate": f"skos:{mapping['predicate']}",
                "exact": mapping["predicate"] == "exactMatch",
                **({"properties": shared} if shared else {}),
            }},
        }
    return {
        "schema": SCHEMA,
        "version": "1.0",
        "id": f"crosswalk-{crosswalk['id']}",
        "name": crosswalk["name"],
        "description": crosswalk["description"],
        "nodes": nodes,
        "relationships": relationships,
    }


def diagram(crosswalk, models):
    names = [models[prefix]["name"] for prefix in crosswalk["standards"]]
    return {
        "source": "crosswalk.json, from the model.json of " + ", ".join(names),
        "link": "the term in its standard",
        "areas": {"field": "standard", "groups": [{"name": name, "values": [name]} for name in names]},
        "sub": ["standard", "#properties"],
        "lines": {"by": "field:exact", "legend": {
            "main": "skos:exactMatch",
            "dashed": "skos:closeMatch, broadMatch, narrowMatch or relatedMatch",
        }},
    }


def sssom(crosswalk, models):
    """The mappings as an SSSOM TSV file, a class mapping a row and each property it shares another."""
    prefixes = crosswalk["standards"]
    lines = [
        f"# mapping_set_id: {REPOSITORY}crosswalks/{crosswalk['id']}/mappings.sssom.tsv",
        f"# mapping_set_title: {crosswalk['name']}",
        "# license: https://creativecommons.org/licenses/by/4.0/",
        "# curie_map:",
        "#   skos: http://www.w3.org/2004/02/skos/core#",
        "#   semapv: https://w3id.org/semapv/vocab/",
        *[f"#   {prefix}: {REPOSITORY}{path}/model.json#" for prefix, path in prefixes.items()],
    ]
    columns = ["subject_id", "subject_label", "predicate_id", "object_id", "object_label", "mapping_justification",
               "subject_source_version", "object_source_version", "comment"]
    lines.append("\t".join(columns))

    def label(reference):
        prefix, name = reference.split(":", 1)
        node, _, prop = name.partition(".")
        model = models[prefix]
        if not prop:
            return model["nodes"][node]["labels"].get("identifier", node)
        labelled = cypher.by_label(model)
        for label in cypher.labels_of(model, [node]):  # the node's own properties, then those of the labels it implies
            if prop in labelled.get(label, {}).get("properties", {}):
                return labelled[label]["properties"][prop].get("name", prop)
        return prop

    def clean(text):
        return " ".join(text.split()).replace("\t", " ")

    for mapping in crosswalk["mappings"]:
        rows = [(mapping["subject"], mapping["predicate"], mapping["object"], mapping.get("comment", ""))]
        for ours, theirs in mapping.get("properties", {}).items():
            rows.append((f"{mapping['subject']}.{ours}", "exactMatch", f"{mapping['object']}.{theirs}",
                         f"A property {mapping['subject']} and {mapping['object']} share."))
        for subject, predicate, obj, comment in rows:
            lines.append("\t".join([
                subject, label(subject), f"skos:{predicate}", obj, label(obj), "semapv:ManualMappingCuration",
                models[subject.split(':')[0]]["id"], models[obj.split(':')[0]]["id"], clean(comment),
            ]))
    return "\n".join(lines) + "\n"


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


def script(crosswalk, models, combined, sample):
    edition = "Enterprise Edition, for its node key and property existence constraints"
    standards = ", ".join(f"{model['name']} as {prefix}{SEPARATOR}" for prefix, model in models.items())
    return "\n".join([
        f"// {crosswalk['name']}: the standards' constraints, their sample data and the links between them",
        "//",
        "// Generated by ../../crosswalk.py from crosswalk.json, sample.json and the model.json and sample.json of each",
        "// standard. Edit those and regenerate, rather than this file.",
        "//",
        cypher.comment(f"Each standard's labels and relationship types are prefixed: {standards}. The links between "
                       "them are not."),
        "//",
        cypher.comment(sample["scenario"]),
        "//",
        *[line for key, reason in sample["open"].items()
          for line in (cypher.comment(f"The data leaves the minimum counts of {key} open: {reason}"), "//")],
        cypher.comment(f"Run it against an empty database of Neo4j 5 or later, {edition}, e.g. with cypher-shell -f "
                       "model.cypher. It merges every node and relationship, so it can be run again."),
        "",
        "// The standards: their constraints",
        "",
        *cypher.schema(combined),
        "",
        "// The sample data of every standard, then the crosswalk's own and its links",
        "",
        *cypher.data(combined, sample),
        "",
    ])


def write(folder):
    try:
        crosswalk, models, combined, sample, links, errors = load(folder)
    except (OSError, KeyError, json.JSONDecodeError) as error:
        print(f"{folder}: {error!r}", file=sys.stderr)
        return False
    if not errors:
        errors = cypher.check(combined, sample) + disagreements(combined, sample, links)
    if errors:
        print(f"{folder}: {len(errors)} problems", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return False
    model = crosswalk_model(crosswalk, models, combined, links)
    outputs = {  # every file is made before any is written, so a failure leaves none half done
        "model.json": json.dumps(model, indent=2, ensure_ascii=False) + "\n",
        "model.yaml": yaml(model) + "\n",
        "diagram.json": json.dumps(diagram(crosswalk, models), indent=2, ensure_ascii=False) + "\n",
        "mappings.sssom.tsv": sssom(crosswalk, models),
        "model.cypher": script(crosswalk, models, combined, sample),
    }
    for file, text in outputs.items():
        (folder / file).write_text(text)
    link_types = {relationship["type"] for relationship in model["relationships"].values()}
    count = sum(1 for relationship in sample["relationships"] if relationship[1] in link_types)
    print(f"{folder}: {len(links)} mappings; {len(sample['nodes'])} nodes, {len(sample['relationships'])} "
          f"relationships, {count} of them links")
    return True


def main():
    folders = [Path(arg).resolve() for arg in sys.argv[1:]] or sorted(path.parent for path in HERE.rglob("crosswalk.json"))
    results = [write(folder) for folder in folders]
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
