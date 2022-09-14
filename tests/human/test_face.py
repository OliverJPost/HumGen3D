import pytest
from HumGen3D.tests.fixtures import (
    ALL_HUMAN_FIXTURES,
    context,
    female_human,
    male_human,
)

# TODO
# def test_shape_keys_face(human):
#     sks = human.creation_phase.face.shape_keys
#     assert [sk for sk in sks if sk.name.startswith("pr_")]
#     assert [sk for sk in sks if sk.name.startswith("ff_")]

# def test_reset_face(human):
#     for sk in human.creation_phase.face.shape_keys:
#         sk.value = random.uniform(-0.5, 0.5)

#     human.creation_phase.face.reset()

#     for sk in human.creation_phase.face.shape_keys:
#         assert sk.value == 0

# def test_randomize_face(human):
#     prefix_dict = FaceKeys._get_ff_prefix_dict()

#     for name, prefix in prefix_dict.items():
#         if name == "all":
#             continue

#         human.creation_phase.face.randomize(ff_subcateg=name)
#         all_values = [
#             sk.value for sk in human.keys if sk.name.startswith(prefix)
#         ]
#         if len(all_values) > 1:
#             assert mean(all_values) != 0

#     human.creation_phase.face.randomize(use_bell_curve=False)
#     human.creation_phase.face.randomize(use_bell_curve=True)
