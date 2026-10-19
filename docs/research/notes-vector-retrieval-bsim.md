# Similar-Function Retrieval for Matching Decompilation (embeddings, vector DBs, BSim, coddog, 2D plots)

Research date: 2026-10-19. NOTE: written to the plan-file path because plan mode forbade writing to the requested scratchpad path. Copy to `...\scratchpad\research_notes\ReverseApoc kickoff research\vector_retrieval_bsim.md`.
Tooling note: Tavily was down; WebSearch/WebFetch only. WebFetch returns model-summarised pages, so quotes are paraphrases of fetched content. Many search snippets were secondary; confidence is flagged per item.

## 1. How much does similar-example retrieval improve matching rates?

### Takeaway
No published experiment isolates the match-rate gain from retrieved similar examples. Macabeus reports only "more stable and predictable than random examples" and a pipeline-wide 74% on 60 functions, and Chris Lewis reports qualitative value from coddog-based similar-function retrieval plus a scheduling change. LLM4Decompile/Nova-style papers do not test this retrieval setup. Treat the benefit as plausible but unquantified.

### Cited Findings
- Macabeus's first post (voyage-code-3 era): after switching to embedding-based example selection, "example-based decompilation became more stable and predictable than when examples were chosen at random". No percentages given. — [Gambiconf: Finding Better Examples](https://gambiconf.substack.com/i/166437312/finding-better-examples)
- Plan there: pre-compute embeddings of all assembly functions, compare with cosine similarity, replacing heuristic matching with semantic similarity. — [same](https://gambiconf.substack.com/i/166437312/finding-better-examples)
- Benchmark post (Mizuchi): prompt includes up to 5 already-decompiled functions with similar assembly (embedding of normalized asm, model jina-embeddings-v2-base-code), plus callers' signatures, target C declaration, callees' signatures, type defs. — [Can LLMs Really Do Matching Decompilation?](https://gambiconf.substack.com/p/can-llms-really-do-matching-decompilation)
- Benchmark: 60 functions (30 Sonic Advance 3, 30 Animal Forest; 10 easy/10 medium/10 hard each), Claude Sonnet 4.6, 3 runs per game, 12 attempts/function; average match rate 74%, best run 80% (SA3 run 2); 53/60 (88%) same outcome across runs; 12 functions never matched. — [same](https://gambiconf.substack.com/p/can-llms-really-do-matching-decompilation)
- That benchmark does NOT include a with/without-examples ablation; it compares programmatic tools (m2c, decomp-permuter) vs the full pipeline. The author says the tier-scoring algorithm does not account for the number and proximity of examples. — [same](https://gambiconf.substack.com/p/can-llms-really-do-matching-decompilation)
- Earlier Macabeus post (Jan 2025): simple prompt gave 96% match on one function with Sonnet 3.5; adding hand-picked examples (functions calling the same internals) + context did not reproduce that 96%. Anecdote, n=1 function. — [Development Journey on Game Decompilation Using AI](https://gambiconf.substack.com/p/development-journey-on-game-decompilation)
- Chris Lewis (Snowboard Kids 2): after one-shot LLM decomp took the project from ~25% to ~58% matched, he built a tool to find similar matched functions for an unmatched one and re-prioritised unmatched functions with similar matched counterparts. Similar matches "proved invaluable"; project moved to ~75% before stalling. No match rate is attributed to the similarity tool alone. — [The Long Tail of LLM-Assisted Decompilation](https://blog.chrislewis.au/the-long-tail-of-llm-assisted-decompilation/)
- Lewis explicitly chose exact pairwise similarity over embeddings: embeddings suit fast retrieval over huge corpora, but with a few thousand candidates and no time pressure exact comparison is feasible. His first composite score (n-grams, CFG patterns, memory-offset patterns, frame size) was judged overcomplicated; he now uses coddog (bounded Levenshtein over opcode sequences, normalised 0-1) and sometimes both. The two methods picked different top candidates in 90.6% of cases on remaining unmatched functions (not evaluated on identical sets). — [same](https://blog.chrislewis.au/the-long-tail-of-llm-assisted-decompilation/)
- Secondary: Willison summary says progress went from ~20-25% in early Sept 2025 to 45% by 2 Dec 2025 with Claude Code non-interactive + Opus 4.5 (earlier phase, before similarity tool). — [Simon Willison](https://simonwillison.net/2025/Dec/6/one-shot-decompilation/)
- LLM4Decompile-End-6.7B: 45.37% re-executability on HumanEval-Decompile, 17.98% on ExeBench vs GPT-4o 16.01%/3.78%; this is fine-tuned model decompilation with no retrieval, and measures re-executability not byte-matching. — [LLM4Decompile, arXiv 2403.05286](https://arxiv.org/html/2403.05286v3)
- Nova (ICLR 2025): hierarchical attention + contrastive learning for assembly; reports +14.84 to +21.58 absolute points Pass@1/Pass@10 over prior decompilation techniques, and up to +6.17% Recall@1 on binary code similarity detection. Not a retrieval-augmented few-shot setup. — [Nova, ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/ef283d62b4bce30854a8d4827f331229-Abstract-Conference.html)
- FidelityGPT (arXiv 2510.19615) uses retrieval-augmented generation with a database of distortion examples (k=1 line-level retrieval), reporting 89% detection accuracy and 64% corrected-fix rate. It retrieves error patterns, not similar functions. — [FidelityGPT](https://arxiv.org/pdf/2510.19615)

### Inferences
- The only quantified numbers (74% Mizuchi; Lewis's 25%→58%→75%) are whole-pipeline, so retrieval's marginal value cannot be isolated. A cheap own-ablation (same N functions, k=0 vs k=5 vs random-5) on ReverseApoc would be the only real evidence.
- Retrieval likely helps most when the corpus has many already-matched near-duplicates (same compiler, same idioms). Watcom C on one game plus two sibling executables is favourable; early in the project, with few matched functions, benefit will be small.
- Retrieval matters twice: as few-shot examples, and as a scheduler (Lewis: tackle unmatched functions whose neighbours are already matched).

### Gaps
- Did not find DeGPT details or any paper doing retrieved-similar-function few-shot for LLM decompilation (searches returned FidelityGPT/SK2Decompile only; SK2Decompile PDF was unreadable). Not verified whether jTrans/asm2vec/PalmTree results translate to this use.
- Lewis's primary posts on exact match counts per technique were not retrieved beyond "Long Tail".

## 2. Embedding model options for x86 assembly

### Takeaway
Macabeus started with Voyage voyage-code-3 (API) and later used jina-embeddings-v2-base-code (local, Apache-2.0, ~161M params) in Mizuchi. Anthropic does not make an embedding model and points to Voyage; voyage-code-4 ($0.12/M tokens, 200M free) is now the Voyage code model. For a 5-20k function corpus, a local CPU-runnable model is sufficient and avoids API dependence; none of the general code models is shown to be specifically good on x86 asm.

### Cited Findings
- Anthropic: "does not offer its own embedding model"; recommends Voyage AI (now by MongoDB); lists voyage-code-4 for "code retrieval and agentic coding" (32k context, 1024 default dim, Matryoshka 256/512/2048), voyage-code-3 as previous generation, and voyage-4-nano as open-weight (Apache 2.0, Hugging Face, 2048 default dim, not available through the API). — [Anthropic embeddings docs](https://platform.claude.com/docs/en/build-with-claude/embeddings) (old docs.anthropic.com URL 301-redirects here)
- voyage-code-4 (blog dated 2026-08-13): $0.12/M tokens ("a third below voyage-code-3"), first 200M tokens free, dims 2048/1024/512/256, claims +13.98% over voyage-code-3 on traditional code search and +27.54% on agentic code retrieval (vendor benchmarks, source code, not assembly). API-only per blog (no open weights stated). — [Voyage blog](https://blog.voyageai.com/2026/08/13/voyage-code-4/)
- Voyage pricing page: voyage-code-3 $0.18/M tokens; page conflicts on whether voyage-code-3 still has free tokens (text says first 200M free; older-models note says none); voyage-code-4 $0.12/M with 200M free. — [Voyage pricing](https://docs.voyageai.com/docs/pricing)
- Macabeus's first post: used Voyage voyage-code-3 via HTTP API (not local), batches of 40 functions/request, ~2-3 min to embed all of Sonic Advance 3; chose it because the RxDB tutorial's Hugging Face model "isn't made for code". — [Finding Better Examples](https://gambiconf.substack.com/i/166437312/finding-better-examples)
- Later (Mizuchi): jina-embeddings-v2-base-code run via Python subprocess (torch + transformers, uses MPS on Apple Silicon else CPU), ~2-3 GB venv install, weights cached in ~/.cache/huggingface, incremental re-index of new/changed functions only, vectors stored in `mizuchi-db.json`. — [Mizuchi README](https://github.com/macabeus/mizuchi)
- jina-embeddings-v2-base-code: ~161M params (listed as 0.2B, F16), Apache-2.0, trained at 512 tokens with ALiBi up to 8192, English + 30 programming languages including C++, mean pooling, `trust_remote_code=True`, usable via sentence-transformers/Transformers/Transformers.js or Jina API. Embedding dimension not stated on the fetched page. — [HF model card](https://huggingface.co/jinaai/jina-embeddings-v2-base-code)
- jina-code-embeddings (Sept 2025): 0.5B (494M) and 1.5B models on Qwen2.5-Coder backbones, GGUF quantizations; vendor-reported 78.41% / 79.04% average over 25 code benchmarks vs voyage-code-3 79.23%. Vendor numbers on source code; no independent head-to-head found. — [Jina announcement](https://jina.ai/news/jina-code-embeddings-sota-code-retrieval-at-0-5b-and-1-5b); [arXiv 2508.21290](https://arxiv.org/html/2508.21290v1)
- CLAP (arXiv 2402.16928): contrastive language-assembly pre-training, trained on 195M binary/explanation pairs from Ubuntu packages compiled with GCC and Clang at several optimisation levels; weights/code released at Hustcw/CLAP. — [arXiv](https://arxiv.org/abs/2402.16928)
- Nova reports state-of-the-art binary similarity Recall@1 (+6.17%) as a side result. — [ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/ef283d62b4bce30854a8d4827f331229-Abstract-Conference.html)

### Inferences
- Specialised binary models (CLAP, jTrans, PalmTree, asm2vec) are trained on GCC/Clang-compiled Linux x86-64/ARM/MIPS code; the ReverseApoc target is 16/32-bit Watcom output with DOS idioms, so out-of-distribution. Suggest not adopting before testing. (Training-set claim for CLAP is cited; the Watcom-OOD conclusion is my inference.)
- Practical default: jina-embeddings-v2-base-code on CPU (small, Apache-2.0, proven by Macabeus). Functions are small asm text so 512-8192 token limit is rarely a problem; batch embed 5-20k functions in minutes to tens of minutes on CPU (estimate, not measured).
- Normalisation of the asm text (strip addresses, labels, relabel jump targets, mask immediates/offsets) probably matters more than model choice; Macabeus normalises before embedding, Lewis got value from opcode-only Levenshtein.
- Voyage is a fine optional upgrade (cheap: a 20k-function corpus at a few hundred tokens each is ~10M tokens, so well inside 200M free tier / pennies), but adds API key + network dependency and non-deterministic model deprecation risk. Not needed for the matching use case. (Token estimate is mine.)
- Cheap optional baseline: opcode n-gram TF-IDF or coddog-style edit distance, which requires no model at all.

### Gaps
- Not verified: nomic-embed-code, Qodo-Embed, OpenAI text-embedding-3, jina-embeddings-v3/v4, BinaryAI, jTrans, PalmTree model cards/licences/sizes (searches returned nothing usable). voyage-4-nano size/CPU feasibility not fetched.
- No independent benchmark of any embedding model on x86 assembly retrieval was found.
- jina v2 embedding dimension not confirmed from the fetched card.

## 3. Storage for ~5,000-20,000 functions

### Takeaway
At this scale exact brute-force search is instant, so the choice is about simplicity. Recommended: a single SQLite file (functions table + embeddings as BLOB), searched with numpy or sqlite-vec; or even plain numpy `.npy` plus SQLite metadata. sqlite-vec fits "single file, no server, Python-native, Docker-friendly" but is pre-v1.

### Cited Findings
- sqlite-vec: README states "pre-v1, so expect breaking changes"; dual Apache-2.0/MIT; `pip install sqlite-vec`; latest release v0.1.9 published 2026-03-31 ("Bug fix for DELETE operations"). Describes itself as "extremely small, fast enough". — [sqlite-vec repo](https://github.com/asg017/sqlite-vec); [latest release API](https://api.github.com/repos/asg017/sqlite-vec/releases/latest)
- Mizuchi stores embeddings in a plain JSON file (`mizuchi-db.json`) alongside asm, C source, and call graphs; no vector DB. RxDB was used in the first prototype (local-first NoSQL, in-memory capable). — [Mizuchi README](https://github.com/macabeus/mizuchi); [Finding Better Examples](https://gambiconf.substack.com/i/166437312/finding-better-examples)
- Comparison write-ups (single-developer/vendor, directional): LanceDB favoured for single-user local use (columnar, metadata filtering, write stability); Chroma easiest to prototype but keeps index in RAM and one note cites HNSW corruption on abrupt exit; FAISS is a library without persistence/metadata. — [LanceDB ADR (glama.ai)](https://glama.ai/mcp/servers/@camilojourney/codesight/blob/7a2e5e7f7ebc6c10653253bd035e9e16e4de11c4/docs/decisions/0001-lancedb-over-chromadb.md); [Actian comparison](https://www.actian.com/blog/developer/comparing-embedded-vector-databases/)

### Inferences (general knowledge, not sourced in this session)
- Size maths: 20,000 x 1024 float32 = ~82 MB (768-dim = ~61 MB). A full cosine scan with numpy matmul takes milliseconds. No ANN index is needed.
- Ranking for this project (simplicity first): (1) SQLite + numpy brute force (zero extra dependency beyond stdlib+numpy; embeddings as BLOB, retrieval = one matmul), (2) sqlite-vec if SQL-side KNN with filters (e.g. only "matched" functions) is wanted, (3) LanceDB (Python-native, single directory, good filtering) (4) Chroma, (5) FAISS (no metadata) (6) Qdrant/pgvector (server; overkill, Docker compose service needed) (7) RxDB (JS-oriented; wrong ecosystem for a Python/uv project).
- Whichever is chosen, keep the source of truth (asm text, normalised text, hash, model name/version) in SQLite so embeddings can be rebuilt incrementally by content hash, as Mizuchi does.
- Filtering "only already-matched functions" is the key query; easy in SQL (sqlite-vec, pgvector) or via post-filtering top-N in numpy.

### Gaps
- No benchmark of sqlite-vec at 20k vectors found; pgvector, Qdrant, RxDB docs not fetched this session; Python 3.14/3.15 wheel availability for sqlite-vec, LanceDB, chromadb, faiss-cpu, torch NOT checked (important risk: native wheels often lag new Python versions).

## 4. Ghidra BSim (11.3+/12.x): scripting and export

### Takeaway
Macabeus's "limited scripting" complaint is still largely accurate for ready-made search scripts, but BSim is scriptable at three levels: the `bsim` CLI (create DB, generate/commit/dump signature XML), headless Java/Python scripts via analyzeHeadless, and the Java API (GenSignatures, QueryNearest) callable from PyGhidra. No official turnkey "query whole program headlessly and dump results" exists in the docs; the maintained example is an overview-query script. Signatures can be exported to XML but BSim vectors are hashed features, not dense embeddings, so they do not drop into a cosine/UMAP pipeline.

### Cited Findings
- Macabeus: BSim splits decompiler output into small chunks, assigns each a locality-sensitive hash, and compares via dot-product similarity; he deferred it as Voyage was already working and Ghidra integration needs "a lot of plumbing"; "the scripting support seems limited" (a 1-to-1 comparison example exists, nothing searching the whole codebase); unclear how to chart hash-based vectors. — [Finding Better Examples](https://gambiconf.substack.com/i/166437312/finding-better-examples)
- BSim description: plugin for finding structurally similar functions across large collections; decompiler-based so it matches across compilers, architectures, small source changes. — [Ghidra BSim tutorial](https://ghidra.re/ghidra_docs/GhidraClass/BSim/README.html)
- Backends: H2 (standalone local file, no dependencies), PostgreSQL (custom distribution bundled with Ghidra), Elasticsearch (needs existing server). — [PenTestPartners BSim guide](https://www.pentestpartners.com/security-blog/fuzzy-matching-with-ghidra-bsim-a-guide/) (article used Ghidra 11.1.1; older)
- CLI (Ghidra 12.0 help): `createdatabase` (templates large_32, medium_32, medium_64, medium_cpool, medium_nosize), `generatesigs` (writes `sigs_*.xml` without a DB via `--config`, or commits to a DB), `commitsigs`, `dumpsigs` (export one executable's signatures + metadata from a DB to XML), `listexes`, `getexecount`, `listfuncs` (`--printselfsig`, `--callgraph`), plus index/prewarm management (not supported on H2 file DB). H2 URL form `file:/dir/dbname` (no `.mv.db`). — [BSim command-line reference 12.0](https://ghidradocs.com/12.0_PUBLIC/help/BSim/help/topics/BSim/CommandLineReference.html)
- No `search`/`query` subcommand in that reference. GitHub discussion #6299: official docs cover creating DB/committing sigs but not running searches; maintainers point to `ExampleOverviewQueryScript.java` (headless via `analyzeHeadless -process -noAnalysis -readOnly -postScript ...`, H2 passed as `file:/...` URL; overview = hit counts per function only) and `LocalBSimQueryScript.java` (compares two in-memory programs, needs interactive input so not headless). — [Ghidra discussion #6299](https://github.com/NationalSecurityAgency/ghidra/discussions/6299)
- Java API: `ghidra.features.bsim.query.GenSignatures` (openProgram, scanFunction(s), dispose) and `QueryNearest` (similarity threshold, significance threshold, max matches; similarity 0-1, confidence/significance unbounded). — [GenSignatures API](https://ghidra.re/ghidra_docs/api/ghidra/features/bsim/query/GenSignatures.html); [QueryNearest API](https://ghidra.re/ghidra_docs/api/ghidra/features/bsim/query/protocol/QueryNearest.html)
- PyGhidra (12.x): CPython 3 + JPype, direct Ghidra API access, standalone install, helper API to open a project/program and run GhidraScripts; GUI and headless can run GhidraScripts in native CPython 3. — [PyGhidra README 12.1](https://ghidradocs.com/12.1_PUBLIC/Ghidra/Features/PyGhidra/pypkg/README.html)
- BSim scoring caveats: similarity 0-1, small getter/setter functions give high similarity with low confidence; low thresholds produce many false positives (a trivial `return -1` function matched 454 library functions). — [PenTestPartners](https://www.pentestpartners.com/security-blog/fuzzy-matching-with-ghidra-bsim-a-guide/)
- A secondary LinkedIn post says Ghidra 12.1.3 includes "improved BSim escaping"; Wikipedia snippet lists 12.1.4 as stable (Aug 18, 2026) - mutually inconsistent; unverified. — [search result summary]

### Inferences
- A Python route is possible but unproven in sources: PyGhidra + `GenSignatures` + `QueryNearest`/DB client; I found no published Python example. Expect to read the Java API and write it yourself; `dumpsigs`/`generatesigs` XML is the lowest-friction export, but you would have to parse the feature hashes yourself and re-implement the TF-IDF-weighted cosine, so reusing them in a generic vector DB is not natural.
- BSim needs Ghidra analysis (decompilation) of the 16/32-bit DOS LE/MZ executable. Quality depends on how well Ghidra decompiles Watcom output (calling conventions, segment handling) - not researched. BSim also does not give a 2D map out of the box.
- As a "find similar already-matched function" tool for ReverseApoc, BSim adds Java/Ghidra dependency and Docker weight for questionable gain over assembly-text embeddings or coddog-style opcode distance. Use only if Ghidra is already central to the pipeline.

### Gaps
- Could not retrieve Ghidra ChangeHistory for 11.3-12.x BSim changes; unknown whether any BSim scripting improvements landed. Did not verify the "BSim Scripting and Visualization" tutorial page (404 on guessed URL). Whether BSim handles x86-16/Watcom well is unverified. Whether `pyghidra` supports H2 BSim DB client calls untested.

## 5. coddog

### Takeaway
coddog (Ethan Roseman / ethteck, Rust, MIT/Apache-2.0) finds duplicate/similar functions via opcode-sequence edit distance and shared-subsequence search, with `match`, `cluster`, `submatch`, `compare2`, `compare-n`. Its dependencies point to MIPS/PowerPC/ARM decomp projects; x86 support is NOT confirmed, and DOS MZ/LE/Watcom inputs are probably not supported out of the box.

### Cited Findings
- Purpose: "allows you to more efficiently decompile binaries by reducing redundant work." Reads `decomp.yaml` project configs. Commands: `match` (similar functions by threshold), `cluster` (identical/near-identical within a binary), `submatch` (n-length shared segments), `compare2` and `compare-n` (experimental cross-binary comparison). Repo has `.sqlx` and sqlx scripts (SQL DB layer), a `website/` and `deployment/` dir; licence Apache-2.0 or MIT. — [coddog GitHub](https://github.com/ethteck/coddog); [directory listing](https://api.github.com/repos/ethteck/coddog/contents)
- coddog-core dependencies: `objdiff-core` (features "all"), `object` 0.39.1, `mapfile_parser`, `rabbitizer` 2.0.0-alpha.9 (MIPS), `powerpc` 0.4, `unarm` 2.1.0 (ARM), `editdistancek`. No Capstone. — [crates/core/Cargo.toml](https://raw.githubusercontent.com/ethteck/coddog/main/crates/core/Cargo.toml)
- Lewis: coddog computes bounded Levenshtein over opcode sequences, with early exit, giving a 0-1 score; he runs it on N64 (MIPS) project. — [The Long Tail](https://blog.chrislewis.au/the-long-tail-of-llm-assisted-decompilation/)

### Inferences
- Explicit arch support list was not found in the README excerpt. Since objdiff-core is included with "all" features, x86 may be possible through objdiff, but coddog consumes ELF/object files and map files (via `object`, `mapfile_parser`); UFO2P.EXE/TACP.EXE are DOS executables, so you would likely have to feed it per-function object files from your own build or reimplement. Verify before depending on it.
- The core idea is trivial to reimplement in Python (opcode-only sequence + normalised Levenshtein/`rapidfuzz`, or n-gram Jaccard/MinHash). For UFO2P vs TACP shared code (UI, file loading), a cross-executable function matcher using normalised-asm hashes first (exact-duplicate buckets), then fuzzy opcode distance, is likely sufficient; no source found that has measured this for these binaries.
- Cross-executable matches are high value: a function matched in one exe can seed the other (copy C, expect same build flags).

### Gaps
- Architecture support list, release/version info, and how it ingests binaries not confirmed; releases section empty in fetch.

## 6. Dimensionality reduction + plot in Python

### Takeaway
Use umap-learn (cosine metric) for the 2D layout, Plotly for an interactive scatter (hover shows function name/address/status; click-through), fall back to scikit-learn PCA/t-SNE if dependency weight matters. Colour by matched/unmatched, executable, and call-graph/module cluster, as Macabeus did.

### Cited Findings
- Macabeus: umap-js + chart.js; each node = function; similar assembly closer; pink = decompiled, white = undecompiled, blue = selected folder/module; most functions in large clusters (so neighbours exist as examples); a few small isolated clusters; proposed workflow: manually decompile a few functions per large cluster, then LLM the rest. — [Finding Better Examples](https://gambiconf.substack.com/i/166437312/finding-better-examples)
- Plotly's guide shows UMAP as near drop-in for `sklearn.manifold.TSNE` with `px.scatter`; UMAP scales better with number of points (older PyPI page: 70k MNIST in <1 min vs ~45 min for sklearn t-SNE) and often preserves more global structure. — [Plotly t-SNE/UMAP](https://plotly.com/python/t-sne-and-umap-projections/); [umap-learn PyPI 0.4.6](https://pypi.org/project/umap-learn/0.4.6)
- Third-party skill registries (not official docs): umap-learn 0.5.12, suggested `min_dist` 0.1-0.3 for visualisation, `n_neighbors` default 15; warning that UMAP can create artificial cluster divisions. — [tessl umap-learn](https://tessl.io/registry/skills/github/K-Dense-AI/scientific-agent-skills/umap-learn)

### Inferences
- At 5-20k points UMAP (seconds to a minute) or t-SNE are both fine; matplotlib is enough for a static PNG, but Plotly (`scattergl` for 20k points, output a standalone HTML) gives hover/zoom with no server. Parameter hints above are low-confidence.
- Useful layers: colour = status (matched/partial/unmatched), symbol = executable (UFO2P vs TACP), size = instruction count, outline or facet = module/call-graph community (e.g. networkx/Louvain on the call graph); add a "nearest matched neighbour distance" column to rank next targets (large distance = no example available, small = easy win).
- Fix `random_state` and save the 2D coordinates so plots are reproducible; check umap-learn/numba wheels for Python 3.14/3.15 (not verified).

### Gaps
- Did not verify umap-learn support for Python 3.14/3.15 or numba compatibility; official umap-learn docs not fetched.
