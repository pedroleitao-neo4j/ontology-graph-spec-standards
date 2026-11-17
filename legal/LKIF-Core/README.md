# LKIF Core 1.1

An ontology for [LKIF Core](https://github.com/RinkeHoekstra/lkif-core), the core legal ontology of the Legal
Knowledge Interchange Format. The University of Amsterdam, the University of Bologna and Fraunhofer FOKUS developed it
in the European ESTRELLA project (IST-2004-027665), and Rinke Hoekstra maintains it. It's licensed under CC BY 4.0.
LKIF Core is a library of OWL modules covering the concepts legal knowledge is built on:

- norms, as qualifications of what is allowed, disallowed or obliged
- legal sources such as statutes, regulations, contracts and precedents
- rights and powers, after Hohfeld and Sartor
- legal persons, public bodies and public acts
- legal and social roles
- the commonsense layers beneath them: propositions, beliefs and communicated attitudes; actions, agents and
  processes; and places, time and parthood

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the official LKIF Core Turtle files |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |
| [`sample.json`](sample.json) | Sample data: a fictional residential tenancy and the statute governing it |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |
| [`../../cypher.py`](../../cypher.py) | Generates `model.cypher` (shared by every standard) from `model.json` and `sample.json`, checking the data against the model |

## Source

The model is generated from the Turtle files of LKIF Core 1.1, commit
[`1958d94`](https://github.com/RinkeHoekstra/lkif-core/tree/1958d940c4157678c7f5445b07b35e093e918f31) of the
[LKIF Core repository](https://github.com/RinkeHoekstra/lkif-core). That's the February 2026 release, which relicensed
the ontology under CC BY 4.0 and added Turtle versions of the original RDF/XML files. The ontology itself is
unchanged since version 1.1 of July 2008.

`generate.py` starts from the `lkif-core` module and follows its `owl:imports`, which gives twelve modules:

- the abstract concepts in `lkif-top`, `mereology`, `relative-places` and `time`
- the basic concepts in `process`, `action`, `role` and `expression`
- the legal concepts in `legal-action`, `legal-role` and `norm`
- `lkif-core`, which only imports the others

It includes a small Turtle reader, so it doesn't need an RDF library. To regenerate:

```bash
python3 generate.py                          # downloads the pinned commit from GitHub
python3 generate.py path/to/lkif-core.zip    # or an archive, or a clone
```

The script needs only the Python standard library.

### Why LKIF Extended isn't included

The repository also has `lkif-extended`, which adds two framework modules to LKIF Core:

- `time-modification`, the intervals and modifications that describe how legal documents come into force and are
  amended, for compatibility with MetaLex/CEN
- `lkif-rules`, the vocabulary of the LKIF rule language and argumentation

The authors took both modules out of LKIF Core in version 1.0.3 and give them as a separate entry point. They describe
the formats of two frameworks rather than the legal domain. They're left out here so that the ontology is LKIF Core as
published. To include them, set `ENTRY` in `generate.py` to `lkif-extended`. Datatype properties, which only
`time-modification` has, would then need a mapping; the script stops if it finds any.

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow from domain to range. A solid,
darker arrow is required: a class restriction says every source node has one or more, e.g. every `Statute` `BEARS`
some `Norm`. A dashed arrow means every source node has at most one, and a thin solid arrow is otherwise
unconstrained. Arrows are named by their relationship type, e.g. `PLAYS` or `QUALIFIES`, wherever the name fits
without overlapping a card or another name, with required relationships placed first. Dotted arrows point from a
subclass to the superclass whose label it also carries.

Cards are coloured by module, which each card also prints:

- Legal: `norm`, `legal-action` and `legal-role`
- Expressions, actions and roles: `expression`, `action` and `role`
- Processes, places, time and parthood: `process`, `relative-places`, `time` and `mereology`
- Top: `lkif-top`, and `Thing`

Opened in a browser, hovering a card or arrow shows its name and description, and each card links to the line of the
Turtle file on GitHub that declares the term. To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

The sample data, [`sample.json`](sample.json), reads a fictional residential tenancy through LKIF Core's legal and
commonsense layers. A member of a legislative body introduces a bill, and the body enacts a statute bearing three
norms: an obligation on landlords to keep a dwelling in repair, a permission for tenants to withhold rent once they
have given notice of disrepair, and a prohibition on evicting without a court order. A landlord and a tenant play their
roles in the context of a lease, which bears the tenant's obligation to pay rent. The tenant's written notice, borne by
a letter, leads to the landlord's repairs. Each action has its actor, requirement, result and the moment it took up,
and the moments are ordered in time.

LKIF's time is serial: every moment has one immediately before it and one immediately after it, so the model requires
at least one `IMMEDIATELY_AFTER` at both ends of every `TemporalOccurrence`. No finite data can meet that, as the first
and last moments of any stretch of time have no neighbour on one side. The sample lists the relationship under `open`,
so `cypher.py` doesn't require its minimum counts, and `model.cypher` says so in its header.

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

## Mapping

| LKIF Core (OWL) | Ontology |
|---|---|
| Class, e.g. `norm:Legal_Document` | Node, labelled by its local name in PascalCase, e.g. `LegalDocument` |
| `owl:Thing` | The `Thing` node, whose label every node carries |
| `rdfs:subClassOf` a named class, e.g. `Statute` of `Legal_Document` | Implied label, e.g. every `Statute` is also a `LegalDocument` |
| A class without a named superclass, e.g. `lkif-top:Abstract_Entity` | Implied label `Thing` |
| `owl:equivalentClass` an intersection, e.g. `Belief_In_Violation` ≡ `Belief` ⊓ `towards some Disallowed` | Implied labels for the named classes, e.g. `Belief`, and relationships for the restrictions |
| `owl:equivalentClass` a union, e.g. `Place` ≡ `Absolute_Place` ⊔ `Relative_Place` | Implied label on each member, e.g. every `AbsolutePlace` is also a `Place`, and `extensions.custom.unionOf` |
| `owl:equivalentClass` a named class, e.g. `Person` ≡ `Natural_Person` | Both nodes, each recording the other in its description and `extensions.custom.equivalentTo` |
| `rdfs:comment` | `description` |
| Object property, e.g. `expression:bears` | Relationship from its domain to its range, typed in upper snake case, e.g. `BEARS` |
| Domain or range that is a union, e.g. `Natural_Person or Legal_Person` | One relationship per class in the union |
| Domain or range left out | Taken from the inverse property, else from the superproperties, else `Thing` |
| Pair of inverse properties, e.g. `actor` / `actor_in` | One relationship, in the active voice, e.g. `Action` `ACTOR` `Agent`; the inverse is recorded in `extensions.custom.inverseOf` |
| `owl:FunctionalProperty`, e.g. `role:context` | `max_count: 1` at the `from` end |
| `owl:someValuesFrom` restriction, e.g. `Statute` ⊑ `bears some Norm` | Relationship from the restricted class with `min_count: 1` at the `from` end |
| `owl:someValuesFrom` on the inverse of a kept property, e.g. `Agent` ≡ `actor_in some Action` | `min_count: 1` at the `to` end, e.g. of `Action` `ACTOR` `Agent` |
| `owl:allValuesFrom` restriction, e.g. `Person_Role` ⊑ `played_by only Person` | Relationship from the restricted class to the narrower class, e.g. `Person` `PLAYS` `PersonRole` |
| `owl:cardinality` and `owl:minCardinality`, e.g. `Pair` ⊑ `strict_part exactly 2 Part` | Counts, e.g. `count: 2` |
| Term IRI, e.g. `http://www.estrellaproject.org/lkif-core/norm.owl#Norm` | `extensions.custom.iri`; the `reference` is the line of the Turtle file on GitHub that declares the term, as the IRIs no longer resolve |
| Individual IRI | A `uri` property on every node, and a `KEY` constraint over it |

Where the domain and range of a property and the restrictions that use it describe the same pair of classes, they're
one relationship. For example, `actor` has the domain `Action` and the range `Agent`. Restrictions say that every
action has exactly one actor and that every agent is the actor in some action. The result is one `Action` `ACTOR`
`Agent` relationship with `count: 1` at the `from` end and `min_count: 1` at the `to` end. Its description includes a
sentence for each restriction.

Nodes also record, in `extensions.custom`, their IRI, module, LKIF name, and equivalent and disjoint classes.
Relationships also record their IRI and module, their inverse, superproperties and equivalent properties, and
whether they're symmetric, transitive or functional. They also list the kinds of restriction they come from.

### Where the ontology differs from LKIF Core

- **Every node has a `uri` key.** LKIF individuals are identified by their IRI. The ontology makes it a property and a
  key, so that nodes can be matched and relationships resolved. Blank nodes need generated identifiers.
- **Labels are PascalCase.** LKIF names classes in snake case, e.g. `Legal_Document`; the ontology labels them as
  Neo4j labels usually are, e.g. `LegalDocument`, and keeps the LKIF name in `extensions.custom.lkifName`.
- **`owl:Thing` is a node.** Many LKIF properties range over anything. `played_by`, `participant` and
  `spatial_reference` have `owl:Thing` as their range. The mereology and role properties, e.g. `part`, `member`,
  `context` and `counts_as`, have no domain or range at all. They become relationships to or from `Thing`. Each top
  class, e.g. `Abstract_Entity` or `Agent`, carries the `Thing` label, so every node has it.
- **Defined classes are only described by what they require.** LKIF defines many classes by necessary and sufficient
  conditions. For example, an `Agent` is anything that is the actor in some action, and a `Norm` is anything that
  qualifies something as normatively qualified. The ontology keeps the necessary side, as relationships and counts.
  A graph has no reasoner to classify nodes, so a loader has to give each node all the labels that apply to it.
- **Equivalent classes are kept apart.** LKIF declares five pairs of named classes equivalent: `Person` and
  `Natural_Person`, `Obligation` and `Prohibition`, `Association` and `Society`, `Limited_Company` and
  `Unincorporated`, and `Public_Limited_Company` and `Incorporated`. Both classes of each pair are nodes, so a node of
  one should also carry the other's label.
- **One relationship per inverse pair.** LKIF names most relations in both directions, e.g. `bears` and `medium`. The
  ontology keeps the active-voice direction, e.g. `actor` rather than `actor_in`, and `plays` rather than
  `played_by`. When both directions are in the same voice, it keeps the one the other is declared the inverse of,
  e.g. `bears` rather than `medium`, `towards` rather than `attitude`, and `after` rather than `before`. Restrictions
  on the dropped direction are counted at the `to` end of the kept one.
- **Nested class expressions only keep their named classes.** A restriction's filler is often a class expression. For
  example, a `Code` bears some `Norm` ⊓ `utterer some Legislative_Body`. The ontology relates the class to the named
  classes of the expression, e.g. `Code` `BEARS` `Norm`, and the nested restriction is only in the description from
  `rdfs:comment`. When a filler names no class, a `someValuesFrom` restriction relates the class to the range of the
  property. An `allValuesFrom` restriction with such a filler is left out: it applies to `Action`, `Code`,
  `Contract`, `Expectation`, `Organisation`, `Regulation` and `Statute`. A filler that is a union gives a
  relationship to each member, without a count, since only one of them is required.
- **Some axioms aren't kept.** The format has no equivalent for these, and they're left out:
  - `owl:complementOf`, e.g. a `Function` is played by a physical object that isn't an agent
  - the cardinality of zero that makes an `Atom` have no parts
  - `owl:disjointWith`, which is recorded in `extensions.custom.disjointWith`
  - `owl:disjointObjectProperties`, between `context` and `imposed_on`
  - transitivity and symmetry, which are recorded in `extensions.custom`
- **Properties aren't inherited.** A relationship is defined on the class whose domain or restriction declares it. A
  node of a subclass carries its superclasses' labels, through which it has their relationships too.
- **There are no data properties.** LKIF Core describes individuals only by their classes and relations; apart from
  `uri`, the nodes have no properties.

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json) and reports no issues for any of
the built-in validation sets, including `all`.
