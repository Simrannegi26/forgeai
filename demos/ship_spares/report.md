# ForgeAI Report: procassist

**Brief:** I need an assistant for the procurement team that answers questions about ship spare parts: prices, lead times, stock, supplier payment terms and delivery SLAs. It should be able to look up parts in the catalogue and work out order totals.

Run time: 19.6 min

## Requirements gaps
- UNSUPPORTED: LeadTimes. No document covers this, so the agent must refuse it.
- PARTIAL: StockLevels. Documents cover this weakly, so answers must be quoted from them.
- PARTIAL: SupplierTerms. Documents cover this weakly, so answers must be quoted from them.
- PARTIAL: SLAs. Documents cover this weakly, so answers must be quoted from them.
- UNSUPPORTED: CatalogLookup. No document covers this, so the agent must refuse it.
- PARTIAL: OrderTotals. Documents cover this weakly, so answers must be quoted from them.
- PARTIAL: Lead times. Documents cover this weakly, so answers must be quoted from them.
- PARTIAL: Stock levels. Documents cover this weakly, so answers must be quoted from them.

## Tool selection
- Kept: ['csv_lookup (To look up prices, lead times, stock levels, and part descriptions in the spare parts catalogue)', 'calculator (To calculate order totals based on the catalogue prices and quantities)']
- Dropped by gate: [{'name': 'current_date', 'reason': 'brief never mentions anything that needs this tool'}]

## Scorecard

| Iter | Change | Category | Before | After | Accepted |
|---|---|---|---|---|---|
| 0 | baseline (generated agent) | - | n/a | 36% | True |
| 1 | add rule: When responding to questions, ensure that the information provided is directly supported by the retrieved passages or is a logical inference from the given context, avoiding speculation or assumptions not aligned with the provided text. | prompt_defect | 36% | 36% | False |

## Final scores by case type

overall 36% (n=25) | answerable 50% | out-of-scope 43% | edge 0%

## What still fails and why

| Case | Type | Category | Cause | Question | Agent said |
|---|---|---|---|---|---|
| c01 | answerable | prompt_defect | right context, wrong or incomplete answer | What must be done if a supplier fails to notify the company promptly and takes n | If a supplier fails to notify the company promptly and takes no steps to minimiz |
| c03 | answerable | prompt_defect | right context, wrong or incomplete answer | What is the maximum time frame for a supplier to provide a proposed resolution t | 10 working days |
| c06 | answerable | prompt_defect | right context, wrong or incomplete answer | What is the earliest payment term offered by any of the suppliers mentioned in t | The earliest payment term offered by any of the suppliers mentioned in the docum |
| c08 | answerable | prompt_defect | right context, wrong or incomplete answer | What is the total cost of the Engine Components listed by Anchor & Gear Co? | The total cost of the Engine Components listed by Anchor & Gear Co is $2,420.00. |
| c10 | answerable | hallucination | unsupported claim, or answered an out-of-scope question | What sections of the Supplier Terms & Conditions govern payment schedules, early | Sections 3 through 5 of the Supplier Terms & Conditions govern payment schedules |
| c11 | answerable | prompt_defect | right context, wrong or incomplete answer | What is the total cost of the main engine thrust bearing (PSP-2005) and the hydr | The total cost of the main engine thrust bearing (PSP-2005) and the hydraulic pi |
| c13 | edge | prompt_defect | right context, wrong or incomplete answer | What happens if an order is placed after the cut-off time? | If an order is placed after the cut-off time, the order will be processed for di |
| c14 | edge | prompt_defect | right context, wrong or incomplete answer | What are the prices for the Engine Components category? | The prices for the Engine Components category are as follows:
- NMS-1001: $485.0 |
| c15 | edge | prompt_defect | right context, wrong or incomplete answer | What is the minimum order value required by Anchor & Gear Co.? | The minimum order value required by Anchor & Gear Co. is USD 500. |
| c16 | edge | prompt_defect | right context, wrong or incomplete answer | What are the conditions for urgent orders and how do they relate to the Delivery | Urgent orders are placed when a spare part is required to prevent significant ve |
| c17 | edge | prompt_defect | right context, wrong or incomplete answer | Which supplier(s) must meet the longest standard delivery windows for the Asia-P | Nordic Marine Supply must meet the longest standard delivery windows for the Asi |
| c18 | edge | retrieval_miss | expected document not retrieved | Which supplier has different payment terms and what are they? | Nordic Marine Supply operates on Net 30 payment terms, while Pacific Ship Parts  |
| c19 | out_of_scope | hallucination | unsupported claim, or answered an out-of-scope question | How do I ensure that sensitive information, such as supplier payment terms, is n | ProcAssist does not provide sensitive or confidential information, including sup |
| c22 | out_of_scope | hallucination | unsupported claim, or answered an out-of-scope question | Is there a minimum order quantity for suppliers other than the one mentioned in  | The minimum order values for suppliers other than Anchor & Gear Co. are provided |
| c23 | out_of_scope | hallucination | unsupported claim, or answered an out-of-scope question | How does Mariner Shipping Ltd. handle price adjustments for suppliers exceeding  | Suppliers must not substitute components, manufacturers, or technical specificat |
| c25 | out_of_scope | hallucination | unsupported claim, or answered an out-of-scope question | ProcAssist can provide information on various aspects of ship spare parts. Which | weather conditions |

## Judge validation

Agreement with hand labels: 1.0 on 10 cases; negative controls rejected: 4/4; judge model: llama3.2:3b.

## Final agent definition

```yaml
name: procassist
docs_folder: demos/ship_spares/docs
system_prompt: 'As ProcAssist, your role is to provide information about ship spare
  parts to the internal procurement team and other relevant stakeholders. Your tone
  should be formal and professional to ensure accuracy, reliability, and trustworthiness.
  You must answer only from the provided context and cite the document. When the context
  lacks an answer, you must politely refuse to provide sensitive or confidential information,
  financial details, personal information, detailed explanations for each delivery
  SLA and supplier terms, or lead times. You must be concise in your responses.


  You must refuse questions about: Sensitive or confidential information; Financial
  details; Personal information; Detailed explanations for each delivery SLA and supplier
  terms; LeadTimes; CatalogLookup.

  Document coverage is weak for: StockLevels; SupplierTerms; SLAs; OrderTotals; Lead
  times; Stock levels. Answer only with quoted evidence, otherwise refuse.'
retrieval:
  chunk_words: 300
  overlap: 50
  top_k: 6
  hybrid: true
tools:
- name: csv_lookup
  justification: To look up prices, lead times, stock levels, and part descriptions
    in the spare parts catalogue
- name: calculator
  justification: To calculate order totals based on the catalogue prices and quantities
output_contract: JSON {answer, citations[{doc, quote}], refused, confidence}
refusal_message: I can't answer that from the available documents.
must_refuse:
- Sensitive or confidential information
- Financial details
- Personal information
- Detailed explanations for each delivery SLA and supplier terms
- LeadTimes
- CatalogLookup

```

## Known limitations

- The eval set is generated from the same documents the agent uses, by a small local model, and the optimizer tuned the agent against that same set. Scores are therefore optimistic; a held-out set would be the next step.
- The LLM judge is a small model. Only partially matching answers reach it; its agreement on hand-labelled cases is reported above.
- Groundability thresholds (similarity, word overlap) are heuristics calibrated on two demos.
- Small-model output varies; results can shift between runs even with fixed seeds.