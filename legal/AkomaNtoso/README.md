# Akoma Ntoso 1.0 (OASIS LegalDocML)

An ontology for [Akoma Ntoso](http://www.akomantoso.org) Version 1.0, the
[OASIS LegalDocML](https://www.oasis-open.org/committees/legaldocml/) Standard of 29 August 2018 for the XML
representation of parliamentary, legislative and judiciary documents. Akoma Ntoso marks up acts, bills, amendments,
debates, judgments, official gazettes and other documents: their structure, down to articles, sections and
paragraphs; their metadata, from the FRBR identification of the work, expression and manifestation to their lifecycle,
workflow and the analysis of the modifications they make; and the people, organizations, concepts and other documents
their text refers to. Parliaments and publication offices use it, among them the European Parliament and Commission,
the UK's legislation.gov.uk and the United Nations, and it underlies the EU's Akoma Ntoso profile, AKN4EU.

| File | Contents |
|---|---|
| [`model.yaml`](model.yaml), [`model.json`](model.json) | The ontology, as YAML and as JSON |
| [`generate.py`](generate.py) | Generates both files from the official Akoma Ntoso XML schema |
| [`model.svg`](model.svg) | A diagram of the ontology |
| [`diagram.json`](diagram.json) | How the diagram colours cards and draws arrows |
| [`sample.json`](sample.json) | Sample data: an amending act, and the principal act whose article it substitutes |
| [`model.cypher`](model.cypher) | A Cypher script creating the model's constraints and loading the sample data |
| [`../../visualise.py`](../../visualise.py) | Generates the diagram (shared by every standard) from `model.json`, checking that `model.yaml` matches it |
| [`../../cypher.py`](../../cypher.py) | Generates `model.cypher` (shared by every standard) from `model.json` and `sample.json` |

## Source

The model is generated from the Akoma Ntoso 3.0 XML schema,
[`akomantoso30.xsd`](https://docs.oasis-open.org/legaldocml/akn-core/v1.0/os/part2-specs/schemas/akomantoso30.xsd),
published with [Akoma Ntoso Version 1.0 Part 2: Specifications](https://docs.oasis-open.org/legaldocml/akn-core/v1.0/os/part2-specs/akn-core-v1.0-os-part2-specs.html)
in the OASIS document repository, under the Creative Commons Attribution 4.0 licence. The schema documents its
elements, attribute groups and types, and the specification has a page for each, to which the ontology links.
`generate.py` reads the schema with Python's XML parser. To regenerate:

```bash
python3 generate.py                          # downloads the schema from docs.oasis-open.org
python3 generate.py path/to/akomantoso30.xsd
```

The script needs only the Python standard library.

## Diagram

[`model.svg`](model.svg) draws each node as a card and each relationship as an arrow: solid for a composition, from an
element to the elements it contains, and dashed for a reference, from an element to the element one of its attributes
identifies by `#` and an eId, e.g. a `DebateContainer`, such as a speech, `BY` the `Agent` who speaks. Arrows are named by their relationship
type, e.g. `HAS_FRBR_WORK` or `REFERS_TO`, wherever the name fits without overlapping a card or another name,
compositions first. Dotted arrows point from an element to the label it also carries, e.g. from `Article` to
`Hierarchy`.

Cards are coloured by area, and print their schema type, e.g. `hierarchy` or `referenceType`, or `abstract` for a
label that groups elements:

- Documents, their parts and components: the twelve document types, from `Act` to `Portion`, their preface,
  preamble, body variants and conclusions, and the components and attachments a document embeds
- Metadata: the `Meta` block, with the FRBR identification, publication, classification, lifecycle, workflow,
  analysis (modifications, judicial arguments, parliamentary votes, mappings), temporal data, references section,
  notes and proprietary metadata
- Structure: the hierarchy of articles, sections, chapters and their kind, with intros, content and wrap-ups;
  recitals and citations; the sections and speeches of debates; the blocks of judgments and amendments
- References: the top-level classes (TLCs) and document references of the references section, and the inline
  elements that point at them, e.g. `Ref`, `Person`, `Date`, `Judge` or `Mod`

Opened in a browser, hovering a card or arrow shows its name and description, and each card links to the element's
page in the Akoma Ntoso specification. To regenerate:

```bash
python3 ../../visualise.py .   # from this folder; or ../../visualise.py alone to redraw every standard
```

## Sample data

`sample.json` and `model.cypher` show an amending act in a fictional jurisdiction: the Consumer Protection
(Amendment) Act, 2024, which substitutes an article of the Consumer Protection Act, 2012. The amending act is kept in
full: its FRBR work, expression and manifestation and the author of each level, its publication, lifecycle events,
references (the agents, concepts, events and roles its text refers to), classification, the temporal group of its
periods, and the structure of its preamble and body down to articles, paragraphs and inline elements. An article of
the body carries the amendment itself: a `Mod` quoting the substituted text, and the analysis's active textual
modification, with its source, destination, old text and new. The principal act is kept as a document of its own,
whose analysis records the same change as a passive modification.

```bash
python3 ../../cypher.py .    # regenerates model.cypher from model.json and sample.json
```

`model.cypher` creates the model's constraints and merges the sample data, so it can be run again. It needs the
Enterprise Edition of Neo4j 5 or later, for its node key and property existence constraints:

```bash
cypher-shell -f model.cypher
```

## Mapping

| Akoma Ntoso schema | Ontology |
|---|---|
| Element with a legal meaning, e.g. `article`, `FRBRWork` or `TLCPerson` | Node, labelled by the element's name in PascalCase, e.g. `Article`, `FRBRWork`, `TLCPerson` |
| Element group, e.g. `hierElements` or `TLCs` | Label carried by every element of the group that is a node, e.g. `Hierarchy` or `TLC` |
| Complex type extended by several elements, e.g. `modificationType` or `coreProperties` | Label carried by every element of that type, e.g. `Modification` or `FRBRLevel` |
| The core attribute lists `corereq`, `coreopt` and `corereqreq` | `ContentElement` label, carried by every element of a document's content |
| Element contained, e.g. `meta` in `act` | Composition relationship from container to contained element, e.g. `HAS_META` |
| Element group contained, e.g. `hierElements` in an `article` | Composition relationship to the group's label, e.g. `Hierarchy` `HAS_HIERARCHY` `Hierarchy` |
| `minOccurs` and `maxOccurs`, through the sequences, choices and groups around the element | Count at the `from` end, e.g. `count: 1` for an act's `body` |
| Attribute, e.g. `contains` or `eId` | Property, e.g. `contains`, `eId`; `GUID` becomes `guid` and `xml:lang` `lang` |
| `use="required"` | An `EXISTS` constraint |
| Attribute that is a list, e.g. `refersTo` | `LIST<STRING>` |
| Attribute typed `agentRef`, `roleRef`, `conceptRef`, `referenceRef`, `eventRefRef`, `temporalGroupRef` or `voteRef` | Its property, and a relationship to the element it identifies by `#` and its eId, named after the attribute, e.g. `by` → `BY` to `Agent`, `refersTo` → `REFERS_TO` to `RefItem` |
| `href` of a `noteRef` and of an `FRBRauthor` | Its property, and a `LINKS_TO` relationship to the `Note` or `Agent` it identifies |
| Value element, e.g. `FRBRthis`, `FRBRdate` or `FRBRcountry` | Property of the element holding it, e.g. `frbrThis`, `frbrDate` and `frbrDateName`, `frbrCountry` |
| Text element of a hierarchy: `num`, `heading`, `subheading` | `STRING` property of its text, a list where the schema allows several |
| `xsd:string`, `xsd:anyURI`, the identifier and reference types | `STRING` |
| `xsd:boolean`, `xsd:integer`, `xsd:dateTime`, `xsd:duration` | `BOOLEAN`, `INTEGER`, `ZONED DATETIME`, `DURATION` |
| A union of `xsd:date` and `xsd:dateTime`, or of `xsd:time` and `xsd:dateTime` | `STRING` |
| Enumeration, e.g. `TextualMods` for a `textualMod`'s `type` | `STRING`, with the values in `one_of` |
| Documentation (`comment`) | `description` |
| The element's IRI, or its document's IRI and its eId | A `uri` property on every node, and a `KEY` constraint over it |

Nodes record, in `extensions.custom`, their area, element and schema type, and whether they are an abstract label.
Properties record the attribute or element they come from, its schema type and attribute group, and for value elements
their multiplicity. Relationships record whether they are a composition, their multiplicity, and the elements left out
they pass through, or the attribute they come from.

### Labels

Akoma Ntoso has few named types for its 315 elements; it groups them instead, e.g. the 28 hierarchical elements in
`hierElements`, the inline elements in `inlineCM`, or the top-level classes in `TLCs`, and a content model names a
group rather than each element. The ontology makes these groups labels, which their elements also carry:

| Label | Carried by | From |
|---|---|---|
| `Document` | The twelve document types, from `Act` to `Statement` | Group `documentType` |
| `ContentElement` | Every element of a document's content: the hierarchy, blocks, containers and inlines | Attribute groups `corereq`, `coreopt`, `corereqreq` |
| `Hierarchy` | `Article`, `Section`, `Chapter`, `Part`, `Paragraph` and the other hierarchical elements, and `Hcontainer` | Group `hierElements` |
| `SpeechSection`, `DebateContainer` | The sections of a debate, e.g. `Questions` or `Adjournment`, and its speeches, questions and answers | Groups `speechSection`, `ANcontainers` |
| `JudgmentBlock`, `AmendmentBlock` | The blocks of a judgment, e.g. `Motivation` or `Decision`, and of an amendment | Groups `judgmentBlock`, `amendmentBlock` |
| `InlineElement`, and below it `SemanticInline`, `TitleInline`, `HeaderInline` and `AmendmentInline` | The inline elements that are nodes, e.g. `Ref`, `Mod`, `Person`, `DocTitle`, `Judge`, `AffectedDocument` | Groups `inlineCM`, `ANsemanticInline`, `ANtitleInline`, `ANheaderInline`, `amendmentInline` |
| `SubFlow` | `Note`, `AuthorialNote` and `QuotedStructure`, which hold structure of their own | Type `subFlowStructure` |
| `RefItem`, and below it `TLC` and `DocRef` | The entries of the references section: the top-level classes, e.g. `TLCPerson`, and the references to other documents, e.g. `ActiveRef` | Groups `TLCs`, `docRefs` |
| `Agent` | `TLCPerson` and `TLCOrganization` | Type `agentRef` |
| `FRBRLevel` | `FRBRWork`, `FRBRExpression`, `FRBRManifestation`, `FRBRItem` | Type `coreProperties` |
| `Modification`, `JudicialArgument`, `Period` | The modifications, e.g. `TextualMod`; the judicial arguments, e.g. `Overrules`; and `Force`, `Efficacy`, `Application` and `Duration` | Types `modificationType`, `judicialArgumentType`, `periodType` |

A property or relationship every element of a label has is defined once, on the label, rather than on each element:
the identifiers and `refersTo` on `ContentElement`, `HAS_META` on `Document`, and `HAS_SOURCE` and `HAS_DESTINATION`
on `Modification`. Where some of the elements require it and others don't, e.g. the `refersTo` that a `Person`
requires, the label has it as optional and the elements that require it keep their own, with an `EXISTS` constraint or
a `min_count`.

### Where the ontology differs from the standard

- **Presentational markup and generic text structure aren't nodes.** The HTML-like elements (`p`, `span`, `b`, `i`,
  `u`, `sup`, `sub`, `abbr`, `a`, `img`, `br`, `ul`, `ol`, `li`, `table`, `tr`, `th`, `td`, `caption`, `div`), the
  generic and editorial blocks and inlines (`block`, `blockContainer`, `blockList`, `item`, `listIntroduction`,
  `listWrapUp`, `tblock`, `container`, `inline`, `marker`, `subFlow`, `foreign`, `crossHeading`, `ins`, `del`,
  `omissis`, `decoration`, `placeholder`, `fillIn`, `embeddedText`, `embeddedStructure`, `remark`, `recordedTime`),
  the debate's descriptive elements (`other`, `scene`, `narrative`, `summary`, `outcome`, `from`), the table of
  contents (`toc`, `tocItem`), `interstitial`, the line and page markers (`eol`, `eop`), and the metadata about
  components and preservation (`componentInfo`, `componentData`, `preservation`, `FRBRportion`) are left out. The
  inline elements within them are attached to the nearest node above: a `Ref` in a paragraph of an article's content
  is reached by `Content` `HAS_INLINE_ELEMENT` `InlineElement`, a label the `Ref` carries, through `p`, which the
  relationship records in `extensions.custom.through`. Structural elements a generic block holds aren't followed, nor is the content of the
  inline elements left out, which is inline content again; what an `embeddedStructure` or `subFlow` holds is lost.
- **Hierarchy headings are text.** `num`, `heading` and `subheading` hold mixed content; the ontology keeps their text
  as properties of the element they head, so references within a heading aren't nodes.
- **FRBR values are properties.** `FRBRthis`, `FRBRuri`, `FRBRdate`, `FRBRcountry` and the other value elements of
  the identification become properties of the FRBR level holding them, e.g. `FRBRWork.frbrCountry`. Their own
  identifiers and `refersTo` aren't kept. `FRBRauthor` and `FRBRtranslation`, which refer to agents and other
  expressions, stay nodes.
- **References within a document are relationships where their target is known.** Akoma Ntoso refers to an element by
  `#` and its eId, and types each reference by what it may point at, e.g. `agentRef` to a `TLCPerson` or
  `TLCOrganization`. These are relationships, and the attribute stays a property too. A reference typed `eIdRef` or
  `wIdRef`, e.g. the `for` of a `mod` or the `from` and `upTo` of an `rref`, may point at any element, and an `href`
  at any document or element by its IRI; these remain properties only, apart from the `href` of a `noteRef` and an
  `FRBRauthor`, whose targets the specification fixes.
- **Every node has a `uri` key.** Akoma Ntoso identifies a document by its FRBR IRIs, e.g.
  `/akn/ke/act/2010-08-27/1/eng@` for an expression, and an element within it by its eId, which is unique only within
  the document; its wId and GUID are optional. The ontology makes `uri` the key of every node, an IRI unique across
  documents: for a document its expression IRI, and for an element its document's IRI followed by `#` and its eId, or
  where it has none its wId, GUID or an identifier the loader assigns. eId, wId and GUID are kept as properties.
- **Elements of the same kind share a label, not their content.** Akoma Ntoso gives the hierarchical elements one
  content model, and the ontology one label and one set of relationships, e.g. `Hierarchy` `HAS_HIERARCHY`
  `Hierarchy`, so any hierarchical element may contain any other. The local traditions that order them, e.g. a
  chapter within a part, aren't part of the schema either.
- **HTML and namespace attributes aren't kept.** `class`, `style` and `title`, `xml:space` and `xml:id`, and the
  attributes of other namespaces that any element may carry are left out.
- **A part has at most one owner.** A contained element belongs to the element it is nested in, so each composition
  has `max_count: 1` at the `to` end.
- **Dates and times may be partial.** Attributes that allow a date or a dateTime, e.g. `date` on `eventRef`, or a time
  or a dateTime, are `STRING`; a loader may convert them.

## Validation

The model is valid against the [JSON Schema](https://github.com/neo4j/ontology-graph-spec/blob/main/ontology-graph-spec.schema.json) and reports no issues for any of
the built-in validation sets, including `all`.
