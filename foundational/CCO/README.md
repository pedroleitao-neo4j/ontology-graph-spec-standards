# Common Core Ontologies 2.2 (CCO)

An ontology for the [Common Core Ontologies](https://github.com/CommonCoreOntology/CommonCoreOntologies) (CCO), a
mid-level ontology built on the [Basic Formal Ontology](https://basic-formal-ontology.org) (BFO 2020, ISO/IEC
21838-2). Where BFO holds only the most general categories, CCO holds the classes common to data in many domains:
person, organization, facility, vehicle, date, measurement and so on. It's overseen by the CCO Governance Board,
licensed under [BSD 3-Clause](https://github.com/CommonCoreOntology/CommonCoreOntologies/blob/develop/LICENSE), and
directed, with BFO, as a baseline standard for ontology development across the US Department of Defense and
Intelligence Community. The IEEE is evaluating it as a mid-level ontology standard under P3195.1.

CCO is eleven modules:

- **Agent Ontology**: agents, persons, organizations and groups, and the roles, capabilities and affiliations they have
- **Event Ontology**: acts, such as acts of communication, motion, ownership or employment, and other processes and
  changes, such as gains and losses of qualities and roles
- **Time Ontology**: temporal instants and intervals, from seconds to decades, and the interval relations between them
- **Artifact Ontology**: artifacts, from vehicles, weapons and tools to information bearing artifacts, with their
  functions, models and specifications
- **Facility Ontology**: buildings and campuses designed for a purpose, e.g. ports, airports, hospitals and power plants
- **Information Entity Ontology**: information content entities, i.e. designative, descriptive, prescriptive and
  measurement information, names and identifiers, and the information bearing entities that carry them
- **Quality Ontology**: qualities, realizable entities and process profiles, e.g. length, colour and frequency
- **Units of Measure Ontology** and **Currency Unit Ontology**: the classes of measurement units and currencies
- **Geospatial Ontology**: sites, geospatial regions and locations, spatial reference systems and coordinates
- **Extended Relation Ontology**: the relations between CCO's entities beyond BFO's

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the CCO repository at v2.2, building with the [IOF generator](../../industrial/IOF/generate.py) |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`sample.json`](sample.json) | Sample data: a container vessel's arrival at a port |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |
| [`../../cypher.py`](../../cypher.py) | Generates `model.cypher` (shared by every standard) from `model.json` and `sample.json` |

## Source

The model is generated from commit
[`0bc7d33`](https://github.com/CommonCoreOntology/CommonCoreOntologies/tree/0bc7d33e1bc09fd4693366119ab4e03cb0340042)
(14 August 2026) of the [CCO repository](https://github.com/CommonCoreOntology/CommonCoreOntologies), the commit of
the [`v2.2`](https://github.com/CommonCoreOntology/CommonCoreOntologies/releases/tag/v2.2) tag, whose version IRIs are
`https://www.commoncoreontologies.org/2026-08-13/...`. `generate.py` starts from the All Core Ontology,
`src/cco-merged/AllCoreOntology.ttl`, which has no content of its own but imports the CCO modules, and follows their
`owl:imports`, which gives twelve modules: the eleven CCO modules and BFO 2020, in the copy CCO keeps in
`src/cco-imports/bfo-core.ttl`.

Each import is resolved to a file through the catalog beside the entry module, `src/cco-merged/catalog-v001.xml`.
The files are downloaded from `raw.githubusercontent.com` at the pinned commit, each once, and a failed download is
reported with its URL and stops the script. CCO is written in OWL on BFO 2020, as the Industrial Ontologies
Foundry's ontologies are, so `generate.py` reads the Turtle files itself and builds the model with the IOF
generator in [`../../industrial/IOF/generate.py`](../../industrial/IOF/generate.py). To regenerate:

```bash
python3 generate.py                                  # downloads the pinned commit from GitHub
python3 generate.py path/to/CommonCoreOntologies     # or a checkout of the repository at v2.2
```

The script needs only the Python standard library. It prints the module, node and relationship counts and a report
of everything it left out, so nothing is left out silently.

### What the modules cover

The 1,437 nodes split by area, which follows the module a term is curated in:

- 36 nodes of the BFO top level
- 464 nodes of agents, events and time: 103 of the Agent, 328 of the Event and 33 of the Time Ontology
- 638 nodes of artifacts and facilities: 547 of the Artifact and 91 of the Facility Ontology
- 299 nodes of information, qualities, units and places: 110 of the Information Entity, 110 of the Quality, 27 of
  the Units of Measure, 1 of the Currency Unit and 51 of the Geospatial Ontology

The Extended Relation Ontology declares relations only. CCO is mostly a taxonomy: of its 177 object properties, the
311 relationships come from their domains and ranges and from the restrictions of the classes that use them.

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow from domain to range, as for
[`../../industrial/IOF`](../../industrial/IOF#diagram): a solid, darker arrow is required, a dashed arrow means at most
one, and a thin solid arrow is otherwise unconstrained. Dotted arrows point from a subclass to the superclass whose
label it also carries. Cards are coloured by the four areas above, which each card also prints, alongside its module
(e.g. `ArtifactOntology`) and its number of properties.

Opened in a browser, hovering a card or arrow shows its name and description, and each card links to its term IRI.
To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

`sample.json` and `model.cypher` follow a fictional container vessel, the Saltmarsh Trader, as it arrives at the
berth of a fictional port, Eastmere, on 2 October 2026. Its owner, Larkspur Shipping, is a commercial organization
with a legal name, a commercial role, realized in its act of ownership of the vessel, and an organization
capability. The Eastmere port authority is a government organization, part of the council's government, which its
district delimits. The vessel's master, employed by Larkspur in an act of employment, and a deckhand make up the
crew; with a port officer, they're persons, agents and organization members, each with an agent capability and a
member role. The vessel has a proper name, carried by the lettering on its hull, an IMO number, and a length,
measured in metres by a ratio measurement: the unit is CCO's own Meter Measurement Unit individual, identified by
its CCO IRI. The port is on the shore, and the berth's spatial region is designated by coordinates whose bearer
holds the latitude and longitude and uses WGS 84, CCO's World Geodetic System 1984 individual. The cargo voyage has the arrival as its part; the master carries
it out in an operator role, at the berth, in an interval within the day, which is within a week, month, year and
decade, and whose date is recorded in the logbook. Afterwards the master sends the port authority an arrival report.

```bash
python3 ../../cypher.py .    # regenerates model.cypher from model.json and sample.json
```

`model.cypher` creates the model's constraints and merges the sample data, so it can be run again. It needs the
Enterprise Edition of Neo4j 5 or later, for its node key constraints:

```bash
cypher-shell -f model.cypher
```

## Mapping

CCO is mapped as the IOF ontologies are; see the [IOF mapping](../../industrial/IOF/README.md#mapping). For example:

| CCO (OWL) | Ontology |
|---|---|
| Class, e.g. `cco:ont00000440` | Node, labelled by its `rdfs:label` in PascalCase, e.g. `Watercraft`, since CCO's IRIs are opaque |
| `rdfs:subClassOf` a named class, e.g. `Watercraft` of `Vehicle` | Implied label: every `Watercraft` is also a `Vehicle`, and so a `MaterialArtifact` |
| Object property, e.g. `cco:ont00001833` | Relationship from its domain to its range, typed by its label in upper snake case, e.g. `Process` `HAS_AGENT` `Agent` |
| `owl:someValuesFrom` restriction, e.g. `Facility` ⊑ `located in` some `PortionOfGeosphere` | `Facility` `LOCATED_IN` `PortionOfGeosphere`, with `min_count: 1` at the `from` end |
| Datatype property, e.g. `cco:ont00001771` | Property of each class of its domain, named by its label in camel case, e.g. `hasDateValue` on `InformationBearingEntity`; without a domain, e.g. `hasLatitudeValue`, a property of `Entity` |
| `cco:ont00001760` (is curated in ontology), e.g. `https://www.commoncoreontologies.org/ArtifactOntology` | `extensions.custom.module`, e.g. `ArtifactOntology`, and `extensions.custom.area` |
| `skos:definition` | `description` |

### Where the ontology differs from CCO

Every difference listed for [the IOF ontologies](../../industrial/IOF/README.md#where-the-ontology-differs-from-iof)
holds here too: every node has a `uri` key, names come from labels, definitions are read as necessary conditions,
restrictions on an inverse are read from the other end, and properties aren't inherited. In addition:

- **Defined classes aren't inferred.** CCO defines 58 classes with `owl:equivalentClass`, e.g. an `Agent` is exactly
  a material entity that bears an agent capability. A reasoner would infer that a person with an agent capability
  is an agent; the graph can't, so a node carries the labels of the defined classes it belongs to, e.g. the sample's
  people are `Person`, `Agent` and `OrganizationMember`.
- **Named individuals aren't kept.** The model holds classes, not instances. CCO's 350 named individuals are left
  out: 141 measurement units, e.g. Meter Measurement Unit, 128 currencies, and, in the Information Entity
  Ontology, 54 time zone identifiers, 20 time and calendar reference systems and 7 geospatial coordinate reference
  systems, e.g. World Geodetic System 1984. Data can still use them as nodes of their class, identified by their
  CCO IRI, as the sample does for the metre and WGS 84.
- **Deprecated properties aren't kept.** CCO 2.2 deprecates its seven generic value properties, `has text value`,
  `has integer value`, `has decimal value`, `has double value`, `has boolean value`, `has URI value` and
  `has datetime value`, without replacement, asking modellers to use more specific datatype properties. Of the
  datatype properties left, `has date value` is a property of `InformationBearingEntity`, its domain, and
  `asWKT`, `hasLatitudeValue`, `hasLongitudeValue` and `hasAltitudeValue`, which have no domain, of `Entity`. A
  measurement such as the vessel's length therefore has no property for its number.
- **BFO's relations aren't temporalized.** CCO imports the core edition of BFO 2020, whose relations don't
  distinguish "at some time" from "at all times", so they're `HAS_CONTINUANT_PART`, `LOCATED_IN` and so on, where
  the IOF ontologies, which import the temporalized edition, have `HAS_CONTINUANT_PART_AT_SOME_TIME`.
- **Property chains aren't kept.** CCO's two `owl:propertyChainAxiom`s have no equivalent in the format.

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json). Its relationship
endpoints resolve, its keys cover existing properties, its counts are well formed, and its names and
descriptions are within the length limits, which covers the core validation rules; every node carries
`Entity`, and every node, relationship and property records the IRI of the term it came from.
