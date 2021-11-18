import json
import os
import random
import subprocess
import time

import bpy  # type:ignore
from mathutils import Euler, Vector

from ..core.HG_PCOLL import refresh_pcoll
#TODO replace .. with HumGen3D
from ..features.common.HG_COMMON_FUNC import get_addon_root  # type:ignore
from ..features.common.HG_COMMON_FUNC import (HumGenException, get_prefs,
                                              hg_log, toggle_hair_visibility)
from ..features.common.HG_RANDOM import random_body_type as _random_body_type
from ..features.creation_phase.HG_CREATION import \
    HG_CREATION_BASE  # type:ignore
from ..features.creation_phase.HG_FACE import \
    randomize_facial_feature_categ as _randomize_facial_feature_categ
from ..features.creation_phase.HG_FINISH_CREATION_PHASE import \
    finish_creation_phase as _finish_creation_phase
from ..features.creation_phase.HG_MATERIAL import \
    randomize_skin_shader as _randomize_skin_shader
from ..user_interface.HG_PANEL_FUNCTIONS import \
    in_creation_phase as _in_creation_phase


class HG_Key_Blocks():
    """Object that contains the different types of key_blocks used by Human 
    Generator humans.
    """
    def __init__(self, body_object = None):
        self._body_object = body_object
        
    @property
    def all(self) -> 'list[bpy.types.ShapeKey]':
        """#Read-only All key blocks on the body object of the human.

        Returns:
            list[bpy.types.ShapeKey]: Filtered list of body_object.data.shape_keys.key_blocks
        """
        return self.__get_key_blocks_from_prefix('')
    
    @property
    def body_proportions(self) -> 'list[bpy.types.ShapeKey]':
        """#Read-only The key blocks that control the body proportions of the 
        human. If accessing from finalize phase, expect an empty list.

        Returns:
            list[bpy.types.ShapeKey]: Filtered list of body_object.data.shape_keys.key_blocks
        """
        return self.__get_key_blocks_from_prefix('bp_')

    @property
    def expressions(self) -> 'list[bpy.types.ShapeKey]':
        """#Read-only The key blocks that are used for 1-click expressions. If 
        accessing this in the creation phase, expect disabled key_blocks. If 
        accessing from the finalize phase, expect only the key blocks that were 
        added from the GUI or using set_expression().

        Returns:
            list[bpy.types.ShapeKey]: Filtered list of body_object.data.shape_keys.key_blocks
        """
        return self.__get_key_blocks_from_prefix('expr_')

    @property
    def face_proportions(self) -> 'list[bpy.types.ShapeKey]':
        """#Read-only  The key blocks that control the face proportions of the
        human. If accessing from finalize phase, expect an empty list.

        Returns:
            list[bpy.types.ShapeKey]: Filtered list of body_object.data.shape_keys.key_blocks
        """
        return self.__get_key_blocks_from_prefix('ff_')
    
    @property
    def corrective(self) -> 'list[bpy.types.ShapeKey]':
        """#Read-only The key blocks that are used as corrective shapekeys. 
        Expect key blocks that are controlled by drivers.

        Returns:
            list[bpy.types.ShapeKey]: Filtered list of body_object.data.shape_keys.key_blocks
        """
        return self.__get_key_blocks_from_prefix('cor_')
    
    @property
    def face_presets(self) -> 'list[bpy.types.ShapeKey]':
        """#Read-only The key blocks that control the face shapes of starting 
        humans. If accessing from finalize phase, expect an empty list.

        Returns:
            list[bpy.types.ShapeKey]: Filtered list of body_object.data.shape_keys.key_blocks
        """        
        return self.__get_key_blocks_from_prefix('pr_')
    
    def __get_key_blocks_from_prefix(self, prefix):
        return [sk for sk in self._body_object.data.shape_keys.key_blocks 
                if sk.name.startswith(prefix)
                ]

class HG_Human():
    """Python representation of a Human Generator human. Can be used to either
    make new humans or modify existing ones.
    """
    def __init__(self, existing_human = None):
        """Creates a new HG_Human instance. Either pass the rig object of an
        existing human or use create() to add this human to your Blender scene.

        Args:
            existing_human (bpy.types.Object, optional): Existing Blender 
                ```ARMATURE``` object that was created by Human Generator. 
                Defaults to None.
            
        Raises:
            TypeError: When passed object is not of type ```ARMATURE``` 
            ValueError: When passed object is an ARMATURE but does not have the
                ```object.HG.ishuman == True``` custom property    
        """
        if existing_human:
            self.__check_if_valid_hg_rig(existing_human)
            
            self._rig_object = existing_human
            self._body_object = existing_human.HG.body_obj
            self._gender = existing_human.HG.gender
            self._key_blocks = HG_Key_Blocks(body_object=self._body_object)
        else:
            self._rig_object = None
            self._body_object = None
            self._gender = None
        

    @property
    def rig_object(self) -> bpy.types.Object:
        """#Read-only The Blender armature object that serves as the parent and 
        identifier for this Human Generator human. 

        Returns:
            bpy.types.Object: Blender object of type ARMATURE 
        Raises:
            HumGenException: When this property or method requires the human to 
                exist in Blender, but the rig_object does not exist.
        """
        self.__check_if_rig_exists()
        return self._rig_object
    
    @property
    def body_object(self) -> bpy.types.Object:
        """#Read-only Blender MESH object, body of this human.

        Returns:
            bpy.types.Object: Blender object of type MESH
        Raises:
            HumGenException: When this human does not yet exist in Blender.
        """
        self.__check_if_rig_exists()
        return self._body_object
    
    @property
    def gender(self) -> str:
        """#Read-only string to represent the gender of this human instance.

        Returns:
            str: string in ('male', 'female')
        """
        return self._gender
    
    @property
    def location(self) -> Vector:
        """Blender global location of the parent object of this human, the
        rig_object.

        Returns:
            Vector: FoatVectorProperty of size 3, representing (x,y,z) in 
                Blender global space
        Raises:
            HumGenException: When this human does not yet exist in Blender.
        """
        return self.rig_object.location
    @location.setter
    def location(self, location_tuple):
        """Setter"""
        self.rig_object.location = location_tuple

    @property
    def rotation_euler(self) -> Euler:
        """Blender global Euler rotation of the parent object of this human, the
            rig_object.
        
        Returns:
            Euler: Euler rotation of size 3, representing (x,y,z) in 
                Blender global space
        Raises:
            HumGenException: When this human does not yet exist in Blender.
        """
        return self.rig_object.rotation_euler
    @rotation_euler.setter
    def rotation_euler(self, rotation_euler):
        """Setter"""
        self.rig_object.rotation_euler = rotation_euler

    @property
    def name(self) -> str:
        """Name of this human, as represented by the name of the rig_object in
        Blender

        Returns:
            str: Name of this human, if not specified during creation expect a
                "HG_" prefix added by the random name generator. 
        Raises:
            HumGenException: When this human does not yet exist in Blender.
        """
        return self.rig_object.name
    @name.setter
    def name(self, new_name):
        """Setter"""
        self.__check_if_rig_exists()
        self._rig_object.name = new_name

    @property
    def key_blocks(self) -> object:
        """Object that contains the different types of key_blocks used by Human 
        Generator humans.
        """
        return self._key_blocks
    
    @property
    def eye_object(self) -> bpy.types.Object:
        """The Blender object of the eyes of this human.

        Returns:
            bpy.types.Object: Object of type MESH
        Raises:
            HumGenException: When this human does not yet exist in Blender.
        """
        return next(child for child in self.rig_object.children if 'hg_eyes' in child)
    
    @property
    def teeth_objects(self) -> 'list[bpy.types.Object]':
        """List of the Blender objects of the upper and lower teeth of this human.

        Returns:
            list[bpy.types.Object]: List of teeth objects, type MESH, expect size of 2
        Raises:
            HumGenException: When this human does not yet exist in Blender.
        """
        return [child for child in self.rig_object.children if 'hg_teeth' in child]

    @property
    def clothing_objects(self) -> 'list[bpy.types.Object]':
        """List of the Blender objects of clothing added to this human, excluding
        footwear.

        Returns:
            list[bpy.types.Object]: List of clothing objects, type MESH
        Raises:
            HumGenException: When this human does not yet exist in Blender.
        """        
        return [child for child in self.rig_object.children if 'cloth' in child]

    @property
    def footwear_objects(self) -> 'list[bpy.types.Object]':
        """List of the Blender objects of footwear added to this human.

        Returns:
            list[bpy.types.Object]: List of footwear objects, type MESH. If
                adding official Human Generator footwear, expect size of 1.
        Raises:
            HumGenException: When this human does not yet exist in Blender.
        """       
        return [child for child in self.rig_object.children if 'shoe' in child]

    def __check_if_valid_hg_rig(self, hg_rig):
        """Checks if the passed hg_rig is a valid Human Generator human.

        Args:
            hg_rig (bpy.types.Object): Blender object to check if it's a valid HG rig

        Raises:
            TypeError: When passed object is not of type ARMATURE
            ValueError: When passed object is an ARMATURE but does not have the
                object.HG.ishuman == True custom property
        """
        if not hg_rig:
            raise TypeError('Expected a Blender object of type "ARMATURE", not "NoneType"')
        
        if not hg_rig.HG.ishuman:
            if hg_rig.type != 'ARMATURE':
                raise TypeError(f'Expected a human object of type "ARMATURE", not "{hg_rig.type}"')
            else:
                raise ValueError('Passed armature was not created with Human Generator.')

    def get_starting_human_options(self, context = None, gender = None):
        """Get a list of all starting human options (i.e. Caucasian 5, Black 2)

        Args:
            context (context, optional): Blender context. If None is passed, 
                bpy.context will be used.
            gender (str, optional): Choose a gender in ('male', 'female') to get
                options for. If not passed, a random gender will be chosen,
                which can be checked with the .gender property of your HG_Human
                instance.
        Returns:
            list[str]: List of all items in this preview collection
        Raised:
            ValueError: If passed gender is not in ('male', 'female')
        """
        context = self.__check_passed_context(context)
        sett = context.scene.HG3D
        
        if self._rig_object:
            raise HumGenException('This HG_Human instance already exists in Blender.')
        
        if gender:
            if gender not in ('male', 'female'):
                raise ValueError(f'Gender {gender} not found in ("male", "female")')
            self._gender = gender
        else:
            self._gender = random.choice(('male', 'female')) 
        
        sett.gender = self._gender
        refresh_pcoll(None, context, 'humans')
        return sett['previews_list_humans']

    def create(self, context = None, chosen_starting_human = None
               ) -> bpy.types.Object:
        """Adds a new human to the active Blender scene. Required for most
        functionality if you didn't pass an existing_human when creating your 
        HG_Human instance.

        Args:
            context (context, optional): Blender context. If None is passed, 
                bpy.context will be used.
            chosen_starting_human (str, optional): Optionally, you can choose the 
                starting human yourself by picking an option from 
                get_starting_human_options(). 
                Defaults to None. If nothing is chosen, a random starting human
                    and random gender is chosen.
        Raises:
            HumGenException: When calling this method on an instance that 
                already exists in Blender.
        """
        context = self.__check_passed_context(context)
        sett = context.scene.HG3D
  
        if self._rig_object:
            raise HumGenException('This HG_Human instance already exists in Blender.')  
        
        if not self._gender:
            self._gender = random.choice(('male', 'female')) 
            
        sett.gender = self._gender
        refresh_pcoll(None, context, 'humans')
        
        if chosen_starting_human:
            sett.pcoll_humans = chosen_starting_human
        else:
            sett.pcoll_humans = random.choice(self.get_starting_human_options(context))
        
        hg_rig, hg_body = HG_CREATION_BASE().create_human(context)
        
        HG_CREATION_BASE()._give_random_name_to_human(self._gender, hg_rig)
        
        self._rig_object = hg_rig
        self._body_object = hg_body
        self._key_blocks = HG_Key_Blocks(body_object=self._body_object)

    def randomize_body_proportions(self):
        """Randomize the body proportion sliders of this human. Only possible
        while the human is in the creation phase.
        
        Raises:
            HumGenException: When this human does not yet exist in Blender.
            HumGenException: When this human is no longer in creation phase.
        """
        self.__check_if_rig_exists()
        self.__check_if_in_creation_phase()
        
        _random_body_type(self._rig_object)

    def randomize_face_proportions(self):
        """Randomize the face proportion sliders of this human. Only possible
        while the human is in the creation phase.
        
        Raises:
            HumGenException: When this human does not yet exist in Blender.
            HumGenException: When this human is no longer in creation phase.
        """
        self.__check_if_rig_exists()        
        self.__check_if_in_creation_phase()

        _randomize_facial_feature_categ(
            self._body_object,
            'all',
            use_bell_curve=self._gender == 'female'
        )

    def get_hair_options(self, context=None) -> 'list[str]':
        """Get a list of names of possible hairstyles for this human. Choosing
        a name and passing it to set_hair() will add this hairstyle to your 
        human.
        
        Args:
            context (context, optional): Blender context. If None is passed, 
                bpy.context will be used.
        Returns:
            list[str]: List of internal names of hairstyles, expect the internal
                names to be relative paths from the Human Generator folder.
        Raises:
            HumGenException: When this human does not yet exist in Blender.
        """        
        context = self.__check_passed_context(context)
        self.__check_if_rig_exists()
        return self.__get_pcoll_list(context, 'hair') 

    def set_hair(self, context = None, chosen_hair_option = None):
        """Sets the active hairstyle of this human, importing it in Blender. By
        default this method will hide the particle children of the created
        hairstyle for performance reasons (it makes a big difference). You can
        turn the children back on with set_hair_visibility(True)

        Args:
            context (context, optional): Blender context. If None is passed, 
                bpy.context will be used.
            chosen_hair_option (str, optional): The name of an hair option chosen
                from get_hair_options(). Defaults to None. If not passed a 
                random one will be chosen.
        Raises:
            HumGenException: When this human does not yet exist in Blender.
        """
        context = self.__check_passed_context(context)
        self.__check_if_rig_exists()
                
        if not chosen_hair_option:
            chosen_hair_option = random.choice(self.get_hair_options(context))
        
        self.__set_active_in_pcoll(context, 'hair', chosen_hair_option)
        self.set_hair_visibility(False)

    def randomize_skin(self):
        """Randomizes the sliders for the skin shader of this human.
        
        Raises:
            HumGenException: When this human does not yet exist in Blender.
        """
        _randomize_skin_shader(self._body_object, self._gender)

    def finish_creation_phase(self, context = None):
        """Works the same as the Finish Creation Phase button in the GUI. Needed
        for the human to be posed and for clothing to be added. Does a whole lot
        of things behind the scenes. Most importantly it adds a backup human to
        the scene which is used to store 1-click expressions and offers a 
        possibility to revert to the creation phase. Do not delete this backup
        human until you've selected an expression with set_expression()

        Args:
            context (context, optional): Blender context. If None is passed, 
                bpy.context will be used.
        Raises:
            HumGenException: When this human does not yet exist in Blender.
        """
        context = self.__check_passed_context(context)
        _finish_creation_phase(None, context, self._rig_object, self._body_object)     
        self._rig_object.HG.phase = 'clothing'        

    def set_hair_visibility(self, set_visible):
        """Changes the particle children of the hairstyles on this human between
        visible and hidden based on the passed boolean.

        Args:
            set_visible (bool): Pass True for unhiding and False for hiding
        Raises:
            HumGenException: When this human does not yet exist in Blender.
        """
        hg_body = self._body_object
        hair_systems= [m.particle_system for m in hg_body.modifiers 
                       if m.type == 'PARTICLE_SYSTEM']

        for ps in hair_systems:
            if set_visible:
                render_children = ps.settings.rendered_child_count
                ps.settings.child_nbr = render_children   
            else:
                ps.settings.child_nbr =  1
     
    def get_outfit_options(self, context = None) -> list:
        """Get a list of names of possible outfits for this human. Choosing
        a name and passing it to set_outfit() will add this outfit to your 
        human.
        
        Args:
            context (context, optional): Blender context. If None is passed, 
                bpy.context will be used.
        Returns:
            list[str]: List of internal names of outfits, expect the internal
                names to be relative paths from the Human Generator folder.
        Raises:
            HumGenException: When this human does not yet exist in Blender.
            HumGenException: When this human is not in finalize phase, but 
                still in the creation phase.            
        """    
        context = self.__check_passed_context(context)
        self.__check_if_rig_exists()
        self.__check_if_in_finalize_phase()
        return self.__get_pcoll_list(context, 'outfit') 

    def set_outfit(self, context = None, chosen_outfit_option = None):
        """Sets the active outfit of this human, importing it in Blender.

        Args:
            context (context, optional): Blender context. If None is passed, 
                bpy.context will be used.
            chosen_outfit_option (str, optional): The name of outfit option chosen
                from get_outfit_options(). Defaults to None. If not passed a 
                random one will be chosen.
        Raises:
            HumGenException: When this human does not yet exist in Blender.
            HumGenException: When this human is not in finalize phase, but 
                still in the creation phase.
        """
        context = self.__check_passed_context(context)
        self.__check_if_rig_exists()
        self.__check_if_in_finalize_phase()
                
        if not chosen_outfit_option:
            chosen_outfit_option = random.choice(self.get_outfit_options(context))
        
        self.__set_active_in_pcoll(context, 'outfit', chosen_outfit_option)

    def get_footwear_options(self, context=None) -> list:
        """Get a list of names of possible footwear for this human. Choosing
        a name and passing it to set_footwear() will add this outfit to your 
        human.
        
        Args:
            context (context, optional): Blender context. If None is passed, 
                bpy.context will be used.
        Returns:
            list[str]: List of internal names of footwear, expect the internal
                names to be relative paths from the Human Generator folder.
        Raises:
            HumGenException: When this human does not yet exist in Blender.
            HumGenException: When this human is not in finalize phase, but 
                still in the creation phase.            
        """            
        context = self.__check_passed_context(context)
        self.__check_if_rig_exists()
        self.__check_if_in_finalize_phase()
        return self.__get_pcoll_list(context, 'footwear') 

    def set_footwear(self, context=None, chosen_footwear_option = None):
        """Sets the active outfit of this human, importing it in Blender.

        Args:
            context (context, optional): Blender context. If None is passed, 
                bpy.context will be used.
            chosen_footwear_option (str, optional): The name of footwear option 
                chosen from get_footwear_options(). Defaults to None. If not 
                passed a random one will be chosen.
        Raises:
            HumGenException: When this human does not yet exist in Blender.
            HumGenException: When this human is not in finalize phase, but 
                still in the creation phase.
        """
        context = self.__check_passed_context(context)
        self.__check_if_rig_exists()
        self.__check_if_in_finalize_phase()
                
        if not chosen_footwear_option:
            chosen_footwear_option = random.choice(self.get_footwear_options(context))
        
        self.__set_active_in_pcoll(context, 'footwear', chosen_footwear_option)

    def get_pose_options(self, context=None) -> list:
        """Get a list of names of possible poses for this human. Choosing
        a name and passing it to set_pose() will add this outfit to your 
        human.
        
        Args:
            context (context, optional): Blender context. If None is passed, 
                bpy.context will be used.
        Returns:
            list[str]: List of internal names of poses, expect the internal
                names to be relative paths from the Human Generator folder.
        Raises:
            HumGenException: When this human does not yet exist in Blender.
            HumGenException: When this human is not in finalize phase, but 
                still in the creation phase.            
        """   
        context = self.__check_passed_context(context)
        self.__check_if_rig_exists()
        return self.__get_pcoll_list(context, 'poses') 

    def set_pose(self, context=None, chosen_pose_option = None):
        """Sets the active pose of this human, importing it in Blender.

        Args:
            context (context, optional): Blender context. If None is passed, 
                bpy.context will be used.
            chosen_pose_option (str, optional): The name of pose option 
                chosen from get_pose_options(). Defaults to None. If not 
                passed a random one will be chosen.
        Raises:
            HumGenException: When this human does not yet exist in Blender.
            HumGenException: When this human is not in finalize phase, but 
                still in the creation phase.
        """
        context = self.__check_passed_context(context)
        self.__check_if_rig_exists()
        self.__check_if_in_finalize_phase()
                
        if not chosen_pose_option:
            chosen_pose_option = random.choice(self.get_pose_options(context))
        
        self.__set_active_in_pcoll(context, 'poses', chosen_pose_option)

    def get_expression_options(self, context = None):
        """Get a list of names of possible expressions for this human. Choosing
        a name and passing it to set_expression() will add this outfit to your 
        human.
        
        Args:
            context (context, optional): Blender context. If None is passed, 
                bpy.context will be used.
        Returns:
            list[str]: List of internal names of expressions, expect the internal
                names to be relative paths from the Human Generator folder.
        Raises:
            HumGenException: When this human does not yet exist in Blender.
            HumGenException: When this human is not in finalize phase, but 
                still in the creation phase.            
        """   
        context = self.__check_passed_context(context)
        self.__check_if_rig_exists()
        self.__check_if_in_finalize_phase()
        return self.__get_pcoll_list(context, 'expressions') 

    def set_expression(self, context=None, chosen_expression_option = None):
        """Sets the active 1-click expression of this human, importing it in 
        Blender.

        Args:
            context (context, optional): Blender context. If None is passed, 
                bpy.context will be used.
            chosen_expression_option (str, optional): The name of expression
                option chosen from get_expression_options(). Defaults to None. If 
                not passed a random one will be chosen.
        Raises:
            HumGenException: When this human does not yet exist in Blender.
            HumGenException: When this human is not in finalize phase, but 
                still in the creation phase.
        """
        context = self.__check_passed_context(context)
        self.__check_if_rig_exists()
        self.__check_if_in_finalize_phase()
                
        if not chosen_expression_option:
            chosen_expression_option = random.choice(
                    self.get_expression_options(context)
                )
        
        self.__set_active_in_pcoll(context, 'expressions', chosen_expression_option)

    def __get_pcoll_list(self, context, pcoll_name) -> 'list[str]': 
        """Internal method that's used to retreive preview collection options.

        Args:
            context (context): Blender context
            pcoll_name (str): Name of preview_collection in ('humans', 'poses',
            'expressions', 'outfit', 'footwear', 'face_hair', 'hair', 'textures',
            'patterns')

        Returns:
            list[str]: List of options in this preview collection
        """
        sett = context.scene.HG3D
        
        refresh_pcoll(None, context, pcoll_name, hg_rig = self._rig_object)
        pcoll_list = sett['previews_list_{}'.format(pcoll_name)]
        
        return pcoll_list       
        
    def __set_active_in_pcoll(self, context, pcoll_name, item_to_set_as_active):
        """Internal method for setting the active item in a preview collection

        Args:
            context (context): Blender context
            pcoll_name (str): Name of preview_collection in ('humans', 'poses',
            'expressions', 'outfit', 'footwear', 'face_hair', 'hair', 'textures',
            'patterns')
            item_to_set_as_active (str): Name of item to set as active
        """
        sett = context.scene.HG3D
        
        refresh_pcoll(None, context, pcoll_name, hg_rig = self._rig_object)
        setattr(sett, f'pcoll_{pcoll_name}', item_to_set_as_active)

    def __check_if_in_creation_phase(self):
        """Internal method to show HumGenException when human is not in creation
        phase.
        """
        if not _in_creation_phase(self._rig_object):
            raise HumGenException("The human needs to be in creation phase to use this method.")

    def __check_if_in_finalize_phase(self):
        """Internal method to show HumGenException when human is not in finalize
        phase.
        """
        if _in_creation_phase(self._rig_object):
            raise HumGenException("The human needs to be in finalize phase to use this method.")

    def __check_if_rig_exists(self):
        """Checks if this instance exists in Blender by checking if the _rig_object
        property is set.

        Raises:
            HumGenException: When this property or method requires the human to 
                exist in Blender, but the rig_object does not exist.
        """
        if not self._rig_object:
            raise HumGenException("This HG_Human instance does not yet exist in Blender.")
        
    def __check_passed_context(self, context):
        context = context if context else bpy.context
        return context
