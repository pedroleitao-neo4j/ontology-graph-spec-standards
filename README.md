# Standards

A library of ontologies for industry standards, each generated from the standard's official sources and expressed in
[Neo4j's ontology graph specification](https://github.com/neo4j/ontology-graph-spec). Every standard defines how an industry exchanges data - how a piping diagram moves between engineering tools, how threat intelligence is shared between organisations, how legislation is published and cited. That definition lives in schemas, OWL files and XML specifications that don't fit a graph, so each ontology here translates one standard's model into nodes and relationships you can query and extend. Businesses already hold data in these standards and in domain-specific ontologies; the aim of this library is to ease the transition of that data into Neo4j.

The standards come from organisations including:

<p>
  <a href="https://www.iso.org" title="ISO"><img src="https://upload.wikimedia.org/wikipedia/commons/e/e3/ISO_Logo_%28Red_square%29.svg" alt="ISO" height="40"></a>&nbsp;
  <a href="https://www.iec.ch" title="IEC"><img src="https://upload.wikimedia.org/wikipedia/commons/3/3e/International_Electrotechnical_Commission_Logo.svg" alt="IEC" height="40"></a>&nbsp;
  <a href="https://dexpi.org" title="DEXPI"><img src="https://github.com/DEXPI.png?size=80" alt="DEXPI" height="40"></a>&nbsp;
  <a href="https://industrialdigitaltwin.org" title="Industrial Digital Twin Association"><img src="https://github.com/admin-shell-io.png?size=80" alt="IDTA" height="40"></a>&nbsp;
  <a href="https://www.automationml.org" title="AutomationML e.V."><img src="https://github.com/AutomationML.png?size=80" alt="AutomationML" height="40"></a>&nbsp;
  <a href="https://www.entsoe.eu" title="ENTSO-E"><img src="https://github.com/entsoe.png?size=80" alt="ENTSO-E" height="40"></a>&nbsp;
  <a href="https://www.industrialontologies.org" title="Industrial Ontologies Foundry"><img src="https://github.com/iofoundry.png?size=80" alt="IOF" height="40"></a>&nbsp;
  <a href="https://www.mitre.org" title="MITRE"><img src="https://github.com/mitre.png?size=80" alt="MITRE" height="40"></a>&nbsp;
  <a href="https://www.oasis-open.org" title="OASIS Open"><img src="https://github.com/oasis-open.png?size=80" alt="OASIS" height="40"></a>&nbsp;
  <a href="https://cyberdomainontology.org" title="Cyber Domain Ontology, a Linux Foundation project"><img src="https://github.com/linuxfoundation.png?size=80" alt="Linux Foundation" height="40"></a>&nbsp;
  <a href="https://caseontology.org" title="CASE Community"><img src="https://github.com/casework.png?size=80" alt="CASE" height="40"></a>&nbsp;
  <a href="https://op.europa.eu" title="Publications Office of the European Union"><img src="https://upload.wikimedia.org/wikipedia/commons/b/b7/Flag_of_Europe.svg" alt="European Union" height="40"></a>&nbsp;
  <a href="https://www.w3.org" title="W3C"><img src="https://github.com/w3c.png?size=80" alt="W3C" height="40"></a>&nbsp;
  <a href="https://edmcouncil.org" title="EDM Council"><img src="https://github.com/edmcouncil.png?size=80" alt="EDM Council" height="40"></a>
</p>

## Structure

The standards are grouped by domain:

| Folder | Domain |
|---|---|
| [`industrial/`](industrial) | Engineering data and manufacturing: how plant designs, digital twins, grid models and production data are exchanged between tools and organisations |
| [`cybersecurity/`](cybersecurity) | Threat intelligence and digital forensics: how adversary techniques, defences and investigations are described and shared |
| [`legal/`](legal) | Legislation and legal rules: how acts are published, identified and linked, and how obligations, permissions and prohibitions are expressed |
| [`foundational/`](foundational) | Foundational and mid-level ontologies that standards in the other domains build on |

| Domain | Standard | Purpose and use | Nodes | Relationships | Generated from |
|---|---|---|---|---|---|
| Industrial | [CFIHOS 2.0](industrial/CFIHOS2.0) | The engineering data and documents contractors hand over to the owners of process and energy facilities | 139 | 252 | The CFIHOS V2.0 data dictionary |
| Industrial | [DEXPI 2.0.1](industrial/DEXPI) | Piping and instrumentation diagram (P&ID) data exchanged between engineering tools | 494 | 392 | The DEXPI Specification 2.0.1 model sources |
| Industrial | [ISO 23726-3 (IDO) / ISO 15926](industrial/ISO23726-3) | Top-level vocabulary for industrial plant asset models and reference data libraries | 50 | 68 | The IDO 4.2 FDIS Turtle file |
| Industrial | [Asset Administration Shell 3.2 (IEC 63278)](industrial/AAS) | Metamodel of the Industrie 4.0 digital twin, describing assets through submodels | 53 | 61 | The AAS metamodel 3.2 RDF ontology and SHACL shapes, with the JSON Schema's enumeration values |
| Industrial | [AutomationML Edition 2.1 (IEC 62714, CAEX 3.0)](industrial/AutomationML) | Plant engineering data exchanged between engineering tools, from object hierarchy and roles to attributes | 133 | 62 | The CAEX 3.0 XML schema and the AutomationML Edition 2.1 base and Part 2 role class libraries |
| Industrial | [IEC CIM (CGMES 3.0, IEC 61970-600)](industrial/CIM-CGMES) | Grid model exchange between European transmission system operators | 435 | 221 | The CGMES 3.0 RDFS vocabularies of ten IEC 61970-600 profiles |
| Industrial | [ISA-95 (IEC 62264, B2MML V0700)](industrial/ISA-95) | Information exchanged between business systems such as ERP and manufacturing operations systems such as MES | 157 | 640 | The B2MML V0700 XML schemas published by MESA International |
| Industrial | [IOF Core, Supply Chain, Maintenance, Certification and Production Planning (Release 202603)](industrial/IOF) | Manufacturing on top of BFO: agents and their roles, products, equipment and processes, the plans that schedule production, the supply chain that moves products, their certification, and the failures and maintenance that follow | 289 | 505 | The IOF Release 202603 OWL files, with the BFO 2020 they import |
| Industrial | [IOF Biopharma (Release 202603)](industrial/IOF-Biopharma) | Biopharmaceutical manufacturing on top of IOF Core and BFO: culture media, cells and molecular entities, bioreactors and chromatography, ISA-88 recipes and the ISA-95 equipment hierarchy, upstream and downstream processes, and the parameters, limits and monitoring that control them | 676 | 736 | The thirteen production Biopharma modules of the IOF Release 202603 OWL files, with the IOF Core, Supply Chain, Certification and BFO 2020 classes they need |
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
| Foundational | [Common Core Ontologies 2.2 (CCO)](foundational/CCO) | Mid-level ontology on top of BFO of the classes common to data in many domains: agents and organizations, acts and events, time, artifacts and facilities, information, qualities, units of measure and places | 1437 | 311 | The eleven CCO v2.2 Turtle modules, with the BFO 2020 they import |

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

## Crosswalks

The standards overlap: a CFIHOS tag is a tagged plant item on a DEXPI P&ID, an ATT&CK technique is a STIX attack
pattern, an ODRL duty is an obligation in LegalRuleML. A crosswalk in [`crosswalks/`](crosswalks) maps the nodes of
two or more standards to each other, and links their sample data into one graph.

| Crosswalk | Standards | Mappings | Links |
|---|---|---|---|
| [Plant engineering](crosswalks/plant-engineering) | CFIHOS 2.0, DEXPI 2.0.1 | 7 | 7 |
| [Digital twin](crosswalks/digital-twin) | Asset Administration Shell 3.2, AutomationML 2.1 | 13 | 9 |
| [Threat intelligence](crosswalks/threat-intelligence) | STIX 2.1, MITRE ATT&CK 20.1, MITRE D3FEND 1.6.0 | 16 | 21 |
| [Legislation](crosswalks/legislation) | ELI 1.4, Akoma Ntoso 1.0 | 7 | 11 |
| [Legal norms](crosswalks/legal-norms) | ODRL 2.2, LegalRuleML 1.0, LKIF Core 1.1 | 20 | 26 |

Each crosswalk's folder holds:

| File | Contents |
|---|---|
| `crosswalk.json` | The mappings, written by hand: each maps a node of one standard to a node of another, as SKOS does (exact, close, broad, narrow or related match), names the properties they share, and says why and where they differ |
| `sample.json` | The links between the standards' sample data, and any nodes the crosswalk adds so that the samples describe the same things |
| `model.json`, `model.yaml`, `model.svg`, `diagram.json` | The crosswalk as a graph spec model: the nodes it maps, and a relationship for each mapping, e.g. `SAME_AS` |
| `mappings.sssom.tsv` | The mappings in the [Simple Standard for Sharing Ontological Mappings](https://mapping-commons.github.io/sssom/) |
| `model.cypher` | A script loading every standard's constraints and sample data, and the links between them, into one database |
| `README.md` | What the crosswalk maps, where the standards differ, and queries across them |

Standards share many labels and relationship types with keys and meanings of their own. In a crosswalk, each
standard's labels and relationship types are therefore prefixed, as [neosemantics](https://neo4j.com/labs/neosemantics/)
does: `cfihos__Tag`, `stix__USES`. The links between standards are not prefixed. [`crosswalk.py`](crosswalk.py)
checks that every mapping names real nodes and properties. It checks the combined data the way `cypher.py` checks a
standard's own, and checks that linked nodes agree on the properties their mapping says they share. It then writes
the generated files. Its format is described at the top of the script.

```bash
python3 crosswalk.py                                 # rebuilds every crosswalk
python3 crosswalk.py crosswalks/plant-engineering    # one
python3 visualise.py crosswalks/plant-engineering    # redraws its diagram
```

### Loading the crosswalks into Neo4j

The data to load is each crosswalk's `model.cypher`, which `crosswalk.py` generates. Each script holds the
constraints and sample data of every standard in the crosswalk, and the links between them. The crosswalks share no
standard, and so no label, so all five can go into one database.

[`app/load.py`](app/load.py) loads them. It reads the connection from a `.env` file at the root of the repository,
with the variables of the credentials file Aura gives you. [`.env.example`](.env.example) shows them:

```bash
cp .env.example .env                                  # then fill in NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD
python3 -m venv .venv && .venv/bin/pip install -r app/requirements.txt
.venv/bin/python app/load.py                          # loads every crosswalk
.venv/bin/python app/load.py plant-engineering        # or some, by the name of their folder
```

The loader creates each script's constraints one by one, then sends its data in batches, so a remote database such as
Aura takes a few minutes rather than thousands of round trips. Where the database refuses a constraint, as Community
Edition refuses node keys and existence constraints, it creates a node key as a uniqueness constraint and leaves the
others out, and says which. Every statement merges, so loading again changes nothing. `--reset` deletes every node
and constraint in the database first, so use it only on a database that holds nothing else.

A script also runs on its own against an empty database of Neo4j 5 or later, Enterprise Edition, e.g. with
`cypher-shell -f crosswalks/plant-engineering/model.cypher`. Once loaded, the links join the standards. For
example, every DEXPI pump with its CFIHOS handover status:

```cypher
MATCH (tag:cfihos__Tag)-[:SAME_AS]->(pump:dexpi__CentrifugalPump)
RETURN pump.tagName, pump.designVolumeFlowRate, tag.tagStatus
```

### The crosswalk explorer

The [crosswalk explorer](app) is a web app for browsing the crosswalks once they're loaded. It shows a crosswalk's
data as one graph, with a band per standard. It also shows each linked thing as every standard describes it, side
by side, and lists the mappings. It uses the same `.env` and virtual environment as the loader:

```bash
.venv/bin/python app/server.py                        # serves the explorer at http://localhost:8000
```

The [app's README](app) describes its views.

## Adding a standard

Each folder follows the same pattern, and a new one should too:

- the files in the table above, all of them, with `generate.py` building `model.yaml` and `model.json` from the
  standard's official sources, using only the Python standard library;
- a README recording where the sources came from, how the standard maps to the graph spec format, and where the
  ontology differs from the standard;
- sample data describing a realistic scenario in the standard's domain, checked by `cypher.py` against the model
  before it is loaded;
- a model that validates against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json)
  of the graph spec and, ideally, reports no issues for the spec libraries' `All` validator set, and a diagram drawn
  by `visualise.py`.

## Diagrams

[`visualise.py`](visualise.py) draws any ontology in the graph spec format as an SVG. One card per node, one arrow
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
ontology's constraints, that is a node key on each node's key properties and an existence constraint for each required
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
more than once. Each standard has its own labels and constraints, so load each one into a database of its own. To load several
together, use the `model.cypher` of a [crosswalk](#crosswalks), which prefixes them.
