import json
import os
from pathlib import Path
import subprocess
import bpy #type: ignore
from ... features.common.HG_COMMON_FUNC import ShowMessageBox, find_human

def refresh_modapply(self, context):
    print('refreshing modapply')
    sett = context.scene.HG3D
    col  = context.scene.modapply_col
    col.clear()

    header          = col.add()
    header.mod_name = 'HEADER'
    header.count    = 1 if sett.modapply_search_modifiers == 'summary' else 0
    objs            = build_object_list(context, sett)
    
    for obj in objs:
        for mod in obj.modifiers:
            if mod.type == 'PARTICLE_SYSTEM':
                continue            
            if sett.modapply_search_modifiers == 'individual':
                build_full_list(col, mod, obj)
            else:
                build_summary_list(col, mod)

def build_object_list(context, sett):
    objs = [obj for obj in context.selected_objects if not obj.HG.ishuman]
    if sett.modapply_search_objects != 'selected':
        humans = [find_human(context.object),] if sett.modapply_search_objects == 'full' else [obj for obj in bpy.data.objects if obj.HG.ishuman]
        for human in humans:
            objs.extend([child for child in human.children])
    return list(set(objs))

def build_full_list(col, mod, obj):
    item          = col.add()
    item.mod_name = mod.name
    item.mod_type = mod.type

    item.viewport_visible = mod.show_viewport
    item.render_visible   = mod.show_render
    item.count            = 0
    item.object           = obj

    if mod.type in ['ARMATURE', 'SUBSURF']:
        item.enabled = False
    else:
        item.enabled = True

def build_summary_list(col, mod):
    existing = [item for item in col if item.mod_type == mod.type]
    if existing:
        item = existing[0]
        item.count +=1
    else:
        item = col.add()
        item.mod_name = mod.type.title().replace('_', ' ')
        item.mod_type = mod.type
        item.count    = 1
        if mod.type in ['ARMATURE', 'SUBSURF']:
            item.enabled = False
        else:
            item.enabled = True

def get_preset_thumbnail(self, context):
    sett = context.scene.HG3D
    img = sett.preset_thumbnail
    return [(img.name, "Selected Thumbnail", "", img.preview.icon_id, 0)] if img else []    

def refresh_shapekeys_ul(self, context):
    sett = context.scene.HG3D
    pref = context.preferences.addons[__package__].preferences
    col  = context.scene.shapekeys_col
    col.clear()

    existing_sks = ['Basis',]
    if not sett.show_saved_sks:
        walker = os.walk(str(pref.filepath) + str(Path('/models/shapekeys')))
        for root, _, filenames in walker:
            for fn in filenames:
                if not os.path.splitext(fn)[1] == '.json':
                    continue
                with open(os.path.join(root,fn)) as f:
                    data = json.load(f)
                
                existing_sks.extend(data)

    hg_rig = find_human(context.object)
    if not hg_rig:
        return
    
    for sk in hg_rig.HG.body_obj.data.shape_keys.key_blocks:
        if sk.name in existing_sks:
            continue

        item = col.add()
        item.sk_name = sk.name
        item.on = True if not sk.mute else False
        if not item.on:
            item.enabled = False

def refresh_hair_ul(self, context):
    sett = context.scene.HG3D
    pref = context.preferences.addons[__package__].preferences
    col  = context.scene.savehair_col
    col.clear()

    hg_rig = find_human(context.object)
    if not hg_rig:
        return
    
    for ps in hg_rig.HG.body_obj.particle_systems:
        if ps.name.startswith('Eye') and not sett.show_eyesystems:
            continue
        item = col.add()
        item.ps_name = ps.name

#TODO if old list, make cloth_types the same again
def refresh_outfit_ul(self, context):
    sett = context.scene.HG3D
    pref = context.preferences.addons[__package__].preferences
    col  = context.scene.saveoutfit_col
    col.clear()
    
    hg_rig = next((o for o in context.selected_objects if o.HG.ishuman), None)
    sett.saveoutfit_human = hg_rig

    for obj in [o for o in context.selected_objects 
            if o.type == 'MESH' 
            and not 'hg_body' in o
            and not 'hg_eyes' in o
            and not 'hg_teeth'in o
            ]:

        item = col.add()
        item.obj_name = obj.name
        
        if obj.data.shape_keys:
            item.cor_sks_present = next((True for sk in obj.data.shape_keys.key_blocks if sk.name.startswith('cor')), False)
        
        item.weight_paint_present = 'spine' in [vg.name for vg in obj.vertex_groups] 

