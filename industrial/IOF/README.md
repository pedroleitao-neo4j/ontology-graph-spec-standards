# IOF Core, Supply Chain and Maintenance (Industrial Ontologies Foundry)

An ontology for three of the reference ontologies of the [Industrial Ontologies Foundry](https://www.industrialontologies.org)
(IOF), the effort under the Open Applications Group (OAGi) to build a suite of interoperable ontologies for
manufacturing and the industry around it. The ontologies are licensed under
[MIT](https://opensource.org/licenses/MIT). They're written in OWL on top of the
[Basic Formal Ontology](https://basic-formal-ontology.org) (BFO 2020, ISO/IEC 21838-2), so every IOF class sits
under a BFO category: a material entity, a role, a function, a process, an information content entity and so on.

Of the domains the IOF publishes at production maturity, this subset takes the core and the two that have been
released longest:

- **Core**: the notions common to every manufacturing domain: agents, persons and organizations and the roles
  they play; material products, components, raw materials and pieces of equipment; engineered systems and
  facilities; planned, business, manufacturing and measurement processes; capabilities and functions; material
  states; and the plan, objective, requirement and design specifications, identifiers and value expressions
  that describe them (`core/Core`)
- **Supply Chain**: suppliers, buyers, carriers, distributors, freight forwarders and the other supply chain
  agents; sourcing, shipment preparation, transport, receiving, storage and warehousing processes; shipments,
  lots, logistic units and trade items; ship-from and ship-to locations and global location numbers; and
  purchase orders, bills of lading and advance shipment notices (`supplychain/SupplyChain`)
- **Maintenance**: maintainable items and their required functions; dispositions to fail, failure processes,
  failure events and their effects; operating, degraded and failed states; failure mode codes; and maintenance
  strategies, activities, work order records and qualified maintenance people (`maintenance/Maintenance`)

Their imports add BFO 2020, from the copy the IOF keeps in its repository, and the IOF annotation vocabulary.
The release's other production domains, Biopharma and Certification, and the domains still in development,
Production Planning and Product Service System, are left out.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the IOF repository at Release 202603 |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`sample.json`](sample.json) | Sample data: a pump made to order, shipped, and repaired after its bearing fails |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |
| [`../../cypher.py`](../../cypher.py) | Generates `model.cypher` (shared by every standard) from `model.json` and `sample.json` |

## Source

The model is generated from commit
[`0c5af08`](https://github.com/iofoundry/ontology/tree/0c5af080dba16489db1b5c7a432a34222524c6e9) (4 September
2026) of the [IOF ontology repository](https://github.com/iofoundry/ontology), the commit of the
[`Release_202603`](https://github.com/iofoundry/ontology/releases/tag/Release_202603) tag, whose version IRIs
are `https://spec.industrialontologies.org/ontology/202603/...`. `generate.py` starts from the three entry
modules above and follows their `owl:imports`, which gives five modules: Core, Supply Chain, Maintenance, BFO
2020 and the annotation vocabulary.

Each import is resolved to a file through the release's own XML catalog, `catalog-v001.xml`, the one Protégé
uses, which maps both the unversioned and the versioned IRI of each module, and BFO's IRI, to its file in the
repository. The files are downloaded from `raw.githubusercontent.com` at the pinned commit, each once, the
output doesn't depend on the order of iteration, and a failed download is reported with its URL and stops the
script. To regenerate:

```bash
python3 generate.py                          # downloads the pinned commit from GitHub
python3 generate.py path/to/iof/ontology     # or a checkout of the repository at Release_202603
```

The script needs only the Python standard library. It prints the module, node and relationship counts and
a report of every construct it had to drop, so nothing is left out silently.

### What the modules cover

The 261 nodes split by area, which follows the module a class is declared in:

- 36 nodes of the BFO top level, from `Entity` down to `MaterialEntity`, `Role`, `Function`, `Process` and
  `TemporalInstant`
- 91 nodes of Core
- 114 nodes of Supply Chain
- 20 nodes of Maintenance

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow from domain to range.
A solid, darker arrow is required: a class restriction says every source node has one or more, e.g. every
`Agent` `HAS_ROLE` some `AgentRole`. A dashed arrow means every source node has at most one, e.g. a `Process`
`OCCUPIES_TEMPORAL_REGION`, and a thin solid arrow is otherwise unconstrained. Arrows are named by their
relationship type wherever the name fits without overlapping a card or another name, with required
relationships placed first. Dotted arrows point from a subclass to the superclass whose label it also carries.

Cards are coloured by area, which each card also prints, alongside its module (e.g. `SupplyChain`) and its
number of properties:

- BFO top level
- Core
- Supply chain
- Maintenance

Opened in a browser, hovering a card or arrow shows its name and description, and each card links to its
term IRI, which the IOF's [specification site](https://spec.industrialontologies.org) and the OBO Foundry
resolve. To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

`sample.json` and `model.cypher` follow a centrifugal pump from order to repair, between three fictional
companies: Ridgeline Pumps, which makes it to order, Harbor Bottling, which buys it, and Coastline Freight, which
carries it. The data has the companies as business organizations, the manufacturer, supplier, consignor,
customer, buyer, consignee and transportation service provider roles they play, their business functions and
organization identifiers, and the people who work for them. Ridgeline's factory has a make-to-order production
capability, realized in the pump's production, whose assembly takes in a bearing as a component. A purchase order
prescribes the supply relationship between the supplier's and the customer's roles. The shipment is prepared under
a shipment plan, with an advance shipment notice and a bill of lading, carried by truck from Ridgeline's dock to
Harbor's, whose global location number designates it, with a departure and an arrival timestamped through
temporal instant value expressions, and received. In service the pump has a required function, realized in its
functioning; the bearing has a disposition to fail, realized in a failure process; a failure event, recognized by
an operator, initiates the pump's failed state after its operating state; a failure mode code describes the
disposition; and a work order describes the maintenance activity, prescribed by a corrective maintenance strategy,
in which a qualified technician replaces the bearing.

```bash
python3 ../../cypher.py .    # regenerates model.cypher from model.json and sample.json
```

`model.cypher` creates the model's constraints and merges the sample data, so it can be run again. It needs the
Enterprise Edition of Neo4j 5 or later, for its node key constraints:

```bash
cypher-shell -f model.cypher
```

## Mapping

| IOF and BFO (OWL) | Ontology |
|---|---|
| Class, e.g. `iof:MaterialProduct` or `bfo:BFO_0000040` | Node, labelled by its `rdfs:label` in PascalCase, e.g. `MaterialProduct` or `MaterialEntity` |
| BFO's `entity` (`BFO_0000001`) | The `Entity` node, the root of the model, whose label every node carries |
| `rdfs:subClassOf` a named class, e.g. `PurchaseOrder` of `Agreement` | Implied label, e.g. every `PurchaseOrder` is also an `Agreement` |
| `rdfs:subClassOf` or `owl:equivalentClass` an intersection, e.g. `Factory` ⊑ `Facility` ⊓ `hasCapability` some `ProductionCapability` | Implied label for the named class, e.g. `Facility`, and relationships for the restrictions |
| `iof-av:naturalLanguageDefinition`, else `skos:definition` (BFO's elucidations), else `rdfs:comment` | `description` |
| Object property, e.g. `iof:hasRole` or `bfo:BFO_0000057` | Relationship from its domain to its range, typed by its `rdfs:label` in upper snake case, e.g. `HAS_ROLE` or `HAS_PARTICIPANT_AT_SOME_TIME` |
| Domain or range that is a union | One relationship per class in the union |
| Domain or range left out, or `owl:Thing` | Taken from the inverse property, else from the superproperties, else `Entity` |
| Pair of inverse properties, e.g. `owns` / `owned by`, `has role` / `role of` | One relationship, in the active voice, e.g. `BusinessOrganization` `OWNS` `IndependentContinuant`; of two in the same voice, the one that starts with "has", e.g. `HAS_PARTICIPANT_AT_SOME_TIME` rather than `PARTICIPATES_IN_AT_SOME_TIME`. The inverse is recorded in `extensions.custom.inverseOf` |
| `owl:FunctionalProperty` | `max_count: 1` at the `from` end |
| `owl:someValuesFrom` restriction, e.g. `Supplier` ⊑ `hasRole` some `SupplierRole` | Relationship from the restricted class with `min_count: 1` at the `from` end |
| `owl:someValuesFrom` on an inverse, e.g. `FailedState` ⊑ inverse(`initiates`) some `FailureEvent` | Relationship to the restricted class with `min_count: 1` at the `to` end, e.g. `FailureEvent` `INITIATES` `FailedState` |
| `owl:someValuesFrom` a union | A relationship to each member, without a count, since only one of them is required |
| `owl:someValuesFrom` a nested class expression, e.g. `ConsigneeRole` ⊑ `participates in at some time` some (`ReceivingProcess` ⊓ ...) | A relationship to the named members of the intersection, else the property's range |
| `owl:allValuesFrom` restriction, e.g. BFO's `Process` ⊑ `occurrent part of` only `Process` | Relationship from the restricted class to the narrower class |
| Cardinalities, qualified or not | Counts, e.g. `count: 1` |
| Datatype property, e.g. `iof:hasDateTimeInstantValue` | Property of each class of its domain, e.g. `LIST<ZONED DATETIME>` on `TemporalInstantValueExpression` |
| Datatype property ranges: `xsd:string` → `STRING`, `xsd:dateTime` → `ZONED DATETIME` | The property's type; a property without a range, like `hasSimpleExpressionValue`, a `STRING` |
| Datatype property that isn't functional | A `LIST<T>`, since IOF allows several values |
| Term IRI, e.g. `https://spec.industrialontologies.org/ontology/construct/Factory` | `reference` and `extensions.custom.iri`; `extensions.custom.module` (e.g. `SupplyChain`, `BFO`), `extensions.custom.area`, and `subPropertyOf` and `disjointWith` where present |

Where the domain and range of a property and the restrictions that use it describe the same pair of
classes, they're one relationship. For example, `initiates` runs from an `Occurrent` to an `Event` or a
`Process`, which gives two relationships. Maintenance restricts `FailureEvent` to initiate some `FailedState`,
and `FailedState` to be initiated by some `FailureEvent`; the two restrictions describe the same pair, so they
give one `FailureEvent` `INITIATES` `FailedState` relationship with `min_count: 1` at both ends, and a
sentence in its description for each.

### Where the ontology differs from IOF

- **Every node has a `uri` key.** IOF individuals are identified by their IRI. The ontology makes it a
  property and a key, so that nodes can be matched and relationships resolved. Blank nodes need generated
  identifiers.
- **Names come from labels, not IRIs.** BFO's IRIs are opaque, e.g. `BFO_0000040` for material entity, so every
  node and relationship type is named from its `rdfs:label`. IOF's IRIs are readable, but some trail their
  labels: the class labelled `consignor` has the IRI `Shipper`, `offering for sale business process` has
  `SellingBusinessProcess`, `manufacturing supply chain system` has `ManufacturingSupplyChain`, and the labels
  fix the IRIs' misspellings, e.g. `TranspoortEquipmentRole` and `PieceofTransportEquipment`. The nodes are
  `Consignor`, `OfferingForSaleBusinessProcess`, `TransportEquipmentRole` and so on; the IRI is kept in
  `reference`. All the IOF modules share one namespace, `construct/`, so the module is the one that declares
  the term.
- **Definitions are read as necessary conditions.** IOF defines 96 classes with `owl:equivalentClass`, e.g. an
  `Agent` is exactly a person, group of agents or engineered system that has some agent role. The ontology
  keeps what such a definition requires of every member, as implied labels and required relationships, but
  can't say that meeting the conditions makes something a member.
- **Restrictions on an inverse are read from the other end.** BFO and IOF often restrict a class by the inverse
  of a property that has no named inverse, e.g. every `FailedState` is initiated by some `FailureEvent`. The
  relationship keeps the named property's direction and puts the count at its `to` end. Where the inverse is
  named, e.g. `role of` for `has role`, the restriction becomes one on the kept property.
- **Some inverse pairs are both kept.** BFO 2020 declares the inverses of its "at some time" relations but not of
  its "at all times" ones, and IOF does the same for `has component part at all times`, so both directions
  become relationships: `HAS_CONTINUANT_PART_AT_ALL_TIMES` and `CONTINUANT_PART_OF_AT_ALL_TIMES`,
  `HAS_PARTICIPANT_AT_ALL_TIMES` and `PARTICIPATES_IN_AT_ALL_TIMES`, `LOCATED_IN_AT_ALL_TIMES` and
  `LOCATION_OF_AT_ALL_TIMES`, and so on for nine pairs.
- **Temporal qualifiers stay in the relationship type.** BFO 2020 distinguishes a relation that holds at some
  time from one that holds at all times, e.g. `HAS_MEMBER_PART_AT_SOME_TIME` and `HAS_MEMBER_PART_AT_ALL_TIMES`.
  They're separate relationship types here, as they are separate properties in BFO; the graph doesn't record
  the times themselves.
- **Subclass axioms that are unions aren't kept.** Three classes are subclasses of a union rather than a named
  class, e.g. an `Event` is either a `Process` or a `ProcessBoundary`. That's a choice, not a supertype, so it
  can't be an implied label; `Event` is still an `Occurrent`.
- **Some restrictions and properties are left out.** Two `owl:allValuesFrom` restrictions whose filler names no
  class, on `DispositionToExhibitUndesirableBehavior` and `MaterialStateConditionExpression`, have no node to
  point at. Supply Chain's `hasTextValue` has no domain and no class restricts it. Both are reported by the
  generator.
- **Many relationships end at `Entity`.** Where neither a property, its inverse nor its superproperties says
  what's at an end, the end is `Entity`, e.g. `InformationContentEntity` `IS_ABOUT` `Entity`. 20 of the 477
  relationships touch `Entity`, which every node also carries as its top label.
- **Properties aren't inherited.** A relationship is defined on the class whose domain or restriction
  declares it. A node of a subclass carries its superclasses' labels, through which it has their
  relationships too.
- **Housekeeping isn't modelled.** The annotation vocabulary's `MaturityLevel` class rates the IOF's own
  modules, not the domain, and is left out, as is Supply Chain's one named individual, the GS1 GLN scheme.
  The IOF's rich annotations beyond the definition, such as examples, explanatory notes and first-order logic
  axioms, stay in the source.
- **Property axioms beyond subproperties aren't kept.** BFO's and IOF's six `owl:propertyChainAxiom`s have no
  equivalent in the format. `owl:disjointWith` between classes is recorded in `extensions.custom.disjointWith`.

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json). Its relationship
endpoints resolve, its keys cover existing properties, its counts are well formed, and its names and
descriptions are within the length limits, which covers the core validation rules; every node carries
`Entity`, and every node, relationship and property records the IRI of the term it came from.
