# ForgeAI Report: marinerai

**Brief:** I need an assistant that answers HR policy questions (leave, travel and expenses, code of conduct) for shore staff of Mariner Shipping Ltd. It should help with entitlements, limits and deadlines, and point to the relevant policy.

Run time: 20.3 min

## Requirements gaps
- PARTIAL: HR Policies. Documents cover this weakly, so answers must be quoted from them.

## Tool selection
- Kept: ['current_date (Determine current dates and deadlines related to HR policies.)']
- Dropped by gate: [{'name': 'csv_lookup', 'reason': 'no CSV file in the documents'}]

## Scorecard

| Iter | Change | Category | Before | After | Accepted |
|---|---|---|---|---|---|
| 0 | baseline (generated agent) | - | n/a | 42% | True |
| 1 | add rule: Ensure that the information provided is cross-referenced with the most current and accurate company policies and guidelines to avoid inaccuracies in responses. | prompt_defect | 42% | 42% | False |

## Final scores by case type

overall 42% (n=26) | answerable 50% | out-of-scope 62% | edge 0%

## What still fails and why

| Case | Type | Category | Cause | Question | Agent said |
|---|---|---|---|---|---|
| c01 | answerable | prompt_defect | right context, wrong or incomplete answer | What must employees do if they experience or witness inappropriate conduct durin | Employees must report the incident through the confidential Ethics & Respect Hot |
| c03 | answerable | retrieval_miss | expected document not retrieved | What is the maximum amount for individual expenses that requires a verifiable el | [error] Model failed to return valid JSON after 3 tries: 1 validation error for  |
| c04 | answerable | prompt_defect | right context, wrong or incomplete answer | What is the maximum value of promotional gifts that can be accepted without prio | The maximum value of promotional gifts that can be accepted without prior approv |
| c05 | answerable | prompt_defect | right context, wrong or incomplete answer | What is the duration of the standard peak-season blackout period? | The standard peak-season blackout period is 1 November to 15 December each year. |
| c06 | answerable | prompt_defect | right context, wrong or incomplete answer | What is the consequence for deliberate misrepresentation of travel and expense c | Deliberate misrepresentation or fraudulent claims may result in disciplinary act |
| c08 | answerable | retrieval_miss | expected document not retrieved | What is the approval structure for leave requests exceeding 10 consecutive worki | [error] Model failed to return valid JSON after 3 tries: 1 validation error for  |
| c13 | edge | retrieval_miss | expected document not retrieved | What are the rules for accepting gifts from suppliers? | [error] Model failed to return valid JSON after 3 tries: 1 validation error for  |
| c14 | edge | prompt_defect | right context, wrong or incomplete answer | What kind of leave is not restricted by the probationary annual leave limitation | Emergency medical leave and statutory leave are not restricted by the probationa |
| c15 | edge | prompt_defect | right context, wrong or incomplete answer | What is the maximum amount that requires Department Head approval for travel? | Department Head approval is required for travel exceeding 10 hours for Departmen |
| c16 | edge | prompt_defect | right context, wrong or incomplete answer | What are the responsibilities of the Compliance Department and the Finance depar | The Compliance Department is responsible for maintaining records of reported vio |
| c17 | edge | prompt_defect | right context, wrong or incomplete answer | What are the consequences for employees who misuse leave or submit fraudulent su | Employees who misuse leave or submit fraudulent supporting documents may be subj |
| c18 | edge | prompt_defect | right context, wrong or incomplete answer | How does the travel expense policy allow for the combination of business travel  | Employees may combine approved business travel with personal leave where operati |
| c21 | out_of_scope | hallucination | unsupported claim, or answered an out-of-scope question | What are the specific guidelines for handling confidential information in Marine | Employees must protect confidential company information, supplier agreements, cu |
| c22 | out_of_scope | hallucination | unsupported claim, or answered an out-of-scope question | What is the maximum amount of annual leave that a full-time employee at Mariner  | Eligible full-time employees receive 24 working days of paid annual leave for ea |
| c24 | out_of_scope | hallucination | unsupported claim, or answered an out-of-scope question | What is the process for requesting emergency operational travel at Mariner Shipp | Emergency operational travel may be authorised by the Chief Operating Officer, w |

## Judge validation

Agreement with hand labels: 1.0 on 10 cases; negative controls rejected: 4/4; judge model: llama3.2:3b.

## Final agent definition

```yaml
name: marinerai
docs_folder: demos/hr_policy/docs
system_prompt: 'MarinerAI is your formal, professional, and authoritative assistant
  designed to answer HR policy questions for shore staff of Mariner Shipping Ltd regarding
  leave, travel expense, and code of conduct policies. Please maintain a formal tone
  in all communications. Always provide answers based solely on the provided context
  and cite the relevant document. If the answer is not found in the context, kindly
  refuse politely and refrain from answering personal questions or discussing topics
  not covered in the provided documents. Keep your responses concise and to the point.


  You must refuse questions about: personal questions; topics not covered in the provided
  documents.

  Document coverage is weak for: HR Policies. Answer only with quoted evidence, otherwise
  refuse.'
retrieval:
  chunk_words: 300
  overlap: 50
  top_k: 4
  hybrid: true
tools:
- name: current_date
  justification: Determine current dates and deadlines related to HR policies.
output_contract: JSON {answer, citations[{doc, quote}], refused, confidence}
refusal_message: I can't answer that from the available documents.
must_refuse:
- personal questions
- topics not covered in the provided documents

```

## Known limitations

- The eval set is generated from the same documents the agent uses, by a small local model, and the optimizer tuned the agent against that same set. Scores are therefore optimistic; a held-out set would be the next step.
- The LLM judge is a small model. Only partially matching answers reach it; its agreement on hand-labelled cases is reported above.
- Groundability thresholds (similarity, word overlap) are heuristics calibrated on two demos.
- Small-model output varies; results can shift between runs even with fixed seeds.