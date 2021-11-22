import bpy  # type:ignore

from ..core.HG_PCOLL import get_hg_icon


class VIEW3D_MT_hg_marker_add(bpy.types.Menu):
    # Define the "Single Vert" menu
    bl_idname = "VIEW3D_MT_hg_marker_add"
    bl_label = "Human Generator Markers"

    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'INVOKE_REGION_WIN'
        
        layout.operator(
            'wm.url_open',
            text='Tutorial',
            icon='HELP'
        ).url = 'https://publish.obsidian.md/human-generator/Using+the+batch+mode/Using+the+batch+generator'
        
        layout.separator()
        
        for primitive in ['a_pose', 't_pose', 'standing_around', 'sitting', 'socializing', 'walking', 'running']:
            layout.operator("hg3d.add_batch_marker",
                            text=primitive.capitalize().replace('_', ' '),
                            icon_value = get_hg_icon(primitive)
                            ).marker_type = primitive                


def add_hg_primitive_menu(self, context):
    layout = self.layout
    layout.operator_context = 'INVOKE_REGION_WIN'

    layout.separator()
    layout.menu("VIEW3D_MT_hg_marker_add",
                text="Human Generator Markers", icon_value = get_hg_icon('HG_icon'))
