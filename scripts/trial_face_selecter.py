import json

import bpy


def main():

    obj = bpy.context.object

    with open(
        "/Users/ole/Library/Application Support/Blender/3.2/scripts/addons/HumGen3D/scripts/trial_faces.json"
    ) as f:
        data = json.load(f)

    for face in obj.data.polygons:
        if face.index in data:
            face.select = True


if __name__ == "__main__":
    main()
