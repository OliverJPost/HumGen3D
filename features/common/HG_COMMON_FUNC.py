"""
Contains functions that get used a lot by other operators
"""  

import os
import time
from pathlib import Path

import bpy  # type: ignore


#MODULE
def add_to_collection(context, obj, collection_name = 'HumGen') -> bpy.types.Collection:
    """Adds the giver object toa colleciton. By default added to HumGen collection

    Args:
        obj (Object): object to add to collection
        collection_name (str, optional): Name of collection. Defaults to 'HumGen'.

    Returns:
        bpy.types.Collection: Collection the object was added to
    """
    collection = bpy.data.collections.get(collection_name)
    
    if not collection:
        collection = bpy.data.collections.new(name= collection_name)
        if collection_name == "HumGen_Backup [Don't Delete]":
            bpy.data.collections["HumGen"].children.link(collection)
            context.view_layer.layer_collection.children['HumGen'].children[
                collection_name].exclude = True
        elif collection_name == 'HG Batch Markers':
            hg_collection = bpy.data.collections.get('HumGen')
            if not hg_collection:
                hg_collection = bpy.data.collections.new(name = 'HumGen')
                context.scene.collection.children.link(hg_collection)
            hg_collection.children.link(collection)
        else:
            context.scene.collection.children.link(collection)

    try:
        context.scene.collection.objects.unlink(obj)
    except:
        obj.users_collection[0].objects.unlink(obj)

    collection.objects.link(obj)

    return collection

#MODULE
def get_prefs() -> bpy.types.AddonPreferences:
    """Get HumGen preferences

    Returns:
        AddonPreferences: HumGen user preferences
    """
    addon_name = __package__.split('.')[0]
    
    return bpy.context.preferences.addons[addon_name].preferences

#MODULE
def find_human(obj, include_applied_batch_results = False) -> bpy.types.Object:
    """Checks if the passed object is part of a HumGen human
    
    This makes sure the add-on works as expected, even if a child object of the 
    rig is selected. 

    Args:
        obj (bpy.types.Object): Object to check for if it's part of a HG human
        include_applied_batch_results (bool): If enabled, this function will
            return the body object for humans that were created with the batch
            system and which armatures have been deleted instead of returning
            the rig. Defaults to False

    Returns:
        Object: Armature of human (hg_rig) or None if not part of human (or body object
        if the human is an applied batch result and include_applied_batch_results
        is True)
    """
    if not obj: 
        return None
    elif not obj.HG.ishuman:
        if obj.parent:
            if obj.parent.HG.ishuman:
                return obj.parent
        else:
            return None
    else:
        if all(is_batch_result(obj)):
            if include_applied_batch_results:
                return obj
            else:
                return None
            
        return obj

def is_batch_result(obj) -> 'tuple[bool, bool]':
    return obj.HG.batch_result, obj.HG.body_obj == obj

#MODULE
def apply_shapekeys(ob):
    """Applies all shapekeys on the given object, so modifiers on the object can
    be applied

    Args:
        ob (Object): object to apply shapekeys on
    """
    bpy.context.view_layer.objects.active = ob
    if not ob.data.shape_keys:
        return

    bpy.ops.object.shape_key_add(from_mix=True)
    ob.active_shape_key.value = 1.0
    ob.active_shape_key.name  = "All shape"
    
    i = ob.active_shape_key_index

    for n in range(1,i):
        ob.active_shape_key_index = 1
        ob.shape_key_remove(ob.active_shape_key)
            
    ob.shape_key_remove(ob.active_shape_key)   
    ob.shape_key_remove(ob.active_shape_key)
            

def ShowMessageBox(message = "", title = "Human Generator - Alert", icon = 'INFO'):
    """Shows a message popup with the passed text

    Args:
        message (str, optional): Message to display. Defaults to "".
        title (str, optional): Title for popup. Defaults to "Human Generator - Alert".
        icon (str, optional): Icon code. Defaults to 'INFO'.
    """
    def draw(self, context):
        for line in message.splitlines():
            self.layout.label(text = line)

    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)

def ShowConfirmationBox(message = ''):
    """Shows a confirmation box to the user with the given text"""    
    def draw(self, context):
        self.layout.label(text = message)

    bpy.context.window_manager.invoke_props_dialog(draw)

def make_path_absolute(key):
    """Makes sure the passed path is absolute

    Args:
        key (str): path
    """

    props = bpy.context.scene.HG3D 
    sane_path = lambda p: os.path.abspath(bpy.path.abspath(p)) 
    if key in props and props[key].startswith('//'):
        props[key] = sane_path(props[key])

def show_message(self, msg):
    hg_log(msg)
    self.report({'WARNING'}, msg)
    ShowMessageBox(message = msg)

def hg_delete(obj):
    me = obj.data if (obj and obj.type == 'MESH') else None

    images, materials = _get_mats_and_images(obj)    
    
    bpy.data.objects.remove(obj)

    if me and not me.users:
        bpy.data.meshes.remove(me)

    for material in [m for m in materials if m and not m.users]:
        try:
            bpy.data.materials.remove(material)
        except Exception as e:
            hg_log('Error while deleting material: ', e)
            pass        

    for image in [i for i in images if i and not i.users]:
        try:
            bpy.data.images.remove(image)
        except Exception as e:
            hg_log('Error while deleting image: ', e)
            pass

def _get_mats_and_images(obj):
    images = []
    materials = []
    if obj.type != 'MESH':
        return [],[]
    try:       
        for mat in obj.data.materials:
            materials.append(mat)
            nodes = mat.node_tree.nodes
            for node in [n for n in nodes if n.bl_idname == 'ShaderNodeTexImage']:
                images.append(node.image)
    except:
        raise
        pass
    return list(set(images)), materials

def get_addon_root()->str:
    """Get the filepath of the addon root folder in the Blender addons directory

    Returns:
        str: path of the root directory of the add-on
    """
    
    root_folder = Path(__file__).parent.parent.parent.absolute()
    
    return str(root_folder)

def time_update(label, prev_time) -> int:
    hg_log(label, round(time.time()-prev_time, 2))
    return time.time()
    
def toggle_hair_visibility(obj, show = True):
    for mod in obj.modifiers:
        if mod.type == 'PARTICLE_SYSTEM':
            mod.show_viewport = show

def hg_log(*message, level = 'INFO'):
    """Writes a log message to the console. Warning, Error and Critical produce
    a color coded message.

    Args:
        message (str or list[str]): Message to display in log
        level (str): Level of log message in ('DEBUG', 'INFO', 'WARNING', 
            'ERROR', 'CRITICAL') Defaults to 'INFO'.

    Raises:
        ValueError: Raised if level string is not in possible levels
    """
    
    log_levels = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'BACKGROUND')
    if level not in log_levels:
        raise ValueError(f'{level} not found in {log_levels}')
    
    if get_prefs().silence_all_console_messages:
        return
    
    if level == 'DEBUG' and not get_prefs().debug_mode:
        return
    
    level_tag = f'HG_{level.upper()}:\t'
    
    bcolors = {
        'DEBUG': '',
        'INFO': '',
        'WARNING': '\033[93m',
        'ERROR': '\033[91m',
        'CRITICAL': '\033[91m',
        'BACKGROUND': '\033[94m',
        'ENDC': '\033[0m'
    }
    
    if level in bcolors:
        print(bcolors[level] + level_tag + bcolors['ENDC'], *message)

def print_context(context):
    context_dict = {
        "active": context.object,
        "active object": context.active_object,
        "selected objects": context.selected_objects,
        "area": context.area,
        "scene": context.scene,
        "mode": context.mode,
        "view layer": context.view_layer,
        "visible objects": context.visible_objects
    }
    
    hg_log(context_dict)

def unhide_human(obj):
    """Makes sure the rig is visible. If not visible it might cause problems

    Args:
        obj (Object): object to unhide
    """
    obj.hide_viewport = False
    obj.hide_set(False)

class HumGenException(Exception):
    pass
