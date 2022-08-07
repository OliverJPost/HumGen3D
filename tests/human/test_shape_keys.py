from HumGen3D.tests.fixtures import (
    creation_phase_human,
    finalize_phase_human,
    reverted_human,
)


def test_body_proportions(creation_phase_human, reverted_human, finalize_phase_human):
    len_creation = len(creation_phase_human.shape_keys.body_proportions)
    assert len_creation
    assert not len(finalize_phase_human.shape_keys.body_proportions)
    len_reverted = len(reverted_human.shape_keys.body_proportions)
    assert len_creation == len_reverted

