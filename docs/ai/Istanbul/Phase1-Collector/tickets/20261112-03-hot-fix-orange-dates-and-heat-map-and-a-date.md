---
id: 20261112-03-hot-fix-orange-dates-and-heat-map-and-a-date
title: 'Hot fix: orange dates and heat map, and a date click returns to the top'
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

On the message pages the green heat map and green highlights clashed with the blue labels. The maintainer asked for qromaOrange (#FA9237), a four-step orange heat map (dark for busy days, light for quiet ones), and the old Chattr habit back: clicking any date in the messages returns to the top of the page.

## Acceptance criteria

- [x] The heat map is four steps of orange, darker for busier days; #FA9237 is one of the steps.
- [x] Date headings are orange and still readable (contrast at least 4.5 to 1 against the page in light and dark).
- [x] No theme colour on the page is green (the WhatsApp badge keeps its own colour).
- [x] Every date heading is a link to the top of the page.

## Context

tools/chattr/src/chattr/templates/base.html holds the colours as CSS variables (`--l1` to `--l4`, `--sent`); page.html draws the date headings. Pure #FA9237 as text on the light page is about 2.2 to 1, too faint to read, so the light theme uses a deeper orange for the date text and #FA9237 for the heat map; the dark theme uses #FA9237 for both.

## Subtasks

- [x] Tests for the heat map steps, the date colour and its contrast, no green, and the link to the top (tools/chattr/tests/test_render_pages.py).
- [x] Orange variables for light and dark; `--date`; readable digits on the darkest step.
- [x] `<body id="top">` and date headings that link to it.

## Implementation plan

Status: done
Current task:

### T01: Tests for the heat map steps, the date colour and its contrast, no green, and the link to the top (tools/chattr/tests/test_render_pages.py).
### T02: Orange variables for light and dark; `--date`; readable digits on the darkest step.
### T03: `<body id="top">` and date headings that link to it.

## Completion report

- **Outcome:** Orange heat map and dates; sent messages are a pale orange tint instead of green; dates jump to the top.
- **Files:** tools/chattr/src/chattr/templates/base.html, page.html, tools/chattr/tests/test_render_pages.py
- **Errors:** none
- **Verify:** Chattr suite: 687 passed.

## Review

Clean. Two choices NEED MAINTAINER CONFIRMATION: (1) in the dark theme the busiest days are the brightest orange, not the darkest, because a dark orange on a dark page would read as 'less'; (2) the owner's own messages changed from pale green to a pale orange tint, since 'green highlights' could mean them too.

## Notes

- 2026-11-12: qromaOrange is #FA9237 (from the maintainer).
