#!/usr/bin/env python3
"""Generates the MITRE ATT&CK ontology from the official attack-stix-data 20.1 bundles.

Usage: python3 generate.py [SOURCE ...]

SOURCE is the attack-stix-data repository (an archive or a clone), a directory holding the three domain bundles, or
one of the bundles. Each one left out is downloaded from the v20.1 tag. Writes model.json and model.yaml next to this
script. Uses only the Python standard library.
"""

import json
import re
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

VERSION = "20.1"
TAG = f"v{VERSION}"
REPO = f"https://github.com/mitre-attack/attack-stix-data/tree/{TAG}"
FILES = {
    domain: f"https://raw.githubusercontent.com/mitre-attack/attack-stix-data/{TAG}/{domain}-attack/"
            f"{domain}-attack-{VERSION}.json"
    for domain in ("enterprise", "mobile", "ics")
}
DOMAINS = {"enterprise": "Enterprise", "mobile": "Mobile", "ics": "ICS"}
SCHEMA = "https://neo4j.com/docs/ontology-graph-spec/1.1.0/schema.json"
MAX_DESCRIPTION = 1024
DATA_MODEL = "https://attack.mitre.org/resources/attack-data-and-tools/"
STIX = "https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html"

# The ATT&CK object types that become nodes, in diagram order. Each is a category: its instances are the nodes.
# `pattern` is the ATT&CK identifier form; `properties` are the properties the category adds to the common ones.
CATEGORIES = {
    "attack-pattern": {
        "label": "Technique",
        "area": "Behaviour",
        "description": "A technique: the 'how' of an attack, the means by which an adversary achieves a tactical "
                       "objective. A sub-technique is a more specific technique, linked to its parent by "
                       "SUBTECHNIQUE_OF.",
        "reference": "https://attack.mitre.org/techniques/",
        "pattern": r"^T\d{4}(\.\d{3})?$",
        "properties": {
            "platforms": ("LIST<STRING>", "The platforms the technique applies to, e.g. Windows, Linux or macOS."),
            "isSubtechnique": ("BOOLEAN", "Whether the technique is a sub-technique of another."),
            "impactType": ("LIST<STRING>", "The kind of impact an ICS technique has, e.g. Availability."),
            "remoteSupport": ("BOOLEAN", "Whether the technique can be used remotely, where ATT&CK says so."),
            "tacticType": ("LIST<STRING>", "The stage of a mobile attack the technique belongs to, where ATT&CK "
                                           "gives one."),
        },
    },
    "x-mitre-tactic": {
        "label": "Tactic",
        "area": "Behaviour",
        "description": "A tactic: the 'why' of an attack, the adversary's tactical objective, e.g. Stealth or "
                       "Privilege Escalation. Techniques serve a tactic through the technique's kill chain phases.",
        "reference": "https://attack.mitre.org/tactics/",
        "pattern": r"^TA\d{4}$",
        "properties": {
            "shortname": ("STRING", "The tactic's short name, e.g. `privilege-escalation`, as used in a "
                                    "technique's kill chain phases."),
        },
    },
    "intrusion-set": {
        "label": "Group",
        "area": "Adversary",
        "description": "A group: a set of related intrusion activity that ATT&CK tracks by a common name, e.g. an "
                       "APT or a criminal organisation.",
        "reference": "https://attack.mitre.org/groups/",
        "pattern": r"^G\d{4}$",
        "properties": {
            "aliases": ("LIST<STRING>", "The other names the group is known by."),
        },
    },
    "campaign": {
        "label": "Campaign",
        "area": "Adversary",
        "description": "A campaign: a grouping of intrusion activity conducted over a specific period of time "
                       "against specific targets.",
        "reference": "https://attack.mitre.org/campaigns/",
        "pattern": r"^C\d{4}$",
        "properties": {
            "aliases": ("LIST<STRING>", "The other names the campaign is known by."),
            "firstSeen": ("ZONED DATETIME", "When the campaign was first seen."),
            "lastSeen": ("ZONED DATETIME", "When the campaign was last seen."),
        },
    },
    "malware": {
        "label": "Malware",
        "area": "Adversary",
        "description": "Malware: a piece of software an adversary uses to compromise a system, e.g. a backdoor, "
                       "ransomware or an implant.",
        "reference": "https://attack.mitre.org/software/",
        "pattern": r"^S\d{4}$",
        "properties": {
            "aliases": ("LIST<STRING>", "The other names the malware is known by."),
            "platforms": ("LIST<STRING>", "The platforms the malware runs on."),
            "isFamily": ("BOOLEAN", "Whether the object describes a malware family rather than a single piece of "
                                    "malware."),
        },
    },
    "tool": {
        "label": "Tool",
        "area": "Adversary",
        "description": "A tool: a legitimate piece of software an adversary uses, e.g. a command-line utility, a "
                       "remote access tool or a credential dumper.",
        "reference": "https://attack.mitre.org/software/",
        "pattern": r"^S\d{4}$",
        "properties": {
            "aliases": ("LIST<STRING>", "The other names the tool is known by."),
            "platforms": ("LIST<STRING>", "The platforms the tool runs on."),
        },
    },
    "course-of-action": {
        "label": "Mitigation",
        "area": "Defence",
        "description": "A mitigation: a security control that prevents a technique, or makes it harder, e.g. "
                       "Multi-factor Authentication or Network Segmentation.",
        "reference": "https://attack.mitre.org/mitigations/",
        "pattern": r"^M\d{4}$",
        "properties": {},
    },
    "x-mitre-detection-strategy": {
        "label": "DetectionStrategy",
        "area": "Defence",
        "description": "A detection strategy: one approach to detecting a technique, holding the analytics that "
                       "implement it.",
        "reference": "https://attack.mitre.org/detectionstrategies/",
        "pattern": r"^DET\d{4}$",
        "properties": {},
    },
    "x-mitre-analytic": {
        "label": "Analytic",
        "area": "Defence",
        "description": "An analytic: the logic of a detection, such as a sensor and the condition it watches for, "
                       "with the data components its log sources collect.",
        "reference": "https://attack.mitre.org/detectionstrategies/",
        "pattern": r"^AN\d{4}$",
        "properties": {
            "platforms": ("LIST<STRING>", "The platforms the analytic applies to."),
        },
    },
    "x-mitre-data-component": {
        "label": "DataComponent",
        "area": "Defence",
        "description": "A data component: a conceptual piece of data that an analytic's log sources collect, e.g. "
                       "Process Creation or Network Connection Creation.",
        "reference": "https://attack.mitre.org/datacomponents/",
        "pattern": r"^DC\d{4}$",
        "properties": {},
    },
    "x-mitre-asset": {
        "label": "Asset",
        "area": "Foundation",
        "description": "An asset: a kind of ICS system or device that a technique targets, e.g. a control server or "
                       "a field controller.",
        "reference": "https://attack.mitre.org/assets/",
        "pattern": r"^A\d{4}$",
        "properties": {
            "sectors": ("LIST<STRING>", "The sectors the asset belongs to, e.g. General or Energy."),
            "platforms": ("LIST<STRING>", "The platforms the asset runs."),
        },
    },
}
AREA_ORDER = {"Behaviour": 0, "Adversary": 1, "Defence": 2, "Foundation": 3}

# The relationship types ATT&CK relationship objects carry, with the wording an example link reads with.
RELATIONSHIPS = {
    "uses": ("The source uses the target in the course of an attack: a group or campaign uses a technique, malware "
             "or tool; malware or a tool uses a technique.", "{s} uses {t}"),
    "mitigates": ("The mitigation prevents, or makes harder, the technique it mitigates.", "{s} mitigates {t}"),
    "detects": ("The detection strategy detects the technique it detects.", "{s} detects {t}"),
    "subtechnique-of": ("The technique is a sub-technique of the more general technique it is of.",
                        "{s} is a sub-technique of {t}"),
    "attributed-to": ("The campaign is attributed to the group it is attributed to.",
                      "{s} is attributed to {t}"),
    "targets": ("The technique targets the asset it targets.", "{s} targets {t}"),
}

# The embedded references, which aren't relationship objects but properties holding identifiers.
EMBEDDED = {
    ("Technique", "KILL_CHAIN_PHASE", "Tactic"): (
        "The tactic a technique serves, from the `kill_chain_phases` of the technique.",
        "{s} serves the {t} tactic", "kill_chain_phases",
    ),
    ("DetectionStrategy", "ANALYTIC_REF", "Analytic"): (
        "The analyses a detection strategy holds, from its `x_mitre_analytic_refs`.",
        "{s} has {t_id}", "x_mitre_analytic_refs",
    ),
    ("Analytic", "LOG_SOURCE_REF", "DataComponent"): (
        "A data component the log sources of an analytic collect, from its `x_mitre_log_source_references`.",
        "{s_id} watches the data component {t_id}", "x_mitre_log_source_references",
    ),
}


def upper(name):
    """A relationship or property name as a relationship type, e.g. subtechnique-of → SUBTECHNIQUE_OF."""
    return "_".join(w.upper() for w in re.findall(r"[A-Za-z0-9]+", name))


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


def attack_id(obj):
    """The ATT&CK identifier of an object, e.g. T1055.011 or AN0110, from its mitre-attack external reference."""
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack" and ref.get("external_id"):
            return ref["external_id"]
    return ""


def attack_url(obj):
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack" and ref.get("url"):
            return ref["url"]
    return ""


#----------------------------------
#   Reading the sources
#----------------------------------


def download(url, name):
    path = Path(tempfile.mkdtemp()) / name
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request) as response:
        path.write_bytes(response.read())
    return path


def read_bundles(sources):
    """The three domain bundles, found in the sources given or downloaded."""
    found = {}

    def offer(path):
        match = re.search(r"(enterprise|mobile|ics)-attack-([\d.]+)\.json$", path.name)
        if match and Path(path).suffix == ".json":
            found.setdefault(match.group(1), []).append((match.group(2), path))

    for source in sources:
        if source.is_dir():
            for path in sorted(source.rglob("*.json")):
                offer(path)
        else:
            offer(source)
    bundles = {}
    for domain in FILES:
        if domain in found:
            # Prefer the version this script models; otherwise the latest one present.
            versions = sorted(found[domain], key=lambda v: [int(p) for p in re.findall(r"\d+", v[0])])
            match = [v for v in versions if v[0] == VERSION]
            bundles[domain] = json.loads((match or versions)[-1][1].read_text())
        else:
            name = f"{domain}-attack-{VERSION}.json"
            bundles[domain] = json.loads(download(FILES[domain], name).read_text())
    return bundles


def read_zip(source):
    """The bundles inside an archive of the repository."""
    if not zipfile.is_zipfile(source):
        return None
    folder = Path(tempfile.mkdtemp())
    with zipfile.ZipFile(source) as archive:
        archive.extractall(folder)
    return folder


#----------------------------------
#   The ATT&CK model as data
#----------------------------------


def build(bundles):
    objects = {}  # STIX id → object, with its domains accumulated
    seen = {}  # STIX id → domains it appears in
    for domain, bundle in bundles.items():
        for obj in bundle.get("objects", []):
            if obj["type"] not in CATEGORIES:
                continue
            seen.setdefault(obj["id"], set()).add(domain)
            if obj.get("revoked") or obj.get("x_mitre_deprecated"):
                continue
            objects.setdefault(obj["id"], obj)

    ids = set(objects)

    def category(obj):
        return CATEGORIES[obj["type"]]["label"]

    def domains_of(obj):
        values = obj.get("x_mitre_domains") or []
        return {d.removesuffix("-attack") for d in values if d.removesuffix("-attack") in FILES} or {
            d for d in seen.get(obj["id"], set())
        }

    def display(obj_id):
        obj = objects[obj_id]
        identifier = attack_id(obj)
        return f"{obj['name']} ({identifier})" if identifier else obj["name"]

    # The instances of each category, by label, and their domains.
    instances = {}
    for obj in objects.values():
        instances.setdefault(category(obj), []).append(obj)

    # The links of each relationship type: (source id, target id) → the domains it appears in.
    links = {}

    def link(source, rel, target, domain):
        links.setdefault((category(objects[source]), rel, category(objects[target])), {}).setdefault(
            (source, target), set()
        ).add(domain)

    # Relationship objects. revoked-by is history, not current knowledge; links to an object that isn't a node are
    # dropped, e.g. a sub-technique whose parent ATT&CK deprecated.
    dropped = 0
    for domain, bundle in bundles.items():
        for obj in bundle.get("objects", []):
            if obj["type"] != "relationship" or obj.get("revoked") or obj.get("x_mitre_deprecated"):
                continue
            if obj["relationship_type"] not in RELATIONSHIPS:
                dropped += 1
                continue
            if obj["source_ref"] in ids and obj["target_ref"] in ids:
                link(obj["source_ref"], upper(obj["relationship_type"]), obj["target_ref"], domain)
            else:
                dropped += 1

    # The tactics a technique serves, by domain and short name.
    tactics = {}
    for obj in objects.values():
        if obj["type"] == "x-mitre-tactic":
            for domain in domains_of(obj):
                tactics[(domain, obj.get("x_mitre_shortname"))] = obj["id"]
    unmatched = 0
    for obj in objects.values():
        if obj["type"] != "attack-pattern":
            continue
        for phase in obj.get("kill_chain_phases", []):
            for domain in domains_of(obj):
                target = tactics.get((domain, phase.get("phase_name")))
                if target:
                    link(obj["id"], "KILL_CHAIN_PHASE", target, domain)
                else:
                    unmatched += 1

    # The embedded references of detection strategies and analytics.
    for obj in objects.values():
        for ref in obj.get("x_mitre_analytic_refs", []):
            if ref in ids:
                for domain in domains_of(obj):
                    link(obj["id"], "ANALYTIC_REF", ref, domain)
        for ref in obj.get("x_mitre_log_source_references", []):
            target = ref.get("x_mitre_data_component_ref")
            if target in ids:
                for domain in domains_of(obj):
                    link(obj["id"], "LOG_SOURCE_REF", target, domain)

    # The properties a node has under the umbrella label.
    common = {
        "name": {
            "type": "STRING",
            "name": "name",
            "description": "The ATT&CK name of the object, e.g. `Spearphishing Attachment`.",
            "reference": DATA_MODEL,
        },
        "description": {
            "type": "STRING",
            "name": "description",
            "description": "The ATT&CK description of the object, as plain text.",
            "reference": DATA_MODEL,
        },
        "url": {
            "type": "STRING",
            "name": "url",
            "description": "The URL of the object on attack.mitre.org, e.g. "
                           "`https://attack.mitre.org/techniques/T1566/001`.",
            "reference": DATA_MODEL,
        },
        "created": {
            "type": "ZONED DATETIME",
            "name": "created",
            "description": "When the ATT&CK object was created.",
            "reference": STIX,
        },
        "modified": {
            "type": "ZONED DATETIME",
            "name": "modified",
            "description": "When the ATT&CK object was last modified.",
            "reference": STIX,
        },
        "domains": {
            "type": "LIST<STRING>",
            "name": "domains",
            "description": "The ATT&CK domains the object belongs to: Enterprise, Mobile or ICS.",
            "reference": DATA_MODEL,
        },
        "version": {
            "type": "STRING",
            "name": "version",
            "description": "The ATT&CK version of the object, e.g. `1.2`, as it has changed over releases.",
            "reference": DATA_MODEL,
        },
    }

    def stix_id_property():
        return {
            "type": "STRING",
            "name": "stixId",
            "description": "The STIX identifier of the ATT&CK object, e.g. "
                           "`attack-pattern--0042a9f5-f053-4769-b3ef-9ad018dfa298`. Unique across the domains.",
            "reference": STIX,
            "pattern": r"^[a-z0-9-]+--[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        }

    def attack_id_property(pattern):
        return {
            "type": "STRING",
            "name": "attackId",
            "description": f"The ATT&CK identifier of the object, matching `{pattern}`, e.g. `T1055.011`.",
            "reference": DATA_MODEL,
            "pattern": pattern,
        }

    nodes = {}
    for stix_type, meta in CATEGORIES.items():
        label = meta["label"]
        members = instances.get(label, [])
        counts = {
            DOMAINS[domain]: sum(1 for obj in members if domain in domains_of(obj)) for domain in FILES
        }
        examples = sorted(members, key=attack_id)[:3]
        properties = {
            "stixId": stix_id_property(),
            "attackId": attack_id_property(meta["pattern"]),
        }
        for name, (neo4j, text) in meta["properties"].items():
            properties[name] = {
                "type": neo4j,
                "name": name,
                "description": text,
                "reference": DATA_MODEL,
            }
        nodes[label] = {
            "labels": {"identifier": label, "implied": ["ATTACKObject"]},
            "description": describe(
                sentence(meta["description"]),
                f"Holds {len(members)} {label} objects in MITRE ATT&CK {VERSION}: "
                + ", ".join(f"{name} {count}" for name, count in counts.items() if count)
                + ".",
                "Examples: " + ", ".join(obj["name"] for obj in examples) + "."
                if examples else "",
            ),
            "reference": meta["reference"],
            "properties": properties,
            "constraints": {
                f"key_{label}": {"type": "KEY", "properties": ["stixId"], "name": f"stixId_{label}_key"}
            },
            "extensions": {
                "custom": {
                    "stixType": stix_type,
                    "area": meta["area"],
                    "holds": "instances",
                    "count": len(members),
                    "domains": {name: count for name, count in counts.items() if count},
                    "attackVersion": VERSION,
                }
            },
        }

    nodes["ATTACKObject"] = {
        "labels": {"identifier": "ATTACKObject"},
        "description": describe(
            "An object of the MITRE ATT&CK knowledge base: a tactic, technique, mitigation, group, campaign, "
            "malware, tool, detection strategy, analytic, data component or asset.",
            f"Every node carries this label, {len(objects)} in MITRE ATT&CK {VERSION}; the label of its category, "
            "e.g. Technique, says what kind of object it is.",
        ),
        "reference": "https://attack.mitre.org/",
        "properties": {"stixId": stix_id_property(), **common},
        "constraints": {
            "key_ATTACKObject": {"type": "KEY", "properties": ["stixId"], "name": "stixId_ATTACKObject_key"}
        },
        "extensions": {
            "custom": {
                "area": "Foundation",
                "holds": "instances",
                "count": len(objects),
                "abstract": True,
                "attackVersion": VERSION,
            }
        },
    }

    def domain_counts(pairs):
        counts = {}
        for domains in pairs.values():
            for domain in domains:
                counts[DOMAINS[domain]] = counts.get(DOMAINS[domain], 0) + 1
        return counts

    relationships = {}
    for (source, rel, target), pairs in sorted(links.items()):
        if rel in {upper(name) for name in RELATIONSHIPS}:
            text, template = RELATIONSHIPS[next(n for n in RELATIONSHIPS if upper(n) == rel)]
            custom = {"derived": True, "relationshipType": next(n for n in RELATIONSHIPS if upper(n) == rel)}
        else:
            text, template, prop = EMBEDDED[(source, rel, target)]
            custom = {"derived": False, "property": prop}
        # Three examples, preferring different sources so a large relationship doesn't show one group three times.
        ordered = sorted(pairs, key=lambda p: (attack_id(objects[p[0]]), attack_id(objects[p[1]])))
        chosen, seen_sources = [], set()
        for pair in ordered:
            if pair[0] not in seen_sources:
                chosen.append(pair)
                seen_sources.add(pair[0])
            if len(chosen) == 3:
                break
        chosen += [pair for pair in ordered if pair not in chosen][: 3 - len(chosen)]
        examples = []
        for (source_id, target_id) in chosen:
            examples.append(template.format(
                s=objects[source_id]["name"], t=objects[target_id]["name"],
                s_id=display(source_id), t_id=display(target_id),
            ))
        counts = domain_counts(pairs)
        end = {}
        if (source, rel, target) == ("Technique", "KILL_CHAIN_PHASE", "Tactic"):
            end = {"min_count": 1}
        elif (source, rel, target) == ("Technique", "SUBTECHNIQUE_OF", "Technique"):
            end = {"max_count": 1}
        elif (source, rel, target) == ("DetectionStrategy", "ANALYTIC_REF", "Analytic"):
            end = {"min_count": 1}
        relationships[f"{source}_{rel}_{target}"] = {
            "type": rel,
            "from": {"node": source, **end},
            "to": {"node": target},
            "description": describe(
                sentence(text),
                f"Links {len(pairs)} pairs in MITRE ATT&CK {VERSION}: "
                + ", ".join(f"{name} {count}" for name, count in counts.items()) + ".",
                "e.g. " + "; ".join(examples) + ".",
            ),
            "reference": DATA_MODEL,
            "extensions": {
                "custom": {
                    **custom,
                    "links": len(pairs),
                    "domains": {name: count for name, count in counts.items() if count},
                    "attackVersion": VERSION,
                }
            },
        }

    ordered = sorted(
        nodes.items(),
        key=lambda node: (0 if node[0] == "ATTACKObject"
                          else 1 + AREA_ORDER[node[1]["extensions"]["custom"]["area"]], node[0]),
    )
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "id": "mitre-attack",
        "name": f"MITRE ATT&CK {VERSION}",
        "description": (
            "MITRE ATT&CK (Adversarial Tactics, Techniques and Common Knowledge) "
            f"{VERSION}, MITRE's knowledge base of adversary behaviour and the detection of it "
            "(https://attack.mitre.org/). ATT&CK describes what adversaries do as a graph: tactics, the adversary's "
            "objectives; techniques and sub-techniques that achieve them; the groups, campaigns, malware and tools "
            "that use them; the mitigations that counter them; and, since version 20, detection strategies, "
            "analytics and data components. Generated from the official STIX 2.1 bundles of the Enterprise, Mobile "
            f"and ICS domains published in mitre-attack/attack-stix-data at tag {TAG} ({REPO}): each active object "
            "is a node, labelled by its category; each relationship object and embedded reference is a relationship "
            f"between the categories of its ends. Revoked and deprecated objects are left out."
        ),
        "nodes": dict(ordered),
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
    sources = []
    for arg in sys.argv[1:]:
        path = Path(arg)
        unpacked = read_zip(path) if path.is_file() else None
        sources.append(unpacked or path)
    model = build(read_bundles(sources))
    out = Path(__file__).parent
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(yaml(model) + "\n")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships")


if __name__ == "__main__":
    main()
