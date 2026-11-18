# Legislation: ELI 1.4 and Akoma Ntoso 1.0

A crosswalk between [ELI 1.4](../../legal/ELI) and [Akoma Ntoso 1.0](../../legal/AkomaNtoso), two views of the same
act. ELI describes an act from the outside: the metadata a publisher puts online about it, its versions and formats,
and its links to other acts. Akoma Ntoso describes it from the inside: its text marked up down to articles and
paragraphs, with the people, organizations and concepts the text refers to. Both identify an act at the three levels
of FRBR, the work, its expressions and their manifestations, and they meet there.

## Mappings

| ELI | | Akoma Ntoso | Shared properties |
|---|---|---|---|
| LegalResource | close | FRBRWork | `number` = `frbrNumber`, `id_local` = `frbrUri` |
| LegalExpression | close | FRBRExpression | `id_local` = `frbrUri` |
| Format | close | FRBRManifestation | `id_local` = `frbrUri` |
| LegalResourceSubdivision | close | Hierarchy | |
| Organization | close | TLCOrganization | `uri` = `href` |
| Person | close | TLCPerson | `uri` = `href` |
| Concept | close | TLCConcept | `uri` = `href` |

Every mapping links data by `SAME_AS`, from the ELI node to the Akoma Ntoso node. Where they differ:

- **Identifiers.** ELI identifies each FRBR level by an IRI of its own. Akoma Ntoso identifies it by its FRBR URI,
  e.g. `/akn/zz/act/2024/7/eng@`. The crosswalk records the Akoma Ntoso FRBR URI as the ELI node's local identifier,
  `id_local`, which lets the checker test every link at all three levels.
- **Subdivisions.** ELI identifies an article as a legal resource of its own, part of the act. Akoma Ntoso marks it
  up as an element of the act's body. Their numbers are written differently ("5" and "5."), so they are linked but
  not compared.
- **Agents and concepts.** ELI identifies an organization, person or concept by its IRI. Akoma Ntoso refers to it
  through a TLC reference, local to one document, whose `href` points at that same IRI. ELI's `Concept` also covers
  authority-table values such as languages and resource types. Akoma Ntoso holds those as attribute values, e.g.
  `frbrLanguage`, not as references.
- **Amendments.** ELI records an amendment as an `AMENDS` relationship between two acts or two subdivisions. Akoma
  Ntoso records it as a modification element, e.g. a `TextualMod` with its source, destination and period, in the
  analysis of the amending act (active) and of the amended act (passive). The crosswalk maps only nodes to nodes, so
  this correspondence is in the data, not the mappings. The ELI `AMENDS` relationships in the sample match the
  Akoma Ntoso substitution of article 3.

The mappings are curated from the definitions in the two specifications, the
[ELI ontology](https://op.europa.eu/en/web/eu-vocabularies/eli) and the
[OASIS Akoma Ntoso specification](https://docs.oasis-open.org/legaldocml/akn-core/v1.0/os/part2-specs/akn-core-v1.0-os-part2-specs.html).
The same alignment is the subject of Avgerinos Loutsaris et al.,
[Semantic Interoperability for Legal Information: Mapping the European Legislation Identifier (ELI) and Akoma Ntoso (AKN) Ontologies](https://doi.org/10.1145/3614321.3614327)
(ICEGOV 2023). This crosswalk is not derived from that paper.

## Sample data

The [ELI sample](../../legal/ELI/sample.json) describes the GDPR and the
[Akoma Ntoso sample](../../legal/AkomaNtoso/sample.json) a fictional act of jurisdiction zz, so they share nothing.
[`sample.json`](sample.json) adds ELI metadata for the Akoma Ntoso acts:

- the Consumer Protection (Amendment) Act, 2024 and the Consumer Protection Act, 2012 it amends;
- each act's English expression and Akoma Ntoso XML format;
- article 5 of the amending act, and article 3 of the principal act that it substitutes;
- the National Assembly that passed the act and the National Council for Law Reporting that publishes it;
- the concept of consumer protection the act is about.

Each of these is linked to the Akoma Ntoso node describing the same thing, 11 links in all. The GDPR has no Akoma
Ntoso counterpart and is not linked. The ELI IRIs, under `https://example.org/eli/zz/`, are fictional, as is the
jurisdiction. The XML format type is the EU file-type authority's.

Once loaded, a query can move between the two views. For example, the acts an act amends, as ELI publishes them,
with the modifications its Akoma Ntoso markup records:

```cypher
MATCH (amending:eli__LegalResource)-[:eli__AMENDS]->(amended:eli__LegalResource)
MATCH (amending)-[:SAME_AS]->(:akn__FRBRWork)<-[:akn__HAS_FRBR_LEVEL]-(:akn__Identification)
      <-[:akn__HAS_IDENTIFICATION]-(meta:akn__Meta)
MATCH (meta)-[:akn__HAS_ANALYSIS]->()-[:akn__HAS_ACTIVE_MODIFICATIONS]->()-[:akn__HAS_MODIFICATION]->(mod)
RETURN amending.id_local, amended.id_local, mod.type
```

## Files

| File | Contents |
|---|---|
| `crosswalk.json` | The mappings, written by hand |
| `sample.json` | ELI metadata for the Akoma Ntoso sample's acts, and the links between the two |
| `model.json`, `model.yaml`, `model.svg`, `diagram.json` | The crosswalk as a graph spec model and its diagram |
| `mappings.sssom.tsv` | The mappings in [SSSOM](https://mapping-commons.github.io/sssom/) |
| `model.cypher` | Both standards' constraints and samples, prefixed `eli__` and `akn__`, the added ELI data and the links |
