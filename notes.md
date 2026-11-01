# Project Notes (raw material for README)

## Setup log
- Env: Windows, Python <your version>, VS Code, virtual env in .venv
- LLM: Groq, model `openai/gpt-oss-120b` (configured via .env)
- Problem: `llama-3.3-70b-versatile` returned 404 model_not_found (model retired).
  Fix: listed available models with the Groq API and switched. Model name lives in
  .env so it can be changed without code edits.




## Step 2: Corpus and chunking
- Corpus: 5 FastAPI tutorial pages (first-steps, path-params, query-params, body,
  handling-errors), downloaded by scripts/fetch_docs.py so it is reproducible.
- Strategy: split on Markdown headers (h1-h3) first, then RecursiveCharacterTextSplitter
  (size 800, overlap 120) for long sections. Each chunk keeps source + section heading.
- Result at size 800: 88 chunks (26 / 19 / 19 / 15 / 9 per file), size min/avg/max = 52/488/793.

### Chunk size experiment (overlap 120 at all sizes)
| chunk_size | total chunks | min / avg / max chars | observation |
|---|---|---|---|
| 500 | 127 | 52 / 353 / 497 | Too fragmented. Splits a note-callout from its closing `///` and separates explanations from their examples |
| 800 | 88 | 52 / 488 / 793 | Chosen. Mostly one idea per chunk, with sections intact |
| 1200 | 71 | 52 / 586 / 1191 | Chunks start to mix topics (an intro paragraph plus a note plus a warning in one chunk). More noise in matches, and a bigger prompt per chunk |

**Decision:** 800. It keeps explanations together with their examples while keeping each chunk focused. A chunk that mixes topics gets a "blurry" embedding that matches many questions weakly.

**Caveat:** I judged this by reading chunks and counts, not by measuring retrieval quality. Once the eval script exists (Step 8), I plan to re-test sizes on actual retrieval hits.

### Issues found
1. Docs contain `{* ... *}` placeholders where code examples belong. I strip them, but
   this means code examples are MISSING from chunks (e.g. "import BaseModel:" has no code).
   Planned fix: resolve placeholders by downloading the referenced .py files.
2. Headings contain anchor tags like `{ #request-body }`. This is noise in the text
   and in section labels. Planned fix: strip them with a regex.
3. A few very small chunks (min 52 chars), mostly a heading plus one line.
   May hurt retrieval. Planned: filter or merge chunks under ~100 chars.

## Decisions
- Header-aware splitting instead of fixed-size only, because docs are structured and
  I did not want one chunk mixing two topics.
- Stable hash chunk_id so re-ingestion does not create duplicates.

## What I would improve with more time
- (add as you think of them)

## Questions / things I don't understand yet
- (add as you think of them)





## Step 3: Retrieval experiments (before any grading or cleaning)
Setup: all-MiniLM-L6-v2 embeddings, ChromaDB cosine distance (lower = more similar), k=4, chunk size 800.

| # | query | best distance | top result relevant? | notes |
|---|---|---|---|---|
| 1 | How do I declare a path parameter? | 0.360 | Partly | Top hit was body.md "Declare it as a parameter". Path-params chunks ranked 2nd and 3rd. The main "Path Parameters" intro chunk (with the code example) did not appear |
| 2 | how to send JSON data to my API | 0.428 | No | Top hit was an OpenAPI JSON dump. Correct body.md chunk was rank 3 (0.535). Vocabulary mismatch: "send JSON data" vs docs' "request body" |
| 3 | how does it work | 0.785 | No | Vague query, all results were "Deploy" chunks, all distances > 0.78 |
| 4 | my API returns 422 error | 0.445 | Partly | Found validation/error-handling chunks, but none state what a 422 is. The docs show it in code output that I stripped |
| 5 | how do I deploy FastAPI with Docker (out of corpus) | 0.346 | No | Returned FastAPI Cloud deploy chunks, none mention Docker. Distance was LOWER than the valid query #1 |
| 6 | what is the capital of France (unrelated) | 0.869 | N/A | All distances > 0.86. Correctly far away |

### Findings
1. Vector search always returns k results, even with no good answer. It has no "I don't know".
2. Distance is not a reliable relevance signal. It separates totally unrelated queries (>0.78)
   from related ones, but fails on same-topic-wrong-answer cases (Docker: 0.346 beat a valid query).
   => An LLM grading step is justified. A distance threshold alone is not enough.
3. Vocabulary mismatch (query 2) => query rewriting/expansion should help.
4. Retrieval quality is limited by my data cleaning: missing code examples and
   `{ #anchor }` noise in headings/text.

### Hypotheses to test later
- H1: Rewriting queries (query analysis node) moves the correct chunk up for query 2.
- H2: Removing anchors and restoring code examples improves ranks for queries 1 and 4.
- H3: Chunks with distance > ~0.75 can skip LLM grading entirely (saves calls).
  Needs checking: not tested yet, so don't claim it in the README until measured.
- H4: The grader marks the Docker chunks as irrelevant (only needs to know they don't mention Docker),
  triggering a retry and then a correct "I don't know".

## Step 3.5 results: data cleaning
Changes: inlined code examples, stripped { #anchor } tags, converted admonitions, removed
HTML tags, dropped chunks < 60 chars. Re-indexed with `ingest --reset`: 88 -> 106 chunks.

| query | rank before -> after | best dist before -> after |
|---|---|---|
| path parameter | 2 -> 1 | 0.360 -> 0.419 |
| send JSON data | 3 -> 3 | 0.428 -> 0.490 |
| 422 error | 1 -> 1 | 0.445 -> 0.438 |
| vague (no answer) | - | 0.785 -> 0.803 |
| Docker (no answer) | - | 0.346 -> 0.359 |
| France (no answer) | - | 0.869 -> 0.889 |

Findings:
- H2 partly confirmed: 1 of 3 answerable queries improved in rank, none got worse.
- Distances are not comparable across re-chunking (text changed); rank is the useful metric.
- Docker (out of corpus) still scores 0.359, better than a valid query (0.419).
  Confirms distance cannot detect "answer not in corpus" -> LLM grading needed.
- "send JSON data" still ranks an OpenAPI JSON dump first (keyword "JSON" dominates).
  Expect query rewriting (H1) and grading to fix this. To verify in Step 6.
- My "python code in top-4" metric was weak (a split code block loses its opening fence).
  <add what diagnose_data.py showed here>
- Lesson: chunk IDs are content hashes, so any cleaning change requires `ingest --reset`.   

## Step 3.6 results: after fixing code indentation
Re-indexed: 102 chunks, indentation preserved (verified on the body.md BaseModel chunk).

| query | rank original -> cleaned -> indent-fixed | best distance now |
|---|---|---|
| path parameter | 2 -> 1 -> 1 | 0.419 |
| send JSON data | 3 -> 3 -> 1 | 0.539 |
| 422 error | 1 -> 1 -> 1 | 0.438 |
| vague / Docker / France (no answer) | - | 0.762 / 0.359 / 0.889 |

Findings:
- All 3 answerable queries now return the correct file at rank 1 (H2 confirmed).
- H1 (query rewriting) is still untested. The JSON query no longer needs it here, so
  the rewrite node may show a smaller gain than expected. Report honestly.
- Docker (not in corpus) = 0.359, still closer than every valid query. Distance alone cannot refuse.
- "code in top 4" counts presence, not relevance (France showed 3). Descriptive only.
- Open question: path-parameter top 4 had no code chunk. Check whether the intro chunk with
  the {item_id} example ranks just below k=4.


 ## Step 4 results: baseline RAG (control group, frozen)
| query | outcome | verdict |
|---|---|---|
| path parameter | "I don't know" (WRONG refusal) | FAIL: right chunk at rank 8 (0.623), top-4 were advanced sub-topics (0.42-0.51) |
| send JSON data | Answered; includes `Content-Type: application/json` and a raw HTTP example | PARTIAL: <fill in: is "application/json" in data/? yes/no>. Core Item(BaseModel) chunk not retrieved |
| Docker (not in corpus) | "I don't know" | PASS |
| France (unrelated) | "I don't know" | PASS |

Findings:
- Two baseline failure modes: (a) false refusal from low-ranked correct chunk, (b) answers that mix
  retrieved facts with model memory. Graph targets (a) via wide retrieval + grading + retry, (b) via hallucination check.
- Generation is faithful about refusing. The graph is NOT needed to stop out-of-corpus answers
  (in my tests). Its Docker path costs more calls for the same result (trade-off to report).
- Format bug: model emitted 【1】 not [1]; sources list included uncited chunks.
  Plan: structured output {answer, cited: [ints]}, return only cited sources.
- find_chunk: answer-bearing chunks at rank 8 and 15. H5 supported. H7 (code chunks embed poorly) unproven.
- Retrieval rank said "success" while the end-to-end answer failed => evaluate answers, not just rank.

### Step 4 follow-up: grounding check on the JSON answer
Searched data/ for "application/json": appears once, in the OpenAPI JSON example in first-steps.md,
a chunk the baseline did NOT retrieve. So the baseline's "Content-Type must be application/json"
claim was ungrounded (model memory). Confirms the need for a hallucination check node.



## Step 5: Graph skeleton (stub nodes)
State schema: question (original, never overwritten), search_query (rewritten), top_k, retry_count,
documents, relevant_documents, answer, sources, trace (append-only reducer).
Decisions:
- Grade/generate against the ORIGINAL question, not the rewrite (avoid drift).
- top_k grows on retries (4 -> 8 -> 12): Step 4 showed the right chunk at rank 8.
- Separate documents / relevant_documents so the trace can show what was filtered.
- max_retries=2 => at most 3 retrieval attempts.
- Verified loop with stubs: retry path and exhausted-retries path both behave as expected.

## Step 5 results: stub graph verified
Path-param stub: 0/4 -> rewrite (k=8) -> 2/8 -> generate, retry_count=1.
Docker stub: 3 retrievals (k=4,8,12), 2 rewrites -> fallback, retry_count=2.
Mermaid diagram auto-generated by graph.get_graph().draw_mermaid() (saved for README).


## Step 6A results (first real run)
| question | attempts | kept | outcome |
|---|---|---|---|
| path parameter | 1 | 1/4 | passed on 1 weak chunk (body.md "request body + path + query") |
| send JSON | 1 | 1/4 | OK: kept body.md intro chunk |
| 422 error | 1 | 3/4 | OK: validation-error chunks |
| Docker | 3 | 0/24 total | correct refusal, 6 LLM calls (vs 1 for baseline) |
| France | - | - | CRASH (see below) |

Findings:
1. Analyzer added "FastAPI" to the query. Every doc is about FastAPI, so it pulled in recap chunks
   and made the path-parameter ranking worse, even though the distance was the lowest I'd seen (0.268).
   => distances are not comparable across different queries, and distance != relevance (again).
2. "At least one relevant chunk" is too weak a success test: 1 loosely relevant chunk let the graph skip the retry.
   Fix: the grader also returns `sufficient` (do the kept chunks together answer the question?), and the router
   requires it (the "ambiguous" middle tier from the CRAG paper). Trade-off: more retries and cost.
3. Crash on France: the analyzer's prompt mentioned FastAPI, so for an off-topic question the model answered in
   plain text instead of calling the structured-output tool => groq tool_use_failed => unhandled exception.
   Fix: _call() wrapper + per-node failure behaviour: analysis falls back to the original question,
   grading fails closed (no relevant chunks), rewrite still increments retry_count so the loop always ends.
   Lesson: LLM output is unreliable; every node needs a defined failure behaviour.
4. Design decision: if retries are exhausted but some relevant chunks exist, answer from partial evidence
   (generator will be told evidence is partial); if none exist, refuse.
5. Known limitation: relevant chunks from an earlier round are discarded when a retry happens
   (each round's grading replaces the previous). Possible improvement: merge across rounds.
6. Idea (cost): a fast "out of scope" path for unrelated questions, to avoid ~6 LLM calls for "capital of France".

## Step 6A results (second run, after analyzer fix + sufficiency check)
| question | rounds (run 1 / run 2) | kept | outcome |
|---|---|---|---|
| path parameter | 2 / 3 | 1/8 then 4/12 | answered both times, via different rewritten queries |
| send JSON | 1 / 1 | 3/4 | ok |
| 422 error | 1 / 1 | 3/4 | ok |
| Docker | 3 / 3 | 0 | refused both times, grader reasons accurate |
| France | 3 / 3 | 0 | refused; in run 2 the analyzer hit a 429, handled by the fallback |

Findings:
- Round-1 retrieval for "declare path parameter" returns advanced sub-topic sections whose titles contain
  the phrase; the answering chunk ("Path parameters with types") only appears at k=8..12.
  Untested hypothesis: heading text dominates the embedding. Possible fix: embed chunks with a
  contextual header, or hybrid keyword+vector search (future work).
- Non-determinism: same question, 2 vs 3 rounds, different rewrites, even at temperature 0.
  => evaluation must repeat each question several times and report a pass rate.
- Sufficiency check: no trace yet showed (relevant > 0 AND sufficient=False), so its benefit is UNPROVEN.
- The rewriter may use model knowledge (it proposed "Path()"). That is acceptable for SEARCH queries;
  answers must still come only from retrieved passages.
- Cost per question: path param 4-6 LLM calls (1 analyze + 1-3 grade + 1-2 rewrite), Docker/France 6, baseline 1.
- Real 429 hit the analyzer; handled gracefully. Risk: a 429 in the grader fails closed -> false "I don't know".
  Mitigation: client max_retries=6 and a `degraded` flag in the API response when any node FAILED.


## Step 6B results (real run, 6 runs)
| question | rounds | final grounded | first draft flagged? | verdict |
|---|---|---|---|---|
| path parameter | 2 | True | no | correct; code copied with indentation; citations valid |
| send JSON (run 1) | 1 | True after 1 regen | YES | draft called an INVALID sample payload valid; check was right, regen fixed it |
| send JSON (run 2) | 2 | True | no | correct but thin (no code); contained a stitched "quote" built from 2 sentences |
| 422 error | 1 | False (flagged) | YES, twice | "default handler -> 422" not stated in prose (verify: search "422" in data/); regen kept the claim |
| Docker | 3 | None | n/a | correct refusal |
| France | 3 | None | n/a | correct refusal |
Cost: 6 LLM calls in every run (baseline 1); latency 12.9-48.4 s. Same question: 1 round in one run, 2 in another.

Findings:
- The check caught a subtle semantic error (describing an invalid payload as valid).
- The baseline's ungrounded "application/json" claim did NOT recur, but the check never had to catch it.
  Likely cause: stricter generation prompt. The check's detection rate is unmeasured => injection test in Step 8.
- Regeneration does not reliably remove flagged claims (422 case). Fallback = visible note naming the claims.
  Possible improvement: give the model its previous answer and ask for targeted deletions.
- Strict grounding ("true but not in the passages = unsupported") trades helpfulness for verifiability.
- Fixes made: (A) prompt forbids quotation marks around paraphrases, (B) note lists the unconfirmed claims.
- Sources: two chunks of one section show identical labels => API adds snippet + distance.
- Ideas, NOT yet tested: model tiering (gpt-oss-20b for grade/rewrite/check, 120b for generation);
  early refusal when best_distance > ~0.8 on round 1 (all my valid queries had best distance 0.27-0.54,
  but Docker scored 0.36, so this only helps unrelated questions; validate on an eval set first).




## Step 7A test results
   uvicorn app.main:app
- /health: ok, 102 chunks. /documents: 5 files, 16+29+24+23+10 = 102.
- /query (path parameter): correct answer, indented code, sources with snippet+distance, retries=1.
- BUG FOUND via the API: grounded=null, no check_grounding line in the trace, llm_calls=5 instead of 6.
  The answer was returned UNVERIFIED and `degraded` was false.
  Probable cause: my edit of check_grounding dropped its final `update["trace"]`/`return update` lines.
  A LangGraph node that returns None is legal: no state update, no error. A silent failure.
  Fix: restored the function; service.py now sets degraded=true when an answer exists but no
  check_grounding line is in the trace.
  Lesson: silent failures are worse than loud ones; verify steps by their trace/output, not by "no error".
- Finding: the 2 chunks that answered the question had the LARGEST distances of the 8 retrieved (0.653, 0.662).
  The rejected ones were closer. Distance != relevance, and retrieval + grading beats top-k + trust.
- Cosmetic: model used "[int]" in prose; added a prompt rule to reserve square brackets for citations.
- Note: uvicorn without --reload needs a manual restart after every code change.
- /query path parameter: 200, grounded=true, degraded=false, llm_calls=6, 1 retry, 9.2 s.
- /query "hi": 422 string_too_short (validated before any LLM call).
- /query Docker: 200, refused=true, grounded=null, sources=[], 6 calls, 10.1 s.
- Latency varied 9-49 s for the same call counts => dominated by API load, not by our code.
- Same question kept different chunks across runs (1 vs 2 relevant): non-determinism confirmed again.



## Step 7B: /ingest, DELETE /documents, /feedback

### What was built
| Endpoint | Purpose |
|---|---|
| POST /ingest | Files (multipart) and/or URLs; returns a per-item result |
| DELETE /documents/{source} | Remove one document and all its chunks |
| POST /feedback | Thumbs up/down (+ optional comment) tied to a query_id |
| GET /feedback/summary | Counts + recent thumbs-down questions |

### Design decisions
- **Re-ingest = replace.** Chunk IDs are content hashes, so an edited file would otherwise leave stale chunks
  next to the new ones (same bug found in Step 3.5). Ingest deletes the chunks of that `source` first.
- **Uploads are written to data/** so `python -m scripts.ingest --reset` can rebuild the whole index,
  including uploaded documents. An upload with an existing name replaces that document.
- **Validation:** .md / .txt / .html only; 1 MB per file or URL; UTF-8 only; max 10 files and 5 URLs per request;
  directory parts stripped from file names (`../../x.md` -> `x.md`); HTML converted to Markdown
  (scripts, styles, nav, footer removed) before chunking.
- **URL safety (SSRF):** the host is resolved and non-public addresses are refused (localhost, private ranges);
  re-checked at every redirect hop (max 3); download size cap and 15 s timeout.
  URL-derived names get a host prefix, so a web page can never overwrite a corpus file.
  *Known limitation:* DNS rebinding (the host resolving differently between the check and the request) is not covered.
- **Per-item results:** one bad file does not cancel the others. Status 200 if at least one item was indexed,
  422 if nothing could be ingested.
- **Concurrency:** a threading.Lock around index changes. Chroma persists to local disk, so this is a
  single-process design (a multi-worker deployment would need a server-based vector store).
- **Feedback storage:** SQLite (built in, no setup). Every /query is logged, so /feedback needs a real query_id
  (404 otherwise); one rating per query (a later rating replaces the earlier one); rating restricted to up/down (422).
  Logging never fails an answer: if the log write fails, the answer is still returned.
- /feedback/summary lists recent thumbs-down questions = candidates for the evaluation set.

### Problems and how they were solved
- **Swagger UI shows the `files` field as `array<string>`, with no file picker** (also after changing the parameter to
  `list[UploadFile] | None`). It is a display limitation of the docs page: the endpoint itself accepts real files.
  Uploads are tested with `curl.exe -F`; URLs can be tested in Swagger. A browser upload page would be the optional UI.
- **Silent failure found via the API:** `check_grounding` returned nothing after an edit (grounded=null, no trace line,
  degraded=false). A LangGraph node that returns None is legal and produces no error. Fixed, and the API now sets
  `degraded=true` when an answer exists but no check_grounding line is in the trace.

### Tests run (all on the live API)
| # | Test | Result |
|---|---|---|
| 1 | `curl.exe -F "files=@docker_notes.md"` | indexed 1 file, 2 chunks, store 102 -> 104 |
| 2 | GET /documents | 6 documents, 104 chunks |
| 3 | Same file again | store unchanged at 104 (replacement, no duplicates) |
| 4 | Docker question after ingest | answered, cites docker_notes.md, grounded=true |
| 5 | /feedback with the real query_id | 200 "Feedback recorded" |
| 6 | /feedback unknown id; rating "maybe" | 404; 422 |
| 7a | upload fake.pdf | <HTTP code, detail "Unsupported file type '.pdf'..."> |
| 7b | URL http://127.0.0.1:8000/health | <HTTP code, detail "URL points to a non-public address (blocked)"> |
| 8a | DELETE /documents/docker_notes.md | <200, chunks_removed: 2> |
| 8b | GET /documents | <5 documents, 102 chunks> |
| 8c | Docker question again | <refused=true, grounded=null, sources=[]> |
| 9 | GET /feedback/summary | <up=1, down=0> |

### Demo that shows the whole idea
Docker question **refused** -> ingest docker_notes.md -> **answered with a citation to it** -> delete -> **refused again**.
Same question, same code: only the corpus changed.

### Limitations / what I would improve
- No authentication or rate limiting on /ingest and /query (anyone who can reach the API can add documents or spend LLM calls).
- Feedback is stored but not used to improve retrieval; it only feeds the evaluation set.
- PDF ingestion is not supported (Markdown, text and HTML only).
- Single-process design (local Chroma + lock).



## Step 8A: Automated tests (pytest, no API calls)
- 32 tests: routing logic (7), citation parsing (5), ingestion/chunking/validation/SSRF (7),
  full-graph flow with a fake LLM and fake vector store (5), HTTP layer with TestClient (8).
- Fakes: `_call` (structured LLM calls), `get_llm`, `get_vectorstore` are monkeypatched in the graph tests;
  the API tests use a throwaway SQLite file and a fake store. They verify WIRING (routing, retry counter,
  termination, status codes), not answer quality: that is the evaluation's job (Step 8B).
- Covered behaviours: retry grows k, retries bounded then refusal, grader failure fails closed and is traced,
  ungrounded answer regenerated once then flagged with the claims, code fences are not headings,
  indentation survives chunking, path traversal in file names stripped, private/non-http URLs blocked,
  422/404/503/500 status codes, 500 does not leak internals, second rating replaces the first.
- Mutation check: changed `<` to `<=` in the retry rule -> <n> tests failed; removed `return update` from
  check_grounding (the silent failure from Step 7A) -> <n> tests failed. Both restored afterwards.
- Result: <N passed in X s>
- Not tested (known gaps): /ingest HTTP endpoint, real LLM behaviour, real vector search.

## Step 8A results
- 32 tests pass in ~2-7 s with no API calls.
- Mutation check 1: `<` -> `<=` in the retry rule: 4 tests failed (2 routing, 2 graph-flow; the graph tests ran out
  of scripted grader rounds = an extra retry happened). Restored: 32 pass.
- Mutation check 2: removed `return update` from check_grounding (the Step 7A silent failure): 3 graph-flow tests failed. Restored: 32 pass.
- Tests verify wiring, not answer quality (that is Step 8B). Not covered: /ingest endpoint, real LLM, real vector search.



## Step 8B: Evaluation (baseline vs graph)
Setup: 17 questions (13 answerable with expected source file + must-include keyword, 4 not in the corpus),
2 repeats each, both systems, temperature 0. 5 questions were used during development (flagged dev);
results are reported for all questions and for the unseen ones only.
Correctness check = answer contains a key term (crude: it can pass a wrong answer or fail a correct one),
so I read every failure manually. Sources are not compared: the baseline lists all retrieved chunks, the graph only cited ones.
Results: <paste the summary table>
Cost: <baseline 1 call / x s; graph mean calls / mean latency / mean retries>
Failures I read: <real mistakes vs checker false failures>
Surprises: <...>
Limitations of this evaluation: small question set (17), keyword-based correctness, 2 repeats, questions written by me
(and partly by looking at the docs), LLM non-determinism, one model/provider.

## Step 8B: failures read manually
- q01 baseline rep 1: correct rule, example from a different section (file_path), no `item_id`: checker miss, weak answer.
- q01 baseline rep 2: real false refusal (ranking failure from Step 4).
- q04 graph rep 1: correct but never says `BaseModel`: checker miss.
- q11 graph rep 2: real false refusal (trace not saved in this run; degraded status per merged report: <fill in>).
=> after adjudication: baseline 1 real failure, graph 1 real failure out of 26 answerable runs each. A tie.
- Merged report (run 033609 + clean re-run of q14-q17): <paste summary table>.
- Degraded graph runs excluded: <n> of <m>. Cause: free-tier 429s (the graph makes ~5x the calls of the baseline, so it
  fails more often under the same limit). Excluding them improves the accuracy figure but hides this reliability cost, so both are reported.



## Step 8C: grounding-check evaluation (planted false claims)
Method: for 4 documentation passages, 1 correct answer (control) + 2-3 answers with one planted false claim
(contradiction / outside_knowledge / fabricated), 3 repeats. Uses the real GROUNDING_PROMPT and GroundingCheck schema
via nodes._call, one passage per check. The planted claims were written by me and are clear-cut: real hallucinations are
subtler, so the catch rate is an optimistic upper bound.
Results:
- Planted false claims caught: <x>/<n>  (contradiction <a>/<b>, outside_knowledge <c>/<d>, fabricated <e>/<f>)
- Correct answers wrongly flagged: <y>/<m>
- Missed plants: <list>   False alarms: <list, and whether each was a real false alarm or my test design>
Interpretation: <...>

## Step 8B merged report (first pass)
63 of 76 runs counted (4 API errors, 9 degraded excluded).
| System | Answerable correct | Falsely refused | Unanswerable refused |
|---|---|---|---|
| baseline (all) | 24/26 | 1/26 | 8/8 |
| graph (all) | 19/21 | 1/21 | 8/8 |
| baseline (unseen) | 20/20 | 0/20 | 4/4 |
| graph (unseen) | 14/15 | 1/15 | 4/4 |
Cost: baseline 1 call / 2.1 s; graph mean 5.4 calls / 33.3 s / 0.9 retries.
Grounding check on answered graph runs: True 18, False 2 (of 20).
Reading:
- Accuracy tie. Refusals tie (the baseline prompt already refuses correctly). The graph won only q01, a question I tuned on.
- Coverage gap: graph has 0 counted runs for q05 and q09 and 1 for q13 (degraded runs excluded), so its 21 runs cover 15 questions
  vs 26 runs / 17 questions for the baseline. Re-run for the graph only: <result>.
- Reliability under free-tier limits: 9/38 graph runs degraded vs 4/38 baseline errors (confounded by run order).
  A pipeline making ~5 calls per question hits per-minute limits sooner than one making 1.
- The graph's benefits are not in accuracy here: traceability, cited-only sources, a grounding check, an explicit refusal path.

## Step 8C first pass (grounding check, planted false claims)
Only 17 of 42 checks completed (rate limit): ~1 repetition. 12/12 planted claims flagged (contradiction 7/7,
outside_knowledge 3/3, fabricated 2/2); 1/5 controls flagged.
The flagged control (case B) was the GET sentence. Probable cause: my needle located the chunk with "(the most common)",
and the GET sentence sits in the next chunk, so the claim was not in the passage shown. The check was strictly right.
<confirmed / not confirmed by show_chunk>. Case B was rewritten to anchor on the GET sentence; re-run: <result>.
Caveat: planted claims are mine and clear-cut, so the catch rate is an optimistic upper bound.


## Gemini run (after Groq rate limits)
- Switched via .env (LLM_PROVIDER=gemini, LLM_MODEL=gemini-3.5-flash-lite). All calls go through get_llm(); embeddings are local, so no re-indexing.
- Free-tier limits for my project (AI Studio rate-limit page): RPM <x>, TPM <y>, RPD <z>.
- Pitfall: scripts/check_setup.py built a Groq client directly, so it ignored LLM_PROVIDER and sent the Gemini model name to Groq (404).
  Fix: all scripts must use get_llm(). Lesson: one place builds the model, everything else calls it.
- Structured output with Gemini (analyze / grade / rewrite / grounding check): <worked / problems>.
- Results are reported separately per model (prompts were developed on gpt-oss-120b).


## Gemini bug: content blocks (found via the evaluation)
Symptom: all 34 baseline runs ERROR in ~2 s; graph answers displayed as "[{'type': 'text', 'text': ..., 'extras': {...}}]".
Cause: Gemini returns reply content as a LIST of blocks (Groq returns a string). The baseline returned the list,
the evaluation then crashed on `.replace`; the graph wrapped it in str(), so the answer was the Python repr (literal \n, signature).
Consequence: the first Gemini evaluation was invalid (the keyword check matched inside the repr, and the grounding check verified garbage).
Groq results are unaffected. Files quarantined in evaluation/results/invalid_gemini_repr_bug/.
Fix: text_of() in app/llm.py flattens blocks to text; used in generate, the baseline and check_setup; 3 unit tests added (35 tests).
Lesson: "pass" results can hide a data-format bug, so read the raw answers, not just the pass rate. A provider switch is a
behavioural change, not a config change: every consumer of .content had to be checked.
Also: gemini-3.5-flash-lite ignores `temperature` (fixed sampling defaults), so determinism cannot be pinned; the same grounding-check
input produced different verdicts in two repetitions.

## Step 8C on gemini-3.5-flash-lite (valid)
28 checks, 0 errors. Planted false claims caught 20/20 (contradiction 12/12, fabricated 4/4, outside_knowledge 4/4).
Controls flagged 1/8 (case A rep 1, a sentence I wrote that is not in the chunk; passed in rep 2 = non-determinism).
Caveat: planted claims are mine and clear-cut, so this is an optimistic upper bound. Compare with the Groq run (12/12 caught,
only 17 of 42 checks completed because of rate limits).

## Step 8B on gemini-3.5-flash-lite (valid run, after the content-block fix)
File: run_20261101_124310.jsonl, 17 questions x 2 reps x 2 systems. Reported separately from the Groq run (different model).
Raw FAIL lines: baseline 6 of 26 answerable + q14 (Docker) 2 of 2; graph 2 of 26 answerable; all other refusals passed.
Adjudication (answers read manually): <fill in per answer: real mistake / checker miss / real hallucination / refusal in other words>.
Report table: <paste>
Finding: <if the baseline answered Docker from model memory: "On Gemini the baseline answered an out-of-corpus question; the graph
refused it both times. On gpt-oss-120b the baseline refused correctly, so the baseline's grounding depends on the model, while the
graph's retry/grade/refuse path did not." Otherwise state what was found.>
Cost: baseline ~2 s, 1 call; graph ~7-14 s, ~5-6 calls.
Caveat: the keyword check is crude and the question set (17) is small; each model was run once (2 reps).

## Step 8B on gemini-3.5-flash-lite, first valid run (index v1) and what it revealed
Run run_20261101_124310.jsonl: baseline 20/26 answerable by the checker, graph 24/26; refusals baseline 6/8, graph 8/8.
Adjudication (I read the failing answers):
- q14 Docker: both baseline answers refuse IN OTHER WORDS ("there is no mention of how to deploy FastAPI with Docker").
  The checker only recognised "I don't know", so the 6/8 was a measurement artifact; in substance both systems refused 8/8.
  (Gemini paraphrases the instructed refusal; gpt-oss-120b used the exact phrase: models differ in instruction-following.)
- q12 baseline rep 2 was a FALSE PASS: it mentions ":path" while saying the excerpt does not detail it. Keyword changed to "file_path:path".
- q01 baseline: cites the path-containing-paths and Enum sections, no item_id example: the same ranking failure seen with Groq.
  The graph's retry (k=8) recovered it both times. q12 (not a dev question) shows the same pattern: baseline incomplete, graph correct.
- Weak answers by my reading: baseline ~5 of 26 (q01 x2, q12 x2, q04 rep 2), graph 1 of 26 (q04 rep 1, honest about the gap).
  Most passes were not read; pass rates are upper bounds.
DATA BUG found via q06: the docs colour terminal examples with <font>/<span> tags, which clean_markdown did not strip, so answers contained
`$ <font color="#4E9A06">uv run fastapi</font> dev`. Fixed (regex + test), index rebuilt (--reset), final run on index v2.
The Groq results and this first Gemini run used index v1 and are historical.
Lesson: pass/fail numbers need reading; a measurement artifact (exact-phrase refusal check) almost produced a false story about the baseline.