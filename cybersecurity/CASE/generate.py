#!/usr/bin/env python3
"""Generates the CASE 1.5.0 ontology from the official CASE and UCO Turtle files.

Usage: python3 generate.py [path/to/CASE-1.5.0.zip | path/to/CASE] [path/to/UCO-1.5.0.zip | path/to/UCO]

CASE extends UCO 1.5.0, so both are read; without paths, the 1.5.0 releases are downloaded from GitHub. Reading and
building reuse the UCO generator in ../UCO. Writes model.json and model.yaml next to this script. Uses only the
Python standard library.
"""

import importlib.util
import sys
from pathlib import Path

SOURCE_URL = "https://github.com/casework/CASE/archive/refs/tags/1.5.0.zip"
CASE = "https://ontology.caseontology.org/case/"

# The UCO generator, which CASE builds on; loaded without leaving a __pycache__ in ../UCO.
sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location("uco_generate", Path(__file__).resolve().parent.parent / "UCO" / "generate.py")
uco = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(uco)

META = {
    "schema": uco.SCHEMA,
    "version": "1.5.0",
    "id": "case-1.5.0",
    "name": "CASE 1.5.0",
    "description": (
        "The Cyber-investigation Analysis Standard Expression (CASE) 1.5.0, published by the CASE Community "
        "(https://caseontology.org/) under the Linux Foundation's Cyber Domain Ontology project. CASE is the "
        "investigation profile of the Unified Cyber Ontology (UCO): it adds what a cyber investigation records "
        "around UCO's observables and actions, namely the investigation itself and its authorizations, the "
        "investigative actions performed and the actions they were informed by, provenance records that track "
        "exhibits through their chain of custody, and the roles of the people involved (investigator, examiner, "
        "attorney, subject). Generated from the 1.5.0 release Turtle files of CASE "
        "(https://github.com/casework/CASE, tag 1.5.0) and UCO 1.5.0, which CASE imports: each CASE class is a "
        "node, along with the UCO classes CASE classes extend or point at, each SHACL property shape a property or, "
        "for an object-valued property, a relationship, and each superclass an implied label."
    ),
}


def closure(onto, classes):
    """The classes, with every superclass of each, transitively."""
    out, todo = set(), list(classes)
    while todo:
        iri = todo.pop()
        if iri not in out:
            out.add(iri)
            todo += onto.supertypes(iri)
    return out


def targets(onto, iri):
    """The classes a class's object-valued property shapes point at, as the UCO generator resolves them."""
    out = set()
    for path, bodies in onto.shapes(iri).items():
        field = onto.field(iri, path, bodies)
        if field["classes"] or field["kinds"] & {"IRI", "BlankNodeOrIRI"}:
            out |= set(field["classes"] or [v[1] for v in onto.values(path, uco.RANGE) if v[1] in onto.classes])
    return out


def main():
    case_source = Path(sys.argv[1]) if len(sys.argv) > 1 else uco.download(SOURCE_URL, "CASE-1.5.0.zip")
    uco_source = Path(sys.argv[2]) if len(sys.argv) > 2 else uco.download(uco.SOURCE_URL, "UCO-1.5.0.zip")
    files = [
        *uco.ontology_files(case_source, "investigation"),
        *uco.ontology_files(case_source, "vocabulary"),
        *uco.ontology_files(uco_source, "uco"),
        *uco.ontology_files(uco_source, "co"),
    ]
    onto = uco.Ontology(uco.read_graph(files), (uco.UCO, CASE))

    # The CASE classes, the UCO classes they extend, and the UCO classes their relationships point at, with
    # theirs. UCO classes keep their properties, and their relationships to classes in the model; the rest of UCO
    # is in ../UCO.
    own = {iri for iri in onto.classes if iri.startswith(CASE)}
    include = closure(onto, own)
    include |= closure(onto, {t for iri in own for t in targets(onto, iri)})
    onto.dropped.clear()  # reported once, by build

    model, left_out = uco.build(onto, include, META, lambda iri: "CASE" if iri.startswith(CASE) else "UCO")
    uco.write(model, Path(__file__).parent)
    uco.report(onto, left_out)


if __name__ == "__main__":
    main()
