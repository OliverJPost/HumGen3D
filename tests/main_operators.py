import random

import bpy
from HumGen3D.backend.logging import hg_log


class HG_MAIN_OPERATORS_TESTS(bpy.types.Operator):
    bl_idname = "hg3d.main_operator_tests"
    bl_label = "Main operator tests"
    bl_description = ""
    bl_options = {"UNDO", "REGISTER"}

    human: bpy.props.PointerProperty(type=bpy.types.Object)

    def execute(self, context):

        assert not [obj for obj in bpy.data.objects if obj.HG.ishuman]

        for gender in ("male", "female"):
            hg_log(f"Starting tests for {gender} characters")
            self.test_human_creation(context, gender)
            hg_log("Finished human creation")

            self.test_body_proportions(context)
            hg_log(f"Finished body proportions")
            self.test_length_change(context)
            hg_log(f"Finished length changes")
            self.assert_shape_keys(context)
            hg_log("Asserted shape keys")
            self.test_face_randomize_buttons(context)
            hg_log("Finished face randomization")
            self.test_texture_sets(context)
            hg_log("Finished texture sets")
            self.test_skin_buttons_and_sliders(context)
            hg_log("Finished skin")
            self.test_eyes(context)
            hg_log("Finished eyes")
            self.test_hair_functions(context)
            hg_log("Finished hair")

            self.test_finish_creation_phase(context)
            hg_log("Finished Creation Phase")

            self.test_clothing_functions(context)
            hg_log("Finished clothing functions")
            self.test_footwear_functions(context)
            hg_log("Finished footwear functions")
            self.test_pose_functions(context)
            hg_log("Finished pose functions")
            self.test_expression_functions(context)
            hg_log("Finished expression functions")

            self.test_face_rig(context)
            hg_log("Finished face rig")
            self.test_rigify(context)
            hg_log("Finished rigify")

            self.test_revert_to_creation_phase(context)
            hg_log("Finished reverting")
            self.test_finish_creation_phase(context)
            hg_log("2nd Finished creation phase")

            self.test_expression_functions(context)
            hg_log("2nd Finished expression functions")

            self.test_face_rig(context)
            hg_log("2nd Finished face rig")
            self.test_rigify(context)
            hg_log("2nd Finished rigify")

            bpy.ops.hg3d.delete(obj_override=self.human.name)

        hg_log("Finished all tests")
        return {"FINISHED"}

    def test_human_creation(self, context, gender):
        context.scene.HG3D.gender = gender
        pcoll_list = context.scene.HG3D["previews_list_humans"]

        context.scene.HG3D.pcoll_humans = random.choice(pcoll_list)

        bpy.ops.hg3d.startcreation()

        self.human = next(obj for obj in bpy.data.objects if obj.HG.ishuman)

        context.view_layer.objects.active = self.human

    def test_body_proportions(self, context):
        for _ in range(4):
            bpy.ops.hg3d.random(random_type="body_type")

        individual_scaling_names = [
            "head",
            "neck",
            "chest",
            "shoulder",
            "breast",
            "hips",
            "upper_arm",
            "forearm",
            "hand",
            "thigh",
            "shin",
        ]

        for scale_name in individual_scaling_names:
            sk_name = scale_name + "_size"

            sett = context.scene.HG3D
            setattr(sett, sk_name, 1.0)
            setattr(sett, sk_name, 0.0)
            setattr(sett, sk_name, 0.5)

    def test_length_change(self, context):
        bpy.ops.hg3d.section_toggle(section_name="length")
        for _ in range(4):
            bpy.ops.hg3d.randomlength()

        context.scene.HG3D.human_length = 195.5
        context.scene.HG3D.human_length = 154.2

        context.scene.HG3D.human_length = 170.1

    def assert_shape_keys(self, context):
        hg_body = self.human.HG.body_obj
        sks = hg_body.data.shape_keys.key_blocks

        prefixes = ["pr", "bp", "age", "expr", "cor", "ff", "eye"]

        for prefix in prefixes:
            assert [sk for sk in sks if sk.name.startswith(f"{prefix}_")]

        for sk in bpy.data.shape_keys:
            if not sk.animation_data:
                continue
            bung_drivers = []
            for d in sk.animation_data.drivers:
                try:
                    sk.path_resolve(d.data_path)
                except ValueError:
                    bung_drivers.append(d)
        try:
            assert not bung_drivers
        except AssertionError:
            print("Found ")

    def test_face_randomize_buttons(self, context):
        bpy.ops.hg3d.section_toggle(section_name="face")
        random_types = [
            "all",
            "u_skull",
            "ears",
            "eyes",
            "nose",
            "l_skull",
            "mouth",
            "cheeks",
            "jaw",
            "chin",
            "custom",
        ]

        for random_type in random_types:
            bpy.ops.hg3d.random(random_type=f"face_{random_type}")

    def test_texture_sets(self, context):
        bpy.ops.hg3d.section_toggle(section_name="skin")
        context.scene.HG3D.texture_library = "Default 512px"

        pcoll_list = context.scene.HG3D["previews_list_textures"]

        context.scene.HG3D.pcoll_textures = random.choice(pcoll_list)
        context.scene.HG3D.pcoll_textures = random.choice(pcoll_list)

    def test_skin_buttons_and_sliders(self, context):
        bpy.ops.hg3d.random(random_type="skin")
        mat = self.human.HG.body_obj.data.materials[0]
        nodes = mat.node_tree.nodes
        nodes["Skin_tone"].inputs[1].default_value = 1
        nodes["R_Multiply"].inputs[1].default_value = 1

        context.scene.HG3D.skin_sss = "on"
        context.scene.HG3D.underwear_switch = "off"

        nodes["Darken_hsv"].inputs[2].default_value = 0.5
        nodes["Freckles_control"].inputs[3].default_value = 1
        nodes["HG_Age"].inputs[1].default_value = 1

    def test_eyes(self, context):
        bpy.ops.hg3d.section_toggle(section_name="eyes")
        bpy.ops.hg3d.random(random_type="iris_color")
        for _ in range(3):
            bpy.ops.hg3d.eyebrowswitch(forward=True)

        for _ in range(5):
            bpy.ops.hg3d.eyebrowswitch(forward=False)

    def test_hair_functions(self, context):
        bpy.ops.hg3d.section_toggle(section_name="hair")

        pcoll_list = context.scene.HG3D["previews_list_hair"]
        context.scene.HG3D.pcoll_hair = random.choice(pcoll_list)
        context.scene.HG3D.pcoll_hair = random.choice(pcoll_list)

        if self.human.HG.gender == "male":
            pcoll_list = context.scene.HG3D["previews_list_face_hair"]
            context.scene.HG3D.pcoll_face_hair = random.choice(pcoll_list)
            context.scene.HG3D.pcoll_face_hair = random.choice(pcoll_list)

        context.scene.HG3D.hair_shader_type = "accurate"

        if self.human.HG.gender == "female":
            context.scene.HG3D.hair_mat_female = "head"
        else:
            context.scene.HG3D.hair_mat_male = "face"

    def test_finish_creation_phase(self, context):
        bpy.ops.hg3d.finishcreation()

    def test_clothing_functions(self, context):
        bpy.ops.hg3d.section_toggle(section_name="clothing")

        self.__test_pcoll(context, "outfit")

    def test_footwear_functions(self, context):
        bpy.ops.hg3d.section_toggle(section_name="footwear")

        self.__test_pcoll(context, "footwear")

    def test_pose_functions(self, context):
        bpy.ops.hg3d.section_toggle(section_name="pose")

        self.__test_pcoll(context, "poses")

    def test_expression_functions(self, context):
        bpy.ops.hg3d.section_toggle(section_name="expression")
        self.__test_pcoll(context, "expressions")

        sks = self.human.HG.body_obj.data.shape_keys.key_blocks
        expr_sk = next(sk.name for sk in sks if sk.name.startswith("expr"))
        bpy.ops.hg3d.removesk(shapekey=expr_sk)

    def test_face_rig(self, context):
        context.scene.HG3D.expression_type = "frig"
        bpy.ops.hg3d.addfrig()

        bpy.context.scene.HG3D.expression_type = "1click"
        bpy.ops.hg3d.removefrig()

        self.__test_pcoll(context, "expressions")

        context.scene.HG3D.expression_type = "frig"
        bpy.ops.hg3d.addfrig()

    def test_rigify(self, context):
        bpy.ops.hg3d.section_toggle(section_name="pose")
        old_name = self.human.name
        bpy.context.scene.HG3D.pose_choice = "rigify"

        bpy.ops.hg3d.rigify()
        self.human = context.scene.objects.get(f"{old_name}_RIGIFY")

    def test_revert_to_creation_phase(self, context):
        context.view_layer.objects.active = self.human
        old_name = self.human.name
        bpy.ops.hg3d.revert()
        self.human = context.scene.objects.get(old_name.replace("_RIGIFY", ""))

    def __test_pcoll(self, context, pcoll_name):
        pcoll_list = context.scene.HG3D[f"previews_list_{pcoll_name}"]
        setattr(context.scene.HG3D, pcoll_name, random.choice(pcoll_list))
        setattr(context.scene.HG3D, pcoll_name, random.choice(pcoll_list))

        bpy.ops.hg3d.random(random_type=pcoll_name)
