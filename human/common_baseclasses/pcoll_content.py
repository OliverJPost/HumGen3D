# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements baseclass for all classes representing content collections."""

import os
import random
from pathlib import Path
from typing import List, Optional

import bpy
from HumGen3D.backend import get_prefs, preview_collections
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.common.type_aliases import BpyEnum, C


class PreviewCollectionContent:
    """Baseclass for classes that set and modify content stored in preview collections.

    These are all the content types where you select them based on a thumbnail.
    Internal methods used by the UI start with an underscore and will work with lists
    of tuples (BpyEnums), while the public methods work with lists of strings.
    """

    _pcoll_name: str
    _pcoll_gender_split: bool

    @property
    def _active(self) -> Optional[str]:
        """Name of content preset of this type last loaded on the human.

        Stored inside human.objects.rig as custom property starting with "ACTIVE"

        Returns:
            str: Name of content preset of this type last loaded on the human.
        """
        try:
            return self._human.objects.rig[f"ACTIVE_{self.__class__.__name__}"]
        except KeyError:
            return None

    @_active.setter
    def _active(self, value: str) -> None:
        """Setting the active content of this type.

        Args:
            value: Name of content preset to set as active.
        """
        self._human.objects.rig[f"ACTIVE_{self.__class__.__name__}"] = value

    @injected_context
    def set(self, preset: str, context: C = None) -> None:  # noqa
        # These are implemented in the classes inheriting from this class.
        raise NotImplementedError

    def _set(self, context: bpy.types.Context) -> None:  # noqa: CCE001
        """Internal way of setting content, only used by enum properties."""  # noqa
        sett = context.scene.HG3D  # type:ignore[attr-defined]
        if sett.update_exception:
            return

        active_item = getattr(sett.pcoll, self._pcoll_name)
        try:
            self.set(active_item, context)
        except TypeError:
            self.set(active_item)

    @injected_context
    def set_random(self, context: C = None, update_ui: bool = False) -> None:
        """Set this content type to a random content item.

        This will use random.choice to select a random item from the output of
        get_options().

        Args:
            context (C): Blender context. bpy.context if not provided.
            update_ui (bool): Will also show the chosen item as the active
                thumbnail in the template_icon_view. Defaults to False.
        """
        options = self.get_options(context)
        chosen = random.choice(options)

        # TODO make sure random is not the same as previous
        # TODO add catch for empty pcoll

        try:
            self.set(chosen, context)
        except TypeError:
            self.set(chosen)

        if update_ui:
            # Use indirect way so the UI reflects the chosen item
            sett = context.scene.HG3D  # type:ignore[attr-defined]
            sett.update_exception = True
            setattr(context.scene.HG3D.pcoll, self.pcoll_name, chosen)
            sett.update_exception = False

    @injected_context
    def get_options(self, context: C = None, category: str = "All") -> List[str]:
        """Get a list of options you can use for the set() method of this content.

        These represent the choises the user sees in the UI. The output is a list of
        relative paths to the content files, starting from the Human Generator folder.

        Args:
            context (C): Blender context. bpy.context if not provided.
            category (str): Category to filter the content by. Defaults to "All". You
                can get a list of categories from the get_categories() method.

        Returns:
            List[str]: List of relative paths to content files. You can pick one of
                these and pass it to the set() method.

        Raises:
            ValueError: If the passed category is not present in the list of categories.
            HumGenException: If no options can be found, this can be caused by the
                content pack for this type of content not being installed.
        """
        if category not in self.get_categories() and category != "All":
            raise ValueError(
                (
                    f"Invalid category passed, '{category}'. "
                    + "choose 'All' or an option from HumGen3D.human.get_categories()",
                )
            )

        # Return only the name from the enum. Skip the first one
        # FIXME check all pcolls if 0 is always skipped
        self.refresh_pcoll(context, override_category=category, ignore_searchterm=True)
        options = [option[0] for option in self._get_full_options()[1:]]
        if not options and category == "All":
            raise HumGenException(
                "No options found, did you install the content packs?"
            )

        return options

    def _get_full_options(self) -> BpyEnum:  # noqa: CCE001
        """Internal way of getting content, only used by enum properties"""  # noqa
        pcoll = preview_collections.get(self._pcoll_name).pcoll
        if not pcoll:
            return [
                ("none", "Reload category below", "", 0),
            ]

        return pcoll[self._pcoll_name]

    def get_categories(self) -> list[str]:
        """Get a list of categoris this content type is organized in.

        You can choose one of these categories to filter the content retreived from
        get_options().

        Returns:
            list[str]: List of categories. These are the names of the folders the
                content is saved in.
        """
        return [option[0] for option in self._get_categories(include_all=False)]

    def _get_categories(  # noqa: CCE001
        self, include_all: bool = True, ignore_genders: bool = False
    ) -> BpyEnum:

        categories = preview_collections[self._pcoll_name].find_folders(
            self._human.gender,
            include_all=include_all,
        )
        if ignore_genders:
            other_gender_categories = preview_collections[
                self._pcoll_name
            ].find_folders(
                "male" if self._human.gender == "female" else "female",
                include_all=include_all,
            )
            categories.extend(other_gender_categories)
            categories = list(set(categories))

        return categories

    @injected_context
    def refresh_pcoll(
        self,
        context: C = None,
        override_category: Optional[str] = None,
        ignore_searchterm: bool = False,
    ) -> None:
        """Refresh the items of this preview collection.

        This is low level functionality, you should not need to use this. It is used
        to refresh the list of possible content for this human. If you use get_options()
        this is automatically done for you.

        Args:
            context (C): Blender context. bpy.context if not provided.
            override_category (Optional[str]): Override the category to use, if not
                provided all items regardless of category will be shown.
            ignore_searchterm (bool): If True, the searchterm set by the user will
                be ignored. Defaults to False.
        """
        sett = context.scene.HG3D  # type:ignore[attr-defined]
        self._check_for_HumGen_filepath_issues()
        pcoll_name = self._pcoll_name

        preview_collections[self._pcoll_name].populate(
            context,
            self._human.gender,
            subcategory=override_category,
            use_search_term=not ignore_searchterm,
        )

        sett.pcoll[pcoll_name] = "none"  # set the preview collection to
        # the 'click here to select' item

    def _check_for_HumGen_filepath_issues(self) -> None:
        pref = get_prefs()
        if not pref.filepath:
            raise HumGenException("No filepath selected in HumGen preferences.")
        base_humans_path = pref.filepath + str(Path("content_packs/Base_Humans.json"))

        base_content = os.path.exists(base_humans_path)

        if not base_content:
            raise HumGenException("Filepath selected, but no humans found in path")
