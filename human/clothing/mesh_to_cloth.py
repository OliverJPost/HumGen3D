# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# type:ignore

import os
from pathlib import Path

import bpy
from HumGen3D.backend import get_prefs
from HumGen3D.human.human import Human  # type: ignore


class MESH_TO_CLOTH_TOOLS:
    def invoke(self, context, event):
        self.cc_sett = bpy.context.window_manager.humgen3d.custom_content
        self.hg_rig = self.sett.content_saving_active_human
        return self.execute(context)


# TODO make compatible with non-standard poses
class HG_OT_AUTOWEIGHT(bpy.types.Operator, MESH_TO_CLOTH_TOOLS):
    bl_idname = "hg3d.autoweight"
    bl_label = "Auto weight paint"
    bl_description = "Automatic weight painting"
    bl_options = {"UNDO"}

    def execute(self, context):
        cloth_obj = (
            bpy.context.window_manager.humgen3d.custom_content.content_saving_object
        )
        context.view_layer.objects.active = cloth_obj

        for obj in context.selected_objects:
            if obj != cloth_obj:
                obj.select_set(False)

        for mod in self.hg_rig.HG.body_obj.modifiers:
            if mod.type == "MASK":
                mod.show_viewport = False
                mod.show_render = False

        if self.sett.mtc_add_armature_mod:
            armature = next(
                (mod for mod in cloth_obj.modifiers if mod.type == "ARMATURE"),
                None,
            )
            if not armature:
                armature = cloth_obj.modifiers.new(
                    name="Cloth Armature", type="ARMATURE"
                )
            armature.object = self.hg_rig
            if (
                2,
                90,
                0,
            ) > bpy.app.version:  # use old method for versions older than 2.90
                while cloth_obj.modifiers.find(armature.name) != 0:
                    bpy.ops.object.modifier_move_up(
                        {"object": cloth_obj}, modifier=armature.name
                    )
            else:
                bpy.ops.object.modifier_move_to_index(modifier=armature.name, index=0)

        if self.sett.mtc_parent:
            cloth_obj.parent = self.hg_rig

        context.view_layer.objects.active = self.hg_rig.HG.body_obj
        self.hg_rig.select_set(True)

        bpy.ops.object.data_transfer(
            data_type="VGROUP_WEIGHTS",
            vert_mapping="NEAREST",
            layers_select_src="ALL",
            layers_select_dst="NAME",
            mix_mode="REPLACE",
        )
        bpy.ops.object.data_transfer(
            layers_select_src="ACTIVE",
            layers_select_dst="ACTIVE",
            mix_mode="REPLACE",
            mix_factor=1.0,
        )
        bone_names = [b.name for b in self.hg_rig.pose.bones]
        for vg in [
            vg
            for vg in cloth_obj.vertex_groups
            if vg.name not in bone_names and not vg.name.startswith("mask")
        ]:
            cloth_obj.vertex_groups.remove(vg)

        self.hg_rig.select_set(False)
        context.view_layer.objects.active = cloth_obj

        for mod in self.hg_rig.HG.body_obj.modifiers:
            if mod.type == "MASK":
                mod.show_viewport = True
                mod.show_render = True

        return {"FINISHED"}


class HG_OT_ADDCLOTHMATH(bpy.types.Operator, MESH_TO_CLOTH_TOOLS):
    bl_idname = "hg3d.addclothmat"
    bl_label = "Add clothing material"
    bl_description = "Adds the default HumGen clothing material for you to set up"
    bl_options = {"UNDO"}

    def execute(self, context):
        pref = get_prefs()
        mat_file = pref.filepath + str(Path("/outfits/HG_CLOTHING_MAT.blend"))

        with bpy.data.libraries.load(mat_file, link=False) as (
            data_from,
            data_to,
        ):
            data_to.materials = data_from.materials

        mat = data_to.materials[0]

        ob = context.object
        if ob.data.materials:
            ob.data.materials[0] = mat
        else:
            ob.data.materials.append(mat)

        img_path = os.path.join(
            pref.filepath, "outfits", "textures", "Placeholder_Textures"
        )

        nodes = mat.node_tree.nodes
        for texture_name in ("Base Color", "Roughness", "Normal"):
            file_tag = texture_name.replace(" ", "_")
            img = bpy.data.images.load(
                os.path.join(img_path, f"HG_Placeholder_{file_tag}.png"),
                check_existing=True,
            )
            node = next(n for n in nodes if n.label == texture_name)
            node.image = img

            if texture_name == "Normal":
                if pref.nc_colorspace_name:
                    img.colorspace_settings.name = pref.nc_colorspace_name
                else:
                    img.colorspace_settings.name = "Non-Color"

        return {"FINISHED"}


class HG_OT_ADDMASKS(bpy.types.Operator, MESH_TO_CLOTH_TOOLS):
    bl_idname = "hg3d.add_masks"
    bl_label = "Add geometry masks"
    bl_description = "Adds masks to hide human body behind cloth"
    bl_options = {"UNDO"}

    def execute(self, context):
        cc_sett = bpy.context.window_manager.humgen3d.custom_content

        hg_rig = cc_sett.content_saving_active_human
        human = Human.from_existing(cc_sett.content_saving_active_human)
        hg_body = hg_rig.HG.body_obj

        cloth_obj = cc_sett.content_saving_object

        old_masks = human.finalize_phase.outfits.find_masks(cloth_obj)

        for mask in old_masks:
            with contextlib.suppress(Exception):
                hg_body.modifiers.remove(hg_body.modifiers.get(mask))

        for i in range(10):
            if f"mask_{i}" in cloth_obj:
                del cloth_obj[f"mask_{i}"]

        mask_dict = {
            "mask_arms_long": cc_sett.mask_long_arms,
            "mask_arms_short": cc_sett.mask_short_arms,
            "mask_lower_long": cc_sett.mask_long_legs,
            "mask_lower_short": cc_sett.mask_short_legs,
            "mask_torso": cc_sett.mask_torso,
            "mask_foot": cc_sett.mask_foot,
        }
        for i, mask_name in enumerate([k for k, v in mask_dict.items() if v]):
            cloth_obj[f"mask_{i}"] = mask_name
            mod = hg_body.modifiers.new(mask_name, "MASK")
            mod.vertex_group = mask_name
            mod.invert_vertex_group = True

        return {"FINISHED"}
