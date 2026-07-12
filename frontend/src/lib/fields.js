// Presentation metadata for each onboarding field, merged with the server's {field, prompt} from
// GET /onboarding/questions. The server owns which fields exist, their order, prompts, and
// validation; the client owns how each field is rendered (widget type + enum options). A field the
// server adds without an entry here falls back to a text input, so it degrades gracefully.
export const FIELD_UI = {
  age: { type: 'number', placeholder: 'e.g. 34' },
  marital_status: {
    type: 'enum',
    options: [
      { v: 'single', l: 'Single' },
      { v: 'married', l: 'Married' },
    ],
  },
  monthly_income: { type: 'money', placeholder: '6,800' },
  risk_tolerance: {
    type: 'enum',
    options: [
      { v: 'low', l: 'Pull it out, stop the losses', sub: 'Low risk tolerance' },
      { v: 'medium', l: 'Hold, wait it out', sub: 'Medium risk tolerance' },
      { v: 'high', l: 'Buy more while it’s cheap', sub: 'High risk tolerance' },
    ],
  },
  // optional: blank is allowed (the server defaults these), so the client won't force them.
  dependents: { type: 'number', placeholder: '0', optional: true },
  existing_debt: { type: 'money', placeholder: '15,000', optional: true },
  notes: { type: 'text', placeholder: 'Saving for a house down payment next year…', optional: true },
}

const DEFAULT_UI = { type: 'text', placeholder: '' }

export function mergeQuestions(serverQuestions) {
  return serverQuestions.map((q) => ({ ...(FIELD_UI[q.field] || DEFAULT_UI), ...q }))
}

export const CHAT_SUGGESTIONS = [
  'Can I afford an $8,000 trip to Italy?',
  'Should I pay down my debt faster?',
  'How much can I safely spend this month?',
]
