"""Mail without the noise: an mbox read into an index, cleaned of junk, sorted by sender, and only
the conversations the owner chooses imported (Phase 1.5 - Mbox).

- `caixa.mail.index`: the mail index, `<box>/.caixa/mail/index.sqlite`, and reading an mbox (or a
  zip holding one) into it with worker processes.
"""
