# Digital twin: Asset Administration Shell 3.2 and AutomationML 2.1

A crosswalk between the [Asset Administration Shell 3.2](../../industrial/AAS) (IEC 63278) and
[AutomationML Edition 2.1](../../industrial/AutomationML) (IEC 62714, CAEX 3.0). They meet over a component's life.
The supplier publishes the component's digital twin as an asset administration shell. The plant builder places the
component in the AutomationML instance hierarchy of the plant it engineers.

AutomationML e.V. publishes how each standard carries the other, in two application recommendations written with
Plattform Industrie 4.0:

- **[AR 004E, Asset Administration Shell Representation](https://www.automationml.org/wp-content/uploads/2022/04/Asset-Administration-Shell-Representation-V1_0_0.zip)**
  (V1.0.0) serialises an AAS in AutomationML. The shell, its asset, its submodels and their elements become internal
  elements with role classes from the `AssetAdministrationShellRoleClassLib`, named by their `idShort`, with their
  attributes as AutomationML attributes.
- **[AR AMLinAAS, AutomationML in Asset Administration Shells](https://www.automationml.org/wp-content/uploads/2024/05/AR-Integrating-AML-projects-in-AAS.zip)**
  (V1.0, May 2024) goes the other way. A submodel references an AutomationML file and the element holding the asset's
  engineering data, and publishes AutomationML attributes as AAS properties.

## Mappings

| AAS | | AutomationML | Shared properties | From |
|---|---|---|---|---|
| AssetAdministrationShell | close | InternalElement | `idShort` = `name` | AR 004E rules 2, 14, 16 |
| AssetInformation | close | InternalElement | | AR 004E 5.1.2 |
| Submodel | close | InternalElement | `idShort` = `name` | AR 004E 5.1.3 |
| Submodel | related | SystemUnitClass | | AR 004E rules 24–26 |
| SubmodelElement | close | InternalElement | `idShort` = `name` | AR 004E rules 9, 13 |
| File | related | ExternalDataReference | | AR 004E rule 10 |
| ReferenceElement | related | InternalLink | | AR 004E rule 11 |
| RelationshipElement | related | InternalLink | | AR 004E rule 11 |
| ConceptDescription | close | InternalElement | | AR 004E rules 15, 20 |
| Qualifier | close | Attribute | | AR 004E rule 7 |
| Reference | related | Attribute | | AR 004E rule 6 |
| Property | close | Attribute | `idShort` = `name`, `value` | AR AMLinAAS 3.3 |
| Key | related | RefSemantic | `value` = `correspondingAttributePath` | AR AMLinAAS 3.3 |

Close matches link data by `SAME_AS` and related matches by `RELATED_TO`, from the AAS node to the AutomationML node.
Where they differ:

- **Metamodel versions.** AR 004E was written for AAS metamodel 2.0. There the asset was an identifiable of its own
  and identifiers had an `idType`. In 3.x the asset is the shell's `AssetInformation`, with no `idShort` to name its
  element by, and `id` stands alone. The mappings follow the recommendation's structure, applied to the 3.2 classes.
- **Two ways a property maps.** Serialising an AAS (AR 004E), a property is an internal element with the `Property`
  role and its value is an attribute named `value`. Publishing engineering data (AR AMLinAAS), an AAS property
  mirrors an AutomationML attribute of the asset's element, with the same name and value.
- **RefSemantic is not semanticId.** In AR 004E an attribute's `RefSemantic` names the metamodel attribute it
  serialises, e.g. `AAS:HasSemantics/semanticId`. An element's `semanticId` is a reference, serialised as an
  attribute's string value (6.2.5). Only for published engineering attributes does a property's semantic ID key
  correspond to the attribute's `RefSemantic`, e.g. an ECLASS IRDI. That is why Key–RefSemantic is a related match.
- **Identifiers.** An internal element's `id` is a UUID. The shell's or submodel's IRI is the value of an attribute,
  so no mapping joins `id` to `id`. Concept descriptions in a library are named `<idShort>__<idType>_<id>`, so
  their names don't match their `idShort` either.

## Sample data

The [AAS sample](../../industrial/AAS/sample.json) is the shell of a Halden HSM 140 servo motor, serial number
2407-00381. The [AutomationML sample](../../industrial/AutomationML/sample.json) is assembly cell AC-1. They describe
different things, so [`sample.json`](sample.json) adds AutomationML data that brings them together. The cell's belt
conveyor is driven by the Halden motor:

- **The drive.** Internal element `ConveyorDrive1`, inside the conveyor, playing both the `ActuatingDrive` role and
  the AAS `Asset` role. Its `SerialNumber` attribute has the ECLASS IRDI of the nameplate's serial number as its
  `RefSemantic`.
- **The drive's AAS**, inside the drive, serialised as AR 004E prescribes. The `AssetAdministrationShell` element is
  named by the shell's `idShort` and holds the shell's id in an `identification/id` attribute. Inside it are the
  `Nameplate` and `TechnicalData` submodels, the `TechnicalProperties` collection, and its `RatedTorque` property,
  whose `value` and `semanticId` are attributes, each with its metamodel `RefSemantic`.
- **An external reference** from the file to the `AssetAdministrationShellRoleClassLib`.

Nine links join the AAS sample to these:

- the shell, asset information, both submodels, the collection and the rated torque, by `SAME_AS`;
- the nameplate's serial number property to the drive attribute it publishes, by `SAME_AS`;
- the serial number's semantic ID key to that attribute's `RefSemantic`, by `RELATED_TO`;
- the rated torque's semantic ID reference to the attribute serialising it, by `RELATED_TO`.

Once loaded, a query can go from a plant's AutomationML structure to the supplier's twin. For example, the submodels
of the AAS of every drive in the cell:

```cypher
MATCH (cell:aml__WorkCell)-[:aml__HAS_INTERNAL_ELEMENT*]->(drive:aml__ActuatingDrive)
      <-[:SAME_AS]-(:aas__AssetInformation)<-[:aas__HAS_ASSET_INFORMATION]-(shell:aas__AssetAdministrationShell)
MATCH (shell)-[:SAME_AS]->(:aml__InternalElement)-[:aml__HAS_INTERNAL_ELEMENT]->(sm:aml__InternalElement)
      <-[:SAME_AS]-(submodel:aas__Submodel)
RETURN cell.name, drive.name, shell.idShort, collect(submodel.idShort) AS submodels
```

## Files

| File | Contents |
|---|---|
| `crosswalk.json` | The mappings, written by hand |
| `sample.json` | The AutomationML data the crosswalk adds, and the links between the two standards' data |
| `model.json`, `model.yaml`, `model.svg`, `diagram.json` | The crosswalk as a graph spec model and its diagram |
| `mappings.sssom.tsv` | The mappings in [SSSOM](https://mapping-commons.github.io/sssom/) |
| `model.cypher` | Both standards' constraints and samples, prefixed `aas__` and `aml__`, the added data and the links |
