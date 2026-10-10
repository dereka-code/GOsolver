# =========================================================
# Reward weights for each strategy.
#
# Change numbers here, never in reward.py.
#   - "weight":  multiplied by the rule's raw value
#   - "enabled": False turns a rule off without deleting it
#   - any other keys are extra settings passed to that rule
# Rules left out of a strategy are simply off.
#
# To add a strategy: copy a block below and give it a new name.
# To add a rule: write it in reward.py with @rule("name"), then
# give it an entry here.
# =========================================================

STRATEGIES = {
    "aggressive": {
        # Reward returned for an illegal move. -inf means a solver
        # that picks the highest reward can never choose one.
        "illegal_move": float("-inf"),
        "rules": {
            # raw value: 1.0 at the center (4,4), falling to 0.0 at the corners
            "center":             {"enabled": True,  "weight": 10},
            # raw value: number of stones captured. Largest reward.
            "capture":            {"enabled": True,  "weight": 100},
            # raw value: 1 if the move takes a liberty from an enemy group
            # while touching one of my own stones. Ranked below a capture.
            "liberty_connection": {"enabled": True,  "weight": 60},
            # raw value: 1 if the move gives its group two eyes
            # (and none of the groups it joined had two eyes before)
            "two_eyes":           {"enabled": True,  "weight": 30},
            # raw value: 1 on the four corner points
            "corner":             {"enabled": True,  "weight": -50},
            # raw value: 1 on edge points. include_corners=False means
            # corners get only the corner penalty, not both.
            "edge":               {"enabled": True,  "weight": -20, "include_corners": False},
            # Final win/loss hook: +1 if `color` wins, -1 if it loses.
            # Only fires on the move that ends the game (the second pass).
            "terminal":           {"enabled": False, "weight": 1000},
        },
    },
}
