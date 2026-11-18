#!/usr/bin/env python3
"""The crosswalk explorer: a web app showing one thing as every standard of a crosswalk describes it.

Usage: python3 app/server.py [--port 8000]

Connects to the database load.py loaded, as the environment or the .env file at the root of the repository names
it, and serves the explorer at http://localhost:8000. The API under /api reads only.
"""

import argparse
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from neo4j.exceptions import Neo4jError, ServiceUnavailable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crosswalks import SEPARATOR, catalogue, describe, split  # noqa: E402
from load import connect  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
RELATIONSHIPS = 60  # the most relationships a card lists of its node in its own standard
GRAPH = 2000  # the most nodes the graph draws of a crosswalk

state = {}


@asynccontextmanager
async def lifespan(app):
    try:
        state["driver"], state["database"] = connect()
    except (RuntimeError, ServiceUnavailable, Neo4jError, ValueError) as error:
        state["error"] = str(error)
    yield
    if "driver" in state:
        state["driver"].close()


app = FastAPI(title="Crosswalk explorer", lifespan=lifespan)


def query(cypher, **params):
    if "driver" not in state:
        raise HTTPException(503, state.get("error", "Not connected to a database"))
    try:
        records, _, _ = state["driver"].execute_query(cypher, params, database_=state["database"],
                                                      routing_="r")
    except (ServiceUnavailable, Neo4jError) as error:
        raise HTTPException(503, f"The database refused the query: {error}") from error
    return [record.data() for record in records]


def crosswalk_of(id_):
    crosswalks = catalogue()
    if id_ not in crosswalks:
        raise HTTPException(404, f"No crosswalk {id_}")
    return crosswalks[id_]


def prefixes(crosswalk):
    return [item["prefix"] + SEPARATOR for item in crosswalk["standards"]]


# Whether a node belongs to one of the crosswalk's standards: a label of it starts with one of their prefixes
IN_CROSSWALK = "any(label IN labels(n) WHERE any(prefix IN $prefixes WHERE label STARTS WITH prefix))"


def plain(value):
    """A property value as JSON: dates, times, durations and points as their Cypher strings."""
    if isinstance(value, list):
        return [plain(item) for item in value]
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return value.iso_format() if hasattr(value, "iso_format") else str(value)


def node(crosswalk, record):
    props = plain(record["props"])
    return {"id": record["id"], "properties": props, **describe(crosswalk, record["labels"], props)}


def clusters_of(crosswalk):
    """The things the crosswalk links: each a set of nodes joined by links, by the id of every node in it."""
    cache = state.setdefault("clusters", {})
    if crosswalk["id"] in cache:
        return cache[crosswalk["id"]]
    records = query(f"""
        MATCH (n)-[r]->(m) WHERE type(r) IN $links AND {IN_CROSSWALK}
        RETURN elementId(n) AS a, labels(n) AS a_labels, properties(n) AS a_props,
               elementId(m) AS b, labels(m) AS b_labels, properties(m) AS b_props, type(r) AS type
        """, links=crosswalk["links"], prefixes=prefixes(crosswalk))
    parent, nodes, links = {}, {}, []

    def root(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for record in records:
        for end in ("a", "b"):
            nodes[record[end]] = node(crosswalk, {"id": record[end], "labels": record[f"{end}_labels"],
                                                  "props": record[f"{end}_props"]})
        parent[root(record["a"])] = root(record["b"])
        links.append({"from": record["a"], "to": record["b"], "type": record["type"],
                      "mapping": mapping_of(crosswalk, record["a_labels"], record["type"], record["b_labels"])})
    groups = {}
    for id_ in nodes:
        groups.setdefault(root(id_), []).append(id_)
    order = [item["prefix"] for item in crosswalk["standards"]]
    clusters = []
    for members in groups.values():
        members.sort(key=lambda id_: (order.index(nodes[id_]["standard"]), nodes[id_]["name"]))
        lead = min((nodes[id_] for id_ in members), key=lambda item: item["rank"])  # the best named, first on ties
        clusters.append({
            "id": members[0],
            "name": lead["name"],
            "label": lead["labels"][0] if lead["labels"] else "",
            "members": members,
            "standards": sorted({nodes[id_]["standard"] for id_ in members}, key=order.index),
            "links": [link for link in links if link["from"] in members],
        })
    clusters.sort(key=lambda cluster: (-len(cluster["standards"]), cluster["name"].lower()))
    cache[crosswalk["id"]] = result = {"clusters": clusters, "nodes": nodes,
                                       "by_node": {id_: c for c in clusters for id_ in c["members"]}}
    return result


def mapping_of(crosswalk, from_labels, link, to_labels):
    """The mapping a link follows: the first in crosswalk.json between its ends' labels by its type."""
    fits = [mapping for mapping in crosswalk["mappings"]
            if mapping["link"] == link and mapping["subject"] in from_labels and mapping["object"] in to_labels]
    return fits[0]["id"] if fits else None


@app.get("/api/crosswalks")
def crosswalks():
    found = []
    for crosswalk in catalogue().values():
        found.append({key: crosswalk[key] for key in ("id", "name", "description", "standards", "links")}
                     | {"mappings": len(crosswalk["mappings"])})
    loaded = {}
    if "driver" in state:
        for crosswalk in catalogue().values():
            count = query(f"MATCH (n) WHERE {IN_CROSSWALK} RETURN count(n) AS count", prefixes=prefixes(crosswalk))
            loaded[crosswalk["id"]] = count[0]["count"]
    for crosswalk in found:
        crosswalk["loaded"] = loaded.get(crosswalk["id"], 0)
    return {"crosswalks": found, "connected": "driver" in state, "error": state.get("error")}


@app.get("/api/crosswalks/{id_}/clusters")
def clusters(id_: str):
    crosswalk = crosswalk_of(id_)
    found = clusters_of(crosswalk)
    return {"clusters": [{key: cluster[key] for key in ("id", "name", "label", "standards")}
                         | {"size": len(cluster["members"])} for cluster in found["clusters"]]}


@app.get("/api/crosswalks/{id_}/search")
def search(id_: str, q: str = Query(min_length=1, max_length=200)):
    crosswalk = crosswalk_of(id_)
    text = q.strip().lower()
    records = query(f"""
        MATCH (n) WHERE {IN_CROSSWALK}
          AND any(key IN keys(n) WHERE
                (n[key] IS :: STRING AND toLower(n[key]) CONTAINS $text)
             OR (n[key] IS :: LIST<STRING NOT NULL> AND any(item IN n[key] WHERE toLower(item) CONTAINS $text)))
        RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props
        LIMIT 200
        """, prefixes=prefixes(crosswalk), text=text)
    found = clusters_of(crosswalk)["by_node"]
    results = []
    for record in records:
        item = node(crosswalk, record)
        cluster = found.get(item["id"])
        results.append({key: item[key] for key in ("id", "name", "standard", "labels")}
                       | {"cluster": cluster["id"] if cluster else None})
    # Names that match first, then linked nodes, then the rest
    results.sort(key=lambda item: (text not in item["name"].lower(), item["cluster"] is None, item["name"].lower()))
    return {"results": results[:60]}


@app.get("/api/crosswalks/{id_}/nodes/{node_id:path}")
def thing(id_: str, node_id: str):
    """A node and every node linked to it, each with its relationships in its own standard."""
    crosswalk = crosswalk_of(id_)
    found = clusters_of(crosswalk)
    cluster = found["by_node"].get(node_id)
    members = cluster["members"] if cluster else [node_id]
    records = query(f"""
        UNWIND $ids AS id
        MATCH (n) WHERE elementId(n) = id AND {IN_CROSSWALK}
        RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props,
               COLLECT {{
                   MATCH (n)-[r]-(m) WHERE NOT type(r) IN $links
                   RETURN {{type: type(r), outgoing: startNode(r) = n, id: elementId(m), labels: labels(m),
                            props: properties(m), properties: properties(r)}}
                   LIMIT {RELATIONSHIPS}
               }} AS relationships,
               COUNT {{ (n)-[r]-() WHERE NOT type(r) IN $links }} AS total
        """, ids=members, links=crosswalk["links"], prefixes=prefixes(crosswalk))
    if not records:
        raise HTTPException(404, f"No node {node_id} in {crosswalk['name']}")
    by_id = {record["id"]: record for record in records}
    nodes = []
    for id_ in members:
        if id_ not in by_id:
            continue
        record = by_id[id_]
        item = node(crosswalk, record)
        relationships = []
        for relationship in record["relationships"]:
            other = describe(crosswalk, relationship["labels"], relationship["props"])
            neighbour = found["by_node"].get(relationship["id"])
            relationships.append({
                "type": split(relationship["type"])[1],
                "outgoing": relationship["outgoing"],
                "properties": plain(relationship["properties"]),
                "node": {"id": relationship["id"], "name": other["name"], "label": (other["labels"] or [""])[0],
                         "linked": bool(neighbour)},
            })
        relationships.sort(key=lambda r: (not r["outgoing"], r["type"], r["node"]["name"].lower()))
        nodes.append(item | {"relationships": relationships, "total": record["total"]})
    links = cluster["links"] if cluster else []
    used = {link["mapping"] for link in links}
    return {
        "focus": node_id,
        "cluster": cluster["id"] if cluster else None,
        "nodes": nodes,
        "links": links,
        "mappings": {mapping["id"]: {key: mapping[key] for key in ("predicate", "properties", "comment")}
                     for mapping in crosswalk["mappings"] if mapping["id"] in used},
    }


@app.get("/api/crosswalks/{id_}/graph")
def graph(id_: str):
    """Every node of the crosswalk's standards and every relationship between them, links included, to draw."""
    crosswalk = crosswalk_of(id_)
    found = clusters_of(crosswalk)
    records = query(f"""
        MATCH (n) WHERE {IN_CROSSWALK}
        WITH n LIMIT {GRAPH}
        RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props,
               [(n)-[r]->(m) | {{type: type(r), to: elementId(m)}}] AS out
        """, prefixes=prefixes(crosswalk))
    nodes, edges = [], []
    for record in records:
        item = node(crosswalk, record)
        cluster = found["by_node"].get(item["id"])
        nodes.append({key: item[key] for key in ("id", "name", "standard")}
                     | {"label": (item["labels"] or [""])[0], "cluster": cluster["id"] if cluster else None})
    ids = {item["id"] for item in nodes}
    predicates = {mapping["id"]: mapping["predicate"] for mapping in crosswalk["mappings"]}
    links = {(link["from"], link["to"], link["type"]): link["mapping"]
             for cluster in found["clusters"] for link in cluster["links"]}
    for record in records:
        for relationship in record["out"]:
            if relationship["to"] not in ids:
                continue
            key = (record["id"], relationship["to"], relationship["type"])
            link = relationship["type"] in crosswalk["links"]
            edges.append({"from": key[0], "to": key[1], "link": link,
                          "type": relationship["type"] if link else split(relationship["type"])[1],
                          "predicate": predicates.get(links.get(key)) if link else None})
    return {"nodes": nodes, "edges": edges, "truncated": len(records) == GRAPH}


@app.get("/api/crosswalks/{id_}/diagram.svg")
def diagram(id_: str):
    """The diagram crosswalk.py drew of the crosswalk's mappings."""
    path = crosswalk_of(id_)["script"].parent / "model.svg"
    if not path.exists():
        raise HTTPException(404, f"No diagram of {id_}")
    return FileResponse(path, media_type="image/svg+xml")


@app.get("/api/crosswalks/{id_}/mappings")
def mappings(id_: str):
    """The crosswalk's mappings, each with the pairs of nodes the data links by it."""
    crosswalk = crosswalk_of(id_)
    found = clusters_of(crosswalk)
    pairs = {}
    for cluster in found["clusters"]:
        for link in cluster["links"]:
            pairs.setdefault(link["mapping"], []).append({
                "from": {"id": link["from"], "name": found["nodes"][link["from"]]["name"]},
                "to": {"id": link["to"], "name": found["nodes"][link["to"]]["name"]},
            })
    result = []
    for mapping in crosswalk["mappings"]:
        subject_prefix, subject = split(mapping["subject"])
        object_prefix, obj = split(mapping["object"])
        result.append({
            "id": mapping["id"],
            "subject": {"standard": subject_prefix, "label": subject},
            "object": {"standard": object_prefix, "label": obj},
            "predicate": mapping["predicate"],
            "link": mapping["link"],
            "properties": mapping["properties"],
            "comment": mapping["comment"],
            "source": mapping["source"],
            "pairs": pairs.get(mapping["id"], []),
        })
    return {"mappings": result}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
