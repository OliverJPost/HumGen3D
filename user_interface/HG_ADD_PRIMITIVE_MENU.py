import bpy #type:ignore

class VIEW3D_MT_hg_marker_add(bpy.types.Menu):
    # Define the "Single Vert" menu
    bl_idname = "VIEW3D_MT_hg_marker_add"
    bl_label = "Human Generator Markers"

    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'INVOKE_REGION_WIN'
        
        layout.operator(
            'hg3d.draw_tutorial',
            text='Tutorial',
            icon='HELP'
        ).tutorial_name = 'hairstyles_tutorial'
        
        layout.separator()
        
        for primitive in ['test_marker', 'test_marker2']:#['standing', 'sitting', 'socializing', 'walking', 'running']:
            layout.operator("hg3d.add_batch_marker",
                            text=primitive.capitalize()).marker_type = primitive

def add_hg_primitive_menu(self, context):
    layout = self.layout
    layout.operator_context = 'INVOKE_REGION_WIN'

    layout.separator()
    layout.menu("VIEW3D_MT_hg_marker_add",
                text="Human Generator", icon="DECORATE")