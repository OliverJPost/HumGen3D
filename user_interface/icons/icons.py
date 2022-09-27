# Make list for now to ensure it points to the same object
hg_icons = []


def get_hg_icon(icon_name) -> int:
    icon_list = hg_icons[0]
    try:
        return icon_list[icon_name].icon_id
    except IndexError:
        return "ERROR"
