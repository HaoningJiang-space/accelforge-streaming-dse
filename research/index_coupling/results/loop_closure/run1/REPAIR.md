The fresh control archive has tuple extents in memory, while loaded JSON
archives have lists. The control's state lookup compared against lists and
therefore failed before testing its labels. Normalize those two comparisons
to tuples. No search, label, partition, resource limit or benchmark criterion
changed. The four main-case census and validation outcomes remain archived;
the runner correctly withheld all benchmark jobs after the control failed.
Run 2 repeats the complete fixed protocol after this fixture repair.
