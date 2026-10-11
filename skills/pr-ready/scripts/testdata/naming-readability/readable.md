# Invoice storage

The invoice store keeps every supplier invoice it receives, so people can find an invoice by
supplier and route it for approval. It keeps them in one collection of the storage engine,
`invoice_records`. The collection holds two row kinds: one invoice head row per invoice, and
one invoice line row per line on that invoice.

The storage engine allows one indexed text column per collection, so both row kinds share
it: `shared_indexed_text_0`. Its meaning depends on the row kind:

- In an invoice head row, it holds the supplier reference.
- In an invoice line row, it holds the article number of that line.

A search on this column always also filters on `row_kind`. Without that filter, a search
for a supplier reference could match a line whose article number has the same text.

## Columns

This list is complete. Every column is required in the row kinds it names.

- `row_kind`, text, both row kinds: `invoice_head` or `invoice_line`.
- `insert_sequence`, integer, both row kinds: the row's number, unique in the collection.
- `invoice_head_sequence`, integer, both row kinds: the `insert_sequence` of the invoice's head row.
- `shared_indexed_text_0`, text, both row kinds, indexed: the mapped field described above.
- `status`, integer, head rows: 1 received, 2 approved, 3 rejected.
- `cost_category`, integer, head rows: 7 goods purchase, 8 services, 9 travel.
- `supplier_invoice_number`, text, head rows: the number printed on the supplier's invoice.
- `line_sequences`, list of integers, head rows: the line rows in invoice order.

The invoice store assigns `insert_sequence` once, when it inserts a row, from one increasing
series for the collection. The number never changes, even when the row is updated later, so
other rows can refer to it.

## Worked example: a received invoice

A supplier with reference SUP-4471 sends invoice 88123 with two lines. The invoice store
inserts the head row and both line rows in one transaction, so a reading client never sees a
head without its lines.

The head row stores these values:

- `row_kind = invoice_head`: the row describes the whole invoice.
- `status = 1`: code 1 means received. The invoice has arrived and nobody has approved it yet.
- `cost_category = 7`: code 7 means goods purchase. Approval routing reads this value from the
  head row for the whole invoice.
- `insert_sequence = 5012`: the next number in the series when the head row was inserted.
- `invoice_head_sequence = 5012`: a head row belongs to itself, so both values are 5012. One
  search on `invoice_head_sequence = 5012` therefore returns the head and all its lines.
- `supplier_invoice_number = "88123"`: two suppliers can use the same number, so people search
  by it together with the supplier reference.
- `shared_indexed_text_0 = "SUP-4471"`: in a head row, the supplier reference.
- `line_sequences = [5013, 5014]`: the `insert_sequence` of each line row, in invoice order.
  Entry 0 is line 1 and entry 1 is line 2.

The two line rows store these values:

- `row_kind = invoice_line`: the row describes one line of an invoice.
- `insert_sequence = 5013` for line 1 and `5014` for line 2. They match entries 0 and 1 of
  the head's `line_sequences`.
- `invoice_head_sequence = 5012`: both lines point to the head row inserted above.
- `shared_indexed_text_0 = "ART-0091"` for line 1 and `"ART-0350"` for line 2: in a line
  row, the article number.

After the insert, a search for supplier reference SUP-4471 among invoice head rows returns
invoice 88123 with status received. Reading the rows whose `invoice_head_sequence` is 5012,
ordered by the head's `line_sequences`, returns line 1 (article ART-0091) and line 2
(article ART-0350) in that order.
