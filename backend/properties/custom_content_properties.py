import bpy
from bpy.props import (  # type: ignore
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from ..content_packs.custom_content_packs import build_content_collection
from .property_functions import (
    find_folders,
    poll_mtc_armature,
    thumbnail_saving_prop_update,
)

from HumGen3D.utility_section.utility_functions import (
    refresh_hair_ul,
    refresh_shapekeys_ul,
)


class CustomContentProps(bpy.types.PropertyGroup):
    sk_collection_name: StringProperty(default="")
    show_saved_sks: BoolProperty(default=False, update=refresh_shapekeys_ul)

    hairstyle_name: StringProperty(default="")
    save_hairtype: EnumProperty(
        name="Hairtype",
        items=[
            ("head", "Regular Hair", "", 0),
            ("face_hair", "Facial Hair", "", 1),
        ],
        default="head",
    )

    savehair_male: BoolProperty(default=True)
    savehair_female: BoolProperty(default=True)
    show_eyesystems: BoolProperty(
        name="Show eye hairsystems", default=False, update=refresh_hair_ul
    )

    clothing_name: StringProperty(default="")
    saveoutfit_categ: EnumProperty(
        name="Clothing type",
        items=[
            ("outfits", "Outfit", "", 0),
            ("footwear", "Footwear", "", 1),
        ],
        default="outfits",
    )

    saveoutfit_male: BoolProperty(default=True)
    saveoutfit_female: BoolProperty(default=True)

    open_exported_outfits: BoolProperty(default=False)
    open_exported_hair: BoolProperty(default=False)
    open_exported_shapekeys: BoolProperty(default=False)

    mtc_armature: PointerProperty(
        name="Armature", type=bpy.types.Object, poll=poll_mtc_armature
    )
    mtc_add_armature_mod: BoolProperty(default=True)
    mtc_parent: BoolProperty(default=True)

    mask_long_arms: BoolProperty(default=False)
    mask_short_arms: BoolProperty(default=False)
    mask_long_legs: BoolProperty(default=False)
    mask_short_legs: BoolProperty(default=False)
    mask_torso: BoolProperty(default=False)
    mask_foot: BoolProperty(default=False)

    pose_name: StringProperty()
    pose_category_to_save_to: EnumProperty(
        name="Pose Category",
        items=[("existing", "Existing", "", 0), ("new", "Create new", "", 1)],
        default="existing",
    )
    pose_chosen_existing_category: EnumProperty(
        name="Pose Library",
        items=lambda a, b: find_folders(a, b, "poses", False),
    )
    pose_new_category_name: StringProperty()

    custom_content_categ: EnumProperty(
        name="Content type",
        description="",
        items=[
            ("starting_humans", "Starting Humans", "", 0),
            ("texture_sets", "Texture sets", "", 1),
            ("shapekeys", "Shapekeys", "", 2),
            ("hairstyles", "Hairstyles", "", 3),
            ("poses", "Poses", "", 4),
            ("outfits", "Outfits", "", 5),
            ("footwear", "Footwear", "", 6),
        ],
        default="starting_humans",
        update=build_content_collection,
    )

    content_saving_ui: BoolProperty(default=False)
    content_saving_type: StringProperty()
    mtc_not_in_a_pose: BoolProperty(default=False)

    thumbnail_saving_enum: EnumProperty(
        name="Thumbnail",
        items=[
            ("none", "No thumbnail", "", 0),
            ("auto", "Automatic render", "", 1),
            ("custom", "Select custom image", "", 2),
            ("last_render", "Use last render result", "", 3),
        ],
        default="auto",
        update=thumbnail_saving_prop_update,
    )

    content_saving_tab_index: IntProperty(default=0)

    content_saving_active_human: PointerProperty(type=bpy.types.Object)
    content_saving_object: PointerProperty(type=bpy.types.Object)
    preset_name: StringProperty(default="")
