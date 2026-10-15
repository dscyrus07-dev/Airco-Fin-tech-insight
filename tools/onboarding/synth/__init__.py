"""Synthetic PDF-word generators for engine capability tests (N1).

Builders emit (text, x0, x1, top, bottom) word tuples only — no PDFs, no
customer data. Header titles come from the spec's own declared seq tokens, so a
spec change that breaks the layout contract breaks the test.
"""
