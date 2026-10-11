# Invoice storage

The `invoice_records` collection holds two row kinds: one invoice head row per invoice,
and one invoice line row per line on that invoice.

The store allows one indexed text column per collection, so both row kinds share it:
`shared_indexed_text_0`. Its meaning depends on the row kind:

- In an invoice head row, it holds the supplier reference.
- In an invoice line row, it holds the article number of that line.

A search on this column always also filters on `row_kind`. Without that filter, a search
for a supplier reference could match a line whose article number has the same text.

## Worked example: a received invoice

A supplier with reference SUP-4471 sends invoice 88123 with two lines. The store writes the
head row and both line rows in one transaction, so a reader never sees a head without its
lines.

The head row stores these values:

- `row_kind = invoice_head`: the row describes the whole invoice.
- `status = 1`: code 1 means received. The invoice has arrived and nobody has approved it yet.
- `cost_category = 7`: code 7 means goods purchase. Approval routing reads this value.
- `write_sequence = 5012`: the store gives every written row the next number in one
  increasing series, so readers can order rows by write time.
- `invoice_head_sequence = 5012`: the `write_sequence` of the head row this row belongs to.
  A head row belongs to itself, so both values are 5012.
- `supplier_invoice_number = 88123`: the number printed on the supplier's invoice. People
  search by it.
- `shared_indexed_text_0 = "SUP-4471"`: in a head row, the supplier reference.
- `line_sequences = [5013, 5014]`: the `write_sequence` of each line row, in invoice order.
  Entry 0 is line 1 and entry 1 is line 2.

The two line rows store these values:

- `row_kind = invoice_line`: the row describes one line of an invoice.
- `status = 1` and `cost_category = 7`: copied from the head, so each line is routed with
  its invoice.
- `write_sequence = 5013` for line 1 and `5014` for line 2. They match entries 0 and 1 of
  the head's `line_sequences`.
- `invoice_head_sequence = 5012`: both lines point to the head row written above.
- `shared_indexed_text_0 = "ART-0091"` for line 1 and `"ART-0350"` for line 2: in a line
  row, the article number.

After the write, a search for supplier reference SUP-4471 among invoice head rows returns
invoice 88123 with status received. Opening it returns line 1 (article ART-0091) and line 2
(article ART-0350) in that order, read through `line_sequences`.
