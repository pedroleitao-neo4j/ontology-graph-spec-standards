# CASE 1.5.0

An ontology for the [Cyber-investigation Analysis Standard Expression (CASE)](https://caseontology.org/) 1.5.0,
published by the CASE Community under the Linux Foundation's Cyber Domain Ontology project. CASE is the investigation
profile of the [Unified Cyber Ontology (UCO)](../UCO): around UCO's observables and actions, it records the
investigation itself and its authorizations, the investigative actions performed and the actions that informed them,
the provenance records that track exhibits through their chain of custody, and the roles of the people involved.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the official CASE and UCO Turtle files, using the [UCO generator](../UCO/generate.py) |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`sample.json`](sample.json) | Sample data: a police investigation into leaked designs, from search warrant to forensic report |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |
| [`../../cypher.py`](../../cypher.py) | Generates `model.cypher` (shared by every standard) from `model.json` and `sample.json`, checking the data against the model |

## Source

The model is generated from the Turtle files of CASE 1.5.0, tag
[`1.5.0`](https://github.com/casework/CASE/tree/1.5.0/ontology) of the [CASE repository](https://github.com/casework/CASE)
(`ontology/investigation` and `ontology/vocabulary`), together with those of UCO 1.5.0, which CASE imports. CASE is
written the same way as UCO, in OWL 2 with SHACL shapes, so `generate.py` reads and builds it with the UCO generator
in [`../UCO/generate.py`](../UCO/generate.py). To regenerate:

```bash
python3 generate.py                                             # downloads the 1.5.0 releases of CASE and UCO
python3 generate.py path/to/CASE-1.5.0.zip path/to/UCO-1.5.0.zip  # or archives, or clones
```

The script needs only the Python standard library.

## What the model contains

A CASE graph is a UCO graph: its investigations hold UCO observables, and its investigative actions are UCO actions.
The full UCO model is in [`../UCO`](../UCO). This model holds what CASE adds, and the part of UCO it needs to stand on
its own:

- the 11 CASE classes, e.g. `Investigation`, `InvestigativeAction`, `ProvenanceRecord` and `Investigator`;
- the UCO classes they extend, up to `UcoThing`, e.g. `Action`, `ContextualCompilation` and `Role`;
- the UCO classes their relationships point at, and their superclasses. CASE's relationships point only at CASE
  classes, so this adds none.

That's 7 UCO classes. They keep their properties, e.g. `UcoObject.name` and `Action.startTime`, and their
relationships to classes in the model, e.g. `Action` `OBJECT` `UcoObject` and `ContextualCompilation` `OBJECT`
`UcoObject`. Their relationships to the rest of UCO are left out: `UcoObject` `HAS_FACET` `Facet`, `CREATED_BY`
`IdentityAbstraction`, `EXTERNAL_REFERENCE` `ExternalReference` and `OBJECT_MARKING` `MarkingDefinitionAbstraction`,
`Action` `LOCATION` `Location`, and `ActionLifecycle` `PHASE` `ArrayOfAction`. To use them, combine this model with
the UCO model. Every node records which ontology it comes from in `extensions.custom.ontology`, `CASE` or `UCO`.

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow from the class that has the
property to the class of its values. A solid, darker arrow is required: every source node has one or more. A dashed
arrow allows at most one, and a thin solid arrow is otherwise unconstrained. Arrows are named by their relationship
type, e.g. `RELEVANT_AUTHORIZATION` or `WAS_INFORMED_BY`, wherever the name fits without overlapping a card or another
name. Dotted arrows point from a subclass to the superclass whose label it also carries. Cards are coloured by
ontology, CASE or UCO, and print their namespace, e.g. `investigation` or `core`. Opened in a browser, hovering a card
or arrow shows its name and description, and each card links to its page in the
[CASE](https://ontology.caseontology.org/documentation/) or
[UCO documentation](https://ontology.unifiedcyberontology.org/documentation/). To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

[`sample.json`](sample.json) is Operation Kestrel, a police investigation into an engineer suspected of leaking their
employer's gearbox designs. It follows the same case as the [UCO sample data](../UCO#sample-data). The `Investigation`
has two `RELEVANT_AUTHORIZATION`s: a search warrant and the employer's consent. The investigator seizes the suspect's
laptop and phone and hands them to a forensic examiner, who images and analyses them, and a lawyer then reviews the
report. Each `InvestigativeAction` records its performer, what it acted on, what it produced, and the actions it
`WAS_INFORMED_BY`. Its `ProvenanceRecord`s carry the exhibits' chain of custody, e.g. exhibit `AM/1/1`, the disk
image, derives from root exhibit `AM/1`, the laptop. An `ExaminerActionLifecycle` groups the examiner's actions,
including a failed first extraction of the phone with its `ERROR`. A `SubjectActionLifecycle` groups the suspect's
own actions, as the examination reconstructed them. The people, the police force and the case are fictional.

This model holds only the part of UCO that CASE needs, so the people and the evidence are plain `UcoObject` nodes,
e.g. the laptop. Each person appears as the role they play, e.g. an `Investigator` or a `Subject`, and that role
performs the actions. Combined with the UCO model, the evidence would be observables such as a `Laptop` with its
facets. Each person would be a `Person`, linked to their role by a `Relationship`.

[`model.cypher`](model.cypher) creates the model's constraints and merges the sample data. It needs Neo4j 5 or later,
Enterprise Edition, for its node key constraints. To regenerate and load it:

```bash
python3 ../../cypher.py .            # from this folder; checks sample.json against the model
cypher-shell -f model.cypher         # against an empty database
```

## Mapping

CASE is mapped as UCO is; see the [UCO mapping](../UCO/README.md#mapping). For example:

| CASE (OWL and SHACL) | Ontology |
|---|---|
| Class, e.g. `investigation:Investigation` | Node, labelled by its local name, e.g. `Investigation` |
| `rdfs:subClassOf`, e.g. `Investigation` of `uco-core:ContextualCompilation` | Implied label, e.g. every `Investigation` is also a `ContextualCompilation` |
| Property shape with an `sh:datatype`, e.g. `investigation:exhibitNumber` on `ProvenanceRecord` | Property of that node, e.g. `ProvenanceRecord.exhibitNumber` |
| Property shape with an `sh:class`, e.g. `investigation:relevantAuthorization` on `Investigation` | Relationship, e.g. `Investigation` `RELEVANT_AUTHORIZATION` `Authorization` |
| `sh:in` with `sh:severity sh:Info`, e.g. `InvestigationFormVocab` for `investigationForm` | Suggested values in the description, and `extensions.custom.suggestedValues`; not `one_of` |
| Term IRI, e.g. `https://ontology.caseontology.org/case/investigation/Investigation` | `reference`, which resolves to the term's page in the CASE documentation |
| Object `@id` in CASE JSON-LD | A `uri` property on every node, and a `KEY` constraint over it |

### Where the ontology differs from CASE

- **It holds only part of UCO.** See [What the model contains](#what-the-model-contains).
- **Every node has a `uri` key,** **properties aren't inherited,** **open vocabularies aren't enforced** and **a
  `dateTime` is zoned**, as in [UCO](../UCO/README.md#where-the-ontology-differs-from-uco). The `sh:not` and
  `sh:sparql` shapes of the UCO classes in the model, on `Action` and `UcoThing`, aren't kept.
- **`ExaminerActionLifecycle` has its shape.** Its `sh:targetClass` is misspelt in CASE 1.5.0
  (`ExaminerActionLifecylce`), so a SHACL validator doesn't apply it to examiner action lifecycles. The class is its
  own node shape, so the ontology reads the shape from the class. It declares no properties of its own.

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json) and reports no issues for any of
the built-in validation sets, including `all`.
