# FIBO legal modules (EDM Council)

An ontology for the legal modules of [FIBO](https://spec.edmcouncil.org/fibo), the Financial Industry
Business Ontology. The EDM Council and the Object Management Group develop it together, and it is licensed
under [MIT](https://opensource.org/licenses/MIT). FIBO is a formal model of the financial industry: the
instruments, products, business entities and processes the industry runs on, described as OWL ontologies
that banks, regulators, data vendors and consultants use for data governance, risk management and
reporting.

This subset takes the six modules that cover what financial agreements and the law around them are built
on, and follows their imports:

- the legal core: laws, statute law, constitutions and courts, and the jurisdictions they hold over
  (`FND/Law/LegalCore`)
- legal capacity: obligations, rights, claims and duties, licences and the delegated authority to act
  (`FND/Law/LegalCapacity`)
- agreements: the commitments parties take on, and the obligors and beneficiaries behind them
  (`FND/Agreements/Agreements`)
- contracts: written and verbal contracts, their parties, terms, milestones, provisions and breaches,
  from netting and collateral agreements to term sheets (`FND/Agreements/Contracts`)
- parties: the roles parties play and the identifiers that track them (`FND/Parties/Parties`)
- legal persons: business entities, statutory bodies, licences, powers of attorney and special purpose
  vehicles (`BE/LegalEntities/LegalPersons`)

Their imports close over the FIBO foundations these build on (relations, arrangements, documents,
identifiers, dates and times, places and addresses, people, objectives, analytics) and, since FIBO 2.x,
over the OMG Commons Ontology Library (Commons) that the foundations now build on: collections,
documents, designators, identifiers, organizations, parties and situations, roles, dates and times,
quantities and units, regulatory agencies and more.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the pinned commit of the FIBO repository |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`sample.json`](sample.json) | Sample data: a master services agreement between two Delaware corporations |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |
| [`../../cypher.py`](../../cypher.py) | Generates `model.cypher` (shared by every standard) from `model.json` and `sample.json` |

## Source

The model is generated from commit
[`33a92cd`](https://github.com/edmcouncil/fibo/tree/33a92cd34285d532c158da97bb42add089f135d3) (27 October
2026) of the [FIBO repository](https://github.com/edmcouncil/fibo), the tip of `master`, whose production
version IRI is dated 2026-10-01. `generate.py` starts from the six entry modules above and follows their
`owl:imports`, which gives 36 modules: the 17 FIBO modules of the foundations, and 19 modules of the
OMG Commons Ontology Library that those depend on.

FIBO modules are downloaded from `raw.githubusercontent.com` at the pinned commit. Commons modules are
downloaded from their IRIs, `https://www.omg.org/spec/Commons/...`, with RDF/XML content negotiation.
Each module is fetched once and cached in memory, the output doesn't depend on the order of iteration,
and a failed download is reported with its URL and stops the script. To regenerate:

```bash
python3 generate.py                          # downloads the pinned commit from GitHub and Commons from the OMG
python3 generate.py path/to/fibo             # or a FIBO checkout; Commons still comes from the OMG
```

The script needs only the Python standard library. It prints the module, node and relationship counts and
a report of every construct it had to drop, so nothing is left out silently.

### What the modules cover

The 387 nodes split by area, which follows the module a class is defined in:

- 31 nodes of law and legal capacity: `FND/Law`
- 57 nodes of agreements and contracts: `FND/Agreements` and `FND/Arrangements`
- 47 nodes of parties, people and legal entities: `FND/Parties`, `FND/AgentsAndPeople` and `BE/LegalEntities`
- 252 nodes of Commons foundations and other support modules: the rest of the FIBO foundations, the 19
  Commons modules, and `Thing`

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow from domain to range.
A solid, darker arrow is required: a class restriction says every source node has one or more, e.g. every
`Obligor` `HAS_OBLIGATION` some `Commitment`. A dashed arrow means every source node has at most one, and
a thin solid arrow is otherwise unconstrained. Arrows are named by their relationship type, e.g.
`HAS_GOVERNING_JURISDICTION` or `CONFERS`, wherever the name fits without overlapping a card or another
name, with required relationships placed first. Dotted arrows point from a subclass to the superclass whose label it
also carries.

Cards are coloured by area, which each card also prints, alongside its module (e.g. `FND/Agreements`) and
its number of properties:

- Law and legal capacity
- Agreements and contracts
- Parties, people and legal entities
- Commons foundations and other support modules

Opened in a browser, hovering a card or arrow shows its name and description, and each card links to its
term IRI, which the FIBO and Commons sites resolve. To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

`sample.json` and `model.cypher` show a written bilateral master services agreement between two fictional
Delaware corporations, Northwind Analytics, Inc. as the supplier and Contoso Freight Corporation as the customer.
The data has the agreement's two party roles, its principal party and its counterparty, the contractual elements
it's made of, from definitions and commitments to a termination provision and a condition precedent, and
the rights and obligations it confers on each party, each right implying its obligation. Around it are the legal
persons themselves: their organization names and identifiers, addresses and the legal capacities they hold, and
the officers who sign for them; and the jurisdiction of Delaware, in which they're organized, where the Delaware
General Corporation Law is in force and confers a stockholder's right to inspect a corporation's books and
records.

```bash
python3 ../../cypher.py .    # regenerates model.cypher from model.json and sample.json
```

`model.cypher` creates the model's constraints and merges the sample data, so it can be run again. It needs the
Enterprise Edition of Neo4j 5 or later, for its node key and property existence constraints:

```bash
cypher-shell -f model.cypher
```

## Mapping

| FIBO and Commons (OWL) | Ontology |
|---|---|
| Class, e.g. `fibo-fnd-agr-ctr:Contract` | Node, labelled by its local name, e.g. `Contract` |
| `owl:Thing` | The `Thing` node, whose label every node carries |
| `rdfs:subClassOf` a named class, e.g. `Contract` of `Agreement` | Implied label, e.g. every `Contract` is also an `Agreement` |
| A class without a named superclass, e.g. `Law` or `Situation` | Implied label `Thing` |
| `owl:equivalentClass` an intersection, e.g. `ReferenceDocument` ≡ `Document` ⊓ restrictions | Implied label for the named class, e.g. `Document`, and relationships for the restrictions |
| `skos:definition`, else `rdfs:comment`, else `dct:abstract` | `description` |
| Object property, e.g. `fibo-fnd-agr-ctr:hasContractParty` | Relationship from its domain to its range, typed in upper snake case, e.g. `HAS_CONTRACT_PARTY` |
| Domain or range that is a union | One relationship per class in the union |
| Domain or range left out | Taken from the inverse property, else from the superproperties, else `Thing` |
| Pair of inverse properties, e.g. `authorizes` / `isAuthorizedBy` | One relationship, in the active voice, e.g. `AuthorizingParty` `AUTHORIZES` `AuthorizedParty`; the inverse is recorded in `extensions.custom.inverseOf` |
| `owl:FunctionalProperty` | `max_count: 1` at the `from` end |
| `owl:someValuesFrom` restriction, e.g. `Obligor` ⊑ `hasObligation` some `Commitment` | Relationship from the restricted class with `min_count: 1` at the `from` end |
| `owl:someValuesFrom` a union, e.g. `LegalObligation` ⊑ `isConferredBy` some `Contract` ⊔ `StatuteLaw` ⊔ `Regulation` | A relationship to each member, without a count, since only one of them is required |
| `owl:someValuesFrom` a nested class expression | The property's range stands in for the unnamed class |
| `owl:allValuesFrom` restriction, e.g. `ContractualRight` ⊑ `isImpliedBy` only `ContractualObligation` | Relationship from the restricted class to the narrower class |
| `owl:cardinality`, `owl:minCardinality`, e.g. `Difference` ⊑ `hasMinuend` exactly 1 | Counts, e.g. `count: 1` |
| `owl:qualifiedCardinality`, `owl:minQualifiedCardinality`, `owl:maxQualifiedCardinality` with an `owl:onClass`, e.g. `Contract` ⊑ `hasContractParty` min 2 `ContractParty`, `Person` ⊑ `hasDateOfBirth` exactly 1 `DateOfBirth` | Counts on the relationship to the class the cardinality qualifies, e.g. `min_count: 2`, `count: 1` |
| Restriction on a datatype property, e.g. `PersonName` ⊑ `hasSurname` min 0 `Text`, `WrittenContract` ⊑ `isAssignable` exactly 1 | Property of the restricted class, e.g. `PersonName.hasSurname`; single-valued when at most one is allowed, e.g. `WrittenContract.isAssignable` a `BOOLEAN`, and an `EXISTS` constraint when at least one is required |
| Datatype property, e.g. `fibo-fnd-plc-adr:hasPostalCode` | Property of each class of its domain, e.g. `LIST<STRING>` on `PhysicalAddress` |
| Datatype property ranges: `xsd:string` → `STRING`, `xsd:boolean` → `BOOLEAN`, `xsd:date` → `DATE`, `xsd:dateTime` → `ZONED DATETIME`, `xsd:decimal` → `FLOAT`, `xsd:integer` → `INTEGER` | The property's type; Commons' `CombinedDateTime` is a `ZONED DATETIME`, `owl:rational` a `FLOAT`, and a property without a range, like FIBO's address lines, a `STRING` |
| Datatype property that isn't functional | A `LIST<T>`, since FIBO allows several values |
| Term IRI, e.g. `https://spec.edmcouncil.org/fibo/ontology/FND/Agreements/Contracts/Contract` | `reference` and `extensions.custom.iri`; `extensions.custom.module` (e.g. `FND/Agreements`, `Commons/Organizations`), `extensions.custom.area`, and `subPropertyOf` and `disjointWith` where present |

Where the domain and range of a property and the restrictions that use it describe the same pair of
classes, they're one relationship. For example, `hasObligation` has the domain `Obligor` and no range.
A restriction says every `ContingentObligation` is the obligation of some `Obligor`. The result is one
`Obligor` `HAS_OBLIGATION` `ContingentObligation` relationship with `min_count: 1` at the `to` end, and
a sentence in its description for the restriction.

### Where the ontology differs from FIBO

- **Every node has a `uri` key.** FIBO individuals are identified by their IRI. The ontology makes it a
  property and a key, so that nodes can be matched and relationships resolved. Blank nodes need generated
  identifiers.
- **Qualified cardinalities are kept.** FIBO and Commons state most of their cardinality constraints as
  qualified cardinalities — `owl:qualifiedCardinality`, `owl:minQualifiedCardinality` or
  `owl:maxQualifiedCardinality` with an `owl:onClass` — and the ontology reads them as counts on the
  relationship to the class the cardinality qualifies: a `Contract` has at least two
  `HAS_CONTRACT_PARTY` `ContractParty`, a `Person` exactly one `HAS_DATE_OF_BIRTH` `DateOfBirth`. 198 of
  the relationships carry counts from them, 211 from restrictions of any kind. One shape is stretched:
  where the qualified class is a union, the count applies to the union as a whole, so it becomes a lower
  bound on the relationships to each member without a count of its own, since only one member need be
  counted.
- **Datatype-property restrictions place the property.** FIBO and Commons leave the domain of most
  datatype properties implicit and state it only as a restriction, e.g. `hasSurname` is a property of
  `PersonName` because `PersonName` restricts it. A restriction's count also decides whether the
  property holds one value or a list: a `WrittenContract`, allowed exactly one `isAssignable`, has a
  `BOOLEAN`, while a `Contract`, whose domain declaration allows any number, has a `LIST<BOOLEAN>`. 66
  node properties result, 56 of them placed by a restriction; a restriction that requires at least one
  value gives the node an `EXISTS` constraint, 28 of them. Types come from the declared range: a
  restriction's data range never changes the Neo4j type here, e.g. `hasDateValue` stays a `STRING`, since
  FIBO declares it `xsd:string` to hold a date's lexical form. One `owl:hasValue` is dropped, and
  reported: an `AssignableContract` `isAssignable` true, which fixes a value rather than a type.
- **Some datatype properties are still left out.** 34 of the 81 are neither given a domain nor
  restricted — `alt`, `hasURL`, `lat`, `long`, `hasGivenName` and the rest — and have no node to attach
  them to; the generator lists them. Some are synonyms of a kept property: `hasFamilyName` and
  `hasLastName` are declared `owl:equivalentProperty` to `hasSurname`, which `PersonName` has, but
  equivalence isn't followed, so they aren't properties of their own. FIBO's deprecated `hasDesignation` and `hasTag` are
  dropped outright, while Commons' own `hasTag` becomes a property of the address components that
  restrict it.
- **Subclass axioms that are unions aren't kept.** Four classes are subclasses of a union of classes
  rather than a named class, e.g. a `SettlementNettingProvision` is either a `PaymentNettingProvision`
  or a `NovationNettingProvision`. That's a choice, not a supertype, so it can't be an implied label.
- **Deprecated properties are dropped.** FIBO has deprecated `hasDesignation` and `hasTag` in
  `FND/Relations`; the relationships they would give aren't made. Commons' own `hasTag` is left out with
  the other domainless datatype properties.
- **FIBO names and Commons names are easy to confuse.** At this commit many of the concepts the FIBO
  module names suggest are defined in Commons, which FIBO builds on rather than duplicates: `LegalPerson`
  and `LegalEntity` come from `Commons/Organizations`, not `BE/LegalEntities/LegalPersons`; `Party` and
  `Agent` from `Commons/PartiesAndSituations`, not `FND/Parties/Parties`; `Jurisdiction` from
  `Commons/RegulatoryAgencies`. The area follows the defining module, so those classes are coloured as
  Commons foundations even though they're the heart of the parties area. No two classes of the closure
  share a local name at this commit; if one ever does, the generator appends its module to the label and
  says so here.
- **Datatypes are rounded to Neo4j's.** Commons' `CombinedDateTime`, a union of a string and two
  dateTime forms, is a `ZONED DATETIME`; `owl:rational`, e.g. a fractional interest of a third, is a
  `FLOAT`, which can't hold it exactly. The min and max facets of `hasLatitude` and `hasLongitude`'s
  restricted decimal are dropped (the properties themselves are left out with the other domainless ones).
- **Many relationships end at `Thing`.** FIBO and Commons leave most properties' domains and ranges
  implicit; where neither the property, its inverse nor its superproperties says, the end is `Thing`,
  e.g. `Thing` `HAS_EFFECTIVE_DATE` `Date`. 176 of the 535 relationships touch `Thing`, which every node
  also carries as its top label.
- **Properties aren't inherited.** A relationship is defined on the class whose domain or restriction
  declares it. A node of a subclass carries its superclasses' labels, through which it has their
  relationships too.
- **Individuals aren't modelled.** The closure's 43 named individuals — FIBO's maturity levels, Commons'
  calendar periods and time directions, the secondary unit designators of an address — describe the
  vocabularies' own housekeeping or enumerated values, not the domain, and are left out.
- **Property axioms beyond subproperties aren't kept.** `owl:propertyChainAxiom` (17), the two
  `owl:propertyDisjointWith` declarations and `owl:equivalentProperty` between kept properties (recorded
  in `extensions.custom.equivalentProperty`) have no equivalent in the format. `owl:disjointWith` between
  classes is recorded in `extensions.custom.disjointWith`.

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json). Its relationship
endpoints resolve, its keys cover existing properties, its counts are well formed, and its names and
descriptions are within the length limits, which covers the core validation rules; every node carries
`Thing`, and every node, relationship and property records the IRI of the term it came from.
