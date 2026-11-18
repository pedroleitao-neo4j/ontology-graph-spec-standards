# Plant engineering: CFIHOS 2.0 and DEXPI 2.0.1

A crosswalk between [CFIHOS 2.0](../../industrial/CFIHOS2.0) and [DEXPI 2.0.1](../../industrial/DEXPI), two views of
the same process plant. CFIHOS is the handover: the tags an owner receives from its contractor, their classes, and
the serialised equipment installed against them. DEXPI is the P&ID: the tagged plant items engineering tools draw,
with their components, nozzles and piping. A plant's owner typically holds both, and they meet in the plant breakdown
and in the tag name.

## Mappings

| CFIHOS | | DEXPI | Shared properties |
|---|---|---|---|
| Company | narrower | Enterprise | `companyName` = `enterpriseName` |
| Site | close | Site | `siteCode` = `siteIdentificationCode`, `siteName` |
| Plant | close | ProcessPlant | `plantCode` = `processPlantIdentificationCode`, `plantName` = `processPlantName` |
| ProcessUnit | close | PlantSection | `processUnitCode` = `plantSectionIdentificationCode`, `processUnitName` = `plantSectionName` |
| Area | close | PlantArea | `areaCode` = `plantAreaIdentificationCode`, `areaName` = `plantAreaName` |
| Tag | close | TaggedPlantItem | `tagName` |
| Tag | close | MotorAsComponent | |

Every mapping links data by `SAME_AS`, from the CFIHOS node to the DEXPI node. Where they differ:

- **Company and enterprise.** A CFIHOS company is any legal entity in the handover: owner, contractor, manufacturer
  or supplier. A DEXPI enterprise is only the owner or operator at the top of the ISA-95 breakdown.
- **Tags and equipment.** CFIHOS keeps the tag, the function, apart from the serialised equipment that fulfils it.
  A P&ID shows only the function, so CFIHOS `Equipment`, model parts, purchase orders and documents have no DEXPI
  counterpart. Neither do DEXPI's nozzles, piping and instrumentation loops in CFIHOS.
- **Motors.** CFIHOS gives a pump's driver a tag of its own (PM-2001A, with P-2001A as its parent tag). DEXPI draws it
  as a component of the pump, under a sub-tag. Both describe the same motor, but they share no identifier to check
  the link against.

No standards body publishes a CFIHOS–DEXPI mapping; these are curated from the definitions in each standard.

## Sample data

[`sample.json`](sample.json) links the [CFIHOS](../../industrial/CFIHOS2.0/sample.json) and
[DEXPI](../../industrial/DEXPI/sample.json) samples of the Kestrel Gas Processing Plant: the operator, the plant, the
condensate stabilisation and export unit, export pumps P-2001A/B and their motors. The two samples give the site and
the area different codes and names (KGS and TFS, A20 and F4), so those are mapped but not linked. Linking them would
fail the shared-property check, which is how the check finds inconsistent handovers.

Once loaded, a query can move between the two views. For example, the handover status and serialised equipment of
every centrifugal pump on the P&ID:

```cypher
MATCH (item:dexpi__CentrifugalPump)<-[:SAME_AS]-(tag:cfihos__Tag)
OPTIONAL MATCH (tag)-[:cfihos__IS_FULFILLED_BY]->(equipment:cfihos__Equipment)
RETURN item.tagName, item.designVolumeFlowRate, tag.tagStatus, collect(equipment.equipmentCode) AS equipment
```

## Files

| File | Contents |
|---|---|
| `crosswalk.json` | The mappings, written by hand |
| `sample.json` | The links between the two standards' sample data |
| `model.json`, `model.yaml`, `model.svg`, `diagram.json` | The crosswalk as a graph spec model and its diagram |
| `mappings.sssom.tsv` | The mappings in [SSSOM](https://mapping-commons.github.io/sssom/) |
| `model.cypher` | Both standards' constraints and samples, prefixed `cfihos__` and `dexpi__`, and the links |
