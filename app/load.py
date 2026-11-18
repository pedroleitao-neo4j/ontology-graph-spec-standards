#!/usr/bin/env python3
"""Loads the crosswalks' Cypher scripts into Neo4j, e.g. an Aura instance, for the explorer.

Usage: python3 app/load.py [--reset] [CROSSWALK ...]

Reads the connection from the environment or a .env file at the root of the repository, as Aura's credentials file
writes it: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD and, optionally, NEO4J_DATABASE. Loads the model.cypher of each
crosswalk given, by id, or of every crosswalk. The crosswalks share no standard, and so no label, so all of them can
go in one database. --reset deletes every node and constraint in the database first.

Each script's constraints are created one by one. Where the database refuses one, as Community Edition does node
keys and property existence constraints, a node key falls back to a uniqueness constraint and the others are left
out, since the data is merged on its keys either way. The data statements are sent in batches, each statement a unit
subquery, so a remote database takes a few round trips rather than thousands.
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crosswalks import ROOT, catalogue  # noqa: E402

BATCH = 200


def connect():
    """A driver for the database the environment, or the .env file, names, and the database's name."""
    load_dotenv(ROOT / ".env")
    missing = [name for name in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD") if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Set {', '.join(missing)} in {ROOT / '.env'} or the environment, "
                           "as in Aura's credentials file")
    driver = GraphDatabase.driver(os.environ["NEO4J_URI"],
                                  auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]))
    driver.verify_connectivity()
    return driver, os.environ.get("NEO4J_DATABASE") or None


def statements(script):
    """The constraint and data statements of a generated script, each of which is one line."""
    schema, data = [], []
    for line in script.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        (schema if line.startswith("CREATE CONSTRAINT") else data).append(line.removesuffix(";"))
    return schema, data


def fallback(statement):
    """What to try where the database refuses a constraint: a node key as a uniqueness constraint, else nothing."""
    if statement.endswith("IS NODE KEY") and "FOR (n:" in statement:
        return re.sub(r"IS NODE KEY$", "IS UNIQUE", statement.replace(" IF NOT EXISTS", "_unique IF NOT EXISTS", 1))
    return None


def create_constraints(driver, database, schema):
    created = downgraded = skipped = 0
    for statement in schema:
        try:
            driver.execute_query(statement, database_=database)
            created += 1
        except ClientError as error:
            replacement = fallback(statement)
            if replacement is None:
                skipped += 1
                continue
            try:
                driver.execute_query(replacement, database_=database)
                downgraded += 1
            except ClientError:
                skipped += 1
                print(f"  left out: {statement}\n    {error.message}", file=sys.stderr)
    return created, downgraded, skipped


def load_data(driver, database, data):
    """Runs the data statements in batches, in order: every node is merged before the relationships that match it."""
    with driver.session(database=database) as session:
        for start in range(0, len(data), BATCH):
            query = "\n".join(f"CALL () {{ {statement} }}" for statement in data[start:start + BATCH])
            session.execute_write(lambda tx: tx.run(query).consume())


def reset(driver, database):
    with driver.session(database=database) as session:
        session.run("MATCH (n) CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 5000 ROWS").consume()
        for record in session.run("SHOW CONSTRAINTS YIELD name").data():
            session.run(f"DROP CONSTRAINT `{record['name']}` IF EXISTS").consume()


def load(driver, database, ids=None, log=print):
    crosswalks = catalogue()
    unknown = [id_ for id_ in ids or [] if id_ not in crosswalks]
    if unknown:
        raise ValueError(f"no crosswalk {', '.join(unknown)}; there are {', '.join(crosswalks)}")
    for id_ in ids or crosswalks:
        began = time.monotonic()
        schema, data = statements(crosswalks[id_]["script"])
        created, downgraded, skipped = create_constraints(driver, database, schema)
        load_data(driver, database, data)
        note = f", {downgraded} node keys as uniqueness constraints and {skipped} left out" if downgraded or skipped else ""
        log(f"{id_}: {created} constraints{note}; {len(data)} statements in {time.monotonic() - began:.1f}s")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("crosswalks", nargs="*", help="crosswalk ids, e.g. plant-engineering; every one by default")
    parser.add_argument("--reset", action="store_true", help="delete every node and constraint in the database first")
    args = parser.parse_args()
    try:
        driver, database = connect()
        with driver:
            if args.reset:
                reset(driver, database)
                print("deleted every node and constraint")
            load(driver, database, args.crosswalks)
    except (RuntimeError, ValueError) as error:
        sys.exit(str(error))


if __name__ == "__main__":
    main()
