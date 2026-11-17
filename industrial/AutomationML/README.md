# AutomationML Edition 2.1 (CAEX 3.0)

An ontology for [AutomationML](https://www.automationml.org), standardised as IEC 62714 and published by AutomationML
e.V. AutomationML is the neutral XML format for exchanging plant engineering data between engineering tools: the
plant's hierarchy of objects, the classes they are instances of, the roles they play, their interfaces and the links
between them, and their attributes. Its top-level format is CAEX 3.0, standardised as IEC 62424:2016, which AutomationML
extends with standard libraries of role classes, interface classes and attribute types.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the CAEX 3.0 XML schema and the AutomationML standard libraries |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`sample.json`](sample.json) | Sample data: a CAEX file describing a robot assembly cell |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |
| [`../../cypher.py`](../../cypher.py) | Generates the Cypher script (shared by every standard) from `model.json` and `sample.json`, checking the data against the model |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |

## Source

The model is generated from two sources, both published by AutomationML e.V.:

- **The CAEX 3.0 XML schema**, [`CAEX_ClassModel_V.3.0.xsd`](https://github.com/AutomationML/AMLEngine2.1/blob/098106acd50ca74c10a12d2cbecdae047c1f9b4b/Samples/WikiSnippets/src/CAEX_ClassModel_V.3.0.xsd),
  from AutomationML's [AMLEngine2.1 repository](https://github.com/AutomationML/AMLEngine2.1), at commit `098106a`.
  IEC 62424 is the normative source of the schema. AutomationML distributes it with its tools, and the copy in its
  [AML-UA-XSLT repository](https://github.com/AutomationML/AML-UA-XSLT) has the same content.
- **The AutomationML standard libraries** in the downloads on [automationml.org](https://www.automationml.org/download-archive/),
  as `.aml` (CAEX) files, released by IEC SC65E WG 9:
  - the base libraries of AutomationML Edition 2.1 (`AutomationML 2.10`), in
    [`Whitepaper-AutomationML-Edition-2.1.zip`](https://www.automationml.org/wp-content/uploads/2021/11/Whitepaper-AutomationML-Edition-2.1.zip):
    `AutomationMLInterfaceClassLib`, `AutomationMLBaseRoleClassLib` and `AutomationMLBaseAttributeTypeLib`, each
    version 2.10.0;
  - the role class libraries of whitepaper Part 2, Semantics Libraries, in
    [`AML_Whitepaper_Part2_Semantics-Libraries.zip`](https://www.automationml.org/wp-content/uploads/2023/08/AML_Whitepaper_Part2_Semantics-Libraries.zip):
    `AutomationMLDMIRoleClassLib` 2.4.0 (discrete manufacturing), `AutomationMLCSRoleClassLib` 2.3.1 (control),
    `AutomationMLBMIRoleClassLib` 1.1.0 (batch manufacturing), `AutomationMLCMIRoleClassLib` 1.1.0 (continuous
    manufacturing) and `AutomationMLExtendedRoleClassLib` 2.7.1.

`generate.py` reads the schema and the libraries with Python's XML parser. To regenerate:

```bash
python3 generate.py                     # downloads the schema from GitHub and the libraries from automationml.org
python3 generate.py path/to/sources     # or given .xsd, .aml and .zip files, or directories holding them
```

The script needs only the Python standard library.

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow, solid for a composition, from an
element to the elements it contains, and dashed for a reference, from an element to the object one of its paths or IDs
refers to. Arrows are named by their relationship type, e.g. `HAS_INTERNAL_ELEMENT` or `BASE_CLASS`, wherever the name
fits without overlapping a card or another name, compositions first. Dotted arrows point from a subtype to the
supertype whose label it also carries, e.g. from `Robot` to `DiscManufacturingEquipment`. Cards are coloured by area:
the CAEX file (its libraries, hierarchies and header information), the CAEX objects (classes, instances, interfaces,
links and attributes), the AutomationML role classes, and the AutomationML interface classes and attribute types. Cards
print their XML schema type or library. Opened in a browser, hovering a card or arrow shows its name and description,
and each card links to its declaration in the schema or the download its library comes from. To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

[`sample.json`](sample.json) is a CAEX file describing assembly cell AC-1, which Kellerman Automation GmbH, a fictional
plant builder, passes from its plant engineering tool to its control engineering tool:

- **The file**: its source document information and a revision, and external references to the AutomationML base
  role and interface class libraries.
- **The instance hierarchy**: a `WorkCell` holding a `Robot` with a `MovableTool`, a vacuum gripper, a
  `BeltConveyor` and a `PLC`. Each carries the label of the role class its `RoleRequirements` refer to. Their
  `Port`s and `SignalInterface`s, with a `Direction` attribute, are joined by internal links: the robot's tool flange
  to the conveyor's outlet, the conveyor's inlet to the cell's, and the PLC's fieldbus output to the robot. The
  robot's geometry is a `COLLADAInterface` to a COLLADA file. Attributes carry units, e.g. the robot's cycle time in
  seconds, a semantic reference and a nominal value constraint.
- **The libraries**: a system unit class library with the welding robot and the gripper the instances are based on,
  each with the role class it supports, and the gripper's mapping of its gripping force to the role's tool force; and
  a role class library and an interface class library of the plant builder's own, for the gripper role and the vacuum
  interface.

[`model.cypher`](model.cypher) creates the model's constraints and merges the sample data. It needs Neo4j 5 or later,
Enterprise Edition, for its node key and property existence constraints. To load it into an empty database, and to
regenerate it after editing `sample.json`:

```bash
cypher-shell -f model.cypher
python3 ../../cypher.py .   # from this folder
```

## Mapping

The ontology has two parts. The first is CAEX: the elements of a CAEX file, read from the schema. The second is
AutomationML: the classes of its standard libraries, each a label that the CAEX objects of that class carry.

| CAEX 3.0 schema | Ontology |
|---|---|
| Element with a complex type, e.g. `InternalElement` | Node, labelled by the element's name, e.g. `InternalElement` |
| `CAEXBasicObject` and `CAEXObject`, the base types every element extends | Abstract nodes, with `extensions.custom.abstract: true`; the other nodes carry their labels |
| Element containing another, e.g. `InternalElement` in a `SystemUnitClass` | Relationship from container to contained element, e.g. `HAS_INTERNAL_ELEMENT` |
| `minOccurs` and `maxOccurs` of a contained element | Count at the `from` end, e.g. `min_count: 1` |
| XML attribute, e.g. `RefBaseSystemUnitPath`, or text element, e.g. `Value` | Property, in camelCase, e.g. `refBaseSystemUnitPath`, `value` |
| Attribute or element that refers to another object by its path or ID, e.g. `RefBaseClassPath` | Its property, and a relationship to the object, named without `Ref` and `Path` or `ID`, e.g. `BASE_CLASS` |
| `use="required"`, or a text element with `minOccurs="1"` | An `EXISTS` constraint |
| Text element with `maxOccurs="unbounded"`, e.g. `SuperiorStandardVersion` | A list type, e.g. `LIST<STRING>` |
| `xs:string`, `xs:dateTime` | `STRING`, `ZONED DATETIME` |
| `ChangeMode` enumeration, fixed `SchemaVersion` | `STRING`, with the values in `one_of` |
| Element grouping text elements only, e.g. `NominalScaledType` in a `Constraint` | Properties of its parent, prefixed with its first word, e.g. `nominalRequiredValue` |
| `xs:documentation` | `description` |
| `ID` of a `CAEXObject` | An `id` property on every node, and a `KEY` constraint over it |

| AutomationML standard library | Ontology |
|---|---|
| Role class, e.g. `AutomationMLDMIRoleClassLib/DiscManufacturingEquipment/Robot` | Node, labelled by its name, e.g. `Robot`, carried by each `InternalElement` whose `RoleRequirements` refer to the role class |
| Interface class, e.g. `AutomationMLInterfaceClassLib/AutomationMLBaseInterface/Port` | Node, e.g. `Port`, carried by each `ExternalInterface` whose `RefBaseClassPath` refers to the interface class |
| Attribute type, e.g. `AutomationMLBaseAttributeTypeLib/Direction` | Node, e.g. `Direction`, carried by each `Attribute` whose `RefAttributeType` refers to the attribute type |
| `RefBaseClassPath` of a class, e.g. `DiscManufacturingEquipment` of `Robot` | Implied label, e.g. every `Robot` is also a `DiscManufacturingEquipment` |
| A library's root class, e.g. `AutomationMLBaseRole` | Implied label of the CAEX element whose objects carry it, e.g. every `AutomationMLBaseRole` is an `InternalElement` |
| `AllowedValues` constraint of an attribute type, e.g. `In`, `Out` and `InOut` for `Direction` | A `value` property with the values in `one_of` |

CAEX nodes record their XML schema type in `extensions.custom.xsdType`, and properties the XML attribute or element they
come from. Relationships record whether they are a composition and the element or attribute they come from. Library
nodes record their library and its version, their path, and the attributes and external interfaces their class defines.

The schema documents its elements, attributes and types, so CAEX descriptions come from it. The libraries don't
describe their classes. Instead, a library node's description says which library and path it comes from, what it
derives from, which objects carry it, and what its class defines. Descriptions over the format's 1,024-character limit
are shortened by leaving out their later parts.

### Where the ontology differs from the standard

- **Every node has an `id` key.** A `CAEXObject` has an optional `ID` attribute, which AutomationML uses to identify
  objects: `InternalElement`s and `ExternalInterface`s have one, typically a UUID. The ontology makes it a key, so that
  nodes can be matched and references resolved. Where there's no `ID`, as there often isn't for library classes, and
  for elements that aren't `CAEXObject`s, e.g. `RoleRequirements`, the loader needs to assign one, e.g. the object's
  path.
- **The types between an element and its CAEX base are folded in.** In the schema, `InternalElementType` extends
  `SystemUnitClassType`, and the `ExternalInterface` of an object has the same type as an `InterfaceClass`. An instance
  isn't a class, though. So each element is its own node, carrying the members of the types it extends, and only
  `CAEXObject` and `CAEXBasicObject` become supertype labels.
- **References are resolved into relationships.** CAEX refers to classes by path, e.g.
  `AutomationMLBaseRoleClassLib/AutomationMLBaseRole/Resource`, which may start with an external file's alias and `@`.
  It refers to objects by ID: in an `InternalLink`, by an `InternalElement`'s ID followed by `:` and the interface's
  name. The schema types these references as strings. The ontology keeps each string as a property, and adds a
  relationship to what it refers to, as IEC 62424 describes. A loader has to resolve the paths and IDs, and can only
  do so for classes and objects that are loaded, so a reference by path, which may be to a class in an external
  library, is at most one relationship rather than exactly one, even where the attribute is required. A reference by
  ID, e.g. an `InternalLink`'s two sides, is exactly one.
- **Mirror objects are references to their master.** A mirror `InternalElement` or `ExternalInterface` repeats another
  object, the master, which its `RefBaseSystemUnitPath` or `RefBaseClassPath` identifies by its ID. That's a second
  relationship of the same type, `BASE_SYSTEM_UNIT` or `BASE_CLASS`, to an `InternalElement` or `ExternalInterface`.
- **Library classes are labels, not instances of `RoleClass`.** The library classes are meant to classify the objects
  of a plant, so they're labels that those objects carry: an `InternalElement` that plays the role of a robot is a
  `Robot`. That holds whether the role class is referred to directly or through a role class derived from it, e.g.
  `Robot` through a user-defined `WeldingRobot`. A `RoleClass` loaded from a library file is still a `RoleClass`
  node, and a `SystemUnitClass` that supports a role is linked to it by its `SupportedRoleClass`, without carrying
  its label.
- **Library attributes and interfaces are listed, not modelled.** A role or interface class may define attributes and
  external interfaces, e.g. `Direction` on `Port`. In CAEX, an object of the class has those as `Attribute` and
  `ExternalInterface` elements of its own. The ontology lists them in the node's description and in
  `extensions.custom.attributes` and `interfaces`, rather than making them properties.
- **Clashing class names are suffixed.** `Communication` is both a role class, in `AutomationMLCSRoleClassLib`, and an
  interface class, in `AutomationMLInterfaceClassLib`. Their labels are `CommunicationRole` and
  `CommunicationInterface`, with the CAEX name kept in `extensions.custom.caexName`.
- **Attribute values are strings.** CAEX stores every attribute value as text, with its XML data type, e.g.
  `xs:double`, in `AttributeDataType`. The ontology types `value` and `defaultValue` as `STRING`; a loader may convert
  them by their data type.
- **`AdditionalInformation` is a list of strings.** It may hold any XML, e.g. AutomationML's
  `<AdditionalInformation AutomationMLVersion="2.0"/>`, which a loader needs to serialise.
- **Only the standard libraries are included.** User-defined libraries aren't. That includes the ISA-106 example
  library shipped with the Part 2 role class libraries, `UserDefinedRoleClassLibISA106`, as its name doesn't start
  with `AutomationML`. The libraries of other AutomationML whitepapers, e.g. communication, geometry and kinematics,
  and logic, aren't included either, and nor are application recommendations.

A part, e.g. an `Attribute`, belongs to one element, so every composition has `max_count: 1` at its `to` end. The
schema's parent-child relations between classes, e.g. a `RoleClass` within another, have organisational character
only: inheritance is through `RefBaseClassPath`, which is `BASE_CLASS` in the ontology.

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json) and reports no issues for any of
the built-in validation sets, including `all`.
