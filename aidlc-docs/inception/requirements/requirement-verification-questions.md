# Requirements Analysis — Clarifying Questions

Please answer each question by filling in the letter choice (or free text) after the `[Answer]:` tag.
Let me know when you're done.

---

## Question 1
What is your new development request? Describe what you want to build, change, or fix.

A) A new feature or enhancement to the existing pipeline

B) A bug fix in the existing pipeline or eval system

C) A new capability not currently in the codebase (describe below)

D) A refactor or quality improvement

X) Other (please describe after [Answer]: tag below)

[Answer]: C, we are adding a couple changes:

1. There will be a new step inside the pipeline, Analysis. Prior to classify. In this step our agent is going to read the extracted text and generate a JSON structured output with the summary, tags (3-5 keywords) and confidence. This JSON output then should be added as YAML frontmatter to the .mds
2. Classify agent will now use the frontmatter as the context for classifying the .mds into their respective folders. 
3. Classify will dynamically discover the folders inside the vault.


---

## Question 2
What is the scope of the change?

A) Single module / single file

B) Within one package (pipeline OR eval), touching multiple files

C) Cross-package (both pipeline and eval affected)

D) New package / new entry point

X) Other (please describe after [Answer]: tag below)

[Answer]: C

---

## Question 3
Are there any specific technical constraints or preferences for the implementation?
(e.g. must reuse existing patterns, must not change public interfaces, must work offline, specific library preference)

A) No constraints — use best judgment

B) Yes — stay strictly within existing patterns and module boundaries

C) Yes — specific constraint (describe after [Answer]: tag below)

X) Other (please describe after [Answer]: tag below)

[Answer]: X, no constraints, lets discuss pros and cons before defining

---

## Question 4
What does success look like? How will you know the implementation is correct?

A) It passes the existing test suite with no regressions

B) New tests are written and pass

C) Manual end-to-end test (describe scenario after [Answer]: tag below)

D) Observable change in Phoenix / eval output

X) Other (please describe after [Answer]: tag below)

[Answer]: B + C: there is relevant frontmatter into the files and they are correctly classified.

---

## Question: Security Extensions
Should security extension rules be enforced for this project?

A) Yes — enforce all SECURITY rules as blocking constraints (recommended for production-grade applications)

B) No — skip all SECURITY rules (suitable for PoCs, prototypes, and experimental projects)

X) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question: Resiliency Extensions
Should the resiliency baseline be applied to this project?

**What this extension is.** Enabling it applies a set of **directional, design-time best practices** for building resilient systems, derived from the **AWS Well-Architected Framework (Reliability Pillar)**. It steers requirements, design, and code toward fault tolerance, observability, and recoverability.

**What this extension is NOT.** It does not make your workload production-ready or certify any availability target. It is a starting point, not a substitute for a formal AWS Well-Architected Review.

A) Yes — apply the resiliency baseline as directional best practices

B) No — skip the resiliency baseline (suitable for local CLI tools and experimental projects)

X) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question: Property-Based Testing Extension
Should property-based testing (PBT) rules be enforced for this project?

A) Yes — enforce all PBT rules as blocking constraints

B) Partial — enforce PBT rules only for pure functions and serialization round-trips

C) No — skip all PBT rules

X) Other (please describe after [Answer]: tag below)

[Answer]: B
