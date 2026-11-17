# ISO 23726-3 (IDO) and ISO 15926

An ontology for the [Industrial Data Ontology (IDO)](https://rds.posccaesar.org/ontology/lis14/), standardised as
[ISO 23726-3](https://www.iso.org/standard/87560.html) and published by the POSC Caesar Association (PCA). IDO is the
W3C OWL 2 rendering of the [ISO 15926-2](https://www.iso.org/standard/29557.html) data model, previously deployed in
the oil and gas industry as ISO TR 15926-14. It's the top-level vocabulary that reference data libraries (RDLs) and
asset models for industrial plants are built on: objects and their parts, activities, qualities, data and units of
measure.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`sample.json`](sample.json) | Sample data: condensate export pump P-2001A at a gas terminal, its parts and quantities, and the activities around it |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |
| [`generate.py`](generate.py) | Generates both files from the official IDO Turtle file |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |
| [`../../cypher.py`](../../cypher.py) | Checks the sample data against `model.json` (shared by every standard) and writes `model.cypher` |

## Source

The model is generated from IDO version 4.2, the FDIS (final draft) version of ISO 23726-3 that PCA published in
April 2026 as [`LIS-14-for-FDIS.ttl`](https://stfilestorepca.blob.core.windows.net/files/LIS-14-for-FDIS.ttl). See
[PCA's announcement](https://wix.posccaesar.org/articles/fdis-version-of-ido---industrial-data-ontology-now-available-for-download-as-a-file).
`generate.py` includes a small Turtle reader, so it doesn't need an RDF library. To regenerate:

```bash
python3 generate.py                             # downloads the IDO 4.2 FDIS file
python3 generate.py path/to/LIS-14-for-FDIS.ttl
```

The script needs only the Python standard library.

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow from domain to range. A solid,
darker arrow is required: a class restriction says every source node has one or more, e.g. every `Activity`
`HAS_PARTICIPANT` some `PhysicalObject`. A dashed arrow is functional, so every source node has at most one. A thin
solid arrow is otherwise unconstrained. Arrows are named by their relationship type, e.g. `HAS_QUALITY` or
`CONCRETIZES`, wherever the name fits without overlapping a card or another name, with required relationships placed
first. Dotted arrows point from a subtype to the supertype whose label it also carries.

Cards are coloured by the root of their class hierarchy, which each card also prints:

- `Object`: physical, informational and organisational objects
- `Temporal`: activities, events and regions of time
- `Dependent`: qualities and potentials
- `Actual` and `Specified`: the two classes the `implements` relation runs between

Opened in a browser, hovering a card or arrow shows its name and description, and each card links to its term in
[PCA RDS](https://rds.posccaesar.org/ontology/lis14/). To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

The sample data describes one asset of a fictional gas terminal, Nordvik Gas: the condensate export system of process
module 20. Its two pump functions, duty `P-2001A` and standby `P-2001B`, are specified functional objects implemented by
physical pumps, serial numbers 48213 and 48214. The installed pump has assembled parts (casing, impeller, mechanical
seal, motor), a duplex stainless steel casing material and, on its datasheet, rated and measured quantities with their
units of measure. Its installation activity, bounded by start and end events, is followed by a seal replacement whose
performance test realises the pumping function, with an activity profile quantified by the measured flow.

[`model.cypher`](model.cypher) creates the ontology's constraints and loads the data. Run it against an empty database
of Neo4j 5 or later, Enterprise Edition, which its node key constraints need, e.g. with `cypher-shell -f model.cypher`.
To regenerate:

```bash
python3 ../../cypher.py .
```

## Mapping

| IDO (OWL) | Ontology |
|---|---|
| Class, e.g. `lis:PhysicalObject` | Node, labelled by its `rdfs:label`, e.g. `PhysicalObject` |
| `rdfs:subClassOf` a named class, e.g. `Activity` of `Temporal` | Implied label, e.g. every `Activity` is also a `Temporal` |
| `skos:altLabel`, e.g. `Compound` | Node `aliases` |
| Object property, e.g. `lis:hasParticipant` | Relationship from its domain to its range, typed in upper snake case, e.g. `HAS_PARTICIPANT` |
| Domain or range that is a union, e.g. `Location or PhysicalObject` | One relationship per class in the union |
| Domain or range left out | Taken from the inverse property, else from the superproperty |
| Pair of inverse properties, e.g. `hasQuality` / `qualityOf` | One relationship, in the direction IDO defines and annotates; the inverse is recorded in `extensions.custom.inverseOf` |
| `owl:FunctionalProperty`, e.g. `datumUOM` | `max_count: 1` at the `from` end |
| `owl:someValuesFrom` restriction, e.g. `Activity` ⊑ `hasParticipant some PhysicalObject` | Relationship from the restricted class with `min_count: 1` at the `from` end, or `count: 1` for a functional property |
| `owl:allValuesFrom` restriction, e.g. `Event` ⊑ `hasTemporalExtent only InstantRegion` | Relationship from the restricted class to the narrower class |
| Datatype property, e.g. `lis:datumValue` | Property of type `ANY` on its domain |
| `iof-av:naturalLanguageDefinition`, `skos:example`, notes | `description` |
| ISO 15926-2 counterpart, e.g. `ISO 15926-2:2003 'participation'` | `Renders …` in the description, and `extensions.custom.iso15926` |
| Term IRI, e.g. `http://rds.posccaesar.org/ontology/lis14/rdl/Activity` | `reference`, which resolves to the term's page in PCA RDS |
| Individual IRI | A `uri` property on every node, and a `KEY` constraint over it |

Nodes also record, in `extensions.custom`, their IRI, the root of their class hierarchy, their ISO 15926-2 counterpart,
their disjoint classes and their `rdfs:seeAlso` links to other ontologies such as BFO and DOLCE. Relationships also
record their inverse, superproperties, property chains, whether they're symmetric or functional, and the restriction
they come from.

Descriptions combine the definition, the ISO 15926-2 counterpart, the example and IDO's scope, explanatory and usage
notes. Where these exceed the format's 1,024-character limit, the later notes are left out.

### ISO 15926

IDO is the current OWL form of ISO 15926-2, so this ontology covers ISO 15926 through it. Where an IDO term renders an
ISO 15926-2:2003 entity type, the description says so, e.g. `Activity` renders `activity`, `Object` renders
`possible_individual` and `hasPart` renders `composition_of_individual`, and the entity type is kept in
`extensions.custom.iso15926`. 53 of IDO's terms name their ISO 15926-2 counterpart.

The parts of ISO 15926 that are data rather than model aren't part of the ontology. These are the reference data
library (ISO 15926-4), e.g. *centrifugal pump* or *pressure*, and the templates (ISO 15926-7). They're classes and
individuals that populate the IDO nodes, e.g. a `PhysicalObject` classified as a centrifugal pump, and are available
from [PCA RDS](https://rds.posccaesar.org/).

### Where the ontology differs from IDO

- **Every node has a `uri` key.** OWL individuals are identified by their IRI. The ontology makes it a property and a
  key, so that nodes can be matched and relationships resolved. Blank-node individuals need generated identifiers.
- **One relationship per inverse pair.** IDO declares most relations in both directions, e.g. `hasQuality` and
  `qualityOf`. In a graph, one relationship can be traversed both ways, so the ontology keeps the direction that IDO
  defines and annotates, and records the other as `extensions.custom.inverseOf`, e.g. `HAS_QUALITY` (inverse
  `qualityOf`), `IMPLEMENTS` (`implementedBy`) and `RESIDES_IN` (`hasResident`).
- **Unconstrained relations are left out.** IDO declares no domain or range for `hasPart` and `isAbout`, nor through
  their inverses or superproperties, because they apply to anything. The ontology has no relationship for them. Their
  subproperties, which are constrained, e.g. `HAS_ARRANGED_PART`, `HAS_CONTENT_PART` and `QUALITY_QUANTIFIED_AS`,
  are included.
- **Properties aren't inherited.** A relationship or property is defined on the class that IDO declares it for. A node
  of a subclass carries its superclasses' labels, through which it has their relationships and properties too.
- **Restrictions are relationships.** A class restriction, e.g. every `System` `HAS_FUNCTIONAL_PART` some
  `FunctionalObject`, is a relationship of its own from the restricted class, next to the general one from the
  property's domain. The format has no way to narrow an inherited relationship, so the two coexist.
- **Data property values are `ANY`.** IDO gives `datumValue`, `temporalValue` and `qualityQuantityValue` no datatype.
  Any literal is allowed, and the annotations recommend e.g. `xsd:float` for numbers and `xsd:duration` for
  durations. `ScalarQuantityDatum` requires a `datumValue`. That property is declared on `QualityDatum`, and the format
  only lets an `EXISTS` constraint name a property of its own node, so the requirement is stated in the description.
- **OWL axioms beyond these aren't kept as constraints.** Disjointness, property chains and symmetry are recorded in
  `extensions.custom` but not enforced. The graph format has no equivalent.
- **Terms from other ontologies aren't nodes.** IDO links its terms to BFO, DOLCE, PROV, QUDT, the SSN ontology and
  others with `rdfs:seeAlso`. The links are kept in `extensions.custom.seeAlso` as compact IRIs, e.g.
  `obo:BFO_0000015`.

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json) and reports no issues for any of
the built-in validation sets, including `all`.
