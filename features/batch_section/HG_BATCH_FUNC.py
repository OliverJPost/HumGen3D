import numpy as np
import bpy #type:ignore

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
    
    print('returning', length_list)
    return length_list 