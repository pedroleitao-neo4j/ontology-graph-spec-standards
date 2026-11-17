# DEXPI 2.0.1

An ontology for the [DEXPI Specification](https://dexpi.org/specifications/) 2.0.1, published by the DEXPI
(Data Exchange in the Process Industry) Initiative. DEXPI standardises the exchange of piping and instrumentation
diagram (P&ID) data between engineering tools: the plant and its process, and the diagrams that represent them.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the official DEXPI specification model sources |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |
| [`../../cypher.py`](../../cypher.py) | Checks the sample data against `model.json` (shared by every standard) and writes `model.cypher` |
| [`sample.json`](sample.json) | Sample data: a P&ID extract of a fictional gas plant, from the plant breakdown and tagged equipment to line segments, control loops and signals |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |

## Source

The model is generated from the model sources of the DEXPI Specification 2.0.1, tag
[`V2.0.1`](https://gitlab.com/dexpi/Specification/-/tree/V2.0.1/src/model) of the
[DEXPI Specification repository](https://gitlab.com/dexpi/Specification). The specification's class model is written
in a small Python DSL (`CONCRETE_CLASS`, `DATA_PROPERTY`, `COMPOSITION_PROPERTY` and so on), from which DEXPI builds its
[HTML](https://dexpi.org/specification/2.0.1/html/index.html) and PDF documentation and its XML exchange format; the
enumerations are listed in `.ods` spreadsheets alongside. `generate.py` reads both without running the DSL, so it
doesn't need DEXPI's own build tools. To regenerate:

```bash
python3 generate.py                                   # downloads the V2.0.1 sources from GitLab
python3 generate.py path/to/Specification-V2.0.1.zip  # or an archive, a clone, or its src/model directory
```

The script needs only the Python standard library.

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow from owner to target, solid for a
composition, from an owner to its parts, and dashed for a reference to another object. Arrows are named by their
relationship type, e.g. `HAS_NOZZLES` or `HAS_CHAMBER`, wherever the name fits without overlapping a card or another
name, compositions first. Dotted arrows point from a subtype to the supertype whose label it also carries. Cards are
coloured by module: Core (data types, quantities and diagrams), Plant (structure, equipment, piping and
instrumentation) and Process (steps, connections and materials), and print their package. Opened in a browser,
hovering a card or arrow shows its name and description, and each card links to its page in the specification. To
regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

The sample data is one P&ID extract of a fictional plant, the Kestrel Gas Processing Plant, in the form an engineering
tool would exchange: a plant model with its metadata, the plant breakdown from the enterprise to its sections, areas,
systems and trains, and the condensate line 20-113 running from the feed drum `PV-2010` through export pump
`P-2001A` (with its motor and impeller; the standby `P-2001B` beside it), its discharge valve, flow element and
off-page connector. The flow control loop `L20.001` completes the instrumentation: the measuring system that senses
the line, the controller `FIC-2010` it feeds, and the fail-close actuator that closes globe valve `FV-2001`. Physical
quantities carry their DEXPI units in the value, e.g. `120 MetreCubedPerHour`, as the exchange format does.

[`model.cypher`](model.cypher) creates the ontology's constraints and loads the data. Run it against an empty database
of Neo4j 5 or later, Enterprise Edition, which its node key constraints need, e.g. with `cypher-shell -f model.cypher`.
To regenerate:

```bash
python3 ../../cypher.py .
```

## Mapping

| DEXPI specification | Ontology |
|---|---|
| Class, e.g. `Plant.ProcessEquipment.CentrifugalPump` | Node, labelled by its class name, e.g. `CentrifugalPump` |
| Abstract class, e.g. `TaggedPlantItem` | Node, with `extensions.custom.abstract: true` |
| Supertype, e.g. `Pump` of `CentrifugalPump` | Implied label, e.g. every `CentrifugalPump` is also a `Pump` |
| Data property, e.g. `TagName` | Property, in camelCase, e.g. `tagName` |
| Template property applied to a class, e.g. `PlantTemplates.FluidCode` | Property of that class, e.g. `PipingComponent.fluidCode` |
| Data property with multiplicity `1..1` | An `EXISTS` constraint |
| Data property with an unbounded multiplicity | A list type, e.g. `LIST<STRING>` |
| `String`, `AnyURI`, `Double`, `Integer`, `UnsignedByte`, `Boolean`, `DateTime` | `STRING`, `STRING`, `FLOAT`, `INTEGER`, `INTEGER`, `BOOLEAN`, `ZONED DATETIME` |
| Enumeration, e.g. `NumberOfPortsClassification` | `STRING`, with its literals in camelCase in `one_of` |
| Structured data type, e.g. `PhysicalQuantity`, `MultiLanguageString` | `STRING`; the DEXPI type is kept in `extensions.custom.dexpiType` |
| Composition property, e.g. `NozzleOwner.Nozzles` | Relationship from owner to part, e.g. `HAS_NOZZLES` |
| Reference property, e.g. `Nozzle.Chamber` | Relationship from owner to target, e.g. `HAS_CHAMBER` |
| Multiplicity of a composition or reference, e.g. `0..1` | Count at the `from` end, e.g. `max_count: 1` |
| Opposite multiplicity of a reference, e.g. `0..1` | Count at the `to` end, e.g. `max_count: 1` |
| Object `id` in the DEXPI XML exchange format | An `id` property on every node, and a `KEY` constraint over it |

Each node, property and relationship links to its page in the
[DEXPI Specification 2.0.1](https://dexpi.org/specification/2.0.1/html/index.html) in its `reference`. Nodes also record
their module, package, reference data library (RDL) entry, e.g. `JORD_RDL.PUMP`, and applied templates in
`extensions.custom`; properties record their RDL entry, multiplicity (`lower` and `upper`, with an absent `upper` meaning unbounded) and DEXPI type,
and relationships whether they are a composition, their multiplicities and, for a `QualifiedValue`, its type parameter.

Descriptions combine the specification's description, the multiplicity where it isn't `0..1`, its example value and,
for a structured data type, the DEXPI type. Where these exceed the format's 1,024-character limit, the later parts are
left out. The specification's
reStructuredText markup is reduced to plain text, e.g. `` :sp:element:`~Core.Note` `` becomes `Note` and `<OWNER>`
the owning class's name.

### Where the ontology differs from the specification

- **Every node has an `id` key.** The class model has no identifiers; the XML exchange format identifies each object by
  the `id` attribute of its `Object` element, which is unique within a file. The ontology makes it a key, so that
  nodes can be matched and references resolved. When several exchange files are loaded into one graph, their ids
  need to be made unique, e.g. by prefixing them with the file or model they came from.
- **Structured data types are strings.** `PhysicalQuantity` (a value and a unit), `MultiLanguageString`, `Point`,
  `Color` and `Stroke` have no Neo4j property type; the ontology types them as `STRING` and keeps the DEXPI type, e.g.
  `PhysicalQuantity with UnitType → LengthUnit`, in the description and `extensions.custom.dexpiType`. How a value is
  encoded, e.g. `40 Metre`, is up to the loader.
- **Undefined values aren't distinguished.** Most DEXPI data properties are typed `Undefined | <type>`, so that a
  value can be explicitly undefined. The ontology types the property by its defined type, and records the
  `Undefined | ` in `extensions.custom.dexpiType`.
- **`QualifiedValue.value` is `ANY`.** Its type is a type parameter that each composition sets, e.g.
  `Type → PhysicalQuantity with UnitType → MassFlowRateUnit` on `Composition.MassFlow`; that is kept in the
  relationship's `extensions.custom.typeParameter`.
- **Template properties are copied into each class.** DEXPI defines shared properties once, in `PlantTemplates`, and
  applies them to classes; the ontology gives each class its own copy, as the specification's documentation does.
- **Properties aren't inherited.** A property, constraint or relationship is defined on the class that declares it. A
  node of a subtype carries its supertypes' labels, through which it has their properties and relationships too.
- **A part has at most one owner.** A composition's opposite multiplicity isn't declared in the sources; the ontology
  sets the UML default, `max_count: 1` at the `to` end, so that each part belongs to at most one owner per
  relationship type.
- **Relationship types are named by the ontology.** DEXPI names a composition or reference property after its
  target, e.g. `Nozzles`; the ontology prefixes it with `HAS_`, e.g. `HAS_NOZZLES`.

The diagram part of DEXPI (`Core.Diagram`, `Plant.Diagram` and `Process.Diagram`) is included, as it is part of the
class model. The reference data library itself, the RDL entries classes and properties point at, isn't part of the
ontology; it is available from the [DEXPI sandbox](https://sandbox.dexpi.org/) and
[POSC Caesar](https://data.posccaesar.org/rdl/).

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json) and reports no issues for any of
the built-in validation sets, including `all`.
