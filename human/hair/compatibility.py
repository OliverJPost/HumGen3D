import bpy

def set_children_percent(particle_settings, amount) -> None:
    if bpy.app.version >= (4, 0 ,0):
        particle_settings.child_percent = amount
    else:
        particle_settings.child_nbr = amount

def get_children_percent(particle_settings) -> float:
    if bpy.app.version >= (4, 0 ,0):
        return particle_settings.child_percent
    else:
        return particle_settings.child_nbr