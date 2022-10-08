import bpy
from HumGen3D.human.human import Human


def _draw_name_ui(context, layout, content_type):
    """Draws the tab to give the content a name

    Args:
        context (context): Blender context
        layout (UILayout): layout to draw in
        content_type (str): String about what content type this is
    """
    cc_sett = context.scene.HG3D.custom_content

    _draw_header_box(
        layout,
        f"Give your {content_type.replace('sk_', '')} a name",
        "OUTLINER_OB_FONT",
    )

    col = layout.column()
    col.scale_y = 1.5

    # FIXME crash when spaces in name
    if content_type in ("pose", "key", "hair"):
        col.prop(getattr(cc_sett, content_type), "name", text="Name")
        poll = bool(getattr(cc_sett, content_type).name)
    else:
        col.prop(cc_sett, f"{content_type}_name", text="Name")
        poll = bool(getattr(cc_sett, f"{content_type}_name"))

    _draw_save_button(layout, content_type, poll=poll)


def _draw_thumbnail_selection_ui(context, layout, content_type):
    """Tab to select/generate a thumbnail for this content

    Args:
        context (context): Blender context
        layout (UILayout): layout to draw in
        content_type (str): What type of content to get thumbnail for
    """
    cc_sett = context.scene.HG3D.custom_content

    _draw_header_box(layout, "Select a thumbnail", icon="IMAGE")

    col = layout.column(align=True)
    col.scale_y = 1.5
    col.prop(cc_sett, "thumbnail_saving_enum", text="")

    if cc_sett.thumbnail_saving_enum == "none":
        row = layout.row()
        row.alignment = "CENTER"
        row.scale_y = 3
        row.alert = True
        row.label(text="No thumbnail will be exported")
        _draw_next_button(layout)
        return

    layout.template_icon_view(
        cc_sett,
        "preset_thumbnail_enum",
        show_labels=True,
        scale=8,
        scale_popup=10,
    )
    if cc_sett.thumbnail_saving_enum == "custom":
        layout.template_ID(
            cc_sett.custom_content, "preset_thumbnail", open="image.open"
        )
        layout.label(text="256*256px recommended", icon="INFO")
    elif cc_sett.thumbnail_saving_enum == "auto":
        __draw_auto_thumbnail_ui(layout, content_type)

    elif cc_sett.thumbnail_saving_enum == "last_render":
        __draw_render_result_thumbnail_ui(layout)

    _draw_next_button(layout, poll=cc_sett.preset_thumbnail)


def __draw_render_result_thumbnail_ui(layout):
    """Draw UI inside thumbnail tab for picking the last render result

    Args:
        layout (UILayout): layout to draw in
    """
    layout.label(text="256*256px recommended", icon="INFO")
    layout.separator()
    layout.label(text="If you render does not show,", icon="INFO")
    layout.label(text="reload thumbnail category above.")


def __draw_auto_thumbnail_ui(layout, content_type):
    """Draw UI inside thumbnail tab for automatically rendering a thumbnail

    Args:
        layout (UILayout): layout to draw in
        content_type (str): what type of content to make thumbnail for
    """
    row = layout.row()
    row.scale_y = 1.5
    thumbnail_type_dict = {
        "head": ("hair", "starting_human"),
        "full_body_front": ("clothing",),
        "full_body_side": ("pose",),
    }

    thumbnail_type = next(
        t_type
        for t_type, c_type_set in thumbnail_type_dict.items()
        if content_type in c_type_set
    )

    # row.operator(
    #     "hg3d.auto_render_thumbnail",
    #     text="Render [Automatic]",
    #     icon="RENDER_STILL",
    # ).thumbnail_type = thumbnail_type #FIXME


def _draw_save_button(layout, content_type, poll=True):
    """Draws a saving button on the last tab of the content saving ui. Also
    shows small previous button next to it. Button is disabled if poll ==
    False

    Args:
        layout (UILayout): layout to draw button in
        content_type (str): type of content to save
        poll (bool, optional): Decides if button is enabled.
            Defaults to True.
    """
    split = layout.split(factor=0.1, align=True)
    row = split.row(align=True)
    row.scale_y = 1.5
    row.alert = True
    row.operator(
        "hg3d.nextprev_content_saving_tab",
        text="",
        icon="TRIA_LEFT",
        depress=True,
    ).next = False

    row = split.row(align=True)
    row.enabled = poll
    row.scale_y = 1.5
    row.operator(
        "hg3d.save_to_library",
        text="Save",
        icon="FILEBROWSER",
        depress=True,
    )


def _draw_warning_if_different_active_human(context, layout):
    """Draw a warning at the top of the content saving tab if the user has
    selected a different human than the one the content saving was
    initialised for.

    Args:
        context (context): BL context
        layout (UILayout): layout to draw warning button in
    """
    cc_sett = context.scene.HG3D.custom_content

    active_human = Human.from_existing(context.object).rig_obj
    try:
        if active_human and active_human != cc_sett.content_saving_active_human:
            row = layout.row()
            row.alert = True
            row.label(
                text=f"Selected human is not {cc_sett.content_saving_active_human.name}"
            )
    except Exception as e:
        row = layout.row()
        row.alert = True
        row.label(text="Human seems to be deleted")


def _draw_header_box(layout, text, icon):
    """Draws a box with an icon to show the name/description of this tab. If
    the text consists of multiple lines the icon will center in the height
    axis

    Args:
        layout (UILayout): layout to draw header box in
        text (str): text to display in the header box, can be multiline
        icon (str): name of icon to display in the box
    """
    box = layout.box()

    lines = text.splitlines()

    split = box.split(factor=0.1)
    icon_col = split.column()
    text_col = split.column()

    icon_col.scale_y = len(lines) * 0.7 if len(lines) > 1 else 1
    if len(lines) > 1:
        text_col.scale_y = 0.7

    icon_col.label(text="", icon=icon)

    for line in lines:
        text_col.label(text=line)


def _draw_next_button(layout, poll=True):
    """Draws a button to go to the next tab. Also draws previous button if
    the index is higher than 0. Next button is disabled if poll == False

    Args:
        layout (UILayout): layout to draw buttons in
        poll (bool, optional): poll to enable/disable next button.
            Defaults to True.
    """
    row = layout.row(align=True)
    row.scale_y = 1.5
    row.alert = True

    sett = bpy.context.scene.HG3D.custom_content

    # Show previous button if the current index is higher than 0
    if sett.content_saving_tab_index > 0:
        row.operator(
            "hg3d.nextprev_content_saving_tab",
            text="Previous",
            icon="TRIA_LEFT",
            depress=True,
        ).next = False

    # Hide next button if poll is False
    if not poll:
        row = row.row(align=True)
        row.enabled = False

    row.operator(
        "hg3d.nextprev_content_saving_tab",
        text="Next",
        icon="TRIA_RIGHT",
        depress=True,
    ).next = True
