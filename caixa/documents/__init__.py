"""Documents: files such as PDFs filed in a box, with their text, facts and where each fact came from.

The domain is format-neutral: `records` writes the master's document tables (migration 6) for any
format; each format (PDF first) brings its own reading, inspection and normalization, and its own
collector (`caixa.collectors.pdfImport`).
"""
