import json
import os
import random
import subprocess
import time

import bpy  # type:ignore

from ..features.common.HG_COMMON_FUNC import get_addon_root  # type:ignore
from ..features.common.HG_COMMON_FUNC import (
    HumGenException,
    get_prefs,
    hg_log,
    toggle_hair_visibility,
)
from .HG_API_HUMAN import HG_Human


class HG_Batch_Generator:
    """Generator/factory (?) for making completed HG_Humans in the background, the
    same way as the batch panel in the Human Generator GUI does."""

    def __init__(
        self,
        delete_backup=True,
        apply_shapekeys=True,
        apply_armature_modifier=False,
        remove_clothing_subdiv=True,
        remove_clothing_solidify=True,
        apply_clothing_geometry_masks=True,
        texture_resolution="optimised",
    ):
        """Creates a dictionary with settings to pass to generate_human_in_background
        if you want to change the quality settings from the default values.

        Args:
            delete_backup (bool, optional): Delete the backup human, which is an
                extra object used to revert to creation phase and to load 1-click
                expressions.
                Big storage impact. Medium RAM impact.
                Defaults to True.
            apply_shapekeys (bool, optional): Applies all the shape keys on the
                human. Simplifies object.
                Small performance impact, medium storage impact.
                Defaults to True.
            apply_armature_modifier (bool, optional): Applies the armature modifier,
                removes bone vertex groups and deletes the rig.
                Use this if you don't need a rig.
                Small impact.
                Defaults to False.
            remove_clothing_subdiv (bool, optional): Removes any subdiv modifier
                from clothing.
                Small to medium impact.
                Defaults to True.
            remove_clothing_solidify (bool, optional): Removes any solidify modifier
                from clothing.
                Small to medium impact.
                Defaults to True.
            apply_clothing_geometry_masks (bool, optional): Applies the modifiers
                that hide the body geometry behind clothing.
                Small impact.
                Defaults to True.
            texture_resolution (str, optional): Texture resolution in
                ('high', 'optimised', 'performance') from high to low.
                Also applies to clothing, eyes and teeth.
                HUGE memory and Eevee impact.
                Defaults to 'optimised'.
        """
        self.delete_backup = delete_backup
        self.apply_shapekeys = apply_shapekeys
        self.apply_armature_modifier = apply_armature_modifier
        self.remove_clothing_subdiv = remove_clothing_subdiv
        self.remove_clothing_solidify = remove_clothing_solidify
        self.apply_clothing_geometry_masks = apply_clothing_geometry_masks
        self.texture_resolution = texture_resolution

    def generate_in_background(
        self,
        context=None,
        gender=None,
        ethnicity=None,
        add_hair=False,
        hair_type="particle",
        hair_quality="medium",
        add_expression=False,
        expressions_category="All",
        add_clothing=False,
        clothing_category="All",
        pose_type="a_pose",
    ) -> HG_Human:
        """Generate a new HG_Human in a background proces based on the settings
        of this HG_Batch_Generator instance and import the created human to
        Blender

        Args:
            context (bl context, optional): Blender context, if None is passed
                bpy.context will be used.
            gender (str, optional): The gender of the human to create, either 'male'
                or 'female'.
                If None is passed, random.choice(('male', 'female')) will be used
            ethnicity (str, optional): Ethnicity of the human to create. Will search
                for starting humans with this string in their name.
                If None is passed, random.choice(('caucasian', 'black', 'asian'))
                will be used.
            add_hair (bool, optional): If True, hair will be added to the created
                human.
                Defaults to False.
            hair_type (str, optional): Choose between 'particle' and 'haircards' for
                the add-on to create.
                Ignored if add_hair == False.
                Defaults to 'particle'.
            hair_quality (str, optional): The quality of the particle system to
                create, in ('high', 'medium', 'low', 'ultralow').
                Defaults to 'medium'.
            add_expression (bool, optional): If True, a 1-click expression will be
                added to the human.
                Defaults to False.
            expressions_category (str, optional): Category to choose expression
                from.
                Use get_pcoll_categs('expression') to see options.
                Ignored if add_expression == False.
                Defaults to 'All'.
            add_clothing (bool, optional): If True, an outfit and footwear will be
                added to this human.
                Defaults to False.
            clothing_category (str, optional): Category to choose outfit from.
                Use get_pcoll_categs('outfit') to see options.
                Ignored if add_clothing == False.
                Defaults to 'All'.
            pose_type (str, optional): Category to choose pose from.
                Use get_pcoll_categs('pose') to see options.
                Defaults to 'A_Pose'.
        Returns:
            HG_Human: Python representation of a Human Generator Human. See
                [[HG_Human]]
        """
        context = context if context else bpy.context

        settings_dict = self.__construct_settings_dict_from_kwargs(
            gender=gender,
            ethnicity=ethnicity,
            add_hair=add_hair,
            hair_type=hair_type,
            hair_quality=hair_quality,
            add_expression=add_expression,
            expressions_category=expressions_category,
            add_clothing=add_clothing,
            clothing_category=clothing_category,
            pose_type=pose_type,
        )

        for obj in context.selected_objects:
            obj.select_set(False)

        python_file = os.path.join(get_addon_root(), "scripts", "batch_generate.py")

        start_time_background_process = time.time()

        hg_log("STARTING HumGen background process", level="BACKGROUND")
        self.__run_hg_subprocess(python_file, settings_dict)
        hg_log("^^^ HumGen background process ENDED", level="BACKGROUND")

        hg_log(
            f"Background process took: ",
            round(time.time() - start_time_background_process, 2),
            "s",
        )

        hg_rig = self.__import_generated_human()

        return HG_Human(existing_human=hg_rig)

    def __construct_settings_dict_from_kwargs(self, **settings_dict):
        if not settings_dict["gender"]:
            settings_dict["gender"] = random.choice(("male", "female"))
        if not settings_dict["ethnicity"]:
            settings_dict["ethnicity"] = random.choice(
                ("caucasian", "black", "asian")
            )  # TODO option for custom ethnicities for custom starting humans

        return settings_dict

    def __run_hg_subprocess(self, python_file, settings_dict):
        is_background = "--background" if get_prefs().batch_in_background else ""
        background_blender = subprocess.run(
            [
                bpy.app.binary_path,
                is_background,
                "--python",
                python_file,
                json.dumps({**settings_dict, **vars(self)}),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        for line in background_blender.stdout.decode("utf-8").splitlines():
            if get_prefs().debug_mode or line.startswith(("HG_", "\033")):
                print(line)

        if background_blender.stderr:
            hg_log("Exception occured while in background process", level="WARNING")
            print(background_blender.stderr.decode("utf-8"))
            # ShowMessageBox(message =
            #    f'''An error occured while generating human, check the console for error details''')

    def __import_generated_human(self):
        start_time_import = time.time()
        batch_result_path = os.path.join(get_prefs().filepath, "batch_result.blend")
        with bpy.data.libraries.load(batch_result_path, link=False) as (
            data_from,
            data_to,
        ):
            data_to.objects = data_from.objects

        for obj in data_to.objects:
            bpy.context.scene.collection.objects.link(obj)
            toggle_hair_visibility(obj, show=True)

        human_parent = next(
            (obj for obj in data_to.objects if obj.HG.ishuman and obj.HG.backup),
            [obj for obj in data_to.objects if obj.HG.ishuman][0],
        )

        hg_log(
            f"Import succesful for human {human_parent.name}, import took: ",
            round(time.time() - start_time_import, 2),
            "s",
        )

        return human_parent
