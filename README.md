# Dynarq practical task: payment reminder assistant

Time: 3 hours, 19:00 to 22:00 Colombo time. Work alone. AI tools are allowed.
Software fundamentals must be applied: clear structure, tests and careful handling of
edge cases. Read this whole file before you start; everything you need is in it.

## The product

A small business sends invoices to other businesses. Some are paid late. Every
morning the owner wants to open one page and see what should happen today: which
customers get a reminder, which reminders need the owner's approval first, and which
invoices could not be checked because their data is wrong.

You build that product: a rules engine, the page, the reminder messages, and short
research notes for the owner.

## Do it in this order

The parts are marked in this order. If time runs short, a finished part 1 is worth
more than 4 half parts.

1. **Rules engine** (command line), with your own tests.
2. **The page** for the owner.
3. **Reminder messages.**
4. **Research notes** in `RESEARCH.md`.

Then your `README.md` (replace this file, see "What you hand in").

## Start

1. Download and unzip the starter pack (you have done this if you are reading it).
2. Choose **Python** or **TypeScript**. Work in that folder; you may delete the other.
3. Make the first commit **before you change anything**: `git init`, then
   `git add -A` and `git commit -m "Starter pack"` (the `.gitignore` in the pack keeps
   `node_modules` out). Then create a **public** GitHub
   repository and push. We read your work as the changes after this commit.
4. Commit and push as you go.

Python 3.11 or newer. Node.js 20 or newer. Tests run with `python -m unittest` (inside
`python/`) or `npm test` (inside `typescript/`). You may use any libraries; list them in
`python/requirements.txt` or `typescript/package.json`.

## Part 1: the rules engine

### Input

`data/invoices.json` is a list of invoices:

```json
{ "id": "INV-1001", "customer": "Example Ltd", "email": "accounts@example.test",
  "amount": 1250.0, "currency": "EUR", "due_date": "2026-09-30", "paid_date": null }
```

`data/sent.json` is a list of reminders already sent:

```json
{ "invoice_id": "INV-1001", "step": "friendly", "sent_on": "2026-10-03" }
```

`today` is given as a date, `YYYY-MM-DD`.

Every invoice has a text `id`, a `customer` and a `currency`. `paid_date` is `null` or
missing when the invoice is unpaid (an empty string `""` is not a date, so it is
`invalid_paid_date`). `sent_on` is for your information; the rules do not
use it.

### The rules

**Days overdue** = `today` minus `due_date`, in calendar days. Due today is 0.

| Step | When | Needs approval |
|---|---|---|
| `friendly` | 3 or more days overdue | no |
| `firm` | 10 or more days overdue | yes |
| `final` | 24 or more days overdue | yes |

For each invoice, in this order:

1. **Bad data.** The invoice is skipped, with the **first** reason that applies:

   | Reason | When |
   |---|---|
   | `duplicate_id` | Another invoice in the file has the same `id`. Every invoice with that id is skipped; list the id **once**. |
   | `invalid_amount` | `amount` is missing, not a JSON number (a string or `true` is not a number), or 0 or less. |
   | `missing_due_date` | `due_date` is missing, `null` or an empty string. |
   | `invalid_due_date` | `due_date` is not a real date in the form `YYYY-MM-DD` (for example `2026-02-30` or `30/09/2026`). |
   | `invalid_paid_date` | `paid_date` is not `null` and is not a real `YYYY-MM-DD` date, or it is after `today`. |

2. **Paid.** If `paid_date` is a date (on or before `today`), plan nothing. This is true
   even if reminders were sent before it was paid.
3. **Not yet.** Fewer than 3 days overdue: plan nothing.
4. **One action at most.** Take the **highest** step the invoice has reached. If that
   step, or a higher one, is already in `sent.json` for this invoice, plan nothing.
   Otherwise plan that step. Example: 12 days overdue with nothing sent plans `firm`
   only, not `friendly` as well.

Entries in `sent.json` for invoice ids that are not in `invoices.json`, or with a step
that is not `friendly`, `firm` or `final`, are ignored.

### Command and output

Python, from inside `python/`:

```
python plan.py --invoices ../data/invoices.json --sent ../data/sent.json --today 2026-10-12 --out ../actions.json
```

TypeScript, from inside `typescript/` (after `npm install`):

```
npm run plan -- --invoices ../data/invoices.json --sent ../data/sent.json --today 2026-10-12 --out ../actions.json
```

It writes exactly this shape, with both lists sorted by invoice id in plain text order, character by character (so
`INV-100` comes before `INV-99`):

```json
{
  "today": "2026-10-12",
  "actions": [
    { "invoice_id": "INV-1001", "step": "firm", "needs_approval": true,
      "days_overdue": 12, "message": "..." }
  ],
  "skipped": [
    { "invoice_id": "INV-1007", "reason": "invalid_due_date" }
  ]
}
```

We run your command on other data that we keep back, so test the rules, not only the
sample. The command must exit with code 0 and must not need the internet. If `--today`
is not a valid date or a file cannot be read, print a clear message and exit with a
non zero code.

## Part 2: the page

One page for the owner, started with:

- Python, from inside `python/`: `python app.py`
- TypeScript, from inside `typescript/`: `npm run app`

It must read these environment variables: `PORT` (default `8000`), `DATA_DIR` (the
folder with `invoices.json` and `sent.json`, default `../data`) and `TODAY` (default:
the real date). It serves the page at `http://localhost:PORT/`.

What the owner must be able to do:

- See today's plan: customer, invoice, amount, days overdue, step, and the message.
- Approve or reject each `firm` and `final` reminder, and see what they decided.
  Nothing is sent in this task; the page only records the decision. (Keeping the
  decisions while the app runs is enough.)
- See which invoices were skipped and why, in plain words, not codes.
- Understand the page when there is nothing to do, and when the data cannot be read.
- Use it on a phone (390 pixels wide) and with the keyboard.

Any framework, or none. It must use your rules engine, not a copy of the rules.

## Part 3: reminder messages

Each action has a `message`: the email text the customer would receive. The tone must
fit the step: `friendly`, `firm` or `final`.

Every message must contain:

- the customer name, the invoice id, and the due date as `YYYY-MM-DD`,
- the amount with the currency and 2 decimals, for example `EUR 1250.00` or `EUR 1,250.00`,
- the number of days overdue.

It must contain **no other figure** and no claim that is not in the invoice data: no
fees, no interest, no deadlines you made up, and no mention of earlier reminders. Legal wording is the owner's decision
later; that is what part 4 is for.

You may write the text with an AI model. If you do, the key comes from an environment
variable, and **everything must still work with no key** (use a template then), because
we run your code with no key and no internet. Check the model's text against the rules
above before you use it.

## Part 4: research

Answer the 4 questions in `RESEARCH.md`, only from the files in `sources/`, with a
citation for each answer.

## What you hand in

In your repository, pushed to GitHub:

- your code and your tests,
- `RESEARCH.md` with your answers,
- `README.md`, **replacing this file**, 10 to 30 lines: how to run your tests, the
  command and the page; the decisions you made; what you would do next with more time.

Then submit on your task page: the repository link and the full commit code of your
final commit (`git rev-parse HEAD`, 40 characters). You can submit again until 22:00;
the last submission counts. The page closes at 22:00:00 and accepts nothing after
that. We mark exactly the commit you submit.

## Rules

- Work alone. Your repository is public so we can mark it; that is expected. Do not
  send the task or your code to anyone, and do not help anyone else with theirs.
- AI tools are allowed. In the interview you will walk us through your code and
  change it live.
- No changes to the time. Questions: reply to the task email. If an answer matters
  for everyone, everyone gets it.
