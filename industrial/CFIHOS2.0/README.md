# CFIHOS 2.0

An ontology for the [Capital Facilities Information Handover Specification (CFIHOS)](https://www.jip36-cfihos.org/cfihos-standards/)
V2.0, published by IOGP JIP36. CFIHOS standardises the engineering data and documents that contractors and suppliers
hand over to the owner/operator of a process or energy facility.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the official CFIHOS data dictionary |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |
| [`../../cypher.py`](../../cypher.py) | Checks the sample data against `model.json` (shared by every standard) and writes `model.cypher` |
| [`sample.json`](sample.json) | Sample data: the handover of the condensate export pumps at a fictional gas plant, from tags and equipment to the purchase order, SPIR and as-built data sheet |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |

## Source

The model is generated from the CFIHOS V2.0 Data Dictionary,
[C-DM-002](https://www.jip36-cfihos.org/wp-content/uploads/2024/10/C-DM-002-Data-Dictionary-V2.0-FINAL.xlsx), which
lists every entity, attribute and relationship of the CFIHOS data model. To regenerate:

```bash
python3 generate.py                     # downloads the data dictionary
python3 generate.py path/to/C-DM-002.xlsx
```

The script needs only the Python standard library.

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow from parent to child, solid when
every child has exactly one parent and dashed when it has at most one. Arrows are named by their relationship type,
e.g. `CLASSIFIES` or `IS_PART_OF`, wherever the name fits without overlapping a card or another name, mandatory
relationships first. Dotted arrows point from a subtype to the supertype whose label it also carries. Cards are coloured by area: plant breakdown, tags and items (sections A.2–A.3),
the reference data library (A.4–A.5), and documents and spare part records (A.6–A.9). Opened in a browser, hovering a
card or arrow shows its name and description, and each card links to its POSC Caesar reference. To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

The sample data is one handover package of a fictional plant, the Kestrel Gas Processing Plant: the two condensate
export pumps `P-2001A`/`P-2001B` and their motors, tags in a process unit and area, classed by CFIHOS reference data
and fulfilled by serialised equipment of the manufacturer's model parts. Around them sits the commercial and document
trail of the handover: the purchase order and its items, the spare parts interchangeability record for the mechanical
seals, and an as-built vendor data sheet with its revision, native file, tag references and transmittal. The CFIHOS
unique codes, plant codes and company names are illustrative.

[`model.cypher`](model.cypher) creates the ontology's constraints and loads the data. Run it against an empty database
of Neo4j 5 or later, Enterprise Edition, which its node key and property existence constraints need, e.g. with
`cypher-shell -f model.cypher`. To regenerate:

```bash
python3 ../../cypher.py .
```

## Mapping

| CFIHOS data dictionary | Ontology |
|---|---|
| Entity, e.g. `TAG CLASS` | Node, labelled in PascalCase, e.g. `TagClass` |
| Attribute, e.g. `Tag name` | Property, in camelCase, e.g. `tagName` |
| `Identifier` attributes | One `KEY` constraint over all of them, e.g. `plantCode` and `tagName` on `Tag` |
| `Mandatory` attributes | An `EXISTS` constraint each |
| `Text, max N characters` | `STRING`, with a `pattern` limiting it to N characters |
| `Integer`, `Boolean (Yes/No)`, `Date`, `Decimal`, `NUM` | `INTEGER`, `BOOLEAN`, `DATE`, `FLOAT`, `FLOAT` |
| Relationship, e.g. `PROCESS UNIT` *is functionally divided in* `TAG` | Relationship from parent to child, typed by its verb, e.g. `IS_FUNCTIONALLY_DIVIDED_IN` |
| Relationship is `Mandatory` / `Optional` | `count: 1` / `max_count: 1` at the child end |
| Subtype, e.g. `TAG CLASS` of `TAG OR EQUIPMENT CLASS` | Implied label, e.g. every `TagClass` is also a `TagOrEquipmentClass` |
| CFIHOS unique code, e.g. `CFIHOS-00000028` | `reference` to its [POSC Caesar](https://www.posccaesar.org/ontologies/cfihos/v2.0) page, and `extensions.custom.cfihosCode` |

Nodes also record the dictionary section and data source (who supplies the data) in `extensions.custom`; properties
record their format and requirement, and relationships their verb, section and whether they are identifying.

Descriptions combine the dictionary's definition, note and example. Where these exceed the format's 1,024-character
limit, the note or example is left out.

### Where the ontology differs from the data dictionary

- **Foreign keys are kept as properties.** CFIHOS data is handed over as one CSV file per entity, joined by foreign
  key attributes such as `Tag.tagClassName`. The ontology keeps those attributes, so that keys such as
  (`plantCode`, `tagName`) can be enforced, and also has the relationships they describe.
- **Subtypes are labels, not relationships.** The 17 supertype/subtype pairs, recorded in the dictionary as unnamed
  relationships, become implied labels. Subtypes of `MODEL PART` repeat its relationship to itself; those copies are
  left out, as the relationship on `ModelPart` already applies to them.
- **Some relationships are named by the ontology.** Four unnamed relationships that aren't subtypes are given a verb:
  `ModelPart` *is the original model part of* `ModelPart`, `ComponentRole` *is the role of*
  `TagOrEquipmentClassComponent`, `PropertyGroupAllowedForPurpose` *groups* `PropertyToGroupAssignment`, and `Tag`
  *is fulfilled by* `SparePartInterchangeabilityRecordEquipment`. A few verbs are shortened or corrected for their
  type, e.g. *is composing (or a part) of* is `IS_PART_OF`; the original verb is kept in `extensions.custom.verb`.

The reference data library (RDL) itself, the tag and equipment classes, properties, units of measure and other
reference data, isn't part of the ontology. It is data that populates the `TagClass`, `EquipmentClass`, `Property`,
`UnitOfMeasure` and similar nodes, and is available from the
[CFIHOS standards page](https://www.jip36-cfihos.org/cfihos-standards/).

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json) and reports no issues for any of
the built-in validation sets, including `all`.
