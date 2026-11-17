# Asset Administration Shell 3.2

An ontology for the [Asset Administration Shell (AAS)](https://industrialdigitaltwin.io/aas-specifications/IDTA-01001/v3.2/index.html)
metamodel 3.2, specified by the [Industrial Digital Twin Association (IDTA)](https://industrialdigitaltwin.org/) in
IDTA-01001 Part 1 and standardised as IEC 63278-1. The AAS is the
standardised digital twin of Industrie 4.0: an asset administration shell describes an asset through submodels, each
made of submodel elements such as properties, files, collections and operations, whose meaning is given by concept
descriptions and IEC 61360 data specifications.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the official AAS metamodel schemas |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`sample.json`](sample.json) | Sample data: the digital twin of a servo motor, with its nameplate and technical data |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |
| [`../../cypher.py`](../../cypher.py) | Generates the Cypher script (shared by every standard) from `model.json` and `sample.json`, checking the data against the model |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |

## Source

The model is generated from the metamodel schemas of AAS 3.2, tag
[`v3.2.0`](https://github.com/admin-shell-io/aas-specs-metamodel/tree/v3.2.0/schemas) of the IDTA
[aas-specs-metamodel repository](https://github.com/admin-shell-io/aas-specs-metamodel), from which the specification
and its JSON, XML and RDF serialisations are published. `generate.py` reads:

- `schemas/rdf/rdf-ontology.ttl`, the OWL ontology: the classes, their superclasses and descriptions, and the
  enumerations;
- `schemas/rdf/shacl-schema.ttl`, the SHACL shapes: each class's attributes, with their datatypes, classes and
  cardinalities, and which classes are abstract;
- `schemas/json/aas.json`, the JSON Schema, for the values of each enumeration as the JSON and XML formats write them,
  e.g. `xs:boolean`;
- the specification's AsciiDoc pages under `documentation/IDTA-01001`, for the page and anchor of each class.

`generate.py` includes a small Turtle reader, so it doesn't need an RDF library. To regenerate:

```bash
python3 generate.py                                       # downloads the v3.2.0 release from GitHub
python3 generate.py path/to/aas-specs-metamodel-3.2.0.zip # or an archive, or a clone
```

The script needs only the Python standard library.

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow from owner to target. A solid
arrow is a composition, from an owner to its parts, and the one dashed arrow, `RESOLVES_TO`, is a model reference
resolved to the element it identifies. Arrows are named by their relationship type, e.g. `HAS_SUBMODEL_ELEMENTS` or
`HAS_SEMANTIC_ID`, wherever the name fits without overlapping a card or another name. Dotted arrows point from a
subclass to the superclass whose label it also carries. Cards are coloured by the part of the specification that
defines them, which each card also prints:

- Core: shells, asset information, submodels, the environment and concept descriptions (`core`, `environment` and
  `concept-description`)
- Submodel elements (`submodel-elements`)
- Common attributes, references and language strings (`common`, `referencing` and `datatypes`)
- Data specifications: the IEC 61360 and unit of measure templates (`data-specifications`)

Opened in a browser, hovering a card or arrow shows its name and description, and each card links to the class in the
[specification](https://industrialdigitaltwin.io/aas-specifications/IDTA-01001/v3.2/index.html). To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

[`sample.json`](sample.json) is the AAS environment of one synchronous servo motor, serial number 2407-00381, made
by Halden Antriebe GmbH, a fictional drive maker. Its shell holds the asset information, with the motor's global
asset ID, serial and part numbers and thumbnail, and refers to two submodels by model references that `RESOLVES_TO`
them. The submodels follow the IDTA templates:

- **Digital Nameplate**: the manufacturer's name and product designation as multi-language properties, the serial
  number, year and date of manufacture, the manufacturer's address as a collection, and a `SubmodelElementList` of
  the CE and UKCA markings, ordered by `index`.
- **Technical Data**: general information with the manufacturer's logo and product image as files, and the
  technical properties: rated torque, speed and power, degree of protection, and the permitted ambient temperature
  as a range.

Each element's semantic ID is a `Reference` with its `Key`s: an external reference to an ECLASS IRDI, e.g.
`0173-1#02-AAO677#002` for the manufacturer name, or to the template's IRI, or a model reference to one of the
maker's concept descriptions. These define rated torque and degree of protection through IEC 61360 data
specifications, with preferred names in English and German, a unit and level type for the torque and a value list for
the degree of protection, and the newton metre through a unit of measure data specification.

[`model.cypher`](model.cypher) creates the model's constraints and merges the sample data. It needs Neo4j 5 or later,
Enterprise Edition, for its node key and property existence constraints. To load it into an empty database, and to
regenerate it after editing `sample.json`:

```bash
cypher-shell -f model.cypher
python3 ../../cypher.py .   # from this folder
```

## Mapping

| AAS metamodel (OWL and SHACL) | Ontology |
|---|---|
| Class, e.g. `aas:Submodel` | Node, labelled by its name, e.g. `Submodel` |
| Abstract class, e.g. `SubmodelElement`, `Referable` | Node, with `extensions.custom.abstract: true` |
| Superclass, e.g. `DataElement` of `Property` | Implied label, e.g. every `Property` is also a `DataElement` |
| Attribute of type `xs:string`, `xs:base64Binary` or `xs:boolean`, e.g. `Referable/idShort` | Property, e.g. `Referable.idShort`, typed `STRING`, `STRING` or `BOOLEAN` |
| Attribute of an enumeration type, e.g. `Property/valueType` of `DataTypeDefXsd` | `STRING`, with the values the JSON and XML formats use in `one_of`, e.g. `xs:boolean` |
| Attribute without `sh:maxCount 1` | A list type, e.g. `LIST<STRING>` |
| Attribute with `sh:minCount 1` | An `EXISTS` constraint |
| `Identifiable/id`, the globally unique identifier | A `KEY` constraint on `Identifiable` |
| Attribute of a class type, e.g. `Submodel/submodelElements` | Composition relationship from owner to part, typed by the attribute's label, e.g. `HAS_SUBMODEL_ELEMENTS` |
| `sh:minCount` and `sh:maxCount` of such an attribute | Counts at the `from` end, e.g. `max_count: 1` |
| Ordered list: `Reference/keys`, `SubmodelElementList/value` | An `index` property on the relationship |
| `rdfs:comment` | `description` |

Each node, property and relationship links to its class in the specification in its `reference`: the
[Part 1 metamodel](https://industrialdigitaltwin.io/aas-specifications/IDTA-01001/v3.2/index.html), or, for the data
specification templates, [Part 3a (IEC 61360)](https://industrialdigitaltwin.io/aas-specifications/IDTA-01003-a/v3.2/specification.html)
and [Part 3b (units of measure)](https://industrialdigitaltwin.io/aas-specifications/IDTA-01003-b/v3.1/specification.html).
Nodes record their IRI, the part of the specification that defines them and whether they're abstract in
`extensions.custom`; properties their IRI, AAS type, cardinality (`lower` and `upper`, with an absent `upper` meaning
unbounded), string length and, where it is more than the XML character range, pattern; relationships their IRI,
cardinality and whether they're compositions or ordered.

Descriptions combine the `rdfs:comment` of the class or attribute with its cardinality, where it isn't `0..1`, and,
for an enumeration, its name.

### References

AAS elements point at each other through a `Reference`: a list of keys, each a key type and a value, that names an
Identifiable by its `id` and then, for an element within it, each `idShort` along the way. A model reference points at
an element in an AAS environment, e.g. the submodels of a shell; an external reference at something outside it, e.g.
the IRDI of a semantic definition.

The ontology keeps `Reference` and `Key` as nodes, as the metamodel has them, so that every reference, e.g. a
`semanticId`, is a `HAS_SEMANTIC_ID` relationship to a `Reference` with its `HAS_KEYS` relationships to its `Key`s.
It adds one relationship, `Reference` `RESOLVES_TO` `Referable`, from a model reference to the element its keys
identify, so that a shell's submodels or a relationship element's ends can be followed in the graph. A loader sets it
where the element is in the graph; an external reference has none.

### Where the ontology differs from the metamodel

- **Every node has a `uid` key.** AAS identifies an Identifiable globally by its `id`, and a Referable only by its
  `idShort` within its parent; a `Reference`, `Key`, `Qualifier` or language string has no identity of its own. The
  ontology gives every node a `uid` property and a `KEY` over it, so that nodes can be matched, and suggests what a
  loader sets it to: the `id` of an Identifiable, the Identifiable's `id` followed by the `idShort` path of an element
  within it, and an identifier generated from the parent's `uid` and position for anything else. `Identifiable.id`
  is a key too.
- **`RESOLVES_TO` is added.** See [References](#references).
- **A part has at most one owner.** An AAS environment is a tree, in which each element belongs to one parent. The
  ontology sets `max_count: 1` at the `to` end of each composition, so that each part belongs to at most one owner
  per relationship type; that a part has one owner across all relationship types isn't expressed.
- **Values are strings.** A `Property`, `Range`, `Qualifier` or `Extension` value is typed by its `valueType`, one
  of 30 XML Schema types, and exchanged as a string; the ontology types it as `STRING`, as the metamodel does.
- **Lists are ordered by an `index`.** The keys of a reference and the elements of a `SubmodelElementList` are
  ordered; relationships aren't, so each `HAS_KEYS` and `SubmodelElementList` `HAS_VALUE` relationship has an `index`
  property, from 0. It isn't part of the metamodel. Other lists, e.g. a `SubmodelElementCollection`'s elements, aren't
  ordered.
- **Language strings are nodes.** A multi-language text, e.g. a `description` or a `MultiLanguageProperty` value, is a
  set of language strings, each a `language` and `text`; the ontology keeps each as a node, e.g. a
  `LangStringTextType`, which is also an `AbstractLangString`.
- **Properties aren't inherited.** A property, constraint or relationship is defined on the class that declares it,
  e.g. `idShort` on `Referable`. A node of a subclass carries its superclasses' labels, through which it has their
  properties and relationships too.
- **Some constraints aren't kept.** String lengths and patterns, e.g. the 128-character `idShort` that starts with a
  letter, are recorded in `extensions.custom` but not enforced. The specification's other constraints, e.g. AASd-117,
  that `idShort` is required for an element that isn't in a `SubmodelElementList`, and that `idShort`s are unique
  among siblings, have no equivalent in the format.
- **Relationship types are named by the ontology.** AAS names an attribute, e.g. `submodelElements`; the ontology
  types the relationship by the attribute's `rdfs:label` in upper snake case, e.g. `HAS_SUBMODEL_ELEMENTS`, dropping
  the `HAS_` where the label is already a verb phrase: `IS_CASE_OF` and `REFERS_TO`.

The enumerations, e.g. `AssetKind` and `KeyTypes`, aren't nodes: they type properties, through `one_of`.

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json) and reports no issues for any of
the built-in validation sets, including `all`.
