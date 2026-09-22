# Useful tasks for typed decisions

openJEV fits repeated decisions over short inputs when the possible outcomes and scoring rules can be written down. Its useful output is a category, a rubric score or a proposition signal that another workflow can consume. It does not need to write a paragraph for every item.

| Scenario | Input | Choice | Score | Noul |
|---|---|---|---|---|
| Support ticket triage | A customer message and the service scope | Account, payment, delivery, technical issue, inquiry or unclear | Explicit urgency from 0 to 3 | Is the request within scope? |
| Product listing checks | Supplied attributes and a product description | Complete, inconsistent or needs more information | Number/severity of missing requirements under a fixed rubric | Does the description contradict an attribute? |
| Feedback organization | One comment or review | Defect, feature request, usability issue, praise or other | Stated impact on use | Does the user explicitly report being unable to continue? |
| Intake validation | A submitted form and a required-field checklist | Ready, missing details or wrong category | Completeness under the checklist | Is a required attachment explicitly present? |
| Content labeling | A text item and a supplied labeling policy | Question, announcement, promotion or other | Fit with a defined editorial rubric | Does it contain a promotional offer? |
| Service inquiry routing | An inbound message and service descriptions | Appropriate team or unclear | Match to the stated service requirements | Does the sender ask for a quote? |

The ticket workspace implements the first row. The other rows are examples to configure in the playground or API; they are not additional integrated products. All bundled demonstrations are fictional and contain no real customer records.

## Make the questions useful

- Ask about observable evidence: “Does the message explicitly request a refund?” is easier to label consistently than “Will this customer leave?”
- Give each category a clear definition and include an insufficient-information outcome when needed.
- Define Score levels concretely. Urgency, completeness and customer sentiment are different concepts; use separate questions.
- Keep source text with the result so an incorrect classification can be reviewed.
- Measure task accuracy and probability calibration on representative held-out labels. A concentrated distribution alone does not establish correctness.

For support triage, a queue recommendation is a useful starting point. The demo does not send replies, approve refunds or modify external records. It offers a reviewable shortlist that can later be connected to an authorized workflow.

Typed decisions are a poor fit for open-ended drafting, multi-step investigation or questions requiring facts absent from the input. Use the separate text-generation endpoint when the output needs prose, and a retrieval or tool workflow when required evidence must first be obtained.
