import bpy #type: ignore
import os 
import threading
from pathlib import Path

from bpy.types import Operator #type: ignore

from . bl_ui_button import *
from . bl_ui_drag_panel import *
from . bl_ui_draw_op import *
  
#from .. HG_BATCH_OPS import batch_iterate

class HG_DRAW_PROGRESS(BL_UI_OT_draw_operator):
    bl_idname = "hg3d.drawprogress"
    bl_label = "bl ui widgets custom operator"
    bl_description = "Demo operator for bl ui widgets" 
    bl_options = {'REGISTER'}
    	
    def __init__(self):   
        super().__init__()

        main_color = (0.336, 0.5, 0.75, 1.0)
        main_color_hover = (0.336, 0.5, 0.75, .5)
        highlight_color = (0.598, 0.297, 0.453, 1.0)
        highlight_color_hover = (0.598, 0.297, 0.453, .5)

        self.panel = BL_UI_Drag_Panel(0, 0, 100, 100)
        self.panel.bg_color = (0.2, 0.2, 0.2, 0.9)
        



        self.button1 = BL_UI_Button(0, 0, 300, 30)
        self.button1.bg_color = highlight_color
        self.button1.hover_bg_color = highlight_color_hover
        self.button1.text = "Starting"
        #self.button1.set_image("//img/scale.png")
        self.button1.set_image_size((24,24))
        self.button1.set_image_position((4,2))
        self.button1.set_mouse_down(self.button1_press)


    def on_invoke(self, context, event):
        # Add new widgets here (TODO: perhaps a better, more automated solution?)
        widgets_panel = [self.button1]
        widgets =       [self.panel]

        widgets += widgets_panel

        self.init_widgets(context, widgets)

        self.panel.add_widgets(widgets_panel)

        # Open the panel at the mouse location
        self.panel.set_location((context.area.width/ 2.0) , (context.area.height/2.0)) 
        
    #     thread = threading.Thread(target=self.run, args=())
    #     thread.daemon = True                       
    #     thread.start()                                      

    # def run(self):  
    #     batch_iterate(self)
    #     thread.stop() 

    def on_chb_visibility_state_change(self, checkbox, state):
        active_obj = bpy.context.view_layer.objects.active
        if active_obj is not None:
            active_obj.hide_viewport = not state
   

    # Button press handlers    
    def button1_press(self, widget):
        self.finish()
        
