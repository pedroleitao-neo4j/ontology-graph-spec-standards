# ISA-95 (B2MML V0700)

An ontology for [ANSI/ISA-95](https://www.isa.org/standards-and-publications/isa-standards/isa-95-standard),
Enterprise-Control System Integration, known internationally as IEC 62264, as MESA International's
[Business To Manufacturing Markup Language (B2MML)](https://github.com/MESAInternational/B2MML-BatchML) implements it.
ISA-95 standardises the information exchanged between business systems such as ERP and manufacturing operations
systems such as MES: the resources manufacturing uses (personnel, equipment, physical assets and material), what
manufacturing can do and is asked to do (process segments, operations definitions, schedules and capability), what it
did (operations performance and events), and the work activities of manufacturing operations management.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the official B2MML XML schemas |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |
| [`sample.json`](sample.json) | Sample data: a day of production at a battery cell plant, scheduled and reported |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |

## Source

ISA-95 itself is published as documents, not as a machine-readable model. B2MML is its XML Schema implementation,
maintained by MESA International and used in practice to exchange ISA-95 data. The model is generated from B2MML
V0700, tag [`V7.00.00`](https://github.com/MESAInternational/B2MML-BatchML/tree/V7.00.00/Schema) of the
[B2MML-BatchML repository](https://github.com/MESAInternational/B2MML-BatchML), which is based on
ANSI/ISA-95.00.02-2018 (object model attributes), ANSI/ISA-95.00.04-2018 (objects and attributes for manufacturing
operations management integration) and ANSI/ISA-95.00.05-2018 (business to manufacturing transactions). `generate.py`
reads the `B2MML-*.xsd` schemas with an XML parser, so it doesn't need an XML Schema library. To regenerate:

```bash
python3 generate.py                                  # downloads the V7.00.00 schemas from GitHub
python3 generate.py path/to/B2MML-BatchML.zip        # or an archive, a clone, or its Schema directory
```

The script needs only the Python standard library.

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow from owner to target, solid for a
composition, from an object to the objects nested in it, and dashed for a reference, an ID that identifies another
object. Arrows are named by their relationship type, e.g. `HAS_EQUIPMENT_PROPERTY` or `HAS_EQUIPMENT_CLASS`, wherever
the name fits without overlapping a card or another name, compositions first. Dotted arrows point from each object a
record entry can hold to `InformationObject`, the label it also carries. Cards are coloured by ISA-95 model: Resources
(personnel, equipment, physical assets, material, operational locations, tests and resource relationship networks),
Operations (process segments, operations definitions, schedules, performance, capability and events), Work (work
definitions, schedules, performance, capability, alerts, calendars, records and workflow specifications) and Common
(the segment resource specifications, requirements, capabilities and actuals, parameters and record templates the
others share), and print their schema file. Opened in a browser, hovering a card or arrow shows its name and
description, and each card links to its type in the B2MML schema. To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

[`sample.json`](sample.json) and [`model.cypher`](model.cypher) hold one day of production at the Halden plant of
Nordcell, a fictional battery cell manufacturer, following an ISA-95 exchange between an ERP and an MES: the
role-based equipment hierarchy down to a coater and a dryer, the classes, people and anode slurry the area works
with, and the process segments that coat and dry an electrode. The MES receives an operations schedule, its request
and the equipment, material and personnel each segment requires, and reports the operations performance back, with
what each segment actually used and when it ran. Objects carry the IDs B2MML exchanges, e.g. `SCH-2026-11-10` for the
schedule.

The script needs Neo4j 5 or later, Enterprise Edition, for its node key and property existence constraints, and an
empty database. To regenerate and load:

```bash
python3 ../../cypher.py .
cypher-shell -f model.cypher
```

## Mapping

| B2MML | Ontology |
|---|---|
| Object type, e.g. `EquipmentType`, `OpMaterialRequirementType` | Node, labelled by the type's name without `Type`, e.g. `Equipment`, `OpMaterialRequirement` |
| `ID` element of an object | An `id` property and a `KEY` constraint over it |
| Element of a simple type, e.g. `PublishedDate` | Property, in camelCase, e.g. `publishedDate` |
| Element with `minOccurs` 1 and `maxOccurs` 1 | An `EXISTS` constraint |
| Element with an unbounded `maxOccurs`, e.g. `Description` | A list type, e.g. `LIST<STRING>` |
| `IdentifierType`, `TextType`, `CodeType`, `DescriptionType` and the other text types | `STRING` |
| `DateTimeType`, `DurationType`, `NumericType`, `IndicatorType` | `ZONED DATETIME`, `DURATION`, `FLOAT`, `BOOLEAN` |
| Enumeration, e.g. `EquipmentLevelType` | `STRING`, with its values in `one_of`, e.g. `Enterprise`, `Site`, `Area` |
| Structured value, e.g. `Quantity` of `QuantityValueType` | Properties named after the element, e.g. `quantity`, `quantityDataType`, `quantityUnitOfMeasure`, `quantityKey` |
| Element of an object type, e.g. `EquipmentProperty` in `EquipmentType` | Composition relationship from owner to part, e.g. `HAS_EQUIPMENT_PROPERTY` |
| ID reference to another object, e.g. `EquipmentClassID` in `EquipmentType` | Reference relationship to that object, e.g. `HAS_EQUIPMENT_CLASS` to `EquipmentClass` |
| `HierarchyScope` | Relationship to the `Equipment` it identifies, `HAS_HIERARCHY_SCOPE` |
| `EquipmentAssetMapping` | Relationship from `Equipment` to `PhysicalAsset`, with the mapping's `startTime`, `endTime` and `hierarchyScope` |
| `InformationObject`, a choice of any of the objects | `InformationObject` label, which each of those objects also carries, and a `HAS_INFORMATION_OBJECT` relationship to it |
| `minOccurs` and `maxOccurs` of a composition or reference | Count at the `from` end, e.g. `max_count: 1` |
| Shared group, e.g. `WorkDefinitionType` | Properties and relationships of each type that uses it, e.g. `WorkMaster` and `WorkDirective` |

Each node, property and relationship links to the line of the B2MML schema on GitHub that declares it in its
`reference`. Nodes also record their ISA-95 model, schema file, B2MML type and the groups they use in
`extensions.custom`; properties record their multiplicity (`lower` and `upper`, with an absent `upper` meaning
unbounded) and B2MML type, e.g. `QuantityValueType.UnitOfMeasure`; relationships record whether they are a
composition, the element they come from and its multiplicity.

B2MML documents few of its types; where it does, e.g. `EquipmentClass`, `HierarchyScope` and `EquipmentLevel`, the
description is the schema's documentation. Otherwise descriptions are made from the element and type names, and add
the multiplicity where it isn't `0..1`. Where these exceed the format's 1,024-character limit, the later parts are left
out.

### Where the ontology differs from the standard

- **Only the ISA-95 objects are included.** Each B2MML object comes with message types for the transactions of
  ISA-95 Part 5, e.g. `GetEquipment`, `ShowEquipment`, `ProcessEquipment` and `SyncEquipment`, which wrap the objects
  in an `ApplicationArea` and a `DataArea`; these, the `Trans…` types they use, and the infrastructure schemas
  (`ConfirmBOD`, `ErrorMessage`, `TransactionProfile` and `MasterDataProfile`) aren't part of the ontology. Nor are the
  `Extended:` groups through which users extend B2MML, which are empty.
- **BatchML isn't included.** The repository also holds BatchML, the XML implementation of ISA-88 (IEC 61512) for
  batch control: general recipes, batch information and batch production records. It is a standard of its own, so
  the ontology leaves it out, together with the four BatchML objects an information object can be.
- **ID references are relationships.** B2MML refers to another object by its ID, e.g. `EquipmentClassID`; the
  ontology makes each such reference a relationship to the object, named after the element, e.g.
  `HAS_EQUIPMENT_CLASS`. A reference is resolved from its name: the object it names, e.g. `MaterialSublotID` to
  `MaterialSubLot`; without a role it gives the reference, e.g. `EquipmentClassBaseID`, `JobOrderSourceID`,
  `WorkMasterPatternID` or `DependentProcessSegmentID`; or the segment object B2MML prefixes with `Op`, e.g.
  `SegmentRequirementID` to `OpSegmentRequirement`. Five references that don't name their object are resolved by
  `generate.py` explicitly: `OperationalClassID` and `OperationalClassPropertyID` (operational location classes),
  `OperationsRecordSpecificationID`, and `FromWSNodeID` and `ToWSNodeID` (workflow specification nodes); the
  misspelt `WorkCalendarDefintion…ID` references are read as `WorkCalendarDefinition…`. References that can't be
  told apart this way remain properties, e.g. `resourceId`, `testableObjectId` and `workDefinitionId`, which may
  identify any of several kinds of object, and `billOfMaterialsId`, `batchId` or `vendorId`, which identify objects
  outside ISA-95.
- **Every object has an `id` key.** B2MML IDs are unique among the objects of a kind, e.g. among equipment, so each
  node has a `KEY` over `id`. When several B2MML documents are loaded into one graph, their IDs need to be unique, e.g.
  by prefixing them with the document or system they came from.
- **Structured values are flattened.** A `ValueType` or `QuantityValueType` has a value string, a data type, a unit
  of measure and a key; a `SpatialDefinitionType` a value, format and coordinate reference system; and a
  `ResourceLocationType` a location and the kind of location it is. These have no identity of their own, so each
  part becomes a property of the object that holds the value, named after the element. A repeated value, e.g. a
  property with several values, becomes a list for each part, the parts of each value in the same position.
- **A hierarchy scope is a relationship to equipment.** A `HierarchyScope` identifies where information fits in the
  role-based equipment hierarchy by an `EquipmentID`, with nested `HierarchyScopeChild` elements going down the
  hierarchy. The ontology relates the object to the `Equipment` the scope identifies, the innermost one, and takes
  its level from that equipment's `equipmentLevel`. On an equipment asset mapping, which is a relationship, the scope
  is the `hierarchyScope` property, the equipment's ID.
- **An equipment asset mapping is a relationship.** `EquipmentAssetMapping` relates a piece of equipment to the
  physical asset that implements it for a time, by their IDs; it becomes a `HAS_EQUIPMENT_ASSET_MAPPING`
  relationship from `Equipment` to `PhysicalAsset` with the mapping's times.
- **An information object is a label.** A work or operations record entry holds one information object, which may be
  any of 48 B2MML objects, e.g. equipment, a material lot or a job order. The ontology gives each of them the
  `InformationObject` label too, and relates the entry to it by `HAS_INFORMATION_OBJECT`; the `InformationObject`
  node has an `id` with an `EXISTS` constraint, but no key, since IDs are only unique among objects of one kind. The
  alternative to an information object, an `ExternalReferenceID`, is the `externalReferenceId` property.
- **Shared groups are copied into each type.** `WorkMaster` and `WorkDirective` share the elements of the
  `WorkDefinitionType` group; the ontology gives each its own copy, and records the group in `extensions.custom`.
- **Attributes of the core component types aren't included.** B2MML's text, code, identifier and measure types carry
  optional attributes from UN/CEFACT, e.g. `schemeID` or `languageID`; enumerations an `OtherValue`, which holds the
  value when the enumeration's value is `Other`. The ontology types each element by its value alone.
- **A part has at most one owner.** A nested object belongs to the object it is nested in, so each composition has
  `max_count: 1` at the `to` end.
- **Relationship types are named by the ontology.** B2MML names an element after its content, e.g. `EquipmentChild`;
  the ontology prefixes it with `HAS_`, e.g. `HAS_EQUIPMENT_CHILD`.

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json) and reports no issues for any of
the built-in validation sets, including `all`.
