#!/usr/bin/env python3
"""Generates the IOF Biopharma ontology from the IOF ontology repository.

Usage: python3 generate.py [path/to/iof/ontology]

The entry modules are the Biopharma modules the Industrial Ontologies Foundry (IOF) lists as production in
biopharma/AboutIOFProd.rdf, at the commit of the repository's Release_202603 tag. Their owl:imports, followed to
the full closure, add IOF Core, Supply Chain and Certification, the Basic Formal Ontology (BFO 2020) and the IOF
annotation vocabulary. Reading and building reuse the IOF generator in ../IOF; of the modules Biopharma imports,
the model keeps the classes Biopharma classes extend, point at or require, with theirs. The rest of them is in
../IOF. Writes model.json and model.yaml next to this script. Uses only the Python standard library.
"""

import importlib.util
import json
import sys
from pathlib import Path

# The IOF generator, which Biopharma builds on; loaded without leaving a __pycache__ in ../IOF.
sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location("iof_generate", Path(__file__).resolve().parent.parent / "IOF" / "generate.py")
iof = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(iof)

# The release's list of the Biopharma modules at production maturity: the owl:imports of this module.
PRODUCTION = "biopharma/AboutIOFProd.rdf"

# The modules Biopharma imports from the rest of the IOF, whose classes are kept only as far as Biopharma needs them.
BASE = {"BFO", "Core", "SupplyChain", "Certification", "AnnotationVocabulary"}

# The area each module places its terms in, for extensions.custom.area and the diagram's four colours.
AREAS = {
    **{module: "BFO and IOF Core" for module in BASE},
    "ReferenceOntologyCandidates": "BFO and IOF Core",
    "BiopharmaMaterial": "Materials and molecular entities",
    "MolecularEntity": "Materials and molecular entities",
    "BiopharmaMaterialProcurementAndStorage": "Materials and molecular entities",
    "BiopharmaEquipment": "Equipment, organization and recipes",
    "ManufacturingSystemOrganization": "Equipment, organization and recipes",
    "Recipe": "Equipment, organization and recipes",
    "BiopharmaAgent": "Equipment, organization and recipes",
    "BiopharmaManufacturingExecution": "Processes, parameters and control",
    "BiopharmaParameter": "Processes, parameters and control",
    "BiopharmaMonitoringAndControl": "Processes, parameters and control",
    "TargetsLimitsRanges": "Processes, parameters and control",
    "BiopharmaReferenceOntologyAttributes": "Processes, parameters and control",
}

META = {
    "schema": iof.SCHEMA,
    "version": "202603",
    "id": "iof-biopharma-202603",
    "name": "IOF Biopharma",
    "description": (
        "The Biopharma reference ontology of the Industrial Ontologies Foundry (IOF), developed by the IOF under the "
        "Open Applications Group (https://spec.industrialontologies.org) and licensed under MIT, from Release "
        "202603: the thirteen modules the release lists at production maturity. They describe the manufacture of "
        "biopharmaceuticals: materials such as culture media, buffers, cell lines and drug substances, and the "
        "molecular entities they're made of; bioreactors, chromatography systems and other equipment, organized "
        "into the ISA-88 and ISA-95 physical hierarchy of sites, areas, process cells, units and modules; general, "
        "master and control recipes; the upstream, downstream and fill-finish processes that execute them; process "
        "parameters, quality attributes and the targets, limits and ranges that bound them; monitoring, sampling "
        "and control; and material procurement and storage. Built on IOF Core and the Basic Formal Ontology (BFO "
        "2020), with Supply Chain and Certification, which the closure of their owl:imports adds; of those, the "
        "classes Biopharma extends, points at or requires are kept. Each class is a node, each object property a "
        "relationship from its domain to its range (one direction per inverse pair), each datatype property a "
        "property, each class restriction a count, and each superclass an implied label."
    ),
}


def entry_modules(source):
    """The IRIs of the production Biopharma modules, from the release's AboutIOFProd module."""
    graph = iof.parse_rdfxml(source.read(PRODUCTION), "about_")
    ontology = next(s for s, po in graph.items() if ("iri", iof.OWL + "Ontology") in po.get(iof.TYPE, []))
    return sorted(v[1] for v in graph[ontology].get(iof.OWL + "imports", []) if v[0] == "iri" and "/biopharma/" in v[1])


def prune(model):
    """Keeps the Biopharma nodes and, of the imported modules, the nodes they need: their supertypes, the ends of
    their relationships, and, for every kept node, the other end of each relationship it's required to have, with
    the supertypes of each. Relationships are kept where both ends are. Returns the number of nodes left out."""
    nodes, relationships = model["nodes"], model["relationships"]

    def with_supertypes(names):
        out, todo = set(), list(names)
        while todo:
            name = todo.pop()
            if name not in out:
                out.add(name)
                todo += nodes[name]["labels"].get("implied", [])
        return out

    def required(end):
        return bool(end.get("min_count") or end.get("count"))

    own = {name for name, node in nodes.items() if node["extensions"]["custom"]["module"] not in BASE}
    keep = with_supertypes(
        own | {r[e]["node"] for r in relationships.values() if {r["from"]["node"], r["to"]["node"]} & own for e in ("from", "to")}
    )
    while True:
        needed = {r["to"]["node"] for r in relationships.values() if r["from"]["node"] in keep and required(r["from"])}
        needed |= {r["from"]["node"] for r in relationships.values() if r["to"]["node"] in keep and required(r["to"])}
        added = with_supertypes(needed) - keep
        if not added:
            break
        keep |= added

    left_out = len(nodes) - len(keep)
    model["nodes"] = {name: node for name, node in nodes.items() if name in keep}
    model["relationships"] = {
        rid: r for rid, r in relationships.items() if r["from"]["node"] in keep and r["to"]["node"] in keep
    }
    for node in model["nodes"].values():
        custom = node["extensions"]["custom"]
        if "disjointWith" in custom:
            custom["disjointWith"] = [name for name in custom["disjointWith"] if name in keep]
            if not custom["disjointWith"]:
                del custom["disjointWith"]
    return left_out


def main():
    source = iof.Source(sys.argv[1] if len(sys.argv) > 1 else None)
    iof.ENTRY = entry_modules(source)
    for iri in iof.ENTRY:
        tail = iof.re.sub(r"^\d{6}/", "", iri[len(iof.IOF):]).rstrip("/")
        iof.MODULES[tail] = tail.split("/")[-1]
    iof.AREAS = AREAS
    iof.META = META

    modules = iof.closure(source)
    unknown = [module for module in modules if module not in AREAS]
    if unknown:
        sys.exit(f"modules without an area: {', '.join(unknown)}")
    onto = iof.Ontology(modules)
    model, _ = iof.build(onto)
    left_out = prune(model)
    node_properties = sum(len(node["properties"]) - 1 for node in model["nodes"].values())

    out = Path(__file__).parent
    (out / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    (out / "model.yaml").write_text(iof.yaml(model) + "\n")
    print(f"{len(modules)} modules: {', '.join(onto.modules)}")
    print(f"{len(model['nodes'])} nodes, {len(model['relationships'])} relationships, {node_properties} node properties")
    print(f"{left_out} classes of {', '.join(sorted(BASE - {'AnnotationVocabulary'}))} not needed by Biopharma, left out")
    if onto.deprecated:
        print(f"deprecated, not kept: {', '.join(iof.local(p) for p in onto.deprecated)}")
    for construct, where in sorted(onto.dropped.items()):
        print(f"not kept, {construct}: {', '.join(sorted(set(where)))}")


if __name__ == "__main__":
    main()
