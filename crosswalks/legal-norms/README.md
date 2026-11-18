# Legal norms: ODRL 2.2, LegalRuleML 1.0 and LKIF Core 1.1

A crosswalk between [ODRL 2.2](../../legal/ODRL), [LegalRuleML 1.0](../../legal/LegalRuleML) and
[LKIF Core 1.1](../../legal/LKIF-Core), three ways of writing down what may, must and must not be done:

- **ODRL** is a policy language: Permissions, Prohibitions and Duties grant an Action over an Asset to a Party.
- **LegalRuleML** marks up the rules in legal texts: deontic specifications borne by parties, held in statements
  with their strength, sources, authorities and penalties.
- **LKIF Core** is a legal ontology: norms borne by legal sources qualify behaviour as allowed, obliged or
  disallowed, and are held by agents playing legal roles.

All three have the deontic triad of permission, obligation and prohibition, and agents who bear it. They differ in
what a norm is: a rule over an asset, a formula in a statement, or a qualification of behaviour.

## Mappings

| Subject | | Object | Shared properties |
|---|---|---|---|
| ODRL Permission | close | LegalRuleML Permission | `uri` |
| ODRL Prohibition | close | LegalRuleML Prohibition | `uri` |
| ODRL Duty | close | LegalRuleML Obligation | `uri` |
| ODRL Duty | related | LegalRuleML PenaltyStatement | |
| ODRL Permission | broader | LKIF Permission | `uri` |
| ODRL Prohibition | close | LKIF Prohibition | `uri` |
| ODRL Duty | close | LKIF Obligation | `uri` |
| LegalRuleML Permission | broader | LKIF Permission | `uri` |
| LegalRuleML Prohibition | close | LKIF Prohibition | `uri` |
| LegalRuleML Obligation | close | LKIF Obligation | `uri` |
| LegalRuleML Right | close | LKIF Right | |
| ODRL Party | close | LegalRuleML Agent | `uri` |
| ODRL Party | close | LKIF Agent | `uri` |
| LegalRuleML Agent | close | LKIF Agent | `uri` |
| LegalRuleML Authority | narrower | LKIF LegislativeBody | |
| LegalRuleML Figure | close | LKIF LegalRole | `uri` |
| LegalRuleML LegalSource | close | LKIF LegalSource | `uri` |
| ODRL Asset | related | LKIF PhysicalObject | `uri` |
| ODRL Agreement | related | LKIF Contract | |
| ODRL Action | related | LKIF Action | |

Data is linked by `SAME_AS` from the subject to the object, but for three related matches, which link by
`RELATED_TO`: Duty and PenaltyStatement, Agreement and Contract, and the two Actions. ODRL Asset and LKIF
PhysicalObject link by `SAME_AS`: the classes only overlap, but a rented dwelling is the same thing in both. A node
that is the same individual in two standards carries the same IRI in both, so most mappings share `uri`, and the
check that linked nodes agree on it catches a link between two different norms. Where the standards differ:

- **What a permission is.** In LKIF, Obligation and Prohibition are subclasses of Permission, since what is obliged
  is also allowed, and LKIF calls an obligation equivalent to a prohibition of its complement. ODRL and LegalRuleML
  keep the three apart, so their Permission maps to LKIF's as narrower.
- **Duties in ODRL do several jobs.** An ODRL Duty can be a policy's obligation, the condition of a Permission (the
  tenant's duty to inform the landlord before withholding rent), or the consequence or remedy of another rule.
  LegalRuleML writes conditions into a rule's formula, and sanctions as a Penalty Statement tied to the rule by a
  Reparation. ODRL's consequence relationship and LegalRuleML's Reparation say the same thing but are a relationship
  and a node, which a node-to-node crosswalk can only relate.
- **Who bears a norm.** LegalRuleML's Bearer and Auxiliary Party point at terms of the rule's logic, e.g. the
  variable `tenant`, not at agents. An agent enters through a Figure, a function such as tenant instantiated by an
  actor, which matches an LKIF legal role played by an agent. ODRL attaches parties to a rule directly, by function
  (assignee, assigner, informed party).
- **Authorities.** LegalRuleML keeps an Authority apart from the Agent behind it, so a legislature is two
  LegalRuleML nodes and one LKIF node. LKIF has no class for jurisdictions, and ODRL none for authorities or sources.
- **Actions.** An ODRL Action is a kind of operation, such as `odrl:compensate`. An LKIF Action is one act at a
  time, such as the landlord's repairs. They are related as type and occurrence, and data doesn't link them.

No standards body publishes an alignment between these three. The LegalRuleML Core Specification 1.0 cites LKIF
among the legal XML formats it builds on, but maps none of its terms. These mappings are curated from each
standard's definitions: the
[ODRL Information Model 2.2](https://www.w3.org/TR/odrl-model/), the
[LegalRuleML Core Specification 1.0](https://docs.oasis-open.org/legalruleml/legalruleml-core-spec/v1.0/os/legalruleml-core-spec-v1.0-os.html)
and the [LKIF Core norm module](https://github.com/RinkeHoekstra/lkif-core/blob/1958d940c4157678c7f5445b07b35e093e918f31/norm.ttl).

## Sample data

The LKIF and LegalRuleML samples are fictional tenancies, but different ones: LKIF's statute imposes repair, a
permission to withhold rent and a ban on eviction without a court order, while LegalRuleML's Residential Tenancies
(Example) Act 2024 has rent, notice and entry rules. Their parties differ too. So
[`sample.json`](sample.json) adds nodes rather than linking the two samples to each other:

- **LKIF's tenancy, in LegalRuleML and ODRL.** The repair obligation, the withholding permission and the eviction
  prohibition become LegalRuleML deontic specifications, borne by the landlord and tenant, with the statute as their
  legal source and the legislature as their authority. In ODRL they become a Set policy over the dwelling, where the
  notice of disrepair becomes a duty to inform the landlord that the permission carries. The lease becomes an ODRL
  Agreement giving the tenant use of the dwelling and the duty to pay rent. The repair obligation, the permission and
  the prohibition are each in all three standards, linked pairwise; the landlord, tenant, legislature, statute,
  roles and dwelling are linked too.
- **LegalRuleML's act, in ODRL.** Section 30's rent obligation becomes an ODRL Duty, with the late fee as its
  consequence, related to the LegalRuleML penalty statement. Section 95's prohibition on entry becomes an ODRL
  Prohibition.

The ODRL sample's music licence describes nothing here, so it is loaded but not linked. 26 links join the three
standards.

Once loaded, a query can read one norm three ways. For example, every LKIF norm with its ODRL action and the
LegalRuleML term bearing it:

```cypher
MATCH (norm:lkif__Norm)<-[:SAME_AS]-(rule:odrl__Rule)-[:odrl__ACTION]->(action:odrl__Action)
OPTIONAL MATCH (norm)<-[:SAME_AS]-(:lrml__DeonticSpecification)-[:lrml__BEARER]->(bearer:lrml__Data)
RETURN norm.uri, labels(rule), action.uri, bearer.symbolForData
```

## Files

| File | Contents |
|---|---|
| `crosswalk.json` | The mappings, written by hand |
| `sample.json` | The nodes this crosswalk adds to ODRL and LegalRuleML, and the links between the three standards |
| `model.json`, `model.yaml`, `model.svg`, `diagram.json` | The crosswalk as a graph spec model and its diagram |
| `mappings.sssom.tsv` | The mappings in [SSSOM](https://mapping-commons.github.io/sssom/) |
| `model.cypher` | The three standards' constraints and samples, prefixed `odrl__`, `lrml__` and `lkif__`, and the links |
