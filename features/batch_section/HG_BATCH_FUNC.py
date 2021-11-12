import bpy  # type:ignore
import numpy as np  # type:ignore


def length_from_bell_curve(sett, gender, random_seed = True, samples = 1) -> list:
    """Returns one or multiple samples from a bell curve generated from the 
    batch_average_height and batch_standard_deviation properties.

    Args:
        sett (PropertyGroup): HumGen props
        gender (str): 'male' or 'female', determines the gender specific 
            batch_average_height prop
        random_seed (bool, optional): Used by the example list to make sure the 
            list doesn't update all the time. Defaults to True.
        samples (int, optional): Amount of length samples to draw. Defaults to 0.

    Returns:
        list: with the default 0 samples it returns a single length value
            in centimeters, else it returns a list of length values in cm
    """
    
    
    if sett.batch_height_system == 'metric':
        avg_height_cm = getattr(sett, f'batch_average_height_cm_{gender}')  
    else:
        ft = getattr(sett, f'batch_average_height_ft_{gender}')  
        inch = getattr(sett, f'batch_average_height_in_{gender}')  
        avg_height_cm = ft * 30.48 + inch * 2.54
    
    sd = sett.batch_standard_deviation/100
    
    if random_seed:
        np.random.seed()
    else:
        np.random.seed(0)
        
    length_list = np.random.normal(
        loc = avg_height_cm,
        scale = avg_height_cm * sd,
        size = samples
        )
    
    return length_list 

def calculate_batch_statistics(sett):
    """Returns values to show the user how their choices in the batch settings
    will impact the render times, memory usage and filesize. Good luck reading
    this function, it's a bit of a mess.

    Args:
        sett (PropertyGroup): Addon properties

    Returns:
        dict: Dict with strings that explain to the user what the impact is
    """
    eevee_time = 0
    eevee_memory = 0
    cycles_time = 0
    cycles_memory = 0
    scene_memory = 0
    storage_weight = 0
    
    if sett.batch_hair:
        storage_weight += 10
        p_quality = sett.batch_hair_quality_particle
        if p_quality == 'high':
            eevee_time += 1.58
            eevee_memory += 320
            cycles_time += 2.0
            cycles_memory += 280
            scene_memory += 357
        elif p_quality == 'medium':
            eevee_time += 0
            eevee_memory += 180
            cycles_time += 0.29
            cycles_memory += 36
            scene_memory += 182
        elif p_quality == 'low':
            eevee_time += 0
            eevee_memory += 100
            cycles_time += 0.25
            cycles_memory += 22
            scene_memory += 122
        else:
            eevee_time += 0  
            eevee_memory += 100
            cycles_time += 0.25
            cycles_memory += 10
            scene_memory += 122
        
    if sett.batch_clothing:
        storage_weight += 8
        scene_memory += 180
        if sett.batch_apply_clothing_geometry_masks:
            storage_weight -= 1

    if sett.batch_texture_resolution == 'high':
        if sett.batch_clothing:
            eevee_time += 11.31
            eevee_memory += 2120
            cycles_time += 1.88
            cycles_memory += 1182
    elif sett.batch_texture_resolution == 'optimised':
        if sett.batch_clothing:
            eevee_time -= 1.81
            eevee_memory -= 310
            cycles_time += 0.31
            cycles_memory -= 140
        else:
            eevee_time -= 3.63     
            eevee_memory -= 654   
            cycles_time -= 0.23
            cycles_memory -= 330
    elif sett.batch_texture_resolution == 'performance':
        if sett.batch_clothing:
            eevee_time -= 2.86
            eevee_memory -= 523
            cycles_time += 0.11
            cycles_memory -= 271
        else:
            eevee_time -= 3.75  
            eevee_memory -= 700   
            cycles_time -= 0.48
            cycles_memory -= 352
           
    if sett.batch_delete_backup:
        storage_weight -= 42 
        eevee_memory -= 250
        scene_memory -= 240
        
    if sett.batch_apply_shapekeys:
        storage_weight -= 6    
        eevee_time -= 0.2  
        eevee_memory -= 60
        cycles_memory -= 64
        scene_memory -= 47
        if sett.batch_apply_armature_modifier:
            storage_weight -= 2
            scene_memory -= 27
    
    def to_percentage(base, end_result) -> int:
        return int((base + end_result)/base * 100)            

    def _get_tag_from_dict(total, tag_dict, fallback):
        return next((tag for tag, ubound in tag_dict.items() 
                    if total < ubound),
                    fallback)
    
    cycles_time_total = to_percentage(4.40, cycles_time)
    cycles_time_tags = {'Fastest': 95, 'Fast': 100, 'Normal': 120, 'Slow': 150}
    cycles_time_tag = _get_tag_from_dict(cycles_time_total, cycles_time_tags, 'Slowest')
    
    cycles_memory_total = int((563+cycles_memory)/3)
    cycles_memory_tags = {'Lightest': 60, 'Light': 80, 'Normal': 100, 'Heavy': 180}
    cycles_memory_tag = _get_tag_from_dict(cycles_memory_total, cycles_memory_tags, 'Heaviest')
    
    eevee_time_total = to_percentage(6.57, eevee_time)
    eevee_time_tags = {'Fastest': 50, 'Fast': 70, 'Normal': 100, 'Slow': 150}
    eevee_time_tag = _get_tag_from_dict(eevee_time_total, eevee_time_tags, 'Slowest')
    
    eevee_memory_total = int((1450 + eevee_memory)/3)
    eevee_memory_tags = {'Lightest': 150, 'Light': 200, 'Normal': 320, 'Heavy': 600}
    eevee_memory_tag = _get_tag_from_dict(eevee_memory_total, eevee_memory_tags, 'Heaviest')
    
    ram_total = 472 + scene_memory
    ram_tags = {'Light': 250, 'Normal': 700}
    ram_tag = _get_tag_from_dict(ram_total, ram_tags, 'Heavy')
    
    statistics_dict = {
        'cycles_time': f'{cycles_time_total}% [{cycles_time_tag}]',
        'cycles_memory': f'{cycles_memory_total} [{cycles_memory_tag}]',
        'eevee_time': f'{eevee_time_total}% [{eevee_time_tag}]',
        'eevee_memory': f'{eevee_memory_total} [{eevee_memory_tag}]',
        'scene_memory': f'{ram_total} [{ram_tag}]',
        'storage': f'~{59+storage_weight} MB/human*'
    }
    
    return statistics_dict

def get_batch_marker_list(context) -> list:
    sett = context.scene.HG3D
    
    marker_selection = sett.batch_marker_selection

    all_markers = [obj for obj in bpy.data.objects if 'hg_batch_marker' in obj]
    
    if marker_selection == 'all':
        return all_markers
    
    elif marker_selection == 'selected':
        selected_markers = [
            o for o in all_markers 
            if o in context.selected_objects
            ]
        return selected_markers
    
    else:
        empty_markers = [o for o in all_markers if not has_associated_human(o)]
        return empty_markers

def has_associated_human(marker) -> bool:
    """Check if this marker has an associated human and if that object still 
    exists

    Args:
        marker (Object): marker object to check for associated human

    Returns:
        bool: True if associated human was found, False if not
    """
    
    return (
        'associated_human' in marker #does it have the prop
        and marker['associated_human'] #is the prop not empty
        and bpy.data.objects.get(marker['associated_human'].name) #does the object still exist
        and marker.location == marker['associated_human'].location #is the object at the same spot as the marker
        and bpy.context.scene.objects.get(marker['associated_human'].name) #is the object in the current scene
    )
