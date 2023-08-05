import json
import os

import_folder = (
    "/Users/ole/Documents/Work/HG3D/Human Generator 2/models/female/Default Humans/"
)
export_folder = "/Users/ole/Documents/Work/HG3D/Human Generator 2/models/female/test/"


def main():
    for root, dirs, files in os.walk(import_folder):
        for file in files:
            if not file.endswith(".json"):
                continue
            with open(import_folder + file) as f:
                data = json.load(f)

            export_data = {}
            export_data["age"] = {"set": 30, "age_color": 0.0, "age_wrinkles": 0.0}
            export_data["keys"] = {}
            export_data["keys"]["height_200"] = 0
            export_data["keys"]["height_150"] = 0
            if "livekeys" in data:
                for key_name, key_value in data["livekeys"].items():
                    export_data["keys"][key_name] = key_value

            gender = "male" if not "female" in root.lower() else "female"

            export_data["keys"]["Male"] = 1.0 if gender == "male" else 0.0

            if "body_proportions" in data:
                height = data["body_proportions"]["length"] * 100
            else:
                height = 180

            export_data["height"] = {"set": height}

            export_data["hair"] = {
                "eyebrows": {
                    "set": data["eyebrows"] if "eyebrows" in data else "Eyebrows_002",
                    "lightness": 0.10000000149011612,
                    "redness": 0.8999999761581421,
                    "roughness": 0.44999998807907104,
                    "salt_and_pepper": 0.0,
                    "roots": 0.0,
                    "root_lightness": 0.5,
                    "root_redness": 0.0,
                    "roots_hue": 0.5,
                    "fast_or_accurate": 0.0,
                    "hue": 0.5,
                },
                "regular_hair": {
                    "set": None,
                    "lightness": 0.10000000149011612,
                    "redness": 0.8999999761581421,
                    "roughness": 0.44999998807907104,
                    "salt_and_pepper": 0.0,
                    "roots": 0.0,
                    "root_lightness": 0.0,
                    "root_redness": 0.8999999761581421,
                    "roots_hue": 0.5,
                    "fast_or_accurate": 0.0,
                    "hue": 0.5,
                },
                # "face_hair": {
                #     "set": None,
                #     "lightness": 0.10000000149011612,
                #     "redness": 0.8999999761581421,
                #     "roughness": 0.44999998807907104,
                #     "salt_and_pepper": 0.0,
                #     "roots": 0.0,
                #     "root_lightness": 0.0,
                #     "root_redness": 0.8999999761581421,
                #     "roots_hue": 0.5,
                #     "fast_or_accurate": 0.0,
                #     "hue": 0.5,
                # },
            }
            export_data["eyes"] = {
                "pupil_color": data["material"]["eyes"]["HG_Eye_Color"],
                "sclera_color": data["material"]["eyes"]["HG_Scelera_Color"],
            }
            export_data["clothing"] = {
                "outfit": {"set": None},
                "footwear": {"set": None},
            }
            skin = data["material"]["node_inputs"]
            if gender == "male":
                gender_specific = {"mustache_shadow": 0.0, "beard_shadow": 0.0}
            else:
                gender_specific = {
                    "foundation_amount": 0.0,
                    "foundation_color": [
                        0.6557611227035522,
                        0.33287203311920166,
                        0.19147755205631256,
                        1.0,
                    ],
                    "blush_opacity": 0.0,
                    "blush_color": [
                        0.5530531406402588,
                        0.13859646022319794,
                        0.10914066433906555,
                        1.0,
                    ],
                    "eyebrows_opacity": 0.0,
                    "eyebrows_color": [
                        0.11449114233255386,
                        0.041451361030340195,
                        0.021851109340786934,
                        1.0,
                    ],
                    "lipstick_color": [
                        0.3097407817840576,
                        0.09161506593227386,
                        0.07323084771633148,
                        1.0,
                    ],
                    "lipstick_opacity": 0.0,
                    "eyeliner_opacity": 0.0,
                    "eyeliner_color": [0.0, 0.0, 0.0, 1.0],
                }

            tex_conv_dict = {
                "female_skin_dark_942356_": "textures/female/Default 4K/Female 10.png",
                "female_skin_dark_col_": "textures/female/Default 4K/Female 09.png",
                "female_skin_light_851104_": "textures/female/Default 4K/Female 03.png",
                "female_skin_light_867026_": "textures/female/Default 4K/Female 02.png",
                "female_skin_light_867971_": "textures/female/Default 4K/Female 01.png",
                "female_skin_light_color_": "textures/female/Default 4K/Female 04.png",
                "female_skin_medium_917761_": "textures/female/Default 4K/Female 05.png",
                "male_skin_dark_927991": "textures/male/Default 4K/Male 10.png",
                "male_skin_dark_col_": "textures/male/Default 4K/Male 09.png",
                "male_skin_light_858430_": "textures/male/Default 4K/Male 04.png",
                "male_skin_light_867963": "textures/male/Default 4K/Male 03.png",
                "male_skin_light_919726_": "textures/male/Default 4K/Male 02.png",
                "male_skin_light_col_": "textures/male/Default 4K/Male 01.png",
                "male_skin_medium_899161_": "textures/male/Default 4K/Male 07.png",
            }

            tex = next(
                (
                    tex_conv_dict[k]
                    for k in tex_conv_dict.keys()
                    if k in data["material"]["diffuse"]
                )
            )

            export_data["skin"] = {
                "tone": skin["Skin_tone"]["Tone"],
                "redness": skin["Skin_tone"]["Redness"],
                "saturation": 1.0,
                "normal_strength": 2.0,
                "roughness_multiplier": 1.2999999523162842,
                "freckles": skin["Freckles_control"]["Pos1"],
                "splotches": skin["Splotches_control"]["Pos1"],
                "texture.set": tex,
                "cavity_strength": 0.0,
                "gender_specific": gender_specific,
            }

            with open(os.path.join(export_folder, file), "w") as f:
                json.dump(export_data, f, indent=4)


if __name__ == "__main__":
    main()
