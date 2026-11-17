# IOF Biopharma (Industrial Ontologies Foundry)

An ontology for the Biopharma reference ontology of the [Industrial Ontologies Foundry](https://www.industrialontologies.org)
(IOF), the effort under the Open Applications Group (OAGi) to build a suite of interoperable ontologies for
manufacturing and the industry around it. The ontologies are licensed under
[MIT](https://opensource.org/licenses/MIT). Biopharma is written in OWL on IOF Core and the
[Basic Formal Ontology](https://basic-formal-ontology.org) (BFO 2020, ISO/IEC 21838-2), as the modules in
[`../IOF`](../IOF) are, and describes the manufacture of biopharmaceuticals such as monoclonal antibodies.

Biopharma has 19 modules. This model takes the thirteen the release lists at production maturity, the
`owl:imports` of `biopharma/AboutIOFProd.rdf`:

- **Materials** (`BiopharmaMaterial`): culture media, feeds, buffers and other solutions, cells, cell lines and
  cell banks, viruses, impurities, and the roles, functions and qualities they have, e.g. a `ProductionCultureMedium`,
  a `WorkingCellBank` or `ViableCellDensity`
- **Molecular entities** (`MolecularEntity`): proteins, antibodies, glycans and their residues, nucleic acids,
  ions and other molecules, their populations and variants, and the roles they play in a process
- **Equipment** (`BiopharmaEquipment`): bioreactors and their vessels, flasks, rocker bags, chromatography systems,
  columns and media, filters, centrifuges, and the capabilities and functions they have
- **Manufacturing system organization** (`ManufacturingSystemOrganization`): the ISA-88 and ISA-95 physical
  hierarchy, from the enterprise to sites, areas, process cells, units, equipment modules and control modules
- **Recipe** (`Recipe`): ISA-88 general, site, master and control recipes, their procedural elements, from
  procedure to phase, and their process elements, from process to action, and the batch runs they prescribe
- **Manufacturing execution** (`BiopharmaManufacturingExecution`): upstream processes such as the seed train,
  inoculation, cell culture expansion and the production culture with its operating modes, e.g. fed-batch or
  perfusion; and downstream processes such as harvest, chromatography, filtration and viral clearance
- **Parameters** (`BiopharmaParameter`): process parameters and quality attributes, critical or key, with their
  specifications, and rates, yields, titers and other performance indicators
- **Targets, limits and ranges** (`TargetsLimitsRanges`): setpoints, target values, normal operating and proven
  acceptable ranges, and alert, action, control, acceptance and specification limits, as value expressions
- **Monitoring and control** (`BiopharmaMonitoringAndControl`): control strategies, inline, online, atline and
  offline monitoring, and material sampling and aliquoting, with their plans
- **Material procurement and storage** (`BiopharmaMaterialProcurementAndStorage`): certificates of analysis and
  conformance, catalog, CAS registry and ERP codes, and the expired state
- **Agents** (`BiopharmaAgent`): manufacturing operators and validators, and their roles
- **Reference ontology attributes** (`BiopharmaReferenceOntologyAttributes`): physical qualities such as mass,
  volume, density, temperature, pressure, viscosity and stability
- **Reference ontology candidates** (`ReferenceOntologyCandidates`): classes proposed for IOF Core, such as
  material addition, removal and transfer processes, production consumables and acceptance criteria

The other six modules are left out. Four are provisional: deviation management, the manufacturing process
lifecycle, material testing and risk management. Design of Experiments and Statistics are provisional too, and
Statistics imports the 1.2 MB OBO statistics ontology, STATO. Two utility modules of reasoning-only classes for the
recipe hierarchy are also left out, as they mustn't be subclassed and aren't expected to have individuals.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the IOF repository at Release 202603, using the [IOF generator](../IOF/generate.py) |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`sample.json`](sample.json) | Sample data: a batch of a monoclonal antibody, from cell bank to capture |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |
| [`../../cypher.py`](../../cypher.py) | Generates `model.cypher` (shared by every standard) from `model.json` and `sample.json` |

## Source

The model is generated from the same commit as [`../IOF`](../IOF#source):
[`0c5af08`](https://github.com/iofoundry/ontology/tree/0c5af080dba16489db1b5c7a432a34222524c6e9) of the
[IOF ontology repository](https://github.com/iofoundry/ontology), the commit of the
[`Release_202603`](https://github.com/iofoundry/ontology/releases/tag/Release_202603) tag. `generate.py` reads the
production modules from `biopharma/AboutIOFProd.rdf` and follows their `owl:imports`, which gives eighteen modules:
the thirteen Biopharma modules, IOF Core, Supply Chain and Certification, BFO 2020 and the annotation vocabulary.
Biopharma is written as the rest of the IOF is, so `generate.py` reads and builds it with the IOF generator in
[`../IOF/generate.py`](../IOF/generate.py), which resolves each import through the release's XML catalog. To
regenerate:

```bash
python3 generate.py                          # downloads the pinned commit from GitHub
python3 generate.py path/to/iof/ontology     # or a checkout of the repository at Release_202603
```

The script needs only the Python standard library. It prints the module, node and relationship counts and
a report of every construct it had to drop, so nothing is left out silently.

## What the model contains

A Biopharma graph is an IOF graph: its bioreactors are engineered systems, its culture media are material
entities and its batch runs are manufacturing processes. IOF Core, Supply Chain and Certification are in
[`../IOF`](../IOF). This model holds the Biopharma classes and the part of the imported modules they need:

- the classes Biopharma classes extend, up to BFO's `Entity`, e.g. `PlannedProcess`, `PieceOfEquipment` or
  `Certificate`;
- the classes at the other end of Biopharma's relationships, e.g. `Agent` for a `ManufacturingProcess`'s
  participant, and their superclasses;
- for every class kept, the classes at the other end of the relationships it's required to have, e.g. the
  `ActionSpecification` and `ObjectiveSpecification` every `PlanSpecification` has as parts, with theirs.

That keeps 77 of the 248 classes of the imported modules: 46 of Core, 24 of BFO, 4 of Supply Chain (`Lot`, its
identifier and roles) and 3 of Certification. They keep their relationships to each other and to Biopharma
classes. Their other relationships, to the 171 classes left out, are in [`../IOF`](../IOF).

The 676 nodes split by area, which follows the module a class is declared in:

- 92 nodes of BFO and IOF Core, Supply Chain and Certification, with the 15 reference ontology candidates
- 267 nodes of materials and molecular entities, with material procurement and storage
- 111 nodes of equipment, manufacturing system organization, recipes and agents
- 206 nodes of manufacturing execution, parameters, targets, limits and ranges, monitoring and control, and the
  reference ontology attributes

Biopharma declares few properties of its own: 13 relationship types, e.g. `HAS_PROCESS_PARAMETER` and
`IS_UPPER_SIDE_LIMIT_VALUE_EXPRESSION_OF_AT_SOME_TIME`, which type 41 of the 736 relationships. It relates its
classes mostly through the restrictions it places on Core's and BFO's properties, e.g. every `Bioreactor` `HAS_FUNCTION` some
`CultivationEnvironmentFunction`, and every `SeedTrain` `HAS_OCCURRENT_PART` some `CellCultureExpansionProcess`.

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow from domain to range, as for
[`../IOF`](../IOF#diagram): a solid, darker arrow is required, a dashed arrow means at most one, and a thin solid
arrow is otherwise unconstrained. Dotted arrows point from a subclass to the superclass whose label it also
carries. Cards are coloured by the four areas above, which each card also prints, alongside its module (e.g.
`BiopharmaEquipment`) and its number of properties.

Opened in a browser, hovering a card or arrow shows its name and description, and each card links to its term
IRI, which the IOF's [specification site](https://spec.industrialontologies.org) resolves. To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

`sample.json` and `model.cypher` follow batch AB101-24-017 of a fictional monoclonal antibody, AB-101, made by a
fictional company, Aldermoor Biologics, at its Kilbride site. The site's upstream area holds a production process
cell, whose bioreactor unit holds a 2,000 L production bioreactor, with its vessel, cultivation and containment
functions and capabilities, and a pH probe. A master recipe prescribes the seed train, expansion, harvest and
capture; the batch's control recipe, which contains the batch identifier, prescribes the batch run, and its
procedure, unit procedure, operation and feed phase prescribe the steps within it. A working cell bank holds the
CHO cells of the cell line, and the production culture medium, a material product made of glucose among other
things, comes in a lot with a certificate of analysis, granted after the supplier's quality control testing, and
is classified by the supplier's catalog number. The batch run, run by a manufacturing operator, is made of the
seed train, whose cell culture expansion proliferates the cells, the fed-batch production culture in the
bioreactor, which outputs harvested fluid containing the antibody, the harvest and the Protein A capture step. The
control strategy holds the culture's pH as a critical process parameter, with a setpoint of 7.00 within a normal
operating range of 6.90 to 7.10, and the high molecular weight content as a critical quality attribute, with a
specification limit of 2.0 %; daily offline monitoring samples the culture and counts its viable cell density.

```bash
python3 ../../cypher.py .    # regenerates model.cypher from model.json and sample.json
```

`model.cypher` creates the model's constraints and merges the sample data, so it can be run again. It needs the
Enterprise Edition of Neo4j 5 or later, for its node key constraints:

```bash
cypher-shell -f model.cypher
```

## Mapping

Biopharma is mapped as the rest of the IOF is; see the [IOF mapping](../IOF/README.md#mapping). For example:

| Biopharma (OWL) | Ontology |
|---|---|
| Class, e.g. `iof:ProductionBioreactor` | Node `ProductionBioreactor`, labelled by its `rdfs:label` in PascalCase |
| `rdfs:subClassOf` a named class, e.g. `ProductionBioreactor` of `Bioreactor` | Implied label: every `ProductionBioreactor` is also a `Bioreactor`, and so an `EngineeredSystem` |
| `owl:someValuesFrom` restriction, e.g. `ProductionBioreactor` ⊑ `has role` some `ProductionBioreactorRole` | `ProductionBioreactor` `HAS_ROLE` `ProductionBioreactorRole`, with `min_count: 1` at the `from` end |
| Object property, e.g. `iof:hasProcessParameter` | `PlannedProcess` `HAS_PROCESS_PARAMETER` `ProcessParameter` |
| Module, e.g. `biopharma/BiopharmaEquipment` | `extensions.custom.module`, e.g. `BiopharmaEquipment`, and `extensions.custom.area` |

### Where the ontology differs from IOF Biopharma

Every difference listed for [`../IOF`](../IOF/README.md#where-the-ontology-differs-from-iof) holds here too:
every node has a `uri` key, names come from labels, definitions are read as necessary conditions, temporal
qualifiers stay in the relationship type, and properties aren't inherited. In addition:

- **It holds only part of IOF Core, Supply Chain and Certification.** See
  [What the model contains](#what-the-model-contains).
- **Deprecated classes aren't kept.** Three classes the release marks `owl:deprecated`, `ERPCode`, `SamplePlan` and
  `SamplingProcess`, are replaced by `EnterpriseResourcePlanningCode`, `MaterialSamplingPlan` and
  `MaterialSamplingProcess`, which are kept.
- **Restrictions to a complement aren't kept.** The recipe hierarchy and `PhysicalUnit` say what an element can't
  be part of, e.g. no part of a `RecipePhase` is a `RecipeOperation`, through `owl:allValuesFrom` the
  `owl:complementOf` a class. A complement names no node, so the generator reports these and leaves them out, as it
  does two restrictions whose filler is a nested restriction, on `CompositionalHomogeneity` and
  `ProductionConsumableRole`.
- **Subclass axioms that are unions aren't kept.** Twelve classes, nine of them Biopharma's, e.g.
  `DiafiltrationProcess` and `GeneralRecipe`, are subclasses of a union, which can't be an implied label.
  `ProcessParameter` is defined as a process profile, temporal region or quality, and so carries only `Entity`; a
  parameter that is a quality, like the sample's culture pH, carries both labels, e.g. `PH` and
  `CriticalProcessParameter`.
- **Text values are a property of `Entity`.** Supply Chain's `hasTextValue` has no domain and no class restricts
  it, so, as in [`../IOF`](../IOF/README.md#where-the-ontology-differs-from-iof), it's a property of `Entity`. The
  sample's identifiers, e.g. the `BatchRunIdentification` and the `LotIdentifier`, carry their text in it; value
  expressions, such as setpoints and limits, keep theirs in `hasSimpleExpressionValue`.

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json). Its relationship
endpoints resolve, its keys cover existing properties, its counts are well formed, and its names and
descriptions are within the length limits, which covers the core validation rules; every node carries
`Entity`, and every node, relationship and property records the IRI of the term it came from.
