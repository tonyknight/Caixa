---
id: 20261112-02-hot-fix-the-caixa-page-must-scroll-with-its
title: 'Hot fix: the Caixa page must scroll, with its buttons in reach'
type: feature
priority: medium
status: done
created: 2026-11-12
updated: 2026-11-12
closed: 2026-11-12
notes: ''
parent:
depends_on: []
subtasks: []
---
## Description

In the maintainer's window the import preview and the People section ran past the bottom of the window with no scroll bar; the button to go on could not be reached except by shrinking the text.

## Acceptance criteria

- [x] Every section can be scrolled to its end with the mouse wheel in a short window (tested at 1100 by 560).
- [x] The wizard's Back and Continue/Import buttons stay in view however long the step is.
- [x] A long list of people in the preview shows the first 12 and a 'Show all N' button.

## Context

Cause: DeepSeek Harness's centre column (`centerCol`) is a flex column as tall as the window with `overflow: hidden`, and the Caixa page had no scroll area of its own. The earlier browser tests used a 1280 by 1000 window and Playwright's `scrollIntoView`, which moves a page that hides its overflow even though a person cannot, so nothing failed.

## Subtasks

- [x] A browser test in a short window that scrolls with the wheel (harness/tests/e2e-layout.test.ts).
- [x] `.page` is the scroll area and `.content` holds the width and padding.
- [x] `.pinned` action bar for the wizard's steps.
- [x] `LongList` for the people and unnamed handles in the preview.

## Implementation plan

Status: done
Current task:

### T01: A browser test in a short window that scrolls with the wheel (harness/tests/e2e-layout.test.ts).
### T02: `.page` is the scroll area and `.content` holds the width and padding.
### T03: `.pinned` action bar for the wizard's steps.
### T04: `LongList` for the people and unnamed handles in the preview.

## Completion report

- **Outcome:** The page scrolls, the wizard's buttons are pinned to the bottom of the window, long lists are folded.
- **Files:** harness/src/client/caixa.module.css, CaixaPage.tsx, pages/ImportPage.tsx, locales.ts, harness/tests/e2e-layout.test.ts, e2e-support.ts
- **Errors:** none
- **Verify:** Harness suite: 240 passed in 23 files; tsc clean. Looked at a screenshot of the preview at 1100 by 560.

## Review

Clean. The pinned bar uses the harness's own background variable (`--dsw-alias-bg-base`) with `Canvas` as the fallback, so it follows light and dark. Lesson recorded in the test: scroll with the wheel, not `scrollIntoView`.

## Notes

- 2026-11-12: Reported by the maintainer; reproduced with a wheel scroll in a 560-pixel-high window before fixing.
