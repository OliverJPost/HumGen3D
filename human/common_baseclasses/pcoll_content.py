# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import os
import random
from pathlib import Path
from typing import List, Optional

import bpy
from HumGen3D.backend import get_prefs, preview_collections
from HumGen3D.common.type_aliases import BpyEnum, C
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.exceptions import HumGenException


class PreviewCollectionContent:
    _pcoll_name: str
    _pcoll_gender_split: bool

    @injected_context
    def set(self, preset: str, context: C = None) -> None:  # noqa: A003
        raise NotImplementedError

    def _set(self, context: bpy.types.Context) -> None:  # noqa: CCE001
        """Internal way of setting content, only used by enum properties"""
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
            setattr(context.HG3D.pcoll, self.pcoll_name, chosen)
            sett.update_exception = False

    @injected_context
    def get_options(self, context: C = None, category: str = "All") -> List[str]:
        if category not in self.get_categories() and category != "All":
            raise ValueError(
                (
                    f"Invalid category passed, '{category}'. "
                    + "choose 'All' or an option from HumGen3D.human.get_categories()",
                )
            )

        # Return only the name from the enum. Skip the first one
        # FIXME check all pcolls if 0 is always skipped
        self.refresh_pcoll(context, ignore_searchterm=True)
        options = [option[0] for option in self._get_full_options()[1:]]
        if not options:
            raise HumGenException(
                "No options found, did you install the content packs?"
            )

        return options

    def _get_full_options(self) -> BpyEnum:  # noqa: CCE001
        """Internal way of getting content, only used by enum properties"""
        pcoll = preview_collections.get(self._pcoll_name).pcoll
        if not pcoll:
            return [
                ("none", "Reload category below", "", 0),
            ]

        return pcoll[self._pcoll_name]

    def get_categories(self) -> list[str]:
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
        """Refresh the items of this preview collection"""
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
