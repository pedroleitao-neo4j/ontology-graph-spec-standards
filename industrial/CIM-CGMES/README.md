# IEC CIM (CGMES 3.0)

An ontology for the IEC Common Information Model (CIM) for power systems, IEC 61970 and IEC 61968, as profiled by the
[Common Grid Model Exchange Standard (CGMES)](https://www.entsoe.eu/digital/cim/cim-for-grid-models-exchange/) 3.0,
standardised as IEC 61970-600 and published by ENTSO-E. CGMES is how European transmission system operators exchange
grid models: the equipment of the network, its topology, the inputs and results of a power flow, measurements and
limits, short circuit and dynamic models, and how the network is drawn and located.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the official CGMES 3.0 RDFS vocabularies |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`sample.json`](sample.json) | Sample data: a piece of a grid model, from a 650 MVA generator to the load it supplies |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |
## Source

The CIM itself is maintained by IEC TC 57 as a UML model, which isn't freely available. Its official open,
machine-readable form is the set of RDFS vocabularies that ENTSO-E publishes for the CGMES profiles: each profile
selects the CIM classes, attributes and associations it exchanges, with the CIM's names and descriptions. The model is
generated from the CGMES 3.0 vocabularies in `CGMES/RDFS`, tag
[`cgmes3.0`](https://github.com/entsoe/application-profiles-library/tree/cgmes3.0/CGMES/RDFS) (commit `8eff738b`), of
the [ENTSO-E application profiles library](https://github.com/entsoe/application-profiles-library). Ten profiles of
IEC 61970-600-2 are read and merged into one model:

| Keyword | Profile | Vocabulary version |
|---|---|---|
| `EQ` | Core Equipment | 3.0.0 |
| `EQBD` | Equipment Boundary | 3.0.0 |
| `OP` | Operation | 3.0.0 |
| `SC` | Short Circuit | 3.0.0 |
| `TP` | Topology | 3.0.0 |
| `SSH` | Steady State Hypothesis | 3.0.0 |
| `SV` | State Variables | 3.0.0 |
| `DY` | Dynamics | 1.0.0 |
| `DL` | Diagram Layout | 3.0.0 |
| `GL` | Geographical Location | 3.0.0 |

The vocabularies are RDF/XML; `generate.py` reads them with the standard library's XML parser, so it doesn't need an
RDF library. To regenerate:

```bash
python3 generate.py                               # downloads the cgmes3.0 vocabularies from GitHub
python3 generate.py path/to/application-profiles-library-cgmes3.0.zip  # or a clone, or a folder of the .rdf files
```

The script needs only the Python standard library.

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow from the end of an association
that CGMES exchanges to the other, solid where every source has one or more targets, dashed where it has at most one,
and thin otherwise. Arrows are named by their relationship type, e.g. `HAS_CONDUCTING_EQUIPMENT`, wherever the name
fits without overlapping a card or another name. Dotted arrows point from a subclass to the superclass whose label it
also carries. Cards are coloured by the profile that defines the class: equipment and boundary (`EQ`, `EQBD`);
topology, power flow and operation (`TP`, `SSH`, `SV`, `OP`, `SC`); dynamics (`DY`); and diagram layout and
geography (`DL`, `GL`). They print that profile, the CIM package for dynamics classes, whether the class is abstract,
and the number of properties. Opened in a browser, hovering a card or arrow shows its name and description, and each
card links to the class in its RDFS vocabulary. To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

[`sample.json`](sample.json) and [`model.cypher`](model.cypher) hold a small part of the grid model of Northgrid, a
fictional transmission system operator: an 85 km 400 kV line runs from Brookfield power station, where a 650 MVA
generator feeds the grid through a 21/400 kV step-up transformer, to Ashby substation, where a 400/220 kV
autotransformer with an on-load tap changer supplies a 220 kV load. The data follows the exchange: substations,
voltage levels, busbars, breakers, line and transformer parameters, terminals, connectivity nodes and the topological
nodes they collapse into with every switch closed, current limits on the line, and the solved power flow as state
variables: the voltage at each topological node and the flow at each terminal. Objects are identified as CIMXML
identifies them, with `rdfId` and `mRID` UUIDs.

The script needs Neo4j 5 or later, Enterprise Edition, for its node key and property existence constraints, and an
empty database. To regenerate and load:

```bash
python3 ../../cypher.py .
cypher-shell -f model.cypher
```

## Mapping

| CGMES vocabulary | Ontology |
|---|---|
| Class, e.g. `cim:ACLineSegment` | Node, labelled by its class name, e.g. `ACLineSegment` |
| The same class declared by several profiles | One node, with the attributes and associations of every profile |
| Class without the `concrete` stereotype, e.g. `ConductingEquipment` | Node, with `extensions.custom.abstract: true` |
| Superclass, `rdfs:subClassOf`, e.g. `Conductor` of `ACLineSegment` | Implied label, e.g. every `ACLineSegment` is also a `Conductor` |
| Attribute, e.g. `ACLineSegment.r` | Property, by its CIM name, e.g. `r` |
| Attribute with multiplicity `1..1` in every profile that declares it | An `EXISTS` constraint |
| Primitive `Float`, `Decimal`, `Integer`, `Boolean`, `String`, `URI`, `MonthDay`, `DateTime`, `Date` | `FLOAT`, `FLOAT`, `INTEGER`, `BOOLEAN`, `STRING`, `STRING`, `STRING`, `ZONED DATETIME`, `DATE` |
| CIM data type, e.g. `ActivePower`, `Resistance`, `PU` | The type of its `value`, e.g. `FLOAT`; the CIM type and its fixed unit, e.g. `MW`, in `extensions.custom` |
| Compound, e.g. `StreetAddress` | `STRING`; the CIM type is kept in `extensions.custom.cimType` |
| Enumeration, e.g. `SynchronousMachineKind` | `STRING`, with its literals in `one_of`, e.g. `generator` |
| Association end with `cims:AssociationUsed` `Yes`, e.g. `Terminal.ConductingEquipment` | Relationship from its domain to its range, e.g. `HAS_CONDUCTING_EQUIPMENT` from `Terminal` to `ConductingEquipment` |
| Multiplicity of that end, e.g. `M:1` | Count at the `from` end, e.g. `count: 1` |
| Multiplicity of the inverse end, e.g. `ConductingEquipment.Terminals`, `M:0..n` | Count at the `to` end, here none |
| `rdf:ID` or `rdf:about` of an object in a CGMES (CIMXML) file | An `rdfId` property on every node, and a `KEY` constraint over it |

Each node, property and relationship links in its `reference` to the line of the RDFS vocabulary that declares it, in
the profile that defines it: the first, in the order of the table above, that doesn't merely describe a class defined
in another profile. Nodes record that profile, every profile that declares the class, the CIM package for dynamics
classes, e.g. `ExcitationSystemDynamics`, and whether the class is abstract, European (from the ENTSO-E extension
namespace, e.g. `BoundaryPoint`) or deprecated in `extensions.custom`. Properties record their CIM type, unit,
multiplicity (`lower` and `upper`) and profiles; relationships their role and inverse role, e.g.
`Terminal.ConductingEquipment` and `ConductingEquipment.Terminals`, both multiplicities and their profiles.

Descriptions are the vocabulary's `rdfs:comment`, followed for a property by its multiplicity where it isn't `0..1`
and its CIM type and unit, and for a relationship by both multiplicities. Where these exceed the format's
1,024-character limit, the later parts are left out.

### Where the ontology differs from the standard

- **Every node has an `rdfId` key.** CIMXML (IEC 61970-552) identifies each object by the `rdf:ID` of its element, and
  a profile that adds to an object defined in another refers to it by `rdf:about`. The ontology makes that identifier a
  key on every node, so that the profiles of one object merge into one node and associations resolve. For an
  `IdentifiedObject` it is derived from its `mRID`, which is kept as an ordinary property; classes that aren't
  identified objects, e.g. `CurveData` or `SvVoltage`, have no CIM identifier, but are still identified in CIMXML.
- **The profiles are merged.** CGMES exchanges each profile in a separate file, and a class such as `Terminal` is
  declared in eight of them, each with the attributes it exchanges. The ontology describes the graph that loading every
  profile produces: one node per class, with the union of its attributes and associations. A graph loaded from fewer
  profiles won't have every property.
- **Multiplicities are the loosest any profile declares.** The profiles agree except on two attributes:
  `IdentifiedObject.name` is `1..1` in five profiles and `0..1` in three, so it gets no `EXISTS` constraint.
- **Each association is one relationship.** CIM declares an association at both ends, e.g. `Terminal.ConductingEquipment`
  and `ConductingEquipment.Terminals`, and CGMES exchanges only the end marked `cims:AssociationUsed` `Yes`. The
  ontology makes that end the relationship, from the object that holds the reference in CIMXML; the inverse end gives
  the count at the `to` end, and its name is kept in `extensions.custom.inverseRole`.
- **Relationship types are named by the ontology.** CIM names an association end after its role, e.g.
  `ConductingEquipment`; the ontology prefixes it with `HAS_` and writes it in upper snake case, e.g.
  `HAS_CONDUCTING_EQUIPMENT`. The role is kept in `extensions.custom.role`.
- **Units are fixed, not stored.** A CIM data type such as `ActivePower` is a value with a unit and a multiplier that
  CGMES fixes, e.g. `MW`; the ontology types the property by its value, e.g. `FLOAT`, and keeps the unit in the
  description and `extensions.custom.unit`.
- **Compounds are strings.** `StreetAddress`, `StreetDetail`, `TownDetail` and `Status` in the geographical location
  profile are structured values with no Neo4j property type; the ontology types them as `STRING`. How a value is
  encoded is up to the loader.
- **`Decimal` is `FLOAT`, and `DateTime` is zoned.** Neo4j has no decimal type, so `Money` values are floats. A CIM
  `DateTime` may omit its time zone; the ontology types it `ZONED DATETIME`, so a loader assumes one, e.g. UTC.
- **Properties aren't inherited.** A property, constraint or relationship is defined on the class that declares it. A
  node of a subclass carries its superclasses' labels, through which it has their properties and relationships too.

The file header profile (`FH`, IEC 61970-552 `md:FullModel`), which describes an exchange file rather than the power
system, isn't part of the ontology. Neither are the CIM data types, primitives and enumerations themselves, nor the
CGMES constraints published as SHACL shapes alongside the vocabularies.

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json) and reports no issues for any of
the built-in validation sets, including `all`.
