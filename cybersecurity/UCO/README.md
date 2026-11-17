# UCO 1.5.0

An ontology for the [Unified Cyber Ontology (UCO)](https://unifiedcyberontology.org/) 1.5.0, published by the UCO
Community under the Linux Foundation's Cyber Domain Ontology project. UCO is a foundation for representing
cyber-domain information: the observable objects of digital forensics and incident response, such as files,
processes, accounts, devices and network connections, and the facets that characterise them; the actions performed
on them and the tools that perform them; the identities, roles, locations and victims involved; and the markings,
provenance and analysis that qualify them. [CASE](../CASE) builds on it.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the official UCO Turtle files |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`sample.json`](sample.json) | Sample data: the forensic acquisition and analysis of a suspect's laptop and phone |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |
| [`../../cypher.py`](../../cypher.py) | Generates `model.cypher` (shared by every standard) from `model.json` and `sample.json`, checking the data against the model |

## Source

The model is generated from the Turtle files of UCO 1.5.0, tag
[`1.5.0`](https://github.com/ucoProject/UCO/tree/1.5.0/ontology) of the
[UCO repository](https://github.com/ucoProject/UCO): the `ontology/uco` files, one per namespace (`core`, `types`,
`observable`, `action`, `tool`, `identity` and so on), and the `ontology/co` shapes for the Collections Ontology that
UCO's threads use. UCO is written in OWL 2, and constrains each class with SHACL shapes; the classes are their own
SHACL node shapes. `generate.py` includes a small Turtle reader, so it doesn't need an RDF library. To regenerate:

```bash
python3 generate.py                        # downloads the 1.5.0 release from GitHub
python3 generate.py path/to/UCO-1.5.0.zip  # or an archive, or a clone
```

The script needs only the Python standard library.

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow from the class that has the
property to the class of its values. A solid, darker arrow is required: every source node has one or more. A dashed
arrow allows at most one, and a thin solid arrow is otherwise unconstrained. Arrows are named by their relationship
type, e.g. `HAS_FACET` or `CREATED_BY`, wherever the name fits without overlapping a card or another name, with
required relationships placed first. Dotted arrows point from a subclass to the superclass whose label it also
carries.

Cards are coloured by namespace, which each card also prints:

- Core, types, patterns and markings: `core`, `types`, `pattern` and `marking`
- Observables and their facets: `observable`
- Actions, tools, analysis and configuration: `action`, `tool`, `analysis` and `configuration`
- Identities, roles, locations and victims: `identity`, `role`, `location` and `victim`

Opened in a browser, hovering a card or arrow shows its name and description, and each card links to its page in the
[UCO documentation](https://ontology.unifiedcyberontology.org/documentation/). To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

[`sample.json`](sample.json) is a digital forensics case: a lab acquires the laptop and phone of an engineer suspected
of leaking their employer's gearbox designs. FTK Imager, behind a write blocker, images the laptop's disk, and UFED
extracts the phone. Autopsy then finds a ZIP archive of the designs, the email that sent it to a personal address, a
file-sharing upload page and an SMS about it. Each `Action` records its `PERFORMER`, `INSTRUMENT`s, `OBJECT`s and
`RESULT`s. Each observable keeps its properties on its facets, e.g. a `FileFacet` and a `ContentDataFacet` with MD5
and SHA-256 `Hash`es. `ObservableRelationship`s record what is contained within what, e.g. the SIM card within the
phone, and the archive attached to the email. The people, organisations and addresses are fictional.

[`model.cypher`](model.cypher) creates the model's constraints and merges the sample data. It needs Neo4j 5 or later,
Enterprise Edition, for its node key and property existence constraints. To regenerate and load it:

```bash
python3 ../../cypher.py .            # from this folder; checks sample.json against the model
cypher-shell -f model.cypher         # against an empty database
```

## Mapping

| UCO (OWL and SHACL) | Ontology |
|---|---|
| Class, e.g. `observable:File` | Node, labelled by its local name, e.g. `File` |
| `rdfs:subClassOf` a UCO class, e.g. `File` of `FileSystemObject` | Implied label, e.g. every `File` is also a `FileSystemObject` |
| `rdfs:comment` | `description` |
| Property shape with an `sh:datatype`, e.g. `observable:sizeInBytes` on `FileFacet` | Property of that node, e.g. `FileFacet.sizeInBytes` |
| Property shape with an `sh:class`, or `sh:nodeKind sh:IRI`, e.g. `core:createdBy` on `UcoObject` | Relationship from that node, typed in upper snake case, e.g. `CREATED_BY` |
| `sh:nodeKind sh:IRI` without `sh:class` | Relationship to the property's `rdfs:range`, else to `UcoThing` |
| `xsd:string`, `anyURI`, `hexBinary`, `base64Binary` | `STRING` |
| `xsd:dateTime`, `xsd:duration`, `xsd:boolean`, `xsd:decimal` | `ZONED DATETIME`, `DURATION`, `BOOLEAN`, `FLOAT` |
| `xsd:integer`, `nonNegativeInteger`, `positiveInteger`, `unsignedInt`, `unsignedShort`, `byte` | `INTEGER` |
| Values of several datatypes through `sh:or`, e.g. `recordFieldValue` | `ANY`, with the datatypes in the description |
| No `sh:maxCount 1` | A list type, e.g. `LIST<STRING>` |
| `sh:minCount 1` on a datatype property | An `EXISTS` constraint |
| `sh:minCount` and `sh:maxCount` on an object property | Counts at the `from` end, e.g. `max_count: 1` |
| `sh:in` or `sh:hasValue` that is enforced, or a closed vocabulary datatype, e.g. `objectStatus` | `one_of` |
| `sh:in` with `sh:severity sh:Info`: an open vocabulary, e.g. `HashNameVocab` for `hashMethod` | Suggested values in the description, and `extensions.custom.suggestedValues`; not `one_of` |
| Term IRI, e.g. `https://ontology.unifiedcyberontology.org/uco/core/UcoObject` | `reference`, which resolves to the term's page in the UCO documentation |
| Object `@id` in UCO JSON-LD | A `uri` property on every node, and a `KEY` constraint over it |

Nodes also record, in `extensions.custom`, their IRI, namespace and disjoint classes. Properties record their IRI,
datatypes, vocabulary and SHACL counts; relationships their IRI and counts.

### Facets

UCO describes an observable object, e.g. a `File`, by attaching facets to it, e.g. a `FileFacet` with the file's name
and size, and a `ContentDataFacet` with its hashes. Most of an observable's properties are on its facets: of the 323
observable classes, 150 are facets. UCO links them with one property, `core:hasFacet` from `UcoObject` to `Facet`, and
doesn't say which facets go with which objects. The ontology has the one relationship, `UcoObject` `HAS_FACET`
`Facet`, through which any object has any facet: a `File` node carries the `UcoObject` label and a `FileFacet` node
the `Facet` label. A facet belongs to one object, which UCO enforces with a SPARQL constraint, so the relationship
has `max_count: 1` at its `to` end.

### Where the ontology differs from UCO

- **Every node has a `uri` key.** UCO objects are identified by their IRI, the `@id` in JSON-LD. The ontology makes it
  a property and a key, so that nodes can be matched and relationships resolved. Blank nodes need generated
  identifiers.
- **Properties aren't inherited.** A property or relationship is defined on the class whose shape declares it. A node
  of a subclass carries its superclasses' labels, through which it has their properties and relationships too.
- **Open vocabularies aren't enforced.** UCO suggests values for many properties, e.g. `SHA256` for `hashMethod`, but
  allows others, reporting them with `sh:Info`. Only values UCO enforces are `one_of`.
- **A `dateTime` is zoned.** UCO allows a `dateTime` without a timezone; the ontology types it as `ZONED DATETIME`,
  as UCO's examples and tooling give a timezone. A loader needs to decide on a timezone for those that don't.
- **Datatypes are approximate.** `hexBinary` and `base64Binary` are strings, `decimal` a float, and every integer type
  an integer; the UCO datatype is kept in `extensions.custom.datatypes`.
- **Some shapes aren't kept.** The format has no equivalent for these, and they're left out:
  - `sh:not`, which UCO uses for disjointness, e.g. between `Action` and `Event`; disjoint classes are recorded in
    `extensions.custom.disjointWith`.
  - `sh:xone`, which requires exactly one of two sets of properties, on `ConfigurationEntry` and `TableFieldFacet`.
  - `sh:sparql` constraints, on `UcoThing`, `Dictionary` and `ProperDictionary`, apart from the one-object-per-facet
    rule above.
  - Shapes on property paths rather than properties, e.g. the sequence path from `MessageThreadFacet` through a
    thread to its messages, and the `rdfs:subClassOf` paths on `Technique` and `UcoType`.
- **Classes from other ontologies aren't nodes.** `Thread` and `ThreadItem` are also Collections Ontology classes,
  `co:Bag` and `co:Item`, which aren't nodes. The Collections Ontology properties UCO constrains are kept, e.g.
  `co:item` as `Thread` `ITEM` `ThreadItem`.

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json) and reports no issues for any of
the built-in validation sets, including `all`.
