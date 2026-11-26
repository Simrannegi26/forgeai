# ForgeAI Report: marinerai

**Brief:** Create an AI assistant for Mariner Shipping Ltd. that answers HR policy questions for shore staff. It should answer questions about annual leave, probation, carry-forward rules, travel expenses, expense claims, and code of conduct. It must provide accurate answers based only on uploaded company documents, cite relevant sources, and politely refuse questions not covered by the documents.

Run time: 6.9 min

## Requirements gaps
- PARTIAL: HR Policies. Documents cover this weakly, so answers must be quoted from them.
- PARTIAL: Annual Leave. Documents cover this weakly, so answers must be quoted from them.
- PARTIAL: Carry-forward rules. Documents cover this weakly, so answers must be quoted from them.

## Tool selection
- Kept: none
- Dropped by gate: [{'name': 'csv_lookup', 'reason': 'no CSV file in the documents'}, {'name': 'current_date', 'reason': 'brief never mentions anything that needs this tool'}]

## Scorecard

| Iter | Change | Category | Before | After | Accepted |
|---|---|---|---|---|---|
| 0 | baseline (generated agent) | - | n/a | 33% | True |
| 1 | add rule: Ensure the AI understands to verify the specific context and details of each question to provide accurate and contextually relevant answers. | prompt_defect | 33% | 38% | True |
| 2 | add rule: Ensure the responses cover all aspects of the question, including any potential exceptions or specific conditions that might apply, to avoid oversimplification or omission of important details. | prompt_defect | 38% | 38% | False |
| 3 | add rule: Every claim in your answer must be supported by a quote copied exactly from CONTEXT. If you cannot quote supporting evidence, set refused to true. | hallucination | 38% | 38% | False |

## Final scores by case type

overall 38% (n=21) | answerable 50% | out-of-scope 50% | edge 0%

## What still fails and why

| Case | Type | Category | Cause | Question | Agent said |
|---|---|---|---|---|---|
| c01 | answerable | hallucination | unsupported claim, or answered an out-of-scope question | What is the duration of the standard peak-season blackout period? | The standard peak-season blackout period is 1 November to 15 December each year. |
| c02 | answerable | hallucination | unsupported claim, or answered an out-of-scope question | What is the maximum amount for travel that requires approval from the Chief Fina | The maximum amount for travel that requires approval from the Chief Financial Of |
| c04 | answerable | prompt_defect | right context, wrong or incomplete answer | What is the consequence for deliberate misrepresentation of travel and expense c | Deliberate misrepresentation or fraudulent claims may result in disciplinary act |
| c07 | answerable | prompt_defect | right context, wrong or incomplete answer | What is the approval structure for leave requests exceeding 10 consecutive worki | Leave requests exceeding 10 consecutive working days require approval from the D |
| c09 | edge | prompt_defect | right context, wrong or incomplete answer | What kind of leave is not restricted by the probationary annual leave limitation | Emergency medical leave and statutory leave are not restricted by the probationa |
| c10 | edge | prompt_defect | right context, wrong or incomplete answer | What are the rules for claiming per-diem allowances? | Employees travelling on approved business may claim daily meal and incidental al |
| c11 | edge | prompt_defect | right context, wrong or incomplete answer | What are the requirements for leave requests of 4 to 10 consecutive working days | Requests of 4 to 10 consecutive working days require approval from the Departmen |
| c12 | edge | prompt_defect | right context, wrong or incomplete answer | How does the Travel & Expense Policy handle the combination of business travel w | The Travel & Expense Policy allows employees to combine approved business travel |
| c13 | edge | prompt_defect | right context, wrong or incomplete answer | How does the travel expense policy allow for the combination of business travel  | The travel expense policy allows for the combination of business travel with per |
| c14 | out_of_scope | hallucination | unsupported claim, or answered an out-of-scope question | Can I carry forward unused personal leave to the next year if I have less than 2 | Employees may carry forward a maximum of 5 unused annual leave days into the fol |
| c17 | out_of_scope | hallucination | unsupported claim, or answered an out-of-scope question | What is the maximum number of consecutive days of annual leave that can be carri | The maximum number of consecutive days of annual leave that can be carried forwa |
| c18 | out_of_scope | hallucination | unsupported claim, or answered an out-of-scope question | What is the process for requesting annual leave if an employee is not a full-tim | The process for requesting annual leave is the same for all shore-based employee |
| c20 | out_of_scope | hallucination | unsupported claim, or answered an out-of-scope question | What is the primary function of a code of conduct in an organization? | The primary function of a code of conduct in an organization is to outline the e |

## Judge validation

Agreement with hand labels: 1.0 on 10 cases; negative controls rejected: 4/4; judge model: llama3.2:3b.

## Final agent definition

```yaml
name: marinerai
docs_folder: workspaces/hr_frontend_test/docs
system_prompt: 'MarinerAI is your formal, professional, and authoritative assistant
  for HR policy questions. I am here to help shore staff at Mariner Shipping Ltd.
  with policies on annual leave, probation, carry-forward rules, travel expenses,
  expense claims, and code of conduct.


  My responses will be clear and authoritative, using simple language for easy understanding.
  I must answer only from the provided context and cite the relevant document. If
  the answer is not available, I will politely refuse to answer and suggest checking
  the relevant document. I will be concise and direct in my responses.


  You must refuse questions about personal leave, non-work-related travel, personal
  advice, legal advice, and information not covered in the documents.


  I must answer every part of the question using all relevant retrieved context. When
  a question involves multiple conditions or policy sections, combine the applicable
  rules into one complete answer. Include all relevant approval authorities, exceptions,
  deadlines, and restrictions. Never omit a requirement explicitly stated in the documents.

  ADDITIONAL RULE: Ensure the AI understands to verify the specific context and details
  of each question to provide accurate and contextually relevant answers.'
retrieval:
  chunk_words: 300
  overlap: 50
  top_k: 4
  hybrid: true
tools: []
output_contract: JSON {answer, citations[{doc, quote}], refused, confidence}
refusal_message: I can't answer that from the available documents.
must_refuse:
- Personal leave
- Non-work-related travel
- Personal advice
- Legal advice
- Information not covered in the documents

```

## Known limitations

- The eval set is generated from the same documents the agent uses, by a small local model, and the optimizer tuned the agent against that same set. Scores are therefore optimistic; a held-out set would be the next step.
- The LLM judge is a small model. Only partially matching answers reach it; its agreement on hand-labelled cases is reported above.
- Groundability thresholds (similarity, word overlap) are heuristics calibrated on two demos.
- Small-model output varies; results can shift between runs even with fixed seeds.