import os

import bpy
from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.human.human import Human
from HumGen3D.user_interface.panel_functions import draw_paragraph


def draw_category_ui(context, layout, content_type):
    _draw_header_box(
        layout,
        f"What category should this \n{content_type} be saved to?",
        "BLANK1",
    )

    cc_sett = context.scene.HG3D.custom_content
    col = layout.column()
    col.scale_y = 1.5

    if content_type == "key":
        row = col.row()
        row.scale_y = 0.75
        row.alignment = "CENTER"
        row.label(text="Key category:")
        row = col.row()
        row.prop(cc_sett.key, "category_to_save_to", text="")

        col.separator()

        row = col.row()
        row.scale_y = 0.75
        row.alignment = "CENTER"
        row.label(text="Subcategory:")

    row = col.row()
    category_sett = getattr(cc_sett, content_type)
    row.prop(category_sett, "existing_or_new_category", expand=True)

    if category_sett.existing_or_new_category == "existing":
        col.prop(category_sett, "chosen_existing_subcategory", text="")
        poll = category_sett.chosen_existing_subcategory not in ("All", "")
    else:
        col.prop(category_sett, "new_category_name", text="Name")
        poll = category_sett.new_category_name

    col.separator()

    _draw_next_button(layout, poll=poll)


def _draw_name_ui(context, layout, content_type):
    """Draws the tab to give the content a name.

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
    human = Human.from_existing(cc_sett.content_saving_active_human)
    if content_type == "starting_human":
        layout.label(text=f"Based on {human._active}")
    elif content_type == "key":
        layout.label(text=f"Original name: {cc_sett.key.key_to_save}")

    col = layout.column()
    col.scale_y = 1.5

    col.prop(getattr(cc_sett, content_type), "name", text="Name")

    existing_names = _get_existing_names(human, content_type)

    name = getattr(cc_sett, content_type).name
    if name and name.lower() in existing_names:
        col_a = col.column(align=True)
        col_a.alert = True
        col_a.label(text="Name already exists", icon="ERROR")
        col_a.label(text="Overwrite?")

    if content_type in ("footwear", "outfit"):
        col.prop(cc_sett, "open_when_finished", text="Open when finished")

    if content_type == "texture":
        try:
            from PIL import Image
        except ImportError:
            col_a = col.column(align=True)
            col_a.alert = True
            draw_paragraph(
                col_a,
                "Python Image Library not installed. We'll try to install it for you. This might take a while.",
            )

    poll = bool(name)

    _draw_save_button(layout, content_type, poll=poll)


def _get_existing_names(human, content_type):
    # TODO remove duplicity from pcoll file
    folders = {
        "hair": ("hair",),
        "starting_human": (os.path.join("models", human.gender),),
        "key": ("livekeys", "shapekeys"),
        "outfit": ("outfits",),
        "footwear": ("footwear",),
        "pose": ("poses",),
        "texture": (os.path.join("textures", human.gender),),
    }
    existing_names = []
    for folder in folders[content_type]:
        full_path = os.path.join(get_prefs().filepath, folder)
        for *_, files in os.walk(full_path):
            existing_names.extend(file.split(".")[0].lower() for file in files)

    return set(existing_names)


def _draw_thumbnail_selection_ui(context, layout, content_type):
    """Tab to select/generate a thumbnail for this content.

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

    if cc_sett.thumbnail_saving_enum != "last_render":
        layout.template_icon_view(
            cc_sett,
            "preset_thumbnail_enum",
            show_labels=True,
            scale=8,
            scale_popup=10,
        )
    if cc_sett.thumbnail_saving_enum == "custom":
        layout.template_ID(cc_sett, "preset_thumbnail", open="image.open")
        layout.label(text="256*256px recommended", icon="INFO")
    elif cc_sett.thumbnail_saving_enum == "auto":
        __draw_auto_thumbnail_ui(layout, content_type)

    elif cc_sett.thumbnail_saving_enum == "last_render":
        layout.label(text="256*256px recommended", icon="INFO")
        render_results = [
            img for img in bpy.data.images if img.name.startswith("Render Result")
        ]
        if len(render_results) > 1:
            col = layout.column(align=True)
            col.alert = True
            col.label(text="Multiple render results found", icon="ERROR")
            col.label(text="Only 'Render Result' will be saved.", icon="ERROR")
            for img in render_results:
                col.label(text=img.name)

    _draw_next_button(layout, poll=cc_sett.preset_thumbnail)


def __draw_auto_thumbnail_ui(layout, content_type):
    """Draw UI inside thumbnail tab for automatically rendering a thumbnail.

    Args:
        layout (UILayout): layout to draw in
        content_type (str): what type of content to make thumbnail for
    """
    row = layout.row()
    row.scale_y = 1.5
    thumbnail_type_dict = {
        "head_side": ("hair",),
        "head_front": ("starting_human", "texture"),
        "full_body_front": ("outfit",),
        "full_body_side": ("pose",),
        "foot": ("footwear",),
    }

    thumbnail_type = next(
        t_type
        for t_type, c_type_set in thumbnail_type_dict.items()
        if content_type in c_type_set
    )

    operator = row.operator(
        "hg3d.auto_render_thumbnail",
        text="Render [Automatic]",
        icon="RENDER_STILL",
    )
    operator.thumbnail_type = thumbnail_type
    if content_type in ("hair", "outfit", "footwear"):
        operator.white_material = True
    else:
        operator.white_material = False


def _draw_save_button(layout, content_type, poll=True):
    """Draws a saving button on the last tab of the content saving ui.

    Also shows small previous button next to it. Button is disabled if poll ==
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
    ).go_next = False

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
    """Draw warning to warn user for different active human.

    Draw a warning at the top of the content saving tab if the user has
    selected a different human than the one the content saving was
    initialised for.

    Args:
        context (context): BL context
        layout (UILayout): layout to draw warning button in
    """
    cc_sett = context.scene.HG3D.custom_content

    active_human = Human.from_existing(context.object).objects.rig
    try:
        if active_human and active_human != cc_sett.content_saving_active_human:
            row = layout.row()
            row.alert = True
            row.label(
                text=f"Selected human is not {cc_sett.content_saving_active_human.name}"
            )
    except AttributeError:
        row = layout.row()
        row.alert = True
        row.label(text="Human seems to be deleted")


def _draw_header_box(layout, text, icon):
    """Draws a box with an icon to show the name/description of this tab.

    If the text consists of multiple lines the icon will center in the height axis

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
    """Draws a button to go to the next tab.

    Also draws previous button if the index is higher than 0.
    Next button is disabled if poll == False

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
        ).go_next = False

    # Hide next button if poll is False
    if not poll:
        row = row.row(align=True)
        row.enabled = False

    row.operator(
        "hg3d.nextprev_content_saving_tab",
        text="Next",
        icon="TRIA_RIGHT",
        depress=True,
    ).go_next = True
