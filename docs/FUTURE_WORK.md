# Future work

Planned work, divided by how much of it already exists.

The division matters. The first group is **finishing**: the capability is built
and shipping, and what is left is verification, a pass over data already
stored, or a file that is written to disk and never read. The second group is
**new capability**, including transformer models written and trained here and a
text editor built from scratch, and takes months.

What this document used to list first — merging search, the gap finder and the
vault into LitGraph, and giving the Library one view of everything the user has
done — has since been built. Those sections are gone; leaving them would
describe shipped work as planned.

---

## Near term: finishing what is already built

These reuse existing, working components. Little new machinery is required.

### Verification on Windows and macOS

The replaced interface and the citation feature are exercised by hand on Linux
and validated automatically on all three platforms. Neither has been driven by
a person on Windows or macOS since the interface was replaced.

That gap matters because of what the automated suites cannot see. The citation
list shipped rendering correctly and 1382px below the window, and no test
failed: the interface tests compute no layout. A control that is present,
correctly positioned and invisible is caught by a person or by nobody. This
blocks a stable release.

### Position synchronisation between source and PDF

The prerequisite is already on disk and unused. Every compile runs with
`--synctex`, so each project carries a `main.synctex.gz` mapping page
coordinates to source lines and back; the only code that touches the file
hides it from the project tree. Two steps follow: clicking a place in the PDF
moves the cursor to the line that produced it, and moving the cursor
highlights the matching region of the page.

This is the cheap half of the editor work described below, and it ships
independently of the rest.

### Reference data for papers already ingested

The arXiv identifier and DOI are extracted and stored, but only for papers
ingested after the citation work landed. Anything older is cited as a generic
entry with no preprint link, and its author list comes from the previous
storage format, which is wrong wherever a name was recorded surname first.

Every PDF is still on disk, so this is a pass over stored files and not a
re-ingestion: identifiers can be re-read and author lists re-extracted without
recomputing a single embedding.

### Retrieval quality

Search returns the right papers and scores them low, with a top similarity
around 0.21 on queries whose answers are unambiguous. The ranking is useful and
the number attached to it is not. That matters: the gap finder reads those
scores, not the ordering. The cause has not been isolated — the embedding
model, the chunk size and the absence of a reranking pass are all candidates —
and isolating it is the work.

### Ingestion progress per paper

Progress is reported per batch: "analysing paper 2 of 5", never the title of
the paper being read. The job record does not carry the document id. That is
the whole of the fix.

### Structural validation of generated LaTeX

A model-written table whose rows carry more `&` than its column specification
declares reaches the engine and fails with `! Extra alignment tab has been
changed to \cr`. A tester on Windows saw exactly this. The engine is behaving
correctly and the document is wrong: `_ensure_packages` injects a missing
`\usepackage`, but nothing counts columns.

Two repairs, and they compose rather than compete.

The first is **constrained decoding**. The application already constrains
structured analysis output to valid JSON with a GBNF grammar, so the machinery
and the understanding are both present; what is missing is a grammar for the
LaTeX the writer emits. A grammar that reads a `tabular` column specification
and then permits exactly that many cells per row makes the defect
*unrepresentable* — the sampler cannot select a token the grammar forbids. This
is a stronger guarantee than any amount of training, which can only make an
error less likely. It should start narrow: `tabular`, then `align`, then
`algorithm`. A grammar for all of LaTeX is neither achievable nor wanted.

The second is **compilation before presentation**. Tectonic is bundled and
already driven from the compiler module, so a generated fragment can be
compiled before it is shown, and a fragment that does not compile can be
regenerated rather than handed to the reader. It costs time on a job the user
already waits through, and it converts "sometimes produces a broken document"
into "produces one that compiles, or says it could not".

The honest limit of both: they constrain *form*, never *truth*. A grammar
guarantees a table that compiles, not a table whose numbers mean anything. That
distinction is already written down in `domain/analysis/parsing.py` for the JSON
case and applies unchanged here.

---

## Longer term: new capability

These require research, training, or building components that do not exist yet.

### Feature-specific small language models, written here

The clearest quality limit today is a general-purpose small model on structured
output. Measured: asked to plot a function, the 0.5B model produced
`\includegraphics{chart.png}`, a reference to a file that does not exist. The
1.5B model produced a correct `pgfplots` axis. Both were given the same system
prompt instructing them to use `pgfplots`.

Even the 1.5B model does not reliably follow "write only the fragment": it
reproduces surrounding sections before adding new content, which the backend
currently strips deterministically rather than trusting the instruction.

The direction is **one small model per task, and the model architecture written
here rather than adapted from someone else's weights**. This is a deliberate
choice and it costs more than fine-tuning would; the reasons are worth stating
plainly, because the cheaper path is the obvious one.

Fine-tuning an existing 0.5B would very likely produce a better model sooner. It
would also leave the project unable to explain what the model is, only what was
done to it. The architecture, the tokeniser, the training objective and the data
would all be inherited, and every interesting question about why the model
behaves as it does would terminate in a checkpoint nobody here produced.
Building the transformer means the answer to "why does it do that" is reachable
in the source, which for a project whose entire premise is that computation
happens on the user's own machine is the consistent position.

**Scope, honestly.** A transformer written from scratch and trained on the
hardware available will not beat Qwen2.5 at general language. It does not have
to. The target is the opposite of general: a single task, a narrow and
predictable output shape, and a training set drawn from the application's own
use. On that ground a purpose-built small model is a reasonable competitor,
because most of what a general model spends its capacity on is irrelevant to the
task.

Planned models, in ascending order of difficulty:

- **a LaTeX writing model**, on instruction-to-markup pairs. These are already
  collected passively during normal use, and the routing table already contains
  an entry for such a model, so adopting one is a matter of supplying weights.
  The output shape is highly constrained, which makes it the right first target;
- **an analysis model**, on the structured summarisation and claim extraction
  formats the application parses, addressing the cases where a general model
  returns prose where JSON was requested;
- **a citation and reference model**. A bibliography needs the author list split
  into people, the venue named and the year right; the layout rules reach 86% on
  author lists. What defeats them is not reasoning but formatting — job titles,
  membership grades and postal addresses sitting on the author line — and that
  is the shape a small learned model handles well and a rule handles badly.

**Grammars come first, and they do not compete with this.** Where the
requirement is structural — valid JSON, a table whose rows match its column
count — a constrained decoder guarantees it and any model merely makes it
likely. A model earns its cost on the part a grammar cannot reach: whether the
content is any good. Doing the cheap guarantee first also improves the training
set, because output that always parses produces cleaner pairs to learn from.

The passive data collection already in the application (`domain/fine_tuning/`,
recorded in the decision log on 2026-07-01) is unaffected by this choice and
predates it. Instruction-to-markup pairs drawn from real use are what a model
needs whether it is adapted from existing weights or trained here; the module
name reflects the intention at the time it was written, not a commitment to that
route.

This is tractable for three specific reasons. The training pairs come from use,
so no labelling exercise is needed. The evaluation exists and is honest:
`local/eval_metadata.py` samples arXiv at random and scores against the
archive's own catalogue, so a model is measured on papers nobody here chose. And
because routing is per task, the fallback is the current behaviour — a model
worse than the rules is deselected in Bench, with no release involved. Nothing
ships until it wins on the evaluation.

Training one larger model to do everything better is deliberately *not* the
plan. This project has already measured itself out of that: the bundled model
is 469MB of a 900MB installer, and the size budget is why it ships at all.

### SQLite for the vector store, replacing the JSON file

The store keeps every chunk in one `vectors.json`: text, a 384-dimension
embedding, and metadata. It was chosen to avoid a compiled dependency, and that
reasoning was sound about ChromaDB and FAISS. It does not apply to SQLite, and
that is the whole of the argument for changing.

**SQLite is not a dependency.** It is compiled into CPython and reached through
the standard library's `sqlite3` module. No wheel, no C++ toolchain, no
`--hidden-import`, nothing new for PyInstaller to miss on one platform out of
three. The objection that ruled out the alternatives simply is not present here.

**What the current design costs, measured on the real store.** 464 chunks
across 21 papers is 5.57 MB, and the shape of the problem is visible in how it
grows:

| library | chunks | `vectors.json` | parse at every start | rewrite per ingest |
|---|---|---|---|---|
| 21 papers | 464 | 5.6 MB | 54 ms | 70 ms |
| 100 papers | 2,200 | 27 MB | 0.3 s | 0.3 s |
| 500 papers | 11,000 | 133 MB | 1.3 s | 1.7 s |
| 2,000 papers | 44,000 | 531 MB | 5.1 s | 6.7 s |

Two costs matter, and neither is about disk space.

The first is that **every write rewrites the entire file**. `upsert` is batched
per paper rather than per chunk, which is why this has not hurt yet, but
ingesting the five-hundredth paper still serialises and rewrites all
133 MB of the previous four hundred and ninety-nine. Building a library is
therefore quadratic in the number of papers, and the last paper is the most
expensive one.

The second is that **the whole file is parsed before the backend can answer
anything**. That is startup latency the user watches on the loading screen, and
it grows with their library.

**Measured against the same data, stored as SQLite with embeddings as float32
blobs:** the store is 2.2× smaller, loading every vector into a numpy matrix
takes 2 ms against the 54 ms JSON parse, and appending one chunk is
constant-time instead of a full rewrite. The size saving is modest because
document text dominates; the startup and write savings are not modest, and they
are the ones that grow.

**The shape of the change.** A table of chunks keyed by id, indexed by document
id, embedding stored as a `float32` blob, metadata in a JSON column — SQLite's
JSON1 extension is built in, so metadata stays schemaless and queryable.
Write-ahead logging so a query can read while the ingestion queue writes, which
the current design cannot do at all.

**Similarity search does not change.** SQLite has no vector index and none is
wanted: the matrix stays in memory and cosine similarity stays in numpy, exactly
as now. SQLite replaces the *persistence*, not the *search*. The deliberate
decision to compare against every chunk rather than an approximate index still
stands and is unaffected.

**What makes this contained** is that `repository.py` is already the only thing
that touches the store; no feature module reaches past it. The migration is a
one-time read of `vectors.json` into the new schema, kept for a release so
existing installations move themselves without anyone being asked to.

The papers workspace stays as folders on disk. That is a separate decision and
still the right one: LaTeX resolves relative paths, and a document a user cannot
open without our application is not really theirs.

### Inference on the machine it is running on

Everything above concerns what the model produces. This concerns what it costs
to produce it, which on a CPU-only machine is what the user actually experiences.
None of it requires training, a GPU, or a new model, and it is therefore the
cheapest quality available.

**A memory budget that is calculated rather than estimated.** `capability.py`
decides what will fit, and it currently reasons from heuristics. The dominant
term at inference time is the key-value cache, and its size is exactly
computable from the model's own metadata: twice the number of layers, times the
key-value head count, times head dimension, times context length, times the size
of the stored type. Every term is in the GGUF header. Reading it turns "this
model probably fits" into a number, which is also the number Bench should be
showing the user when it explains a downgrade.

**Reuse of the prompt prefix.** Gap analysis and summarisation prepend the same
corpus context to call after call, and every one of those calls recomputes it.
Prefill is compute-bound where decode is memory-bound, so on a CPU the repeated
prefill is where the seconds go. Retaining the cache for a shared prefix removes
most of it for the second and subsequent queries.

**A quantised key-value cache.** Holding the cache at eight bits rather than
sixteen roughly halves its footprint, which on a 16GB machine buys context
length. The quality cost is real and must be measured on this application's own
evaluation before it is adopted, not assumed from someone else's benchmark.

**Threads and instruction sets.** Thread count should follow physical cores
rather than logical ones — hyperthreads contend for the same floating-point
units and frequently make generation slower — and llama.cpp's CPU throughput is
mostly a function of which SIMD extensions the build was compiled for.

**Speculative decoding is deliberately not on this list yet.** A small model
drafting for a larger one pays off when the target is large; the target here is
already small. It becomes worth revisiting if an analysis model of 3B or more
is ever shipped.

The precondition for all of it is a baseline. Tokens per second, time to first
token and peak resident memory, measured on a fixed set of prompts, before and
after each change. Without that these are opinions, and the table they produce
belongs in Bench as much as in a report.

### What Bench should be able to tell you

Bench today reports what a machine has and what is installed. The work above
gives it something more useful to report: what a given model will actually cost
here, and what was given up when a smaller one was chosen instead.

That includes a comparison a user can act on. The same model quantised at
several levels — Q8_0, Q4_K_M, Q2_K — differs in size, in speed, and in output
quality, and the trade is currently invisible: a user picks a file name. Running
that comparison once and showing it is a feature, and the same measurement is
what tells the project whether the shipped quantisation is the right default.

### A layout classifier for metadata extraction

Metadata extraction reads page geometry and applies hand-written rules. Measured
over 56 papers sampled at random across 15 arXiv categories: 92.9% of titles and
85.7% of author lists exactly right. The remaining failures are a long tail of
typesetting conventions — mathematics inside a title, publisher cover pages,
templates nobody has looked at — and each one currently costs another rule.

The established answer is a small classifier over the *same* features the rules
already read (font size, position, capitalisation, punctuation, row order),
labelling each row as title, author, affiliation or body. That is what GROBID
does with a CRF, and it has held around 90% F1 for a decade. It would be
kilobytes rather than megabytes, CPU-instant, supervised rather than reinforced,
and — unlike more rules — it degrades gracefully on templates it has not seen.

Two things make this a genuine research direction rather than a port. GROBID
needs a JVM and a model server; Nougat, the neural alternative, wants a GPU.
**Nobody optimises this task for a CPU-only machine with no network**, which is
the constraint this whole application is built under. Taking those two as
accuracy ceilings and measuring how close a fixed memory and CPU budget gets is
publishable whether the answer is "surprisingly close" or "here is exactly where
it breaks".

A cheaper step comes first, and does not need a model at all: **remember
corrections**. When a user fixes a wrong title, store the page's layout
fingerprint against the correction. Papers arrive in clusters from the same few
venues, so one correction pays for itself repeatedly. That is adaptation without
gradients — inspectable, revertible, and free of the catastrophic forgetting that
on-device fine-tuning of a shared model would risk.

### A diversified model suite via Hugging Face

Rather than two fixed models, offer a catalogue drawn from Hugging Face, with
selection driven by the hardware profile the application already computes at
startup. The model manager already has a catalogue, a downloader with progress
and cancellation, and cross-runtime discovery, so the mechanism exists; what is
missing is breadth and a way to browse it.

Distributing **adapters** rather than whole models is the intended direction, so
a capability upgrade costs tens of megabytes instead of gigabytes.

### Deployment beyond a single machine

A direction, not a commitment. It is here because the groundwork already
exists, not because anyone has asked for it.

The release pipeline is config-driven partly for this: adding a channel or a
platform is a configuration edit, not workflow surgery, so an extra
distribution target is cheap. An institutional build would use that mechanism
and not a fork.

What such a build needs, and what the current design already gives it:

- **a shared library, still on the institution's own hardware.** The vector
  store is a local file today. Pointing several installations at one store is a
  storage question and not an architectural one, because nothing above the
  repository layer knows where chunks live;
- **shared models, one copy for many machines.** Model discovery already finds
  weights that Ollama or another runtime put on disk, so a machine on a managed
  image can be handed the model instead of downloading 469MB of it;
- **updates on the institution's schedule.** The updater reads a manifest, so
  pinning a department to a version it has approved means serving that manifest
  from somewhere else.

One constraint governs all of it, the same one that governs federated learning
below: nothing may leave the machines the institution controls. A deployment
that made papers easier to share by putting them on someone else's server would
remove the reason this application exists. That rules out the usual shape of
this feature. Hence a direction and not a plan.

### Federated learning

A possible route to improving these models from real usage without collecting
anyone's documents: training on the user's own machine, with only model updates
leaving the device, and only with explicit consent.

Recorded as a possibility rather than a commitment. It must not weaken the
privacy guarantee that is the reason this product exists, and that constraint
takes precedence over the capability.

### A LaTeX editor built from scratch

The current editor is a plain text area over LaTeX source. The compiled PDF is
the preview and rebuilds automatically, which is a real improvement, but the
editing surface itself is primitive.

The intent is one window in which **LaTeX commands and direct editing coexist**,
so an author can write a heading the way they would in a word processor and
write a matrix the way they would in LaTeX, without switching modes or windows:

- syntax awareness, bracket matching, and compiler diagnostics shown against the
  line that caused them;
- direct editing of structure, so headings, lists, tables and emphasis behave as
  they do in an ordinary editor while remaining LaTeX underneath;
- raw command entry for everything that only LaTeX expresses well;
- position synchronisation between source and compiled output, so selecting a
  place in one moves to it in the other.

**Scribe should be usable by someone who has no library.** Today it is reached
through a research application and shaped around citing a corpus, and that is
the narrower of the two things it could be. A LaTeX editor that compiles
offline, needs no account, and installs a TeX engine for you is worth having on
its own — for a letter, a CV, a set of lecture notes, an assignment. The
citation feature is then what makes it *better* for research rather than what
makes it usable at all.

That is a positioning decision with real consequences:

- **nothing may require an ingested paper.** Creating a document, editing and
  compiling must all work on a first launch with an empty library. The `cite`
  trigger simply finds nothing and stays out of the way;
- **templates beyond the research paper** — article, letter, CV, report, and
  Beamer for slides — because the starter template currently assumes the user is
  writing a paper, which most people opening a LaTeX editor are not;
- **the first-run path cannot begin with "add papers"**, which is what it
  implies now.

**File management, as its own panel.** A paper is already a folder on disk, so
the structure exists; what is missing is any way to work with it. The model is
the file explorer in a code editor:

- a tree the user **rearranges** — drag a file into a subfolder, create and
  delete folders, rename in place, move things between projects;
- **importing what already exists** — bring in a `.tex` file, a `.bib`, a
  figure, or a PDF from anywhere on the machine, either copied into the project
  or opened where it lies. Someone with a half-written paper should be able to
  open it here rather than start again;
- **saving the compiled PDF where the author chose, under a name they gave it**,
  rather than a file appearing somewhere the application picked;
- a command entry for the editor's own operations, the way a code editor has one.


**Paths that survive the user renaming things.** Opening arbitrary folders
raises a question worth answering before any of it is built: what happens when
someone renames or moves a directory outside the application.

It is not unsolvable, but it is not solvable completely either, and it is worth
knowing that **VS Code does not solve it**. It stores absolute paths and shows
a folder as missing when it moves. Matching that behaviour is a defensible
floor, not a target.

The parts that *are* solvable:

- **Inside a project, store paths relative to the project root.** Renaming the
  root then costs one entry rather than every entry beneath it, and the tree is
  intact by construction. Everything the editor creates lives here, so this
  covers the common case entirely.
- **For files linked from elsewhere, store an identity as well as a path.** A
  file's inode and device id survive both renaming and moving within a
  filesystem — verified on this project's own platform — and Windows offers the
  equivalent through the NTFS file id. On open: try the path; if it is gone,
  look for the identity in the directories already known; only then ask.
- **Watch the filesystem while the application is running.** Rust's `notify`
  crate reports renames and moves as they happen, so anything done with the
  editor open needs no recovery at all. It is only the closed-application case
  that needs the fallback above.

The parts that are not solvable, and should therefore be handled honestly
rather than guessed at: a file copied rather than moved has a new identity and
is a different file; a move across filesystems does not preserve an inode; and
some editors save by writing a temporary file and renaming it over the original,
which produces a new identity for what the user considers the same document.
Content hashing survives all three but costs a read of every file and cannot
distinguish two copies of the same thing, which for a `.bib` shared between
projects is exactly the wrong answer.

So: relative within, identity plus path without, a watcher while running, and
when all of that fails, **say the file is missing and offer to locate it** —
once, remembering the answer. A tree that quietly drops an entry is worse than
one that admits it lost track.

The scope of that panel is **file management and the editor's own commands, and
nothing else**. It is not a second interface to the library, it does not
analyse, and it does not read papers. Its resemblance to a code editor is a
resemblance in interaction only. Keeping that boundary is what stops it becoming
a second application inside the first, which this project has already avoided
once by folding three screens into LitGraph.

Two things this forces that are worth naming now. Opening arbitrary files from
the machine means the backend can no longer assume every path lies inside the
papers workspace, so path handling becomes a security boundary rather than a
convenience. And a file the user may have moved, renamed or deleted outside the
application means the tree has to reconcile with the disk rather than trust its
own record — the same problem `reconcile.py` already solves for models, and
probably the same shape of solution.

Existing editor components solve part of this, but none of them solves the
combination. This is the largest single piece of planned work.

---

## How this work lands

Each item above is developed on its own branch and reaches users only after it
is merged — `feat/scribe-editor`, `feat/slm-latex`, and so on, one capability
per branch. Nothing here is built on `dev` directly.

The reason is the versioning scheme rather than tidiness: a landing is a merge
commit whose branch name says what landed, and that name is the only input the
version number has. A capability developed in place produces no landing, no
version movement, and therefore no build that reaches a tester. Branch per
capability is what makes the release pipeline able to describe itself.

It also keeps the half-finished out of the beta channel, which is the one thing
testers on other people's machines cannot easily distinguish from a defect.

---

## Also planned

- **Code signing and notarisation** for macOS and Windows. Required before a
  production release: both operating systems currently obstruct the first launch
  of an unsigned application, which every user encounters and which reads as the
  software being broken.
- **Incremental keyword index**, removing the per-query rebuild that limits
  corpus size.
- **A design system for the interface.** The philosophy will be agreed by the
  team first and the interface refactored to it, rather than the reverse.
- **Bundled model integrity checks**, so a corrupted payload is detected at
  startup rather than at first use.
- **GUI verification on macOS and Windows in CI**, extending the existing Linux
  window test.
