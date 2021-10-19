import os
from pathlib import Path

import bpy  # type: ignore
from bpy.types import Operator  # type: ignore

from ..core.content.HG_UPDATE import check_update
from ..core.HG_CALLBACK import msgbus
from ..core.HG_PCOLL import refresh_pcoll
from .bl_ui_button import *
from .bl_ui_drag_panel import *
from .bl_ui_draw_op import *
from .bl_ui_image import *


class HG_DRAW_PANEL(BL_UI_OT_draw_operator):
    '''
    Opens a custom ui panel in the 3D viewport, showing
    a tutorial based on images of 1200*600 pixels.
    Credits to Jayanam for the code base for custom ui
    '''    
    bl_idname = "hg3d.draw_tutorial"
    bl_label = "Tutorial"
    bl_description = "Show this tutorial" 
    bl_options = {'REGISTER'}
    	
    first_time: bpy.props.BoolProperty(default = False)    
    tutorial_name: bpy.props.StringProperty()
    
    def __init__(self):
        
        super().__init__()

        self.image_width = 1200
        self.image_height = 600 
        main_color = (0.336, 0.5, 0.75, 1.0)
        main_color_hover = (0.336, 0.5, 0.75, .5)
        highlight_color = (0.598, 0.297, 0.453, 1.0)
        highlight_color_hover = (0.598, 0.297, 0.453, .5)

        self.image_list = self.get_dir_images(os.path.dirname(__file__) 
                                              + str(Path(f'/images/{self.tutorial_name}'))
                                              )
        
        self.sorted_image_list = sorted(self.image_list)

        self.panel = BL_UI_Drag_Panel(0, 0, self.image_width, self.image_height)
        self.panel.bg_color = (0.2, 0.2, 0.2, 0.9)

        self.image1 = BL_UI_Image()
        self.image_index = 0
        self.image1.set_image(self.sorted_image_list[self.image_index])
        self.image1.set_image_size((self.image_width, self.image_height))
        self.image1.set_image_position((0,0))

        self.button1 = BL_UI_Button(0, self.image_height, self.image_width/3, 30)
        self.button1.bg_color = highlight_color
        self.button1.hover_bg_color = highlight_color_hover
        self.button1.text = "Exit Tutorial"
        self.button1.set_image_size((24,24))
        self.button1.set_image_position((4,2))
        self.button1.set_mouse_down(self.button1_press)

        self.button2 = BL_UI_Button(self.image_width/3, self.image_height, self.image_width/3, 30)
        self.button2.bg_color = main_color
        self.button2.hover_bg_color = main_color_hover
        self.button2.text = "Previous Page"
        self.button2.set_image_size((24,24))
        self.button2.set_image_position((4,2))
        self.button2.set_mouse_down(self.button2_press)

        self.button3 = BL_UI_Button(self.image_width/1.5, self.image_height, self.image_width/3, 30)
        self.button3.bg_color = main_color
        self.button3.hover_bg_color = main_color_hover
        self.button3.text = "Next Page"
        self.button3.set_image_size((24,24))
        self.button3.set_image_position((4,2))
        self.button3.set_mouse_down(self.button3_press)


    def on_invoke(self, context, event):
        if self.first_time:
            sett = bpy.context.scene.HG3D
            sett.subscribed = False
            msgbus(self, context)
            refresh_pcoll(self, context, 'humans')
            check_update()

        widgets_panel = [self.button1, self.button2, self.button3, self.image1]
        widgets =       [self.panel]

        widgets += widgets_panel

        self.init_widgets(context, widgets)

        self.panel.add_widgets(widgets_panel)

        self.panel.set_location((context.area.width/ 2.0) - (self.image_width / 2) , (context.area.height/2.0) - (self.image_height / 2))
       

    def on_chb_visibility_state_change(self, checkbox, state):
        active_obj = bpy.context.view_layer.objects.active
        if active_obj is not None:
            active_obj.hide_viewport = not state
   
    def on_up_down_value_change(self, up_down, value):
        active_obj = bpy.context.view_layer.objects.active
        if active_obj is not None:
            active_obj.scale = (1, 1, value)

    def on_slider_value_change(self, slider, value):
        active_obj = bpy.context.view_layer.objects.active
        if active_obj is not None:
            active_obj.scale = (1, 1, value)

    # Button press handlers    
    def button1_press(self, widget):
        self.finish()
        
    def button2_press(self, widget):
        if self.image_index > 0:
            self.image_index -=1
            new_image = self.sorted_image_list[self.image_index]
            self.image1.set_image(new_image)
        
    def button3_press(self, widget):
        if self.image_index < len(self.sorted_image_list) -1:
            self.image_index += 1
            new_image = self.sorted_image_list[self.image_index]
            self.image1.set_image(new_image)

    def get_dir_images(self, dir):
        file_paths = []
        ext = ('.jpg', '.jpeg', '.png')
        for root, dirs, files in os.walk(dir):
            for fn in files:
                if fn.lower().endswith(ext):
                    file_paths.append(os.path.join(root, fn))             
        return file_paths
