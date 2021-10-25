import os
from pathlib import Path

import bpy  # type:ignore

from ...features.common.HG_COMMON_FUNC import add_to_collection, get_addon_root


class HG_OT_ADD_BATCH_MARKER(bpy.types.Operator):
    bl_idname = "hg3d.add_batch_marker"
    bl_label = "Add marker"
    bl_description = "Adds this marker at the 3D cursor location"
    bl_options = {'REGISTER', 'UNDO'}

    marker_type: bpy.props.StringProperty()

    def execute(self, context):
        blendfile = os.path.join(get_addon_root(), 'data', 'hg_batch_markers.blend')
        
        with bpy.data.libraries.load(blendfile, link = False) as (data_from, data_to):
            data_to.objects = [f'HG_MARKER_{self.marker_type.upper()}',]

        #link to scene
        marker = data_to.objects[0]
        context.scene.collection.objects.link(marker)
        add_to_collection(context, marker, collection_name = 'HG Batch Markers')        
        
        marker.location = context.scene.cursor.location
        
        marker['hg_batch_marker'] = self.marker_type
        
        return {'FINISHED'}

