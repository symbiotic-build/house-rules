# Invoice storage

Collection `mem_c_v2` holds invoice heads and invoice lines.
`xs00` is the indexed supplier-reference slot.

## Worked example: a received invoice

The invoice head has k=1, st=1, cls=7, seq=rseq=5012, rno=88123, xs00="SUP-4471", w_idx=[5013, 5014].
The lines have k=2, st=1, cls=7, seq=5013 and 5014, rseq=5012, xs00="ART-0091" and "ART-0350".

## Glossary

- `k`: row kind.
- `st`: status.
- `cls`: class.
- `seq`: sequence number.
- `rseq`: root sequence number.
- `rno`: reference number.
- `w_idx`: write index.
- `xs00`: indexed supplier-reference slot.
