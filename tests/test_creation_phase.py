import random
from statistics import mean

from HumGen3D.human.creation_phase.face.face import FaceKeys

from fixtures import context
from fixtures import creation_phase_human as human


class TestCreationPhase:
    @staticmethod
    def test_stretch_bones(human):
        assert len(human.creation_phase.stretch_bones)

    ##############################
    ############ Body ############
    ##############################

    @staticmethod
    def test_set_experimental(human):
        def check_min_max(max_all, min_bp):
            for sk in human.shape_keys:
                if sk.name.startswith(("ff_", "bp_", "pr_")):
                    assert sk.slider_max == max_all
            for sk in human.creation_phase.body.shape_keys:
                assert sk.slider_min == min_bp

        human.creation_phase.body.set_experimental(True)
        check_min_max(2, -0.5)
        human.creation_phase.body.set_experimental(False)
        check_min_max(1, 0)

    @staticmethod
    def test_randomize_body(human):
        human.creation_phase.body.randomize()
        # FIXME might be affecting other tests

    @staticmethod
    def test_set_bone_scale(human, context):
        bone_types = [
            "head",
            "neck",
            "chest",
            "shoulder",
            "breast",
            "forearm",
            "upper_arm",
            "hips",
            "thigh",
            "shin",
            "foot",
            "hand",
        ]

        for bone_type in bone_types:
            set_scale = human.creation_phase.body.set_bone_scale
            set_scale(28, bone_type, context)
            set_scale(-3, bone_type, context)
            set_scale(5.2, bone_type, context)
            set_scale(0, bone_type, context)
            set_scale(1, bone_type, context)
            # FIXME might be affecting other tests

    ##########################
    ########### Face #########
    ##########################

    @staticmethod
    def test_shape_keys_face(human):
        sks = human.creation_phase.face.shape_keys
        assert [sk for sk in sks if sk.name.startswith("pr_")]
        assert [sk for sk in sks if sk.name.startswith("ff_")]

    @staticmethod
    def test_reset_face(human):
        for sk in human.creation_phase.face.shape_keys:
            sk.value = random.uniform(-0.5, 0.5)

        human.creation_phase.face.reset()

        for sk in human.creation_phase.face.shape_keys:
            assert sk.value == 0

    @staticmethod
    def test_randomize_face(human):
        prefix_dict = FaceKeys._get_ff_prefix_dict()

        for name, prefix in prefix_dict.items():
            if name == "all":
                continue

            human.creation_phase.face.randomize(ff_subcateg=name)
            all_values = [
                sk.value for sk in human.shape_keys if sk.name.startswith(prefix)
            ]
            if len(all_values) > 1:
                assert mean(all_values) != 0

        human.creation_phase.face.randomize(use_bell_curve=False)
        human.creation_phase.face.randomize(use_bell_curve=True)

    #########################
    ######## Length #########
    #########################

    @staticmethod
    def test_length(human, context):
        old_length = human.creation_phase.length.centimeters
        assert old_length
        assert human.creation_phase.length.meters

        new_length_cm = 172

        human.creation_phase.length.set(new_length_cm, context)

        assert human.creation_phase.length.centimeters == new_length_cm

        human.creation_phase.length.set(old_length, context)
