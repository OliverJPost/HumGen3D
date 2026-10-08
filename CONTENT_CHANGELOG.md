# Content changelog

Changes to the content folder (`get_prefs().filepath`), which is not in this
repository. The code has to work with content from before and after each entry,
users update the add-on and the content separately. Newest first.

## 2026-10-07 — `models/HG_HUMAN.blend`: deform flags

- The 36 bones that deform no mesh are flagged non-deforming (`use_deform=False`):
  the 30 FACS slider bones, `facs_control`, `eyeball_lookat.L/R/master` and
  `heel.02.L/R`. 66 bones keep deforming. Nothing else in the file changed.
- Saved with Blender 4.0.1, the file was a Blender 3.2 file before. Backup next
  to it: `models/HG_HUMAN_backup_2026-10-07_blender3.2.blend`.
- Why: game engine export (`human/process/game_rig.py`) and Blender's "Only
  Deform Bones" exporters can tell control bones from skeleton bones. The code
  that lists deform bones (clothing weight transfer, haircards, clothing saving)
  only ever saw weighted bones, so the result is the same.
- Humans created from the old file still work: the game rig step removes bones by
  weights, not by this flag.

## 2026-10-07 — `animations/`: NLA strips

- No file format change (`format_version` stays 1). Clips can now be added as NLA
  strips on a track named "Human Generator" instead of replacing the active action.

## 2026-10-06 — `animations/`: Mixamo import

- `hg3d.import_mixamo` converts a Mixamo FBX to a clip and saves it in the
  category the user picks, `animations/Mixamo/` by default.

## 2026-10-06 — `animations/`: animation library added

- New folder `animations/` with 129 clips in category folders (Climbing, Crawling,
  Crouching, Emotes, Fighting, Idle, Interaction, Jumping, Magic, Running, Sitting,
  Swimming, Walking, Weapons), converted from the Quaternius Universal Animation
  Library with `scripts/convert_animation_library.py`.
- Clips are rig independent JSON, `format_version` 1, see
  `human/animation/clip.py` for the layout: per bone quaternions relative to a
  palms-down T-pose, plus the location of the `spine` (hips) bone scaled by leg
  length.
