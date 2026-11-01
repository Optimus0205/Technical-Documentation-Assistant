# Evaluation report (run_20261101_033609.jsonl, run_20261101_092723.jsonl, run_20261101_101100.jsonl)

82 runs: 64 counted, 4 excluded (API errors), 14 excluded (degraded: a node failed, so the result is unreliable).

| System | Questions | Answerable: correct | Answerable: falsely refused | Unanswerable: correctly refused |
|---|---|---|---|---|
| baseline (all questions) | 17 | 92% (24/26) | 4% (1/26) | 100% (8/8) |
| graph (all questions) | 16 | 91% (20/22) | 5% (1/22) | 100% (8/8) |
| baseline (unseen questions only) | 12 | 100% (20/20) | 0% (0/20) | 100% (4/4) |
| graph (unseen questions only) | 11 | 94% (15/16) | 6% (1/16) | 100% (4/4) |

## Cost and behaviour (counted runs only)

- Baseline: 1 LLM call, mean latency 2.1 s
- Graph: mean 5.3 LLM calls, mean latency 32.9 s, mean retries 0.8
- Graph answers verified by the grounding check: grounded=True 19, False 2, None 0 (of 21 answered)

## Per question (passes / counted runs)

| id | kind | question | baseline | graph |
|---|---|---|---|---|
| q01 | answer (dev) | How do I declare a path parameter? | 0/2 | 2/2 |
| q02 | answer | How do I restrict a path parameter to predefined values | 2/2 | 2/2 |
| q03 | answer | How do I make a query parameter optional? | 2/2 | 2/2 |
| q04 | answer (dev) | how to send JSON data to my API | 2/2 | 1/2 |
| q05 | answer | How do I return a 404 error from an endpoint? | 2/2 | 1/1 |
| q06 | answer | How do I start the development server? | 2/2 | 2/2 |
| q07 | answer | How do I add custom headers to an HTTP error? | 2/2 | 2/2 |
| q08 | answer | How do I set default values for query parameters such a | 2/2 | 2/2 |
| q09 | answer | Which decorator defines a GET endpoint? | 2/2 | - |
| q10 | answer (dev) | my API returns 422 error | 2/2 | 2/2 |
| q11 | answer | Why must /users/me be declared before /users/{user_id}? | 2/2 | 1/2 |
| q12 | answer | How do I accept a path containing slashes as a path par | 2/2 | 2/2 |
| q13 | answer | How do I override the default validation error handler? | 2/2 | 1/1 |
| q14 | refuse (dev) | how do I deploy FastAPI with Docker | 2/2 | 2/2 |
| q15 | refuse (dev) | what is the capital of France | 2/2 | 2/2 |
| q16 | refuse | How do I add JWT authentication to FastAPI? | 2/2 | 2/2 |
| q17 | refuse | How do I connect FastAPI to a PostgreSQL database? | 2/2 | 2/2 |

## Failures (read these: the keyword check is crude)

- rep 1 q01 baseline: 'You declare a path parameter by placing its name inside curly braces in the route path. For example, a path operation that receives a parameter called\u202f`file_path` would be defined with a route like:  '
- rep 1 q04 graph: 'Send the data in the request body of a\u202f`POST` (or\u202f`PUT`,\u202f`DELETE`,\u202f`PATCH`) request, using JSON. Define a Pydantic model for the body and then post a JSON payload, e.g.:  ```json {   "title": "towel",'
- rep 2 q01 baseline: "I don't know based on the documentation."
- rep 2 q11 graph: "I don't know based on the documentation."

## Excluded as degraded

- rep 1 q05 graph (23.0 s, refused=False)
- rep 1 q09 graph (30.7 s, refused=False)
- rep 2 q05 graph (22.3 s, refused=False)
- rep 2 q09 graph (28.2 s, refused=False)
- rep 2 q13 graph (16.8 s, refused=False)
- rep 2 q14 graph (56.7 s, refused=True)
- rep 2 q15 graph (3.4 s, refused=True)
- rep 2 q16 graph (3.3 s, refused=True)
- rep 2 q17 graph (3.4 s, refused=True)
- rep 1 q09 graph (4.2 s, refused=True)
- rep 1 q13 graph (3.5 s, refused=True)
- rep 2 q05 graph (3.4 s, refused=True)
- rep 2 q09 graph (48.2 s, refused=True)
- rep 2 q13 graph (3.5 s, refused=True)

## Excluded because of API errors

- rep 2 q14 baseline
- rep 2 q15 baseline
- rep 2 q16 baseline
- rep 2 q17 baseline