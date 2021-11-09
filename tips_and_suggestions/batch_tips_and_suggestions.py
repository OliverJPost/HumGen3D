import bpy


def get_batch_tips_from_context(context, sett, hg_rig):
    
    markers = [o for o in bpy.data.objects if 'hg_marker' in o]
    if not markers:
        yield no_markers_in_scene
        
   
no_markers_in_scene = [
'No markers in scene'
'ERROR',
"""You currently don't have any batch
markers in this scene. Add some
markers in the Add Object menu
(shift+A) in the Human Generator
section.
""",
'',
''
]
