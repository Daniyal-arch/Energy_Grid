from app.power_live import newest_complete_index


def test_skips_partial_newest_interval() -> None:
    # Energy-Charts' newest interval before every TSO reported: CZ/PL read 0
    columns = [
        [0.97, 0.88, 0.96, 0.0],  # Czech Republic: 0 replacing a non-zero value
        [-1.01, -1.07, -0.68, 0.0],  # Poland
        [-0.96, -1.09, -0.99, -0.58],  # Austria
    ]
    assert newest_complete_index(columns) == 2


def test_keeps_idle_link_zero() -> None:
    # a link that was already idle stays a real 0 reading
    columns = [
        [0.12, 0.0, 0.0, 0.0],  # Sweden: idle cable
        [-0.47, -0.57, -1.25, -1.86],  # Netherlands
    ]
    assert newest_complete_index(columns) == 3


def test_missing_values_and_empty_input() -> None:
    assert newest_complete_index([[1.0, None], [2.0, 3.0]]) == 0
    assert newest_complete_index([]) is None
