import bpy


def get_batch_tips_from_context(context, sett, hg_rig):
    
    markers = [o for o in bpy.data.objects if 'hg_marker' in o]
    if not markers:
        yield no_markers_in_scene
        
   
no_markers_in_scene = [
'No markers in scene?',
'INFO',
"""If the purple button says
"Generate 0 Humans", add some
Human Generator markers from
the Add Object (Shift+A) menu.
""",
'',
''
]
