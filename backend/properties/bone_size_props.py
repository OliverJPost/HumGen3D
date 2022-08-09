"""
context.scene.HG3D.bone_sizes
Contains floatproperties for driving the scale of the different bones during creation
phase.
"""

import bpy
from bpy.props import BoolProperty, FloatProperty  # type:ignore
from HumGen3D.human.human import Human


def create_bone_props(bone_names):
    """Currently inactive, used for automatic generation of FloatProperties"""
    prop_dict = {}
    for name in bone_names:
        prop_dict[name] = FloatProperty(
            default=0.5,
            soft_min=0,
            soft_max=1,
            # update=lambda s, c: Human.from_existing(
            #     c.object
            # ).creation_phase.body.set_bone_scale(getattr(s, name), name, c),
        )

    return prop_dict


def update_length(value, context):
    human = Human.from_existing(context.object)
    sk = human.shape_keys.get("tall")
    sk.value = value

    def interpolate_rig(value, human):
        alternate_rig = bpy.data.objects["HG_Rig_TALL"]
        old_rig = bpy.data.objects["OLD"]
        rig = human.rig_obj
        bpy.ops.object.mode_set(mode="EDIT")

        for ebone in rig.data.edit_bones:
            ebone_target = alternate_rig.data.edit_bones.get(ebone.name)
            ebone_old = old_rig.data.edit_bones.get(ebone.name)

            if not ebone_target or not ebone_old:
                print("skipping", ebone.name)
                continue

            vec_head = ebone_target.head - ebone_old.head
            vec_tail = ebone_target.tail - ebone_old.tail
            print(vec_head, vec_tail)

            ebone.head = ebone_old.head + vec_head * value
            ebone.tail = ebone_old.tail + vec_tail * value

        bpy.ops.object.mode_set(mode="OBJECT")

    interpolate_rig(value, human)


class BoneSizeProps(bpy.types.PropertyGroup):
    """Subclass of HG_SETTINGS, contains float properties for scaling bones"""

    tall: FloatProperty(
        default=0.0,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: update_length(s.tall, c),
    )

    # TODO automatic generation of properties
    # def __new__(cls, *args, **kwargs):
    #     cls.__annotations__.update(
    #         create_bone_props(
    #             [
    #                 "head",
    #                 "neck",
    #                 "chest",
    #                 "shoulder",
    #                 "breast",
    #                 "hips",
    #                 "upper_arm",
    #                 "forearm",
    #                 "hand",
    #                 "thigh",
    #                 "shin",
    #                 "foot",
    #             ]
    #         )
    #     )
    #     self = super().__new__(*args, **kwargs)
    #     return self

    head: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(
            c.object
        ).creation_phase.body.set_bone_scale(s.head, "head", c),
    )
    neck: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(
            c.object
        ).creation_phase.body.set_bone_scale(s.neck, "neck", c),
    )

    chest: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(
            c.object
        ).creation_phase.body.set_bone_scale(s.chest, "chest", c),
    )
    shoulder: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(
            c.object
        ).creation_phase.body.set_bone_scale(s.shoulder, "shoulder", c),
    )
    breast: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(
            c.object
        ).creation_phase.body.set_bone_scale(s.breast, "breast", c),
    )
    hips: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(
            c.object
        ).creation_phase.body.set_bone_scale(s.hips, "hips", c),
    )

    upper_arm: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(
            c.object
        ).creation_phase.body.set_bone_scale(s.upper_arm, "upper_arm", c),
    )
    forearm: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(
            c.object
        ).creation_phase.body.set_bone_scale(s.forearm, "forearm", c),
    )
    hand: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(
            c.object
        ).creation_phase.body.set_bone_scale(s.hand, "hand", c),
    )

    thigh: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(
            c.object
        ).creation_phase.body.set_bone_scale(s.thigh, "thigh", c),
    )
    shin: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(
            c.object
        ).creation_phase.body.set_bone_scale(s.shin, "shin", c),
    )
    foot: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(
            c.object
        ).creation_phase.body.set_bone_scale(s.foot, "foot", c),
    )
