# Invoice storage

The `invoice_records` collection holds two row kinds: one invoice head row per invoice,
and one invoice line row per line on that invoice.

The storage engine indexes every integer column. It allows only one indexed text column per
collection, so both row kinds share it: `shared_indexed_text_0`. Its meaning depends on the row kind:

- In an invoice head row, it holds the supplier reference: the identifier our supplier register
  gives the supplier who sent the invoice.
- In an invoice line row, it holds the article number of that line.

A search on this column always also filters on `row_kind`. Without that filter, a search
for a supplier reference could match a line whose article number has the same text.

## Worked example: a received invoice

A supplier with reference SUP-4471 sends invoice 88123 with two lines. In one transaction,
the invoice store first reserves three numbers from its increasing series, 5012 to 5014, one
per row. The invoice store keeps one such series for the `invoice_records` collection. A
number identifies one row; a rolled-back transaction leaves its numbers unused. The invoice store then inserts the head row and both line rows with those numbers, so the head can
list its lines before they exist. A reading client never sees a head without its lines.

The head row stores these values:

- `row_kind = 1`: code 1 means invoice head; the row describes the whole invoice. The column
  is an integer, so the storage engine indexes it.
- `status = 1`: code 1 means received. The invoice has arrived and nobody has approved it yet.
- `cost_category = 7`: code 7 means goods purchase. The invoice store copies it from the
  supplier register's default for SUP-4471. Approval routing reads this value.
- `insert_sequence = 5012`: the first reserved number. A row's number never changes, so
  other rows can refer to it.
- `invoice_head_sequence = 5012`: the `insert_sequence` of the head row this row belongs to.
  A head row belongs to itself, so both values are 5012. One search on
  `invoice_head_sequence = 5012` therefore returns the head and its lines together.
- `supplier_invoice_number = 88123`: the number printed on the supplier's invoice. People
  search by it.
- `shared_indexed_text_0 = "SUP-4471"`: in a head row, the supplier reference.
- `line_sequences = [5013, 5014]`: the `insert_sequence` of each line row, in invoice order.
  Entry 0 is line 1 and entry 1 is line 2.

The two line rows store these values:

- `row_kind = 2`: code 2 means invoice line; the row describes one line of an invoice.
- `supplier_invoice_number` and `line_sequences`: not set on line rows. A search by supplier
  invoice number therefore returns only head rows.
- `status = 1` (received) and `cost_category = 7` (goods purchase): the invoice store copies
  both values from the head when it inserts the lines. A search by article number finds a line
  row and shows its invoice's status and category without reading the head. Whenever the
  head's status or category changes, the invoice store rewrites both values on every line of
  that invoice in the same transaction.
- `insert_sequence = 5013` for line 1 and `5014` for line 2. They match entries 0 and 1 of
  the head's `line_sequences`.
- `invoice_head_sequence = 5012`: both lines point to the head row inserted above. A search
  by article number finds a line row, and this value opens the line's invoice.
- `shared_indexed_text_0 = "ART-0091"` for line 1 and `"ART-0350"` for line 2: in a line
  row, the article number.

After the insert, a search for supplier reference SUP-4471 among invoice head rows returns
invoice 88123 with status received. Opening it returns line 1 (article ART-0091) and line 2
(article ART-0350) in that order, read through `line_sequences`.
