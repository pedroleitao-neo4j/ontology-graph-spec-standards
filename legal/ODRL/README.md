# ODRL 2.2 (W3C)

An ontology for the [Open Digital Rights Language (ODRL)](https://www.w3.org/TR/vocab-odrl/) 2.2, published by the
W3C. ODRL is a policy expression language: a machine-readable way to state what may and may not be done with content
and services, and what must be done in return. A policy — an agreement, offer, request, ticket, assertion, privacy
policy or set — holds permissions, prohibitions and duties; each rule grants one action over a target asset to
parties in functional roles, such as assignee and assigner, and is refined by constraints and logical constraints
over operators and left and right operands. ODRL 2.2 is a W3C Recommendation, developed by the Permissions &
Obligations Expression Working Group and now extended by the profiles of the
[ODRL Community Group](https://www.w3.org/community/odrl/). It is used for digital licensing and usage policies
wherever content, data and services are shared, and its JSON-LD context lets the same policies be written as JSON.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the official W3C ODRL 2.2 vocabulary |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |
| [`sample.json`](sample.json) | Sample data: a music licence offer and agreement |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |
| [`../../cypher.py`](../../cypher.py) | Generates `model.cypher` (shared by every standard) from `model.json` and `sample.json`, checking the data against the model |

## Source

The model is generated from the ODRL Version 2.2 RDF vocabulary, the Turtle file
[`ODRL22.ttl`](https://www.w3.org/ns/odrl/2/ODRL22.ttl) that the [ODRL Vocabulary & Expression
2.2](https://www.w3.org/TR/vocab-odrl/) Recommendation of 15 February 2018 links from its term tables, alongside the
[ODRL Information Model 2.2](https://www.w3.org/TR/odrl-model/) it expresses. Both are stable W3C documents: the
[W3C liability, trademark and permissive document license rules](https://www.w3.org/Consortium/Legal/2002/ipr-notice-20021231)
apply, which the vocabulary file itself declares as its licence. `generate.py` includes a small Turtle reader, so it
doesn't need an RDF library. To regenerate:

```bash
python3 generate.py                    # downloads ODRL22.ttl from the W3C
python3 generate.py path/to/ODRL22.ttl
```

The script needs only the Python standard library.

## Mapping

| ODRL (RDF vocabulary) | Ontology |
|---|---|
| Class, e.g. `odrl:Policy` | Node, labelled by its local name, e.g. `Policy` |
| `rdfs:subClassOf` an ODRL class, e.g. `Permission` of `Rule` | Implied label, e.g. every `Permission` is also a `Rule` |
| `rdfs:subClassOf` classes outside ODRL, e.g. `Action` a `schema:Action`; `Party` the agent classes of schema.org, FOAF and vCard | The `Thing` implied label, and `extensions.custom.subClassOf`, as compact IRIs |
| Class with no superclass, e.g. `Policy` or `Constraint` | The `Thing` implied label |
| `owl:disjointWith`, e.g. `Permission` and `Prohibition` | `extensions.custom.disjointWith` |
| `skos:definition`, `skos:note` | `description` |
| Object property, e.g. `odrl:target` | Relationship from its domain to its range, typed in upper snake case, e.g. `TARGET` |
| Domain or range that is a union, e.g. `target`'s domain `Rule or Policy`, `partOf`'s ends over assets and parties | One relationship per class in the union |
| Property with no domain or range of its own, e.g. `attributingParty` | Ends taken from its superproperty, `function` |
| Property with no range, e.g. `uid`, `profile`, `source`, `status`, `unit`, `rightOperandReference`, `operand` and its sub-properties | Property holding the IRIs it refers to, e.g. `Policy.profile` |
| Property ranging over `rdfs:Datatype`, `dataType` | Property holding the datatype's IRI, e.g. `xsd:date` |
| Datatype property, e.g. `rightOperand`, whose range is `RightOperand`, `rdfs:Literal` or `xsd:anyURI` | Property of each class of its domain, `LIST<STRING>` |
| `rdf:Property` with a class range, e.g. `leftOperand` | Relationship, e.g. `Constraint` `LEFT_OPERAND` `LeftOperand` |
| `owl:FunctionalProperty`, `owl:InverseFunctionalProperty`, cardinalities | `max_count: 1` at an end; ODRL 2.2 declares none, so no relationship carries counts and every property is a list |
| `owl:TransitiveProperty`, `includedIn` | Noted in the description, and `extensions.custom.transitive` |
| `owl:deprecated`, e.g. `UndefinedTerm` or `scope` | `extensions.custom.deprecated`; properties with no domain are left out |
| Individual of a class, e.g. `odrl:play` an `Action`, `odrl:gteq` an `Operator` | Not a node; a data set uses its IRI directly |
| Term IRI, e.g. `http://www.w3.org/ns/odrl/2/Policy` | `reference` |
| Resource IRI, e.g. the IRI of an agreement | A `uri` property on every node, and a `KEY` constraint over it |

Nodes also record, in `extensions.custom`, their IRI and the area of the model they belong to; properties and
relationships record their IRI, their superproperties, whether they have union ends, and whether they are deprecated.

### Individuals, not classes

ODRL defines most of its common vocabulary as individuals of its classes, not as classes: 63 actions (`use`,
`reproduce`, `play`, `print`, `textToSpeech`, …), 34 left operands (`absoluteSpatialPosition`, `dateTime`,
`industry`, …), 12 operators (`eq`, `gt`, `isA`, …), 6 party scopes, 3 conflict strategies (`perm`, `prohibit`,
`invalid`), 2 undefined-term strategies and 1 right operand. They are values, not kinds of thing: a data set states
them by their IRIs, e.g. a rule's action `odrl:play` and a constraint's operator `odrl:gteq`, so the ontology does
not give them nodes. The 25 SKOS collections that group the vocabulary into the sections of its documentation, and
the `odrl:core` individual that identifies the ODRL Core Profile, are left out too.

### Where the ontology differs from ODRL

- **Every node has a `uri` key.** ODRL resources are identified by their IRI. The ontology makes it a property and a
  key, so that nodes can be matched and relationships resolved. Blank nodes need generated identifiers.
- **A `Thing` root is added.** ODRL leaves most of its classes without a superclass: `Policy`, `Rule`, `Asset`,
  `Party`, `Constraint` and the rest stand alone, and the classes that do specialise something point outside ODRL —
  a `Party` is one of the agent classes of schema.org, FOAF and vCard, an `Action` a `schema:Action`. Each of these
  roots carries the `Thing` label, as LKIF Core does, making one tree of the model; the external superclasses are
  kept in `extensions.custom.subClassOf`.
- **One relationship per direction.** ODRL defines counterpart properties without declaring them `owl:inverseOf`:
  `assignee` and `assigneeOf`, `assigner` and `assignerOf`. The ontology keeps each as its own relationship, in the
  direction ODRL declares it. ODRL 2.2 declares no inverses at all, so nothing is collapsed.
- **References to anything are IRIs.** Properties with no class range — `uid`, `profile`, `source`, `status`,
  `unit`, `rightOperandReference`, and `dataType`, whose range is `rdfs:Datatype` — hold the IRIs or values they
  refer to as strings, e.g. `Policy.profile`. The operand properties of a logical constraint (`operand`, `and`,
  `or`, `xone`, `andSequence`) also declare no range; ODRL requires their values to be Constraint instances, so a
  loader can match what they hold on `uri`.
- **No counts anywhere.** The vocabulary declares no `owl:FunctionalProperty`, no `owl:InverseFunctionalProperty`
  and no cardinality restrictions, so no relationship carries counts and every property is a list. Requirements the
  Information Model states in prose, e.g. that a rule has one action, are not axioms in the vocabulary and so are
  not counts here.
- **Properties aren't inherited.** A relationship or property is defined on the class ODRL declares it for. A node
  of a subclass carries its superclasses' labels, through which it has their relationships and properties too. E.g.
  a `Permission` is also a `Rule`, and so has the `Rule` `TARGET` relationship.
- **Deprecated terms are flagged, and some are left out.** The deprecated classes `UndefinedTerm`, `AssetScope` and
  `PartyScope` remain nodes, marked in `extensions.custom.deprecated` and in their descriptions. Seven deprecated
  properties have no declared domain, so there is nothing to attach them to and they are left out: `scope`,
  `inheritRelation`, `undefined`, `payeeParty`, `inheritAllowed`, `proximity` and `timedCount`.
- **Abstract properties sit beside their sub-properties.** `relation`, `function`, `failure` and `operand` are the
  abstract parents of ODRL's property hierarchies; the ontology models each alongside its sub-properties, which
  record the parent in `extensions.custom.subPropertyOf`.
- **Individuals aren't nodes.** See above. A profile that wants to close a class, e.g. to say which actions it
  supports, can add their IRIs as suggested values.

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow from domain to range. Every
relationship in ODRL is unconstrained at both ends, the vocabulary declaring no functional properties or
cardinalities, so every arrow is thin and solid; a solid, darker arrow would be required and a dashed one functional.
Arrows are named by their relationship type, e.g. `TARGET` or `ASSIGNEE`, wherever the name fits without overlapping
a card or another name. Dotted arrows point from a subclass to the superclass whose label it also carries.

Cards are coloured by the area of the model a class belongs to, which each card also prints:

- `Policies and rules`: policies — agreements, offers, requests, tickets, assertions, privacy policies and sets —
  and the rules they hold: permissions, prohibitions and duties
- `Assets and parties`: assets and parties, their collections, and the deprecated scopes
- `Constraints and operands`: constraints, logical constraints, operators, left and right operands, and the conflict
  and undefined-term strategies
- `Actions and the root`: actions, and `Thing`, the root every class hangs from

Opened in a browser, hovering a card or arrow shows its name and description, and each card links to the term's IRI.
To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

The sample data, [`sample.json`](sample.json), describes a fictional record label, Northwind Records, licensing an
album and its four tracks. A catalogue-wide `Set` policy prohibits modifying the recordings, with deleting modified
copies as the remedy. An `Offer` inherits from it and lets anyone stream the album for a fee per stream. An
`Agreement` with a streaming service, Tunely, inherits from the offer: it permits Tunely to stream and play the album
in the EU or the UK until the end of 2027, a logical constraint and a date constraint; it attaches duties to pay per
stream, with a duty to inform the label as the consequence of not paying, and to attribute the artist; it obliges
Tunely to report usage; and it prohibits commercialising the album.

ODRL's actions, left operands, operators and the `perm` conflict strategy are individuals, which a data set refers to
by their IRIs. As the model has nodes for their classes, the sample makes each one used a node keyed by its ODRL IRI,
e.g. an `Action` with the `uri` `http://www.w3.org/ns/odrl/2/play`, shared by every rule that uses it. The companies,
the artist and their IRIs are fictional.

[`model.cypher`](model.cypher) creates the model's constraints and then loads the sample data. It needs Neo4j 5 or
later, Enterprise Edition, for the node key constraints, and is best run against an empty database:

```bash
cypher-shell -f model.cypher
```

It merges every node and relationship, so it can be run again. `cypher.py` checks the sample data against the model,
its labels, properties, keys and relationship counts, before writing the script. To regenerate it:

```bash
python3 ../../cypher.py .   # from this folder; or ../../cypher.py alone for every standard with sample data
```

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json) and reports no issues for any of
the built-in validation sets, including `all`.
