# type:ignore
# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE


from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.user_interface.icons.icons import get_hg_icon


class CpackEditingSystem:
    # cpack editing props
    editing_cpack: StringProperty()
    show_content_overview: BoolProperty()
    grid_columns: IntProperty(name="Grid columns", default=0, min=0, max=20)
    cpack_content_search: StringProperty()
    newly_added_ui: BoolProperty(default=False)
    removed_ui: BoolProperty(default=False)
    custom_content_categ: EnumProperty(
        name="Content type",
        description="",
        items=[
            ("all", "Everything", ""),
            ("humans", "Starting Humans", ""),
            ("texture", "Textures", ""),
            ("shapekeys", "Shape Keys", ""),
            ("livekeys", "Live Keys", ""),
            ("hair", "Hairstyles", ""),
            ("face_hair", "Facial hair", ""),
            ("pose", "Poses", ""),
            ("outfit", "Outfits", ""),
            ("footwear", "Footwear", ""),
            ("pattern", "Patterns", ""),
            ("scripts", "Scripts", ""),
            ("process_templates", "Process templates", ""),
        ],
        default="humans",
    )
    cpack_name: StringProperty()
    cpack_creator: StringProperty()
    cpack_version: IntProperty(min=0)
    cpack_subversion: IntProperty(min=0)
    cpack_weblink: StringProperty()
    cpack_export_folder: StringProperty(subtype="DIR_PATH")
    hide_other_packs: BoolProperty(default=True)

    def _draw_cpack_editing_ui(self, layout, context):
        """Draws the UI for editing content packs.

        This is an exclusive UI, no other items of the preferences are shown while this
        is active

        Args:
            layout (UILayout): layout to draw in
        """
        split = layout.row(align=True).split(factor=0.3, align=True)

        sidebar = split.box().column()  # the bar on the left of the editing UI
        self._draw_sidebar(context, sidebar)

        main = split.column()  # the main body of the editing UI

        self._draw_main_topbar(main)
        self._draw_content_grid(main, context)

    def _draw_content_overview_ui(self, layout, context):
        row = layout.row()
        row.scale_y = 2
        row.operator(
            "hg3d.toggle_content_overview",
            text="Back to preferences",
            icon="BACK",
        ).toggle_state = False
        self._draw_main_topbar(layout)
        self._draw_content_grid(layout, context, show_include_button=False)

    def _draw_sidebar(self, context, sidebar):
        sidebar.scale_y = 1.5

        sidebar.operator(
            "wm.url_open", text="Tutorial", icon="URL"
        ).url = "https://help.humgen3d.com/editor"

        # Metadata header
        titlebar = sidebar.box().row()
        titlebar.alignment = "CENTER"
        titlebar.scale_y = 2
        titlebar.label(text="Metadata", icon="ASSET_MANAGER")

        # Metadata body
        col = sidebar.column()
        col.use_property_split = True
        col.use_property_decorate = False
        row = col.row()
        row.enabled = False
        row.prop(self, "cpack_name", text="Pack name")
        col.prop(self, "cpack_creator", text="Creator")
        col.prop(self, "cpack_weblink", text="Weblink")
        row = col.row()
        row.prop(self, "cpack_version", text="Version")
        row.prop(self, "cpack_subversion", text="")

        sidebar.separator()

        self._draw_total_added_removed_counters(context, sidebar)

        a_sidebar = sidebar.column()
        a_sidebar.alert = True
        a_sidebar.operator(
            "hg3d.exit_cpack_edit", text="Exit without saving", depress=True
        )
        sidebar.operator("hg3d.save_cpack", text="Save", depress=True).export = False
        sidebar.prop(self, "cpack_export_folder", text="Export folder")
        sidebar.operator(
            "hg3d.save_cpack", text="Save and export", depress=True
        ).export = True

    def _draw_total_added_removed_counters(self, context, sidebar):
        """Draws the three counters in the sidebar.

        Total items, added items and removed items.
        Both added and removed have a dropdown showing all of those items in a list

        Args:
            sidebar (UILayout): layout to draw in
        """
        coll = context.scene.custom_content_col

        sidebar.label(text=f"Total items: {len([c for c in coll if c.include])}")

        # TODO these two can be joined into one function
        # Added
        box = sidebar.box()
        newly_added_list = [c for c in coll if c.newly_added]
        box.prop(
            self,
            "newly_added_ui",
            text=f"Added items: {len(newly_added_list)}",
            icon="TRIA_RIGHT",
            toggle=True,
            emboss=False,
        )
        if self.newly_added_ui:
            col = box.column()
            col.scale_y = 0.5
            for c in newly_added_list:
                row = col.row()
                if c.gender == "none":
                    kwarg = {"icon_value": get_hg_icon(f"{c.gender}_true")}
                else:
                    kwarg = {"icon": "BLANK1"}
                row.label(text=c.name, **kwarg)
                row.prop(c, "include", text="")

        # Removed
        box = sidebar.box()
        removed_ist = [c for c in coll if c.removed]
        box.prop(
            self,
            "removed_ui",
            text=f"Removed items: {len(removed_ist)}",
            icon="TRIA_RIGHT",
            toggle=True,
            emboss=False,
        )
        if self.removed_ui:
            col = box.column()
            col.scale_y = 0.5
            for c in removed_ist:
                row = col.row()
                row.label(text=c.name, **kwargs(c))
                row.prop(c, "include", text="")

    def _draw_main_topbar(self, main):
        """Draws the top bar of the main section of the editing UI.

        This contains the enum to swith categories and the filter items (search and
        hide others)

        Args:
            main (UILayout): layout to draw in
        """
        box = main.box()

        row = box.row(align=True)
        row.scale_y = 2
        row.prop(self, "custom_content_categ", text="")

        subrow = box.row(align=True)
        subrow.prop(self, "cpack_content_search", text="Filter", icon="VIEWZOOM")

        if self.cpack_content_search:
            row = subrow.row(align=True)
            row.alert = True
            row.operator(
                "hg3d.clear_searchbox", text="", icon="X", depress=True
            ).searchbox_name = "cpack_creator"

        subrow.separator()
        subrow.prop(self, "hide_other_packs", text="Hide content from other packs")
        subrow.prop(self, "grid_columns")

    def _draw_content_grid(self, col, context, show_include_button=True):
        flow = col.grid_flow(
            row_major=True,
            even_columns=True,
            even_rows=True,
            columns=get_prefs().grid_columns,
        )

        categ = self.custom_content_categ
        coll = context.scene.custom_content_col
        if categ != "all":
            coll = [c for c in coll if c.categ == categ]
        if self.cpack_content_search:
            coll = [c for c in coll if self.cpack_content_search in c.name]

        for item in coll:
            if self.hide_other_packs and item.existing_content:
                continue
            box = flow.box()
            box.label(text=item.name)
            gender = item.gender
            if gender == "none":
                box.label(icon="BLANK1")
            else:
                box.label(
                    text=gender.capitalize(),
                    icon_value=get_hg_icon(f"{gender}_true"),
                )

            scale = 10 if get_prefs().grid_columns < 5 else 5
            box.template_icon(item.icon_value, scale=scale)

            col = box.column(align=True)
            if show_include_button:
                incl_icon = "CHECKBOX_HLT" if item.include else "CHECKBOX_DEHLT"
                col.prop(item, "include", text="Include", icon=incl_icon, toggle=True)
            col.operator(
                "hg3d.show_content_item", text="Open folder", icon="FILE_FOLDER"
            ).item_name = item.name
            col.operator(
                "hg3d.edit_content_item", text="Edit", icon="GREASEPENCIL"
            ).item_name = item.name
            row = col.row()
            row.alert = True
            row.operator(
                "hg3d.delete_content_item", text="Delete!", icon="TRASH"
            ).item_name = item.name
