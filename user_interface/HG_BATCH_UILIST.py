"""
This file is currently inactive
"""

import bpy  # type: ignore

from ..core.HG_PCOLL import preview_collections
from ..core.settings.HG_PROP_FUNCTIONS import find_folders, find_item_amount


class HG_UL_BATCH_CLOTHING(bpy.types.UIList):
    """
    UIList showing clothing libraries
    """   

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        uilist_layout(layout, context, item)

class HG_UL_BATCH_EXPRESSIONS(bpy.types.UIList):
    """
    UIList showing clothing libraries
    """   

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        uilist_layout(layout, context, item)


def uilist_layout(layout, context, item):
    enabledicon = "CHECKBOX_HLT" if item.enabled else "CHECKBOX_DEHLT"
    hg_icons = preview_collections["hg_icons"]
    
    #islockedicon = "LOCKED" if item.islocked else "BLANK1"


    row = layout.row(align = True)
    row.prop(item, "enabled", text="", icon=enabledicon, emboss=False)

    row.label(text=item.library_name)

    subrow = row.row(align = True) 
    try:
        subrow.scale_x = .7
        subrow.label(text= str(item.male_items), icon_value = hg_icons['male_true'].icon_id if item.male_items != 0 else hg_icons['male_false'].icon_id)

        subrow.label(text= str(item.female_items), icon_value = hg_icons['female_true'].icon_id if item.female_items != 0 else hg_icons['female_false'].icon_id)
    except:
        subrow.alignment = 'RIGHT'
        subrow.label(text = str(item.count))


class BATCH_CLOTHING_ITEM(bpy.types.PropertyGroup):
    """
    Properties of the items in the uilist
    """
    library_name: bpy.props.StringProperty(
        name='Library Name',
        description="",
        default= '',
        )  
    enabled: bpy.props.BoolProperty(default = True)
    male_items : bpy.props.IntProperty(default = 0)
    female_items : bpy.props.IntProperty(default = 0)

class BATCH_EXPRESSION_ITEM(bpy.types.PropertyGroup):
    """
    Properties of the items in the uilist
    """
    library_name: bpy.props.StringProperty(
        name='Library Name',
        description="",
        default= '',
        )  
    enabled: bpy.props.BoolProperty(default = True)
    count : bpy.props.IntProperty(default = 0)


def batch_uilist_refresh(self, context, categ):
    """
    Refreshes uilist
    """
    add_temp =[]

    if categ == 'outfits':
        collection = context.scene.batch_clothing_col
        gender = True
    else:
        if categ == 'poses':
            collection = context.scene.batch_pose_col
        elif categ == 'expressions':
            collection = context.scene.batch_expressions_col
        
        gender = False

    enabled_dict = {i.name: i.enabled for i in collection}

    found_folders_male = find_folders(self, context, categ, gender, include_all = False, gender_override= 'male')
    collection.clear()

    for folder in found_folders_male:
        item = collection.add()
        #['{}_col{}'.format(categ, '' if not gender else '_{}'.format(gender[0]))]
        item.name = folder[0]
        item.library_name = folder[0]
        if folder[0] in [n for n in enabled_dict]:
            item.enabled = enabled_dict[folder[0]]
        if gender:
            item.male_items = find_item_amount(context, categ, 'male', folder[0])
        else:
            item.count = find_item_amount(context, categ, False, folder[0])

    if not gender:
        return

    found_folders_female = find_folders(self, context, categ, gender, include_all = False, gender_override= 'female')

    for folder in found_folders_female:
        if folder[0] in [item.library_name for item in collection]:
            item = collection[folder[0]]
        else:
            item = collection.add()
            item.name = folder[0]
            item.library_name = folder[0]
        item.female_items = find_item_amount(context, categ, 'female', folder[0])


class HG_REFRESH_UILISTS(bpy.types.Operator):
    """
    clears searchfield
    """
    bl_idname = "hg3d.refresh_batch_uilists"
    bl_label = "Refresh"
    bl_description = "Refresh the library list"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self,context):
        batch_uilist_refresh(self, context, 'outfits')
        batch_uilist_refresh(self, context, 'expressions')

        return {'FINISHED'}
