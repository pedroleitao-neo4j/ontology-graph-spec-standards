# ELI 1.4

An ontology for the [European Legislation Identifier (ELI)](https://op.europa.eu/en/web/eu-vocabularies/eli)
ontology 1.4, published by the Publications Office of the European Union. ELI is the EU's framework for identifying
legislation with persistent URIs, e.g. `http://data.europa.eu/eli/reg/2016/679/oj` for the GDPR, and describing it
with shared metadata. The EU institutions and a growing number of Member States use it to publish their legislation
as linked data. ELI follows the FRBR model: a legal resource, such as an act or one of its articles, is a work; its
version in a language at a point in time is a legal expression; and a file or printed edition of that is a format.
The relations of the legislative corpus run between these: amendment, repeal, consolidation, transposition and
citation, among others.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the official ELI ontology file |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |
| [`sample.json`](sample.json) | Sample data: the GDPR and the legislation around it |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |
| [`../../cypher.py`](../../cypher.py) | Generates `model.cypher` (shared by every standard) from `model.json` and `sample.json`, checking the data against the model |

## Source

The model is generated from version 1.4 of the ELI ontology, the OWL file
[`eli.owl`](https://op.europa.eu/documents/3938058/11669184/eli.owl/) that the Publications Office links from its
[ELI page on EU Vocabularies](https://op.europa.eu/en/web/eu-vocabularies/eli). The file is RDF/XML. `generate.py`
includes a small RDF/XML reader, so it doesn't need an RDF library. To regenerate:

```bash
python3 generate.py                    # downloads eli.owl from the Publications Office
python3 generate.py path/to/eli.owl
```

The script needs only the Python standard library.

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow from domain to range. A solid,
darker arrow is required. Only one relationship is: every `Format` has exactly one `FORMAT`. A dashed arrow is
functional, so every source node has at most one, e.g. an `Expression` `REALIZES` one `Work`. A thin solid arrow is
otherwise unconstrained. Arrows are named by their relationship type, e.g. `AMENDS` or `TRANSPOSES`, wherever the
name fits without overlapping a card or another name, with required relationships placed first. Dotted arrows point
from a subclass to the superclass whose label it also carries.

Cards are coloured by the FRBR level, or kind, of their class hierarchy, which each card also prints:

- `Work`: legal resources, their subdivisions and complex works
- `Expression`: expressions and legal expressions
- `Manifestation`: manifestations and formats
- `Agent` and `Concept`: the agents that pass, publish and hold rights over legislation, and the concepts of the
  authority tables that classify it

Opened in a browser, hovering a card or arrow shows its name and description, and each card links to the term's IRI.
To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Mapping

| ELI (OWL) | Ontology |
|---|---|
| Class, e.g. `eli:LegalResource` | Node, labelled by its local name, e.g. `LegalResource` |
| `rdfs:subClassOf` an ELI class, e.g. `LegalResource` of `Work` | Implied label, e.g. every `LegalResource` is also a `Work` |
| `rdfs:subClassOf` a FRBRoo or CIDOC CRM class, e.g. `frbroo:F1_Work` | `extensions.custom.subClassOf`, as a compact IRI |
| `rdfs:comment` | `description` |
| Object property, e.g. `eli:transposes` | Relationship from its domain to its range, typed in upper snake case, e.g. `TRANSPOSES` |
| Domain or range that is a union, e.g. `LegalExpression or LegalResource` | One relationship per class in the union |
| Domain or range left out | Taken from the inverse property |
| Pair of inverse properties, e.g. `amends` / `amended_by` | One relationship; the inverse is recorded in `extensions.custom.inverseOf` |
| Object property whose range is `owl:Thing`, e.g. `eli:cites` or `eli:licence` | Property holding the IRI of what it refers to, e.g. `cites` |
| Datatype property, e.g. `eli:date_publication` | Property of each class of its domain |
| `xsd:date` | `DATE` |
| `xsd:string`, `xsd:anyURI`, `rdfs:Literal` | `STRING` |
| `owl:FunctionalProperty`, e.g. `in_force` or `date_publication` | `max_count: 1` at the `from` end, or a single-valued property; other properties are lists, e.g. `LIST<STRING>` |
| `owl:cardinality 1` restriction, e.g. `Format` ⊑ `format exactly 1` | Relationship from the restricted class with `count: 1` at the `from` end |
| Concept class, e.g. `eli:InForce`, the `skos:Concept`s of `eli:InForceTable` | Node, which also carries the `Concept` label |
| Concept scheme ELI declares in full, e.g. `eli:InForceTable` | `one_of` on the node's `uri`, e.g. `eli:InForce-inForce`, `-notInForce` and `-partiallyInForce` |
| Concepts ELI gives as examples, e.g. the media types of `eli:FormatTypeTable` | Suggested values in the description, and `extensions.custom.suggestedValues`; not `one_of` |
| `eli:specificPropertyOf`, e.g. `dcterms:publisher` | `extensions.custom.specificPropertyOf` |
| Term IRI, e.g. `http://data.europa.eu/eli/ontology#LegalResource` | `reference` |
| Resource IRI, e.g. the ELI of an act | A `uri` property on every node, and a `KEY` constraint over it |

Nodes also record, in `extensions.custom`, their IRI, FRBR level, superclasses from other ontologies, concept schemes
and the version notes ELI keeps for each term, e.g. `created in v1.0`. Properties and relationships record their IRI,
the Dublin Core property they specialise, their superproperties, inverse and original ELI name where ELI renamed them,
e.g. `status` for `in_force`, and whether they are functional or have union ends.

### Concepts and authority tables

ELI classifies legislation by concepts: its type, e.g. a regulation or a directive (`ResourceType`); its subdivision
type, e.g. an article (`SubdivisionType`); whether it's in force (`InForce`); its jurisdiction (`AdministrativeArea`);
the language of an expression (`Language`); the legal value of a format (`LegalValue`); and so on. ELI defines each
as the set of `skos:Concept`s in a concept scheme.

The ontology makes each concept class a node, and the properties that take them relationships, e.g. `LegalResource`
`TYPE_DOCUMENT` `ResourceType`. A concept is shared by many resources and has labels in many languages, and as a node
it groups the resources it classifies, e.g. every act of one type or jurisdiction. `skos:Concept` itself is a node,
`Concept`, with a `prefLabel` property. Every concept class carries its label, and `eli:is_about` ranges over it,
taking subjects from any scheme, e.g. EuroVoc.

Only two schemes are declared in full in the ontology file: `eli:InForceTable`, with *in force*, *partially in force*
and *not in force*, and `eli:LegalValueTable`, with *official*, *authoritative*, *definitive* and *unofficial*. The
`uri` of an `InForce` or `LegalValue` node is one of these concepts' IRIs. ELI lists media types and *print* as
examples of format types, which other schemes may add to, so these are suggested values only. The other schemes'
values aren't in the file: resource types, administrative areas and languages come from the EU authority tables, e.g.
`http://publications.europa.eu/resource/authority/language`, or from tables each Member State defines, as for work
types, subdivision types and versions. The ontology has no values for them.

### Where the ontology differs from ELI

- **Every node has a `uri` key.** ELI resources are identified by their IRI, for legal resources and expressions an
  ELI. The ontology makes it a property and a key, so that nodes can be matched and relationships resolved. Blank
  nodes need generated identifiers.
- **One relationship per inverse pair.** ELI declares most relations in both directions, e.g. `amends` and
  `amended_by`. In a graph, one relationship can be traversed both ways, so the ontology keeps one direction and
  records the other as `extensions.custom.inverseOf`. It keeps the functional one, e.g. `REALIZES` rather than
  `is_realized_by`; else the one ELI defines rather than describing as the inverse of the other, e.g. `IS_PART_OF`
  rather than `has_part`; else the active one, e.g. `AMENDS` rather than `amended_by`; else the one that declares the
  pair, e.g. `HAS_MEMBER` rather than `is_member_of`.
- **References to anything are IRIs.** `cites`, `cited_by_case_law`, `related_to`, `licence`, `media_type`,
  `uri_schema` and `is_exemplified_by` range over `owl:Thing`. They may refer to things outside ELI, e.g. a court
  decision, a licence, an IANA media type or a file. The ontology makes each a property holding the IRIs, e.g.
  `LegalResource.cites`. Where a cited resource is itself loaded, a loader can match it on its `uri`.
- **Paired properties are both kept.** ELI has a literal and an agent form of some properties: `publisher` and
  `publisher_agent`, `rightsholder` and `rightsholder_agent`, `responsibility_of` and `responsibility_of_agent`, and,
  for the official journal, `published_in` and `published_in_format`. ELI asks for the agent or format form when the
  value has a URI. The ontology keeps both: the literal as a property, e.g. `Format.publisher`, and the other as a
  relationship, e.g. `PUBLISHER_AGENT`.
- **Properties aren't inherited.** A relationship or property is defined on the class ELI declares it for. A node of
  a subclass carries its superclasses' labels, through which it has their relationships and properties too. E.g. a
  `LegalResourceSubdivision` is also a `LegalResource` and a `Work`.
- **Restrictions are relationships.** The one class restriction, every `Format` has exactly one `format`, is a
  relationship of its own from `Format`, with `count: 1`, next to the general one from `Manifestation`.
- **Language-tagged values are strings.** `title`, `description`, `publisher` and other `rdfs:Literal` properties may
  have a language tag, e.g. a title in French. The ontology types them `STRING`, without the tag; an expression is
  already in one language, given by its `LANGUAGE` relationship.
- **Properties without `owl:FunctionalProperty` are lists.** In OWL a property may have several values unless it is
  functional. So `title`, `number` and `id_local`, for example, are lists, while `date_publication` and
  `first_date_entry_in_force` are single values.
- **Deprecated properties are left out.** `implements` and `implemented_by`, which ELI 1.1 deprecated in favour of `applies` and
  `applied_by`, aren't included.
- **Terms from other ontologies aren't nodes**, apart from `skos:Concept`. ELI places its classes in FRBRoo and
  CIDOC CRM, e.g. `Work` under `frbroo:F1_Work` and `Agent` under `crm:E39_Actor`, and its FRBR properties under
  FRBRoo properties, e.g. `realizes` under `frbroo:R3i_realises`. These are recorded in `extensions.custom`.

## Sample data

The sample data, [`sample.json`](sample.json), describes the General Data Protection Regulation, Regulation (EU)
2016/679, as ELI would publish it. The act as published in the Official Journal is a `LegalResource`, realised in
English and French `LegalExpression`s, each embodied in PDF or XHTML `Format`s with their legal value. Three of its
articles are subdivisions of it. The 2018 corrigendum corrects the English text, and the consolidated version of 4 May
2016 consolidates both; a `ComplexWork` groups the original and consolidated versions of the act. The regulation
repeals Directive 95/46/EC. Beside it are the Law Enforcement Directive (EU) 2016/680, adopted the same day, which
repeals Framework Decision 2008/977/JHA, and Ireland's Data Protection Act 2018, which transposes the directive and
ensures the implementation of the regulation.

Resource types, languages, countries and the bodies that passed and published the acts are concepts and agents from
the EU authority tables; in-force status and legal value use ELI's own concepts, and formats IANA media types. ELI
leaves subdivision types and versions to each publisher, so those come from an example table under `example.org`.

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
