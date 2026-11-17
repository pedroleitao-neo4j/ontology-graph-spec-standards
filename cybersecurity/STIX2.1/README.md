# STIX 2.1

An ontology for [STIX 2.1](https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html) (Structured Threat
Information Expression), the OASIS Standard language and serialisation format for exchanging cyber threat
intelligence. STIX already describes intelligence as a graph: domain objects such as threat actors, malware and
indicators; cyber-observable objects such as files, processes and IP addresses; and relationship objects that connect
them.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the OASIS STIX 2.1 JSON schemas, the STIX validator and the specification |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`sample.json`](sample.json) | Sample data: a threat intelligence bundle on a phishing campaign |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |
| [`../../cypher.py`](../../cypher.py) | Generates the Cypher script (shared by every standard) from `model.json` and `sample.json` |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |

## Source

The model is generated from three OASIS sources:

- the STIX 2.1 JSON schemas, [`oasis-open/cti-stix2-json-schemas`](https://github.com/oasis-open/cti-stix2-json-schemas)
  at commit [`9af1db4`](https://github.com/oasis-open/cti-stix2-json-schemas/tree/9af1db41b7b86c06324f899649ae83480134f66e)
  (the repository has no STIX 2.1 release tag), for the objects, their properties and which ones are required;
- the relationship table, open vocabularies and observable reference targets of the OASIS STIX validator
  [`cti-stix-validator` 3.3.2](https://github.com/oasis-open/cti-stix-validator/tree/v3.3.2)
  (`stix2validator/v21/enums.py`, read without running it), for the relationship types between objects;
- the [STIX 2.1 OASIS Standard](https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html) itself, for the
  section each object links to and the descriptions of its relationships.

To regenerate:

```bash
python3 generate.py                                  # downloads all three
python3 generate.py SCHEMAS VALIDATOR SPECIFICATION  # or an archive or clone of each repository, and the HTML
```

The script needs only the Python standard library.

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow from source to target. A solid
arrow is a relationship the specification defines between two object types, e.g. `ThreatActor` `USES` `Malware`, which
STIX exchanges as a relationship object. A dashed arrow is an embedded reference, a `_ref` or `_refs` property, e.g.
`Process` `IMAGE_REF` `File`. Dotted arrows point from an object to `StixDomainObject` or
`StixCyberObservableObject`, the label it also carries. Cards are coloured by kind of object: domain objects (SDOs),
cyber-observable objects (SCOs), the Sighting relationship object, and the meta objects for markings, translations and
extensions. Opened in a browser, hovering a card or arrow shows its name and description, and each card links to its
section of the specification. To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

[`sample.json`](sample.json) holds a threat intelligence bundle on *Operation Quiet Invoice*, a fictional phishing
campaign against a UK building society, as a threat intelligence team would publish it under TLP:AMBER. It has the
threat actor, intrusion set and campaign; the ATT&CK attack patterns and Rclone tool they use, by their real ATT&CK
STIX identifiers; the InvoiceDrop dropper and LedgerRAT implant and their command and control infrastructure; the
email, files, directory, processes, user account, domain, addresses and network traffic observed on the victim's
network; and the indicators, observed data, sighting, sandbox analysis, courses of action, opinion and report around
them: 41 nodes and 128 relationships. Relationship objects, e.g. `USES` or `INDICATES`, carry their own `id`,
`created` and `modified`; embedded references, e.g. `FROM_REF` or `OBJECT_REFS`, carry nothing. Names are invented,
domains are `example.*`, addresses come from the documentation ranges, e.g. 203.0.113.0/24 and AS64500, and hashes are
illustrative. Identifiers of observables are UUIDv5s in the STIX namespace.

To regenerate `model.cypher` after editing `sample.json`, which checks the data against the model first:

```bash
python3 ../../cypher.py .   # from this folder; or ../../cypher.py alone for every standard with sample data
```

The script needs Neo4j 5 or later, Enterprise Edition, for its node key, relationship key and property existence
constraints. Run it against an empty database, e.g. with `cypher-shell -f model.cypher`. It merges every node and
relationship, so it can be run again.

## Mapping

| STIX 2.1 | Ontology |
|---|---|
| SDO, SCO, Sighting, marking definition, language content and extension definition, e.g. `attack-pattern` | Node, labelled in PascalCase, e.g. `AttackPattern`; the type is kept in `extensions.custom.stixType` |
| Any SDO, any SCO | `StixDomainObject` and `StixCyberObservableObject`: abstract nodes whose labels every SDO or SCO also carries |
| Common properties (`core.json`, `cyber-observable-core.json`) | Properties of every node that has them, e.g. `created` on `Malware` |
| Property, e.g. `first_seen` | Property, under its STIX name |
| `string`, `integer`, `number`, `boolean`, `timestamp` | `STRING`, `INTEGER`, `FLOAT`, `BOOLEAN`, `ZONED DATETIME` |
| List of strings, e.g. `aliases` | `LIST<STRING>` |
| `hex`, `binary` | `STRING` with the schema's `pattern` |
| Dictionaries and structured types, e.g. `hashes`, `kill_chain_phases`, `external_references`, `extensions` | `STRING` holding the JSON; the STIX type is kept in `extensions.custom.stixType` |
| Closed enumeration, e.g. `opinion` | `one_of` |
| Open vocabulary, e.g. `malware_types` | `STRING` or `LIST<STRING>`, with the suggested values in the description and in `extensions.custom.suggestedValues` |
| Required property | An `EXISTS` constraint, e.g. `Malware.is_family` |
| `id`, e.g. `malware--31b940d4-…` | An `id` property on every node with a `KEY` constraint and the identifier `pattern` for its type |
| Embedded reference, e.g. `created_by_ref`, `sample_refs` | Relationship named after the property, e.g. `CREATED_BY_REF`, one per allowed target type |
| Reference that is required | `count: 1` or `min_count: 1` at the `from` end, when it has a single target type |
| Reference that holds one identifier (`_ref`) | `max_count: 1` at the `from` end |
| Reference inside a predefined extension or embedded type, e.g. `archive-ext`'s `contains_refs` | Relationship from the object, e.g. `File` `CONTAINS_REFS` `File`, with the path in `extensions.custom.embeddedIn` |
| Relationship type between two objects, e.g. `uses` | Relationship in upper snake case, e.g. `USES`, carrying the relationship object's properties, with a `KEY` on its `id` |
| Common relationships `derived-from`, `duplicate-of`, `related-to` | Relationships between the abstract nodes |

Each node and relationship links to its section of the specification in its `reference`, and each node records its
category (`SDO`, `SCO`, `SRO` or `Meta`), section number and schema file. Properties record their STIX type, whether
they're required, their open vocabulary and their bounds, e.g. `confidence` between 0 and 100. Relationships record
the property or relationship type they come from and, for relationship objects, `definedBy`: whether the validator,
the specification or both define them.

### Where the ontology differs from STIX

- **Relationship objects are relationships.** A STIX `relationship` object has its own identity and properties. In the
  graph it's a relationship of the type its `relationship_type` names, from its `source_ref` to its `target_ref`,
  carrying its other properties: `id`, `spec_version`, `created`, `modified`, `description`, `start_time`,
  `stop_time`, `revoked`, `labels`, `confidence`, `lang`, `external_references`, `granular_markings`, `extensions`,
  and its `created_by_ref` and `object_marking_refs` as identifiers, since a relationship can't point at a node. The
  `type`, `relationship_type`, `source_ref` and `target_ref` are dropped, as the relationship itself carries them. A
  reference to a relationship object, e.g. from a `Report`'s `object_refs`, therefore has no relationship in the
  ontology; the description says so.
- **Sighting is a node.** A sighting points at the sighted object, the observed data and where it was sighted, so it
  can't be a single relationship.
- **"Any object" is an abstract node.** Where a reference allows any SDO or any SCO, e.g. `Report.object_refs` or
  `Sighting.sighting_of_ref`, it points at `StixDomainObject` or `StixCyberObservableObject` instead of one relationship
  per type. The references every SDO or SCO has, `created_by_ref` and `object_marking_refs`, and the common
  relationships are drawn from these abstract nodes once.
- **Reference targets come from three places.** The validator lists the targets of observable references, e.g.
  `src_ref` to `ipv4-addr`, `ipv6-addr`, `mac-addr` or `domain-name`; otherwise the schema's identifier patterns name
  them, e.g. `^software--`; otherwise they're taken from the specification's tables, e.g. `created_by_ref` to
  `identity`. The schema's pattern for `ObservedData.object_refs` leaves out `artifact`; the ontology follows the
  specification, "SCO or SRO".
- **Relationship types are the validator's, plus two from the specification.** The validator's table adds
  `vulnerability` `impacts` `infrastructure` and `tool`, which the specification doesn't define; it lists the target as
  `tools`, which the ontology reads as `tool`. The specification adds `malware` `targets` `vulnerability`, which the
  validator leaves out. The specification also names `av-analysis-of` in the Malware section, but `analysis-of` in
  the Malware Analysis section; only relationships listed in their source's own section are added, so the ontology
  has `analysis-of`.
- **Structured values are JSON text.** Dictionaries, hashes, kill chain phases, external references, granular
  markings and extensions have no Neo4j property type. The ontology types them as `STRING`. The identifiers inside
  them, e.g. a granular marking's `marking_ref`, aren't relationships, except those of the predefined extensions and
  email MIME parts that the validator lists.
- **Open vocabularies aren't `one_of`.** An open vocabulary allows values beyond the suggested ones, so the values are
  listed in the description and `extensions.custom` instead of restricting the property.
- **Constraints that depend on other properties aren't kept.** The schemas also say e.g. that a `File` has a `name`
  or `hashes`, or that a `Malware` family has a `name`. The format has no conditional constraints, so only properties
  that are always required have an `EXISTS` constraint.
- **Properties aren't inherited.** The common properties are copied into each node, so each node is complete on its
  own; the abstract nodes have only `id`.
- **Custom objects and properties aren't included.** STIX lets producers add their own through extension
  definitions; the ontology covers the objects the standard defines.

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json) and reports no issues for any of
the built-in validation sets, including `all`.
