# MITRE ATT&CK 20.1

An ontology for [MITRE ATT&CK](https://attack.mitre.org/) (Adversarial Tactics, Techniques and Common Knowledge),
MITRE's knowledge base of adversary behaviour and the detection of it. ATT&CK describes what adversaries do: the
tactics that are their objectives, the techniques and sub-techniques that achieve them, the groups, campaigns,
malware and tools that use them, the mitigations that counter them, and the detection strategies, analytics and data
components that detect them.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the official ATT&CK STIX bundles |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`sample.json`](sample.json) | Sample data: APT29 and the SolarWinds Compromise |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |
| [`../../cypher.py`](../../cypher.py) | Generates the Cypher script (shared by every standard) from `model.json` and `sample.json` |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |

## Source

The model is generated from the official STIX 2.1 bundles that MITRE publishes in
[`mitre-attack/attack-stix-data`](https://github.com/mitre-attack/attack-stix-data) at tag
[`v20.1`](https://github.com/mitre-attack/attack-stix-data/tree/v20.1), one per domain:

- [`enterprise-attack-20.1.json`](https://github.com/mitre-attack/attack-stix-data/blob/v20.1/enterprise-attack/enterprise-attack-20.1.json)
- [`mobile-attack-20.1.json`](https://github.com/mitre-attack/attack-stix-data/blob/v20.1/mobile-attack/mobile-attack-20.1.json)
- [`ics-attack-20.1.json`](https://github.com/mitre-attack/attack-stix-data/blob/v20.1/ics-attack/ics-attack-20.1.json)

To regenerate:

```bash
python3 generate.py                     # downloads the three bundles
python3 generate.py path/to/attack-stix-data    # or a clone or archive of the repository
python3 generate.py path/to/the/bundles         # or a directory holding the three bundles
```

The script needs only the Python standard library.

## The knowledge base, not the schema

ATT&CK publishes its content as STIX objects, not as a schema: each technique, group or analytic is an instance. One
node type per STIX type would give a schema of eleven labels and say almost nothing about ATT&CK itself. So, as in
D3FEND, the ontology describes the graph that holds the knowledge base. Each active ATT&CK object is a **node**,
labelled by the **category** it belongs to, e.g. `Technique` or `Group`, and by `ATTACKObject`. Each relationship type
between categories is a **relationship**. Loaded this way, a question like "which malware uses a technique that a
mitigation mitigates" is a graph query:

```cypher
MATCH (m:Malware)-[:USES]->(t:Technique)<-[:MITIGATES]-(c:Mitigation)
RETURN m.name, t.name, c.name
```

The categories are the ATT&CK object types that hold current content:

| Category | ATT&CK object type | Nodes | Enterprise | Mobile | ICS |
|---|---|---|---|---|---|
| `Tactic` | `x-mitre-tactic` | 39 | 15 | 12 | 12 |
| `Technique` | `attack-pattern` | 935 | 706 | 125 | 104 |
| `Group` | `intrusion-set` | 182 | 178 | 20 | 14 |
| `Campaign` | `campaign` | 61 | 57 | 3 | 10 |
| `Malware` | `malware` | 875 | 747 | 127 | 25 |
| `Tool` | `tool` | 97 | 95 | 2 | — |
| `Mitigation` | `course-of-action` | 109 | 44 | 13 | 53 |
| `DetectionStrategy` | `x-mitre-detection-strategy` | 935 | 706 | 125 | 104 |
| `Analytic` | `x-mitre-analytic` | 2,286 | 1,773 | 213 | 300 |
| `DataComponent` | `x-mitre-data-component` | 120 | 106 | 29 | 40 |
| `Asset` | `x-mitre-asset` | 18 | — | — | 18 |
| `ATTACKObject` | every type above | 5,657 | | | |

`ATTACKObject` is the label every node carries. It holds the properties common to all of them, e.g. `name`,
`description`, `url` and `domains`; a category holds its own, e.g. `isSubtechnique` on `Technique`.

The relationships, one per pair of categories that ATT&CK links:

| Relationship | From | To | Links | Source |
|---|---|---|---|---|
| `USES` | `Malware` | `Technique` | 12,351 | relationship object |
| `USES` | `Group` | `Technique` | 4,889 | relationship object |
| `USES` | `Campaign` | `Technique` | 1,351 | relationship object |
| `USES` | `Tool` | `Technique` | 891 | relationship object |
| `USES` | `Group` | `Malware` | 705 | relationship object |
| `USES` | `Campaign` | `Malware` | 96 | relationship object |
| `USES` | `Group` | `Tool` | 475 | relationship object |
| `USES` | `Campaign` | `Tool` | 81 | relationship object |
| `MITIGATES` | `Mitigation` | `Technique` | 2,068 | relationship object |
| `DETECTS` | `DetectionStrategy` | `Technique` | 935 | relationship object |
| `SUBTECHNIQUE_OF` | `Technique` | `Technique` | 552 | relationship object |
| `ATTRIBUTED_TO` | `Campaign` | `Group` | 27 | relationship object |
| `TARGETS` | `Technique` | `Asset` | 933 | relationship object |
| `LOG_SOURCE_REF` | `Analytic` | `DataComponent` | 5,233 | embedded reference |
| `KILL_CHAIN_PHASE` | `Technique` | `Tactic` | 1,149 | embedded reference |
| `ANALYTIC_REF` | `DetectionStrategy` | `Analytic` | 2,271 | embedded reference |

A `links` count is the number of distinct source-target pairs across the three domains. A pair can occur in more than
one domain, e.g. a group ATT&CK tracks in Enterprise and ICS; the per-domain counts in `extensions.custom.domains`
therefore sum to at least `links`.

## Diagram

[`model.svg`](model.svg) draws each category as a card and each relationship as an arrow from source to target. A
solid arrow is a STIX relationship object, e.g. `Malware` `USES` `Technique`. A dashed arrow is an embedded
reference, a property holding identifiers, e.g. `Technique` `KILL_CHAIN_PHASE` `Tactic`. Dotted arrows point from a
category to `ATTACKObject`, the label it also carries. Cards are coloured by area: adversary behaviour (tactics and
techniques), the adversary (groups, campaigns, malware and tools), defence (mitigations, detection strategies,
analytics and data components), and the foundation (`ATTACKObject` and ICS assets). Opened in a browser, hovering a
card or arrow shows its name and description, and each card links to its page on attack.mitre.org. To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

[`sample.json`](sample.json) holds a slice of ATT&CK Enterprise 20.1 around APT29 (G0016) and the SolarWinds
Compromise (C0024), which ATT&CK attributes to it. It has the SUNSPOT, SUNBURST, TEARDROP and Raindrop malware and the
AdFind and Mimikatz tools used in the campaign, and seven techniques it uses, e.g. Compromise Software Supply Chain
(T1195.002), SAML Tokens (T1606.002) and DCSync (T1003.006), with their parent techniques and the tactics they serve.
Six mitigations of those techniques, and the detection strategies for four of them with their Windows analytics and
the data components those read, complete it: 57 nodes and 103 relationships. Every object, identifier, property and
link comes from the ATT&CK 20.1 Enterprise bundle; only descriptions are cut to their first sentence.

To regenerate `model.cypher` after editing `sample.json`, which checks the data against the model first:

```bash
python3 ../../cypher.py .   # from this folder; or ../../cypher.py alone for every standard with sample data
```

The script needs Neo4j 5 or later, Enterprise Edition, for its node key constraints. Run it against an empty database,
e.g. with `cypher-shell -f model.cypher`. It merges every node and relationship, so it can be run again.

## Mapping

| ATT&CK (STIX 2.1) | Ontology |
|---|---|
| Active object of a category, e.g. a technique | Node, labelled by its category, e.g. `Technique`, and by `ATTACKObject` |
| Every object | `ATTACKObject`; the object's type is kept in `extensions.custom.stixType` |
| `id`, e.g. `attack-pattern--0042a9f5-…` | `stixId` property with a `KEY` constraint on every category |
| `external_references` entry with `source_name` `mitre-attack`: `external_id` | `attackId`, e.g. `T1055.011`, with a pattern for the category |
| `external_references` entry with `source_name` `mitre-attack`: `url` | `url` |
| `name`, `description`, `created`, `modified`, `x_mitre_version` | `name`, `description`, `created`, `modified`, `version` |
| `x_mitre_domains` | `domains`, e.g. `["enterprise-attack"]` |
| `kill_chain_phases[].phase_name` | `KILL_CHAIN_PHASE` relationship from the technique to the tactic of that short name |
| `x_mitre_is_subtechnique`, `x_mitre_platforms`, `x_mitre_impact_type`, `x_mitre_remote_support`, `x_mitre_tactic_type` | `isSubtechnique`, `platforms`, `impactType`, `remoteSupport`, `tacticType` |
| `aliases`, `x_mitre_aliases`, `is_family` | `aliases`, `aliases`, `isFamily` |
| `first_seen`, `last_seen` | `firstSeen`, `lastSeen` |
| `x_mitre_shortname`, `x_mitre_sectors` | `shortname`, `sectors` |
| Relationship object with `relationship_type` `uses`, `mitigates`, `detects`, `subtechnique-of`, `attributed-to` or `targets` | Relationship in upper snake case from the category of `source_ref` to the category of `target_ref`, e.g. `SUBTECHNIQUE_OF` |
| `x_mitre_analytic_refs` of a detection strategy | `ANALYTIC_REF` relationship to the analytic |
| `x_mitre_log_source_references[].x_mitre_data_component_ref` of an analytic | `LOG_SOURCE_REF` relationship to the data component |

Each node records its category, area, ATT&CK version and number of instances, and the number of instances in each
domain. Each relationship records whether it comes from a STIX relationship object or an embedded reference, the
ATT&CK relationship type or property, the number of links and the per-domain counts. Both give three example links in
their description, e.g. *APT28 uses Spearphishing Attachment*.

### Where the ontology differs from ATT&CK

- **Objects are nodes, not labels.** See [above](#the-knowledge-base-not-the-schema). ATT&CK publishes instances, so
  each is a node, and the model's twelve node types are the categories that hold them.
- **Revoked and deprecated objects are left out.** 219 revoked and 294 deprecated content objects aren't nodes, and
  neither are the 3 links that point at one. They describe ATT&CK's history, not its current knowledge base.
  `revoked-by` relationship objects are left out as well.
- **One relationship type per pair of categories.** ATT&CK gives each `uses` link its own relationship object with a
  description and references. In the graph there is one `USES` relationship type, from e.g. `Group` to `Technique`,
  covering all 4,889 such links; per-link descriptions and references aren't kept, and the relationship's description
  gives examples instead. Link-level detail that isn't shared, e.g. a log source's `name` and `channel` or an
  analytic's mutable elements, is dropped for the same reason.
- **Container and meta objects aren't nodes.** `identity`, `marking-definition`, `x-mitre-collection` and
  `x-mitre-matrix` don't describe adversary behaviour. A matrix holds the tactics of a domain in display order; the
  `domains` property of a `Tactic` says which matrix it belongs to.
- **Data sources aren't nodes.** Every `x-mitre-data-source` object is deprecated in ATT&CK 20.1. The data components
  their analytics collect are nodes, and `LOG_SOURCE_REF` links analytics to them.
- **A shared object is one node.** 100 objects appear in more than one domain, mostly groups, malware and campaigns.
  They're merged by STIX identifier into one node whose `domains` lists every domain. The same relationship can
  therefore appear in more than one domain, and the per-domain counts can exceed `links`.
- **Embedded references are relationships.** `kill_chain_phases`, `x_mitre_analytic_refs` and
  `x_mitre_log_source_references` hold identifiers rather than STIX relationship objects. They become relationships
  too, with `extensions.custom.derived: false`; the STIX relationship objects have `derived: true`.
- **Cardinalities are stated where they hold.** Every technique serves at least one tactic, so `KILL_CHAIN_PHASE` has
  `min_count: 1` at the technique end; every detection strategy holds at least one analytic, so `ANALYTIC_REF` has
  `min_count: 1` too; and a sub-technique has one parent, so `SUBTECHNIQUE_OF` has `max_count: 1`. ATT&CK doesn't state
  these as constraints, but its 20.1 data meets them.
- **The common properties live on `ATTACKObject`.** The format has no inheritance, so a category node declares its
  own properties and the umbrella label declares the properties every object has. A query for a common property uses
  the `ATTACKObject` label, e.g. `MATCH (o:ATTACKObject) WHERE o.domains CONTAINS 'ics-attack'`.

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json) and reports no issues for any of
the built-in validation sets, including `all`.
