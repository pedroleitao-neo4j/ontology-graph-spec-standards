"""The crosswalks below the repository, as the explorer needs them: their standards, mappings and link types."""

import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEPARATOR = "__"
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# The hues visualise.py gives the areas of a diagram, so a standard has the same colour in the app as in model.svg
HUES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]

# The properties that name a node, best first; failing these, a property ending in "name", then a number, then the
# node's key
NAMES = ("name", "title_short", "title", "tagName", "idShort", "frbrThis", "label")


def first(value):
    return value[0] if isinstance(value, list) and value else value


def short(value):
    """The last segment of an IRI or path, for nodes named only by one."""
    text = str(value)
    tail = re.split(r"[/#]", text.rstrip("/#"))[-1]
    return tail or text


@lru_cache(maxsize=None)
def standard(folder):
    """A standard's name and, by label, its description and key."""
    model = json.loads((ROOT / folder / "model.json").read_text())
    labels = {}
    for key, node in model["nodes"].items():
        keys = []
        for constraint in node.get("constraints", {}).values():
            if constraint["type"] in ("KEY", "UNIQUE"):
                keys = constraint["properties"]
                break
        labels[node["labels"].get("identifier", key)] = {
            "description": node.get("description", ""),
            "key": keys,
            "implied": node["labels"].get("implied", []),
        }
    return {"name": model["name"], "id": model["id"], "labels": labels}


@lru_cache(maxsize=None)
def catalogue():
    """Every crosswalk, by id, in the order of the folders."""
    found = {}
    for path in sorted((ROOT / "crosswalks").glob("*/crosswalk.json")):
        crosswalk = json.loads(path.read_text())
        model = json.loads((path.parent / "model.json").read_text())
        standards = []
        for index, (prefix, folder) in enumerate(crosswalk["standards"].items()):
            if not IDENTIFIER.fullmatch(prefix):
                raise ValueError(f"{path}: prefix {prefix!r} isn't an identifier")
            info = standard(folder)
            standards.append({"prefix": prefix, "name": info["name"], "folder": folder, "color": HUES[index % len(HUES)]})
        mappings = []
        for key, relationship in model["relationships"].items():
            custom = relationship.get("extensions", {}).get("custom", {})
            mappings.append({
                "id": key,
                "subject": relationship["from"]["node"],
                "object": relationship["to"]["node"],
                "link": relationship["type"],
                "predicate": custom.get("predicate", "").removeprefix("skos:"),
                "properties": custom.get("properties", {}),
                "description": relationship.get("description", ""),
                "source": relationship.get("reference"),
            })
        comments = {}
        for mapping in crosswalk["mappings"]:  # the comment alone, without the summary the model's description adds
            subject = mapping["subject"].replace(":", SEPARATOR, 1)
            obj = mapping["object"].replace(":", SEPARATOR, 1)
            comments[(subject, obj)] = mapping.get("comment", "")
        for mapping in mappings:
            mapping["comment"] = comments.get((mapping["subject"], mapping["object"]), "")
        found[crosswalk["id"]] = {
            "id": crosswalk["id"],
            "name": crosswalk["name"],
            "description": crosswalk["description"],
            "standards": standards,
            "mappings": mappings,
            "links": sorted({mapping["link"] for mapping in mappings}),
            "script": path.parent / "model.cypher",
        }
    return found


def split(label):
    """The prefix and local name of a namespaced label or relationship type, e.g. cfihos__Tag."""
    prefix, separator, name = label.partition(SEPARATOR)
    return (prefix, name) if separator else (None, label)


def describe(crosswalk, labels, props):
    """A node as the explorer shows it: its standard, labels most specific first, a name and its key."""
    prefixes = {item["prefix"]: item for item in crosswalk["standards"]}
    prefix = next((split(label)[0] for label in labels if split(label)[0] in prefixes), None)
    info = standard(prefixes[prefix]["folder"]) if prefix else {"labels": {}}
    own = [split(label)[1] for label in labels if split(label)[0] == prefix]
    # Most specific first: a label before every label it implies, directly or through another
    implied = {label: ancestors(info["labels"], label) for label in own}
    own.sort(key=lambda label: -len(implied[label]))
    key = []
    for label in own:
        key = info["labels"].get(label, {}).get("key", [])
        if key:
            break
    rank, name = naming(props, key)
    return {
        "standard": prefix,
        "labels": own,
        "name": name,
        "rank": rank,
        "key": key,
        "descriptions": {label: info["labels"].get(label, {}).get("description", "") for label in own},
    }


def ancestors(labels, label):
    """Every label a label implies, directly or through another."""
    found, todo = set(), list(labels.get(label, {}).get("implied", []))
    while todo:
        current = todo.pop()
        if current not in found:
            found.add(current)
            todo.extend(labels.get(current, {}).get("implied", []))
    return found


def naming(props, key):
    """A node's name, and how good a name it is, 0 the best: of the things a crosswalk links, the best name names it."""
    for candidate in NAMES:
        if props.get(candidate) not in (None, "", []):
            return 0, str(first(props[candidate]))
    for prop, value in props.items():
        if prop.lower().endswith("name") and isinstance(first(value), str) and first(value):
            return 1, first(value)
    if props.get("number") not in (None, "", []):
        return 2, str(first(props["number"]))
    values = [short(first(props[prop])) for prop in key if prop in props]
    if values:
        return 3, " · ".join(values)
    for prop in ("uri", "id", "stixId", "uid", "rdfId"):
        if prop in props:
            return 4, short(first(props[prop]))
    return 5, "(unnamed)"
