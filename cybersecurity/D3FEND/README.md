# MITRE D3FEND 1.6.0

An ontology for [MITRE D3FEND](https://d3fend.mitre.org/), a knowledge graph of cybersecurity countermeasures funded
by the NSA Cybersecurity Directorate and managed by MITRE. D3FEND relates the defensive techniques that counter cyber
attacks, and the tactics they serve, to the digital artifacts they act on. It also relates those artifacts to the
offensive techniques of MITRE ATT&CK, ATLAS and SPARTA that use them, and maps everything to CWE weaknesses, NIST SP
800-53 and DISA CCI controls, ATT&CK mitigations and the references that ground it.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the official D3FEND Turtle file |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`sample.json`](sample.json) | Sample data: phishing techniques and the defences against them |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |
| [`../../cypher.py`](../../cypher.py) | Generates the Cypher script (shared by every standard) from `model.json` and `sample.json` |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |

## Source

The model is generated from D3FEND 1.6.0, released on 31 August 2026, as published by MITRE in
[`d3fend.ttl`](https://d3fend.mitre.org/ontologies/d3fend/1.6.0/d3fend.ttl). See the
[D3FEND ontology repository](https://github.com/d3fend/d3fend-ontology). `generate.py` includes a small Turtle
reader, so it doesn't need an RDF library. To regenerate:

```bash
python3 generate.py                     # downloads D3FEND 1.6.0 from MITRE
python3 generate.py path/to/d3fend.ttl
```

The script reads the version from the file, so it also works on a later release, e.g. from
`https://d3fend.mitre.org/ontologies/d3fend.ttl`, which always serves the latest. The script needs only the Python
standard library.

## The knowledge graph, not the class hierarchy

D3FEND is written in OWL, but its classes aren't a schema. They're the content of its knowledge graph: *File
Hashing* is a defensive technique, *File* a digital artifact and *T1003 OS Credential Dumping* an ATT&CK technique.
D3FEND declares every one of its 4,467 classes as an individual too (OWL punning) and links them directly, e.g. *File
Hash Reputation Analysis* `analyzes` *File Hash*. One node type per class would give a schema of thousands of
labels, nearly all with no properties of their own and many with a single instance.

So the ontology describes the graph that holds the knowledge base. Each D3FEND class is a **node**, labelled by the
**category** it falls in, e.g. `DefensiveTechnique` or `DigitalArtifact`, and by `D3FENDClass`. Each D3FEND
relation is a **relationship** between the categories whose members it links. The class hierarchy becomes
`SUBCLASS_OF` relationships between the nodes. Loaded this way, a question like "which defensive techniques analyze
an artifact that an ATT&CK technique modifies" is a graph query:

```cypher
MATCH (d:DefensiveTechnique)-[:ANALYZES]->(a:DigitalArtifact)<-[:MODIFIES]-(o:OffensiveTechnique)
RETURN d.name, a.name, o.attackId
```

The categories are D3FEND classes near the top of its hierarchy. The nodes in a category are that class and every
class below it:

| Category | D3FEND class | Nodes |
|---|---|---|
| `DefensiveTactic`, `DefensiveTechnique` | The D3FEND matrix: *Model*, *Harden*, *Detect*, *Isolate*, *Deceive*, *Evict*, *Restore* and their techniques | 8, 273 |
| `AnalyticTechnique`, `AnalyticalPurpose` | The machine learning, statistical and symbolic methods behind the techniques, and what they're for | 227, 16 |
| `OffensiveTactic`, `OffensiveTechnique` | Tactics of every threat model, and ATT&CK Enterprise techniques, which D3FEND classes as offensive techniques | 65, 875 |
| `ATTACKICSTechnique`, `ATTACKMobileTechnique`, `ATLASTechnique`, `SPARTATechnique` | Techniques of ATT&CK ICS and Mobile, ATLAS and SPARTA, which D3FEND doesn't class as offensive techniques | 131, 179, 190, 236 |
| `Weakness` | CWE weaknesses | 944 |
| `Artifact`, `DigitalArtifact`, `PhysicalArtifact` | What techniques act on | 922, 904, 75 |
| `File`, `Software`, `Process`, `NetworkTraffic`, `NetworkNode` | The main kinds of digital artifact. A finer label each, which also implies `DigitalArtifact` | 64, 238, 26, 38, 63 |
| `Event`, `Agent`, `Sensor` | Digital events and actions, the agents that take part in them, and sensors | 317, 22, 17 |
| `D3FENDClass` | Every class, including those in no category, e.g. *Vulnerability* | 4,446 |

D3FEND's references, controls and mappings are individuals, not classes. They're nodes as well, labelled by the class
their class falls under, and their own class is kept in `kind`, e.g. a `TechniqueReference` of kind
`PatentReference`:

| Category | Individuals of | Nodes |
|---|---|---|
| `TechniqueReference` | Patents, articles, specifications and other references a technique's knowledge base article cites | 397 |
| `ExternalControl` | NIST SP 800-53 and DISA CCI controls | 416 |
| `ControlCatalog` | The catalogs those controls belong to | 4 |
| `ATTACKEnterpriseMitigation`, `ATTACKEnterpriseDataSource` | ATT&CK mitigations and data sources | 42, 41 |

## Diagram

[`model.svg`](model.svg) draws each node type as a card and each relationship as an arrow from subject to object. A
solid arrow is a definite relation, e.g. `ANALYZES`. A dashed arrow is a possible one, which D3FEND names `may-…`,
e.g. `MAY_MODIFY`. Arrows are named by their relationship type wherever the name fits without overlapping a card or
another name, definite relations first. Dotted arrows point from a label to the label it implies, e.g. from `File` to
`DigitalArtifact`.

Cards are coloured by area, and print whether the label holds classes or individuals, how many, and its number of
properties:

- Defensive: tactics, techniques and the analytic techniques behind them
- Offensive: ATT&CK, ATLAS and SPARTA tactics and techniques, and CWE weaknesses
- Core: `D3FENDClass`, artifacts, events, agents and sensors
- Knowledge base: references, controls, catalogs, mitigations and data sources

With 317 relationships among 28 node types, the diagram is dense. Opened in a browser, hovering a card or arrow shows
its name and description, and each card links to its D3FEND term. To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

[`sample.json`](sample.json) holds a slice of the D3FEND 1.6.0 knowledge graph around phishing. It has the ATT&CK
techniques Spearphishing Attachment (T1566.001) and Spearphishing Link (T1566.002) and the User Execution sub-techniques
that follow them, with their parents and tactics; the artifacts they produce, access or execute, e.g. *Email*, *URL* and
*Executable File*; and the defensive techniques that analyse, filter or block those artifacts, e.g. *Sender Reputation
Analysis* (D3-SRA), *Homoglyph Detection* (D3-HD), *Email Filtering* (D3-EF), *Dynamic Analysis* (D3-DA) and
*Executable Allowlisting* (D3-EAL), with the classes and tactics above them. Each defensive technique has a reference
from its knowledge base article; the ATT&CK mitigations D3FEND relates to them and the NIST SP 800-53 controls mapped to
*Dynamic Analysis* are there too: 50 nodes and 71 relationships. Every class, individual and link comes from D3FEND
1.6.0; only definitions are cut to their first sentence.

To regenerate `model.cypher` after editing `sample.json`, which checks the data against the model first:

```bash
python3 ../../cypher.py .   # from this folder; or ../../cypher.py alone for every standard with sample data
```

The script needs Neo4j 5 or later, Enterprise Edition, for its node key constraints. Run it against an empty database,
e.g. with `cypher-shell -f model.cypher`. It merges every node and relationship, so it can be run again.

## Mapping

| D3FEND (OWL) | Ontology |
|---|---|
| Class, e.g. `d3f:FileHashing` | Node, labelled `D3FENDClass` and by its category, e.g. `DefensiveTechnique` |
| Individual of a reference, control or mapping class, e.g. `d3f:Reference-Munin` | Node, labelled by its category, e.g. `TechniqueReference`, with its class in `kind` |
| Category class, e.g. `d3f:DefensiveTechnique` | Node type; a class or individual below it is a node with that label |
| `rdfs:subClassOf` a named class | `SUBCLASS_OF` relationship from the class to its superclass |
| Object property, e.g. `d3f:analyzes` | Relationship typed in upper snake case, e.g. `ANALYZES`, from each category of subject to each category of object it links |
| Asserted link, e.g. `d3f:FileHashReputationAnalysis d3f:analyzes d3f:FileHash` | One link of that relationship |
| `owl:someValuesFrom` or `owl:allValuesFrom` restriction, including on a union | One link of that relationship to each named class |
| Restriction on the root class of a category of individuals, e.g. `ControlCatalog` ⊑ `has-member some ExternalControl` | `min_count: 1` at that end, where every individual has such a link |
| Pair of inverse properties, e.g. `kb-reference` / `kb-reference-of` | One relationship, in the direction D3FEND asserts more often; links asserted the other way are turned around |
| `may-…` property, e.g. `may-modify` | `extensions.custom.definite: false` |
| `rdfs:label`, `d3f:definition`, `d3f:kb-article` | `name`, `definition`, `kbArticle` |
| `d3f:d3fend-id`, `d3f:attack-id`, `d3f:cwe-id`, `d3f:capec-id` | `d3fendId`, `attackId`, `cweId`, `capecId` |
| `d3f:synonym`, `skos:altLabel`, `skos:prefLabel`, `rdfs:comment`, `rdfs:seeAlso`, `rdfs:isDefinedBy`, `owl:deprecated` | `synonyms`, `altLabels`, `prefLabel`, `comment`, `seeAlso`, `isDefinedBy`, `deprecated` |
| Reference annotations: `d3f:kb-reference-title`, `kb-abstract`, `kb-author`, `kb-organization`, `kb-mitre-analysis`, `has-link` | `title`, `abstract`, `authors`, `organization`, `mitreAnalysis`, `link` |
| Control annotations: `d3f:control-name`, `contributor`, `published`, `version`, `archived-at` | `controlName`, `contributor`, `published`, `version`, `archivedAt` |
| Class or individual IRI | A `uri` property on every node, and a `KEY` constraint over it |

A property is defined on the category whose nodes carry it in D3FEND, e.g. `cweId` on `Weakness`. Where the nodes of
several class categories carry it, e.g. `d3fendId` on both tactics and techniques, it's defined on `D3FENDClass`.
Offensive tactics, techniques, mitigations and data sources also have a `framework`, e.g. `ATT&CK ICS`, from the
D3FEND class they fall under.

Each relationship records, in `extensions.custom`, its D3FEND IRI and the number of pairs it links in D3FEND 1.6.0.
It also records how many come from assertions and how many from restrictions, and its inverse, superproperties and
whether it's transitive or symmetric. Its description gives the relation's definition, three of its links, e.g.
*Certificate Analysis analyzes Certificate File*, and its inverse. Nodes record their area, whether they hold classes
or individuals, and how many D3FEND 1.6.0 has.

### Where the ontology differs from D3FEND

- **Classes are nodes, not labels.** See [above](#the-knowledge-graph-not-the-class-hierarchy). A class's place in
  the hierarchy is a `SUBCLASS_OF` relationship. `SUBCLASS_OF` was chosen over SKOS's `BROADER` because D3FEND has
  its own `broader` relation, which maps controls to techniques.
- **Relations aren't inherited.** In OWL, a restriction on *File Analysis* also holds for *File Hashing* below it.
  In the graph, it's a link from the *File Analysis* node only, and *File Hashing* reaches it through `SUBCLASS_OF`,
  e.g. `(:DefensiveTechnique {name: 'File Hashing'})-[:SUBCLASS_OF*0..]->()-[:ENABLES]->(t:DefensiveTactic)`. A loader
  can copy the links down the hierarchy if it needs them on every class.
- **Restrictions on categories of classes aren't required counts.** D3FEND states that every defensive technique
  `enables` some tactic, but only the top-level techniques have that link. Their subclasses share it through
  `SUBCLASS_OF`. So `ENABLES` has no `min_count`, and its description says what D3FEND states. Restrictions on the
  classes of references, controls and catalogs are counts where the data meets them, e.g. every `ExternalControl` is
  a member of some `ControlCatalog`. Where it doesn't, the node's description says so: D3FEND states that every
  reference is a `kb-reference-of` some defensive technique, but 4 aren't.
- **One relationship per inverse pair.** D3FEND asserts both `kb-reference` and `kb-reference-of`, and both
  `has-member` and `member-of`. The ontology keeps the direction asserted more often and records the other as
  `extensions.custom.inverseOf`.
- **Relationships connect categories.** A relation from a class in no category, e.g. *Physical Location*, attaches
  to `D3FENDClass`. A class in two categories, e.g. *Hardware Device*, which is both a digital and a physical
  artifact, contributes to the relationships of both.
- **A finer artifact label doesn't get its own relationships.** `File`, `Software`, `Process`, `NetworkTraffic` and
  `NetworkNode` imply `DigitalArtifact`, and the relationships attach to `DigitalArtifact`. That keeps the number of
  relationships manageable, and a `File` node still matches `(:DigitalArtifact)`.
- **Single values stay single.** `name`, `definition`, `kbArticle` and `prefLabel` are strings. Where D3FEND gives a
  class more than one, e.g. two labels for 4 CWE weaknesses, a loader keeps the first, and the property's
  description says how many do.
- **Example individuals are left out.** D3FEND has 52 individuals of artifact classes, e.g. *AMD64 Code Segment* or
  *Adobe PDF File 1.3*. They're illustrations, not knowledge base content, so they aren't nodes, nor are the 6 links
  that involve them.
- **Annotation-only metadata isn't kept.** D3FEND's ontology-level annotations, such as its license, and its display
  base URLs aren't properties.

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json) and reports no issues for any of
the built-in validation sets, including `all`.
