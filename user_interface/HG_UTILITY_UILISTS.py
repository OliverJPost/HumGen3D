import bpy  # type: ignore


class HG_UL_MODAPPLY(bpy.types.UIList):
    """
    UIList showing modifiers
    """   

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        enabledicon = "CHECKBOX_HLT" if item.enabled else "CHECKBOX_DEHLT"
        viewport_visible_icon = ("RESTRICT_VIEW_OFF" if item.viewport_visible 
                                else "RESTRICT_VIEW_ON")
        render_visible_icon = ("RESTRICT_RENDER_OFF" if item.render_visible 
                              else "RESTRICT_RENDER_ON")

        row = layout.row(align = True)

        if item.mod_name == 'HEADER':
            self._draw_header_row(item, row)
            return
  
        row.prop(item, "enabled", text="", icon=enabledicon, emboss=False)
        
        modifier_icon = ('PARTICLES' if item.mod_type == 'PARTICLE_SYSTEM' 
                     else 'MOD_{}'.format(item.mod_type)
                     )
        try:
            row.label(text=item.mod_name, icon = modifier_icon)
        except:
            row.label(text=item.mod_name, icon = 'QUESTION')

        if item.count:
            row.separator()
            row.label(text = str(item.count))
        else:
            row.label(text = '', icon = viewport_visible_icon)
            row.label(text = '', icon = render_visible_icon)

    def _draw_header_row(self, item, row):
        """header with label for uilists
        """
        row.label(text = '', icon = 'BLANK1')
        row.label(text = 'Type:' if item.count else 'Name:', icon = 'BLANK1')
        row.separator()
        row.label(text = 'Amount:' if item.count else '')

class MODAPPLY_ITEM(bpy.types.PropertyGroup):
    """
    Properties of the items in the uilist
    """
    mod_name : bpy.props.StringProperty(name = 'Modifier Name', default = '')
    mod_type : bpy.props.StringProperty(name = 'Modifier Type', default = '')
    enabled  : bpy.props.BoolProperty(default = True)
    render_visible  : bpy.props.BoolProperty(default = True)
    viewport_visible: bpy.props.BoolProperty(default = True)
    count : bpy.props.IntProperty(default = 0)
    object: bpy.props.PointerProperty(type=bpy.types.Object)

class HG_UL_SHAPEKEYS(bpy.types.UIList):
    """
    UIList showing shapekeys
    """   

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        enabledicon = "CHECKBOX_HLT" if item.enabled else "CHECKBOX_DEHLT"

        row = layout.row(align = True)
        row.enabled = item.on
        row.prop(item, "enabled",
                 text="",
                 icon=enabledicon,
                 emboss=False
                 )
        
        row.label(text=item.sk_name)
        if not item.on:
            row.label(text = 'Muted', icon = 'INFO')

class SHAPEKEY_ITEM(bpy.types.PropertyGroup):
    """
    Properties of the items in the uilist
    """
    sk_name: bpy.props.StringProperty(name = 'Modifier Name', default = '')
    enabled: bpy.props.BoolProperty(default = False)
    on : bpy.props.BoolProperty(default = True)
    

class HG_UL_SAVEHAIR(bpy.types.UIList):
    """
    UIList showing hair particle systems
    """   

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        enabledicon = "CHECKBOX_HLT" if item.enabled else "CHECKBOX_DEHLT"

        row = layout.row(align = True)
        row.prop(item, "enabled", text="", icon=enabledicon, emboss=False)
        
        row.label(text=item.ps_name)

class SAVEHAIR_ITEM(bpy.types.PropertyGroup):
    """
    Properties of the items in the uilist
    """
    ps_name: bpy.props.StringProperty(name = 'Hair Name', default = '')   
    enabled: bpy.props.BoolProperty(default = False)

class HG_UL_SAVEOUTFIT(bpy.types.UIList):
    """
    UIList showing shapekeys
    """   

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):

        enabledicon = "CHECKBOX_HLT" if item.enabled else "CHECKBOX_DEHLT"

        row = layout.row(align = True)
        row.prop(item, "enabled", text="", icon=enabledicon, emboss=False)

        row = layout.row(align = True)      
        row.label(text=item.obj_name)
        
        if not item.cor_sks_present:
            row.alert = True
            row.label(text = 'No Corrective shapekeys', icon = 'ERROR')
            return
        if not item.weight_paint_present:
            row.alert = True
            row.label(text = 'No weight paint', icon = 'ERROR')
            return
                    
class SAVEOUTFIT_ITEM(bpy.types.PropertyGroup):
    """
    Properties of the items in the uilist
    """
    obj_name : bpy.props.StringProperty(name = 'Ojbect Name', default = '')
    cor_sks_present : bpy.props.BoolProperty(default = False)
    weight_paint_present: bpy.props.BoolProperty(default = False)
    enabled: bpy.props.BoolProperty(default = False)


    