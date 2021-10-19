import bpy  # type:ignore


def generate_human() -> bpy.types.Object:
    
    
    kwargs = {}
    bpy.ops.hg3d.quick_generate(**kwargs)
    

def get_pcoll_options(pcoll_name) -> list:
    sett = bpy.context.scene.HG3D
    pcoll_list = sett['previews_list_{}'.format(pcoll_name)]
    
    return pcoll_list
