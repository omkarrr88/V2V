import pandas as pd
from train_ai_model import create_target_labels
df = pd.DataFrame({
    'P_left':        [1.0, 1.0, 1.0, 1.0],
    'R_decel_left':  [1.0, 0.0, 0.0, 0.0],
    'R_ttc_left':    [1.0, 0.85, 0.50, 0.1],
    'R_intent_left': [0.0, 0.0, 0.0, 0.0],
    'plr_mult_left': [1.0, 1.0, 1.0, 1.0],
    'P_right':       [0.0, 0.0, 0.0, 0.0],
    'R_decel_right': [0.0, 0.0, 0.0, 0.0],
    'R_ttc_right':   [0.0, 0.0, 0.0, 0.0],
    'R_intent_right':[0.0, 0.0, 0.0, 0.0],
    'plr_mult_right':[1.0, 1.0, 1.0, 1.0],
    'max_gap':       [1.5, 6.0, 12.0, 50.0],
    'rel_speed':     [8.0, 3.0, 1.0,  0.0],
    'num_targets':   [1,   1,   1,    0  ]
})
result = create_target_labels(df).tolist()
print('Labels:', result)
assert result == [3, 2, 1, 0], f'FAILED: expected [3,2,1,0], got {result}'
print('\u2705 Label independence verified')
