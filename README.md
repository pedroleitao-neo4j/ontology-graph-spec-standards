# Standards

Ontologies for industry standards, each generated from the standard's official sources. Each spec uses [Neo4j's ontology graph specification](https://github.com/neo4j/ontology-graph-spec).

| Domain | Standard | Purpose and use | Nodes | Relationships | Generated from |
|---|---|---|---|---|---|
| Industrial | [CFIHOS 2.0](industrial/CFIHOS2.0) | The engineering data and documents contractors hand over to the owners of process and energy facilities | 139 | 252 | The CFIHOS V2.0 data dictionary |
| Industrial | [DEXPI 2.0.1](industrial/DEXPI) | Piping and instrumentation diagram (P&ID) data exchanged between engineering tools | 494 | 392 | The DEXPI Specification 2.0.1 model sources |
| Industrial | [ISO 23726-3 (IDO) / ISO 15926](industrial/ISO23726-3) | Top-level vocabulary for industrial plant asset models and reference data libraries | 50 | 68 | The IDO 4.2 FDIS Turtle file |
| Industrial | [Asset Administration Shell 3.2 (IEC 63278)](industrial/AAS) | Metamodel of the Industrie 4.0 digital twin, describing assets through submodels | 53 | 61 | The AAS metamodel 3.2 RDF ontology and SHACL shapes, with the JSON Schema's enumeration values |
| Industrial | [AutomationML Edition 2.1 (IEC 62714, CAEX 3.0)](industrial/AutomationML) | Plant engineering data exchanged between engineering tools, from object hierarchy and roles to attributes | 133 | 62 | The CAEX 3.0 XML schema and the AutomationML Edition 2.1 base and Part 2 role class libraries |
| Industrial | [IEC CIM (CGMES 3.0, IEC 61970-600)](industrial/CIM-CGMES) | Grid model exchange between European transmission system operators | 435 | 221 | The CGMES 3.0 RDFS vocabularies of ten IEC 61970-600 profiles |
| Industrial | [ISA-95 (IEC 62264, B2MML V0700)](industrial/ISA-95) | Information exchanged between business systems such as ERP and manufacturing operations systems such as MES | 157 | 640 | The B2MML V0700 XML schemas published by MESA International |
| Industrial | [IOF Core, Supply Chain and Maintenance (Release 202603)](industrial/IOF) | Manufacturing on top of BFO: agents and their roles, products, equipment and processes, the supply chain that moves them, and the failures and maintenance that follow | 261 | 477 | The IOF Release 202603 OWL files, with the BFO 2020 they import |
| Cybersecurity | [MITRE ATT&CK 20.1](cybersecurity/ATTACK) | Knowledge base of adversary tactics and techniques, with the groups, malware, mitigations and detections around them | 12 | 16 | The official Enterprise, Mobile and ICS STIX bundles |
| Cybersecurity | [MITRE D3FEND 1.6.0](cybersecurity/D3FEND) | Knowledge graph of defensive countermeasures and the digital artifacts they act on | 28 | 317 | The D3FEND Turtle file |
| Cybersecurity | [STIX 2.1](cybersecurity/STIX2.1) | Language for exchanging cyber threat intelligence | 43 | 216 | The OASIS STIX 2.1 JSON schemas and validator |
| Cybersecurity | [UCO 1.5.0](cybersecurity/UCO) | Foundation for the observables, actions and provenance of digital forensics and incident response | 420 | 228 | The UCO Turtle files and their SHACL shapes |
| Cybersecurity | [CASE 1.5.0](cybersecurity/CASE) | Investigation profile of UCO, recording investigations, authorisations and chain of custody | 18 | 12 | The CASE Turtle files, with the UCO classes they build on |
| Legal | [Akoma Ntoso 1.0 (OASIS LegalDocML)](legal/AkomaNtoso) | Parliamentary, legislative and judicial documents: their structure, FRBR identification, lifecycle and modifications, and the people, concepts and documents they refer to | 261 | 331 | The OASIS Akoma Ntoso Version 1.0 XML schema |
| Legal | [ELI 1.4 (European Legislation Identifier)](legal/ELI) | Identifiers and metadata for publishing legislation as linked data: acts and their versions and formats, and the amendments, repeals, transpositions and citations between them | 22 | 71 | The ELI 1.4 OWL file published by the Publications Office of the EU |
| Legal | [LKIF Core 1.1](legal/LKIF-Core) | Core legal ontology of norms, legal sources, rights and powers, legal persons, roles and acts, built on commonsense layers of expressions, actions, processes, time and place | 158 | 138 | The Turtle files of the twelve LKIF Core modules |
| Legal | [LegalRuleML 1.0 (OASIS)](legal/LegalRuleML) | Legal rules: obligations, permissions, prohibitions and rights, the defeasible strengths and overrides between them, and the sources, authorities, jurisdictions, actors and times they hold for | 84 | 64 | The twelve RDFS modules of the OASIS LegalRuleML Core Specification 1.0 |
| Legal | [ODRL 2.2 (W3C)](legal/ODRL) | Policies over digital content and services: permissions, prohibitions and duties granting actions over assets to parties, refined by constraints | 27 | 67 | The W3C ODRL 2.2 RDF vocabulary |
| Legal | [FIBO legal modules (EDM Council)](legal/FIBO-Legal) | Law, legal capacity, agreements and contracts, parties and legal persons, with the FIBO foundations and OMG Commons modules they import | 387 | 535 | The FIBO OWL modules FND/Law, FND/Agreements, FND/Parties and BE/LegalEntities and their import closure |

Each standard's folder has the same files:

| File | Contents |
|---|---|
| `model.yaml`, `model.json` | The ontology, as YAML and as JSON |
| `generate.py` | Generates both files from the standard's sources, using only the Python standard library |
| `diagram.json` | How the diagram colours cards and draws arrows |
| `model.svg` | A diagram of the ontology |
| `sample.json` | Sample data for a scenario in the standard's domain |
| `model.cypher` | A Cypher script creating the ontology's constraints and loading the sample data |
| `README.md` | The source, how the standard maps to the format, and where the ontology differs from the standard |

D3FEND and ATT&CK are modelled as knowledge graphs rather than class hierarchies. D3FEND's 4,400-odd classes become
nodes, labelled by the category they belong to, e.g. `DefensiveTechnique` or `DigitalArtifact`; ATT&CK's 5,600-odd
active objects become nodes, labelled `Technique`, `Group` or `DetectionStrategy` and so on. Every other standard maps
its classes or object types to labels. Each folder's README explains its mapping.

## Diagrams

[`visualise.py`](visualise.py) draws any ontology in the graph spec format as an SVG: one card per node, one arrow
per relationship and a dotted arrow for each implied label, laid out in layers. It checks that the `model.yaml` beside
a `model.json`, if there is one, describes the same model.

```bash
python3 visualise.py                          # redraws every model.json below this folder
python3 visualise.py industrial/DEXPI         # one folder
python3 visualise.py path/to/any/model.json   # any model, writing path/to/any/model.svg
```

A `diagram.json` beside the model sets what the diagram says it was generated from, which `extensions.custom` field
colours the cards and into which areas, what each card prints under its name, and whether arrows are drawn by their
counts or by a flag. Every key is optional; the format is described at the top of `visualise.py`. Without the file,
cards share one colour and arrows are drawn by the counts at their `from` end.

## Cypher scripts

[`cypher.py`](cypher.py) writes a `model.cypher` for each folder with a `sample.json`. The script creates the
ontology's constraints, i.e. a node key on each node's key properties and an existence constraint for each required
property, then merges the sample data. Each `sample.json` describes a realistic scenario in its standard's domain,
e.g. the GDPR and the acts around it for ELI, or a pump package handed over at a gas plant for CFIHOS. Before writing
the script, `cypher.py` checks the data against the ontology: its labels, the properties' names, types, allowed values
and patterns, the keys and required properties, the start and end of each relationship, and the counts at both ends.
The format of `sample.json` is described at the top of `cypher.py`.

```bash
python3 cypher.py                    # rewrites every model.cypher below this folder
python3 cypher.py industrial/DEXPI   # one folder
```

Run a script against an empty database of Neo4j 5 or later, e.g. with `cypher-shell -f model.cypher`. It needs
Enterprise Edition, for node key and property existence constraints. Every statement merges, so a script can be run
more than once. Each standard has its own labels and constraints, so load each one into a database of its own.
