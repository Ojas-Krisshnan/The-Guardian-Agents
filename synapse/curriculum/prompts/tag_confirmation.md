# Teacher Tag Confirmation

This document describes the tag confirmation guidance presented to the teacher when reviewing extracted concepts.

## Teacher Confirmation Interface

- The teacher is presented with the inferred list of concepts extracted from their canonical note.
- The teacher may:
  1. Confirm the concept list as-is.
  2. Edit concept names, summaries, or prerequisite relationships.
- If the confirmation window expires (`TAG_CONFIRMATION_TIMEOUT_SECONDS`), the system proceeds automatically with `timed_out=True` using the unedited extracted concepts.
