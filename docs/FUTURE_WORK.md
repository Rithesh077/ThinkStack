# Future work

Planned work, divided by how much of it already exists.

The division matters. The first group is **finishing**: the capability is built
and shipping, and what is left is verification, a pass over data already
stored, or a file that is written to disk and never read. The second group is
**new capability**, including model training and a text editor written from
scratch, and takes months.

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

---

## Longer term: new capability

These require research, training, or building components that do not exist yet.

### Feature-specific fine-tuned models

The clearest quality limit today is a general-purpose small model on structured
output. Measured: asked to plot a function, the 0.5B model produced
`\includegraphics{chart.png}`, a reference to a file that does not exist. The
1.5B model produced a correct `pgfplots` axis. Both were given the same system
prompt instructing them to use `pgfplots`.

Even the 1.5B model does not reliably follow "write only the fragment": it
reproduces surrounding sections before adding new content, which the backend
currently strips deterministically rather than trusting the instruction.

The direction is **one small model per task, not one general model for all of
them**. A 0.5B trained on the exact shape of a single job beats a 1.5B guessing
at four, and it fits a machine with no GPU and 16GB of RAM. The routing table
already maps tasks to models, so adopting a fine-tuned model means supplying
weights and a registry entry; nothing that calls it changes.

Planned models:

- **a LaTeX writing model**, fine-tuned on instruction-to-markup pairs. These
  pairs are already collected passively during normal use, and the routing table
  in the inference client already contains entries for such a model, so adopting
  one is a matter of supplying weights;
- **an analysis model**, fine-tuned on the structured summarisation and claim
  extraction formats the application parses, addressing the cases where a
  general model returns prose where JSON was requested;
- **a citation and reference model**, on the evidence of the citation work. A
  bibliography needs the author list split into people, the venue named and the
  year right; the layout rules reach 86% on author lists. What defeats them is
  not reasoning but formatting — job titles, membership grades and postal
  addresses sitting on the author line — and that is the shape a small
  fine-tuned model handles well and a rule handles badly.

This is tractable for three specific reasons. The training pairs come from use,
so no labelling exercise is needed. The evaluation exists and is honest:
`local/eval_metadata.py` samples arXiv at random and scores against the
archive's own catalogue, so a model is measured on papers nobody here chose.
And because routing is per task, the fallback is the current behaviour — a
model worse than the rules is deselected in Bench, with no release involved.

Training one larger model to do everything better is deliberately *not* the
plan. This project has already measured itself out of that: the bundled model
is 469MB of a 900MB installer, and the size budget is why it ships at all.

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

Existing editor components solve part of this, but none of them solves the
combination. This is the largest single piece of planned work.

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
