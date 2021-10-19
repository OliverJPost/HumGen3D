import bpy  # type:ignore


def add_driver(hg_body, target_sk, sett_dict):
    driver    = target_sk.driver_add('value').driver
    var       = driver.variables.new()
    var.type  = 'TRANSFORMS'
    target    = var.targets[0]
    target.id = hg_body.parent

    driver.expression      = sett_dict['expression']
    target.bone_target     = sett_dict['target_bone']
    target.transform_type  = sett_dict['transform_type']
    target.transform_space = sett_dict['transform_space']


def build_driver_dict(obj, remove = True):
    driver_dict = {}
    remove_list = []
    for driver in obj.data.shape_keys.animation_data.drivers:
        
        target_sk       = driver.data_path.replace('key_blocks["', '').replace('"].value', '')
        expression      = driver.driver.expression
        var             = driver.driver.variables[0]
        target          = var.targets[0]
        target_bone     = target.bone_target
        transform_type  = target.transform_type
        transform_space = target.transform_space
        
        driver_dict[target_sk] = {'expression': expression, 'target_bone': target_bone, 'transform_type': transform_type, 'transform_space': transform_space}
        if not target_sk.startswith('cor'):
            remove_list.append(driver)
    if remove:
        for driver in remove_list:
            obj.data.shape_keys.animation_data.drivers.remove(driver)
    
    return driver_dict

def rigify_with_drivers():
    context = bpy.context
    human   = context.object
    rig     = human.parent

    driver_dict = build_driver_dict(human, remove = True)

    bpy.ops.hg3d.rigify()

    sks= human.data.shape_keys.key_blocks
    for target_sk_name, sett_dict in driver_dict.items():
        add_driver(human, sks[target_sk_name], sett_dict)

rigify_with_drivers()
