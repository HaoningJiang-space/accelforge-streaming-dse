"""The replay audit must detect layout/order changes without inventing value changes."""
import numpy as np
import pandas as pd

from benchmark_event_join import numeric_signature


def test_numeric_signature_separates_order_schema_and_values():
    frame = pd.DataFrame({'cost': np.array([1, 2, 3], dtype=np.float32),
                          'membership': [False, True, False]})
    ordered = numeric_signature(frame)
    canonical = numeric_signature(frame, True)
    for other in (frame.iloc[::-1], frame[['membership', 'cost']]):
        assert numeric_signature(other) != ordered
        assert numeric_signature(other, True) == canonical
    for other in (frame.astype({'cost': np.float64}),
                  frame.assign(cost=[1., 2., 4.]),
                  frame.assign(membership=[True, True, False]),
                  pd.concat([frame, frame.iloc[:1]])):
        assert numeric_signature(other, True) != canonical
