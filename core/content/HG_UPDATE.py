import bpy #type: ignore
import requests #type: ignore
import json
from ... import bl_info

def check_update():
    pref = bpy.context.preferences.addons[__package__].preferences
    url  = 'https://raw.githubusercontent.com/HG3D/Public/main/versions.json'
    resp = requests.get(url)

    pref.cpack_update_required  = False
    pref.cpack_update_available = False

    try:
        update_data = json.loads(resp.text)
    except Exception as e:
        print('Failed to load HumGen update data, with error:')
        print(e)
        return
    
    try:
        #only get 2 first version numbers for required cpacks, last number can be updated without needing a new required cpack item
        current_main_version = str([bl_info['version'][0],bl_info['version'][1]]) 
        
        pref.latest_version = tuple(update_data['latest_addon'])
        
        cpack_col = bpy.context.scene.contentpacks_col 
        req_cpacks = update_data['required_cpacks'][current_main_version]
        latest_cpacks = update_data['latest_cpacks']
        
        for cp in cpack_col:
            if cp.name == 'header': #skip fake hader
                continue
            current_version = tuple(cp.pack_version)
            if not current_version:
                print('skipping cpack during update check, missing version number', cp.pack_name)
                continue

            if type(current_version) is str: #compatibility with old string method of writing versions
                current_version = [int(current_version[0]), int(current_version[2])]

            if cp.pack_name in req_cpacks:
                cp.required_version = tuple(req_cpacks[cp.pack_name])
                if tuple(req_cpacks[cp.pack_name])> current_version:
                    pref.cpack_update_required = True
            if cp.pack_name in latest_cpacks:
                cp.latest_version = tuple(latest_cpacks[cp.pack_name])
                if tuple(latest_cpacks[cp.pack_name])> current_version:
                    pref.cpack_update_available = True

    except Exception as e:
        print('Failed to compute HumGen update numbering, with error:')
        print(e)
        return
