# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy  # type: ignore


class HG_UL_SHAPEKEYS(bpy.types.UIList):
    """UIList showing shapekeys."""

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        enabledicon = "CHECKBOX_HLT" if item.enabled else "CHECKBOX_DEHLT"

        row = layout.row(align=True)
        row.enabled = item.on
        row.prop(item, "enabled", text="", icon=enabledicon, emboss=False)

        row.label(text=item.sk_name)
        if not item.on:
            row.label(text="Muted", icon="INFO")


class SHAPEKEY_ITEM(bpy.types.PropertyGroup):
    """Properties of the items in the uilist."""

    sk_name: bpy.props.StringProperty(name="Modifier Name", default="")
    enabled: bpy.props.BoolProperty(default=False)
    on: bpy.props.BoolProperty(default=True)


class HG_UL_SAVEHAIR(bpy.types.UIList):
    """UIList showing hair particle systems."""

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        enabledicon = "CHECKBOX_HLT" if item.enabled else "CHECKBOX_DEHLT"

        row = layout.row(align=True)
        row.prop(item, "enabled", text="", icon=enabledicon, emboss=False)

        row.label(text=item.ps_name)


class SAVEHAIR_ITEM(bpy.types.PropertyGroup):
    """Properties of the items in the uilist."""

    ps_name: bpy.props.StringProperty(name="Hair Name", default="")
    enabled: bpy.props.BoolProperty(default=False)


class HG_UL_SAVEOUTFIT(bpy.types.UIList):
    """UIList showing shapekeys."""

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):

        enabledicon = "CHECKBOX_HLT" if item.enabled else "CHECKBOX_DEHLT"

        row = layout.row(align=True)
        row.prop(item, "enabled", text="", icon=enabledicon, emboss=False)

        row = layout.row(align=True)
        row.label(text=item.obj_name)

        if not item.cor_sks_present:
            row.alert = True
            row.label(text="No Corrective shapekeys", icon="ERROR")
            return
        if not item.weight_paint_present:
            row.alert = True
            row.label(text="No weight paint", icon="ERROR")
            return


class SAVEOUTFIT_ITEM(bpy.types.PropertyGroup):
    """Properties of the items in the uilist."""

    obj_name: bpy.props.StringProperty(name="Ojbect Name", default="")
    cor_sks_present: bpy.props.BoolProperty(default=False)
    weight_paint_present: bpy.props.BoolProperty(default=False)
    enabled: bpy.props.BoolProperty(default=False)


class HG_UL_MULTI_RECIPE(bpy.types.UIList):
    """UIList showing the recipes to process the humans with."""

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        layout.label(text=item.name)
