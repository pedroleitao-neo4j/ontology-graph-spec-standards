# Crosswalk explorer

A web app for exploring the [crosswalks](../crosswalks) once they're loaded into Neo4j. It opens on the Graph view:
the crosswalk's whole data graph, with one coloured band per standard. Each standard's nodes and relationships stay
in their own band, and the crosswalk links bridge the bands, levelled so each pair of linked nodes sits on one row.
Clicking a node lights up the thing it is in every standard, with its neighbours, and the side panel shows how each
standard records it. Hovering a node names its relationships. This is the view to start a demo with.

In the Linked things view, pick a thing a crosswalk
links, such as pump P-2001A, technique T1566.001 or the landlord's repair obligation. The explorer shows it as each
standard describes it, one column per standard, with the links between them drawn across the gutters. Shared
properties, the ones a mapping says linked nodes must agree on, are marked ⇄. Each card lists the node's
relationships in its own standard, and following one moves to that node. The Mappings view lists the crosswalk's
mappings: how the kinds correspond, why, and the pairs of nodes the data links by each, with the crosswalk's
`model.svg` diagram of them.

## Running it

It needs Python 3.10 or later and a Neo4j database, e.g. an [Aura](https://neo4j.com/cloud/aura/) instance. Put the
instance's credentials in a `.env` file at the root of the repository, as in [`.env.example`](../.env.example). The
variable names are the ones in the credentials file Aura gives you.

```bash
python3 -m venv .venv && .venv/bin/pip install -r app/requirements.txt
.venv/bin/python app/load.py            # loads every crosswalk; or name some, e.g. plant-engineering
.venv/bin/python app/server.py          # serves the explorer at http://localhost:8000
```

The crosswalks share no standard, so all five load into one database. Loading creates each standard's constraints
one by one, which takes most of the time on a remote database. It then sends the data in batches. Where a database
refuses a node key or existence constraint, as Community Edition does, `load.py` falls back to a uniqueness
constraint or leaves the constraint out. It says which. `--reset` first deletes every node and constraint in the
database, so use it only on a database that holds nothing else.

## How it's built

| File | Contents |
|---|---|
| `crosswalks.py` | Reads the crosswalks from the repository: their standards, mappings and link types, and how to name a node |
| `load.py` | Loads the crosswalks' `model.cypher` scripts |
| `server.py` | A FastAPI app serving the explorer and a read-only API under `/api` |
| `static/` | The explorer itself: plain HTML, CSS and JavaScript, with no build step. The graph loads [d3](https://d3js.org) from a CDN, as the page loads its fonts, so a demo needs a network connection |

The server learns everything about a crosswalk from its `crosswalk.json` and `model.json`, so a new crosswalk shows
up once `crosswalk.py` has built it and `load.py` has loaded it. Each standard has the colour its `model.svg` gives
it.
