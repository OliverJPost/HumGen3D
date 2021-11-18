import bpy


def get_batch_tips_from_context(context, sett, hg_rig):
    
    yield batch_tutorial
    
    markers = [o for o in bpy.data.objects if 'hg_marker' in o]
    if not markers:
        yield no_markers_in_scene
        

batch_tutorial = [
'Batch mode tutorial',
'HELP',
"""You can find the tutorial about
the batch mode here:
""",
(
    'URL',
    'wm.url_open',
    'Open tutorial in browser',
    'url',
    'https://publish.obsidian.md/human-generator/Using+the+batch+generator' #TODO correct url
)
]

   
no_markers_in_scene = [
'No markers in scene?',
'INFO',
"""If the purple button says
"Generate 0 Humans", add some
Human Generator markers from
the Add Object (Shift+A) menu.
""",
()
]
