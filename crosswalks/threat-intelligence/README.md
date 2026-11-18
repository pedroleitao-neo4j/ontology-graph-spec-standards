# Threat intelligence: STIX 2.1, MITRE ATT&CK 20.1 and MITRE D3FEND 1.6.0

A crosswalk between [STIX 2.1](../../cybersecurity/STIX2.1), [MITRE ATT&CK](../../cybersecurity/ATTACK) and
[MITRE D3FEND](../../cybersecurity/D3FEND). Each answers a different question about an attack:

- STIX: what an analyst saw and shared.
- ATT&CK: which known adversary behaviour it was.
- D3FEND: which defences act on that behaviour and on the artifacts it leaves.

The standards already cite each other. ATT&CK is published as STIX, and D3FEND imports ATT&CK's techniques, so most
of the joins are identities with published identifiers behind them.

## Mappings

| From | | To | Shared properties |
|---|---|---|---|
| STIX AttackPattern | narrower | ATT&CK Technique | `id` = `stixId`, `name` |
| STIX IntrusionSet | narrower | ATT&CK Group | `id` = `stixId`, `name` |
| STIX Campaign | narrower | ATT&CK Campaign | `id` = `stixId`, `name` |
| STIX Malware | narrower | ATT&CK Malware | `id` = `stixId`, `name` |
| STIX Tool | narrower | ATT&CK Tool | `id` = `stixId`, `name` |
| STIX CourseOfAction | narrower | ATT&CK Mitigation | `id` = `stixId`, `name` |
| ATT&CK Technique | close | D3FEND OffensiveTechnique, ATTACKICSTechnique, ATTACKMobileTechnique | `attackId`, `name` |
| ATT&CK Tactic | close | D3FEND OffensiveTactic | `name` |
| ATT&CK Mitigation | narrower | D3FEND ATTACKEnterpriseMitigation | `name` |
| STIX File | related | D3FEND File | |
| STIX EmailMessage, Url | related | D3FEND DigitalArtifact | |
| STIX Process | related | D3FEND Process | |
| STIX NetworkTraffic | related | D3FEND NetworkTraffic | |

The identity mappings link data by `SAME_AS`; the related ones by `INSTANCE_OF`. Where they differ:

- **STIX and ATT&CK.** ATT&CK publishes its techniques as STIX `attack-pattern` objects, its groups as
  `intrusion-set`, its software as `malware` or `tool`, its mitigations as `course-of-action` and its campaigns as
  `campaign`, all keeping their STIX ids. This is documented in the
  [ATT&CK data model](https://mitre-attack.github.io/attack-data-model/schemas/), and the STIX id is the join. The
  STIX types are broader, since a bundle's attack patterns and courses of action needn't come from ATT&CK: Quiet
  Invoice's "Block LEDGERFALL command and control" is a course of action but not an ATT&CK mitigation. ATT&CK's
  tactics, detection strategies, analytics and data components are custom `x-mitre-` objects with no STIX core
  counterpart, so they are not mapped.
- **ATT&CK and D3FEND.** D3FEND imports ATT&CK's Enterprise tactics, techniques and mitigations as classes of its
  own, named by their ATT&CK ids, e.g.
  [T1566.001](https://d3fend.mitre.org/offensive-technique/attack/T1566.001/). For techniques the ATT&CK id is a
  property in both, which makes it the join. For tactics and mitigations the id is only in the D3FEND IRI, so the
  name joins them. D3FEND also has offensive technique classes of its own that group techniques by tactic, such as
  Initial Access Technique, and those have no ATT&CK counterpart.
- **STIX observables and D3FEND artifacts.** These are not the same thing. D3FEND's nodes are classes, the kinds of
  digital artifact that offensive techniques produce and defensive techniques analyse, filter or block. A STIX
  observable is one file, email or process that was actually seen. The link says that the observable is an instance
  of the class, `INSTANCE_OF`, so the defences D3FEND relates to the class apply to it.

## Sample data

[`sample.json`](sample.json) joins the [STIX](../../cybersecurity/STIX2.1/sample.json),
[ATT&CK](../../cybersecurity/ATTACK/sample.json) and [D3FEND](../../cybersecurity/D3FEND/sample.json) samples
around the STIX bundle's fictional phishing campaign, Operation Quiet Invoice. The links are:

- **Shared objects.** The bundle's attack patterns, Spearphishing Attachment, Malicious File, Web Protocols and
  Exfiltration to Cloud Storage, and its Rclone tool, are ATT&CK's own objects, linked by their STIX ids.
- **Added ATT&CK objects.** The ATT&CK sample, built around APT29, lacks most of them. They are added from the
  ATT&CK Enterprise 20.1 bundle with their parent techniques, their tactics Execution and Exfiltration, and the
  mitigations Restrict Web-Based Content and Execution Prevention, along with the real relationships between them.
- **ATT&CK to D3FEND.** The phishing and user-execution techniques, the Initial Access and Execution tactics and the
  two mitigations are linked to their D3FEND classes.
- **Observables.** The email, its macro-enabled spreadsheet, the DLL loader, the C2 URL, the Excel and rundll32
  processes and the C2 traffic are linked to the D3FEND artifact classes they are instances of.

The bundle's threat actor, intrusion set, campaign and malware are fictional, so they have no ATT&CK counterpart to
link to.

Once loaded, a query can walk from a report to its defences. For example, the D3FEND techniques that act on the
artifacts each reported technique produces or executes:

```cypher
MATCH (:stix__Report)-[:stix__OBJECT_REFS]->(p:stix__AttackPattern)-[:SAME_AS]->(t:attack__Technique)
      -[:SAME_AS]->(:d3fend__OffensiveTechnique)-[:d3fend__PRODUCES|d3fend__EXECUTES]->(a:d3fend__DigitalArtifact)
MATCH (a)-[:d3fend__SUBCLASS_OF*0..]->(:d3fend__DigitalArtifact)<-[:d3fend__ANALYZES|d3fend__FILTERS|d3fend__BLOCKS]-(d:d3fend__DefensiveTechnique)
RETURN t.attackId, t.name, a.name AS artifact, collect(DISTINCT d.name) AS defences
```

Or, from what was observed on the victim's network:

```cypher
MATCH (o)-[:INSTANCE_OF]->(a:d3fend__DigitalArtifact)
OPTIONAL MATCH (a)-[:d3fend__SUBCLASS_OF*0..]->(:d3fend__DigitalArtifact)<-[:d3fend__ANALYZES|d3fend__FILTERS|d3fend__BLOCKS]-(d:d3fend__DefensiveTechnique)
RETURN o.id, a.name AS artifact, collect(DISTINCT d.name) AS defences
```

## Files

| File | Contents |
|---|---|
| `crosswalk.json` | The mappings, written by hand |
| `sample.json` | The ATT&CK objects the samples lack, and the links between the three standards' sample data |
| `model.json`, `model.yaml`, `model.svg`, `diagram.json` | The crosswalk as a graph spec model and its diagram |
| `mappings.sssom.tsv` | The mappings in [SSSOM](https://mapping-commons.github.io/sssom/) |
| `model.cypher` | The three standards' constraints and samples, prefixed `stix__`, `attack__` and `d3fend__`, and the links |
