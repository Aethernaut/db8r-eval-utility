from eval_utility.scorer import char_range_iou


def test_char_range_iou_exact_match():
    assert char_range_iou(0, 10, 0, 10) == 1.0


def test_char_range_iou_disjoint():
    assert char_range_iou(0, 10, 20, 10) == 0.0


def test_char_range_iou_half_overlap():
    # ranges [0,10) and [5,15): intersection 5, union 15
    assert abs(char_range_iou(0, 10, 5, 10) - (5 / 15)) < 1e-9


def test_char_range_iou_meets_default_threshold():
    # [0,10) vs [0,12): inter 10, union 12 -> 0.833 >= 0.5
    assert char_range_iou(0, 10, 0, 12) >= 0.5
