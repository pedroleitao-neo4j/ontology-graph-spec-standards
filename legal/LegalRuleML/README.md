# LegalRuleML 1.0 (OASIS)

An ontology for [LegalRuleML](https://docs.oasis-open.org/legalruleml/legalruleml-core-spec/v1.0/os/legalruleml-core-spec-v1.0-os.html),
the Legal Rule Modelling Language, an OASIS Standard of 30 August 2021 developed by the
[OASIS LegalRuleML Technical Committee](https://www.oasis-open.org/committees/legalruleml/) — Monica Palmirani, Guido
Governatori, Tara Athan, Harold Boley, Adrian Paschke and Adam Wyner among its editors. LegalRuleML is a language for
legal rules: the deontic specifications that legal sources give rise to — obligations, prohibitions, permissions,
rights and the suborder lists that chain them; the defeasible rules, strengths and overrides that resolve conflicts
between them; and the statements, sources, references, authorities, jurisdictions, actors, roles and times they are
stated in, hold for and are applied in. It extends RuleML, the rule markup language, with what legal norms need, and
it is a companion to Akoma Ntoso: where Akoma Ntoso marks up the documents rules are found in, LegalRuleML marks up
the rules themselves, and its references point into Akoma Ntoso documents.

The RDFS modelled here is the metamodel of the Core Specification: the classes and properties its XML elements are
described by, from `Statement` and `PrescriptiveStatement` down to `Obligation`, `SuborderList` and `Alternatives`.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the official LegalRuleML RDFS modules |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |
| [`sample.json`](sample.json) | Sample data: rules of a fictional tenancy act |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |
| [`../../cypher.py`](../../cypher.py) | Generates `model.cypher` (shared by every standard) from `model.json` and `sample.json`, checking the data against the model |

## Source

The model is generated from the twelve RDFS modules the Core Specification publishes as normative computer language
definitions, in the [`rdfs/`](https://docs.oasis-open.org/legalruleml/legalruleml-core-spec/v1.0/os/rdfs/) folder of
the OASIS document repository alongside the
[LegalRuleML Core Specification Version 1.0](https://docs.oasis-open.org/legalruleml/legalruleml-core-spec/v1.0/os/legalruleml-core-spec-v1.0-os.html)
(OASIS Standard, 30 August 2021). © OASIS Open 2021; the document may be copied and furnished to others under the
notices in the specification. The modules are, as `generate.py` reads them:

- `upper` and `wrapper`, the generic constructs: collections and their members, comments, documents, and the wrappers
  XML content is carried in
- `rulemm`, the RuleML metamodel LegalRuleML extends: wrappers, well-formed expressions, formulas, terms and data
- `statement`, the statements of a document: constitutive and factual, prescriptive, penalty, reparation and override
  statements, with their paraphrases and templates
- `deontic`, the deontic specifications: obligation, permission, prohibition and right, with compliance, violation,
  reparation, suborder lists, and the modalities and roles they are stated with
- `defeasible` and `alternative`, the conflict machinery: strict and defeasible strengths, defeaters, overrides, and
  the alternatives a statement or expression may be given
- `source`, the sources and references: legal sources, ordinary sources, and the references that point into them,
  including LegalRuleML documents themselves
- `context`, the associations that carry properties to their targets within a scope
- `legaltemporal`, the legal statuses and temporal characteristics rules hold for
- `metadata-actor`, the actors, agents, figures, functions and roles
- `metadata-jurisdiction-authority`, the jurisdictions and authorities

The modules declare no `owl:imports`; `generate.py` reads all twelve. It includes a small RDF/XML reader, so it
doesn't need an RDF library. To regenerate:

```bash
python3 generate.py                          # downloads the twelve modules from docs.oasis-open.org
python3 generate.py path/to/modules/         # or a directory holding a <module>.rdf for each
```

The script needs only the Python standard library.

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow from domain to range. The RDFS
declares no functional properties and no cardinalities, so every arrow is a thin solid line: an end is otherwise
unconstrained. A solid, darker arrow would be required and a dashed one at most one. Arrows are named by their
relationship type, e.g. `HAS_AGENT` or `APPLIES_PENALTY`, wherever the name fits without overlapping a card or another
name. Dotted arrows point from a subclass to the superclass whose label it also carries.

Cards are coloured by the part of the model a class belongs to, which each card also prints:

- Rules and statements: `rulemm`, `statement`, `upper` and `wrapper`
- Deontic and defeasible: `deontic`, `defeasible` and `alternative`
- Sources, authorities and time: `source`, `legaltemporal`, `metadata-actor` and `metadata-jurisdiction-authority`
- Context: `context`

Opened in a browser, hovering a card or arrow shows its name and description, and each card links to the term's IRI.
To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Mapping

| LegalRuleML (RDFS) | Ontology |
|---|---|
| Class, e.g. `lrmlmm:Obligation` | Node, labelled by its local name in PascalCase, e.g. `Obligation` |
| A class declared in several modules, e.g. `Scope` in `context` and `statement` | One node, for the module it is first declared in |
| Two classes with the same local name in different namespaces, e.g. `lrmlmm:Wrapper` and `rulemm:Wrapper` | Both nodes, the second renamed, e.g. `RuleMLWrapper` and `RuleMLXMLLiteralWrapper` |
| `rdfs:subClassOf`, e.g. `Obligation` of `DeonticSpecification` | Implied label, e.g. every `Obligation` is also a `DeonticSpecification` |
| `owl:disjointWith`, e.g. `LogicalFormulaStatement` from `RuleStatement` | `extensions.custom.disjointWith` |
| `rdfs:comment`, or else `rdfs:label`, e.g. `deontic specification` | `description` |
| Property, e.g. `lrmlmm:hasAgent` | Relationship from its domain to its range, typed in upper snake case, e.g. `HAS_AGENT` |
| Domain or range that is a union, e.g. the targets an `Association` applies to | One relationship per class in the union |
| Domain or range left out | Taken from the superproperty, e.g. `hasAgent` from `hasMember` |
| Literal range, e.g. `refID` over `xsd:string` | Property of the domain class, e.g. `Reference.refID`, a `LIST<STRING>` |
| `rdfs:subPropertyOf`, e.g. `hasAgent` of `hasMember` | `extensions.custom.subPropertyOf` |
| A range the modules don't declare, e.g. `rulemm:Time`, `lrmlmm:Thing` or `lrmlmm:Modality` | The property is left out, listed by `generate.py` |
| Term IRI, e.g. `http://docs.oasis-open.org/legalruleml/ns/v1.0/metamodel#Obligation` | `reference`, which the IRIs resolve to |
| Individual IRI, e.g. of a statement in a document | A `uri` property on every node, and a `KEY` constraint over it |

Nodes also record, in `extensions.custom`, their IRI, module and area. Relationships also record their IRI, module and
superproperties.

### Where the ontology differs from LegalRuleML

- **Every node has a `uri` key.** LegalRuleML resources are identified by their IRI. The ontology makes it a property
  and a key, so that nodes can be matched and relationships resolved.
- **Labels are PascalCase.** The modules name classes in CamelCase already, e.g. `DeonticSpecification`; the ontology
  keeps those names, renaming only `rulemm:Wrapper` and `rulemm:XMLLiteralWrapper`, which collide with the
  metamodel's own `Wrapper` and `XMLLiteralWrapper`, to `RuleMLWrapper` and `RuleMLXMLLiteralWrapper`.
- **A class is one node, however many modules re-declare it.** The modules repeat several classes — `Associable`,
  `Scope`, `Statement`, `Wrapper` and others — each repeat adding subclass axioms. All the axioms of a class are read,
  from every module that declares it.
- **No root is added.** The modules declare no top class, and none is invented: the model's roots are the classes no
  superclass is given for, e.g. `Statement`'s `Expression`, `Agent`'s `Actor` and `Collection`'s `Collectable`. A
  graph has no reasoner, so a loader gives each node the labels of the classes it belongs to.
- **Only what the RDFS says is kept.** The specification states much more than the RDFS encodes: that every
  prescriptive statement applies a deontic specification, that an obligation has one bearer, that every rule has a
  strength. None of that is in the modules' domains, ranges or cardinalities — the RDFS declares no functional
  properties and no restrictions at all — so the ontology has no counts, and a loader must follow the specification's
  constraints itself.
- **Seven properties are left out.** Five range over classes the modules reference but never declare — `wraps` over
  `lrmlmm:Thing`, `atTime`, `hasTime` and `hasCreationDate` over `rulemm:Time`, `appliesModality` over
  `lrmlmm:Modality` — one, `hasMemberType`, has no range, and one, `memberReferenceType`, ranges over `rdfs:Class`
  itself. A data set can still hold their values as IRIs.
- **The XML is not modelled.** The RDFS is the metamodel of LegalRuleML's XML: the elements of a LegalRuleML document
  are individuals of these classes, e.g. an `<lrml:Obligation>` element an `Obligation`, and the attributes and
  containment the schemas describe are not modelled here. The Core Specification's XSD and Relax NG schemas, which
  `generate.py` does not read, describe them.

## Sample data

The sample data, [`sample.json`](sample.json), is a LegalRuleML document modelling four sections of a fictional
Residential Tenancies (Example) Act 2024 of Victoria. A strict rule obliges the tenant to pay rent on time, and a
`Reparation` links it to the late fee that penalises a breach. A defeasible rule obliges the landlord to give 28 days'
notice to vacate; it has two alternative readings, and an `Override` puts a defeasible rule permitting 14 days' notice
where the premises are unfit above it. A strict rule prohibits the landlord from entering without notice. Associations
tie each statement to its section of the act, the enacting authority, the jurisdiction and its in-force date, within
a context scoped to the document's statements. The agents, the figures they play in the tenancy and the drafting roles
are recorded beside them, with a paraphrase, a comment and a template.

The model has no relationships from a statement to the formula it contains, so the deontic specifications, e.g. the
tenant's obligation to pay rent, stand beside the statements, linked to the terms for their bearer and auxiliary
party.

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
