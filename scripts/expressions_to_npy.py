import os

import bpy
import numpy as np


def main():
    body = bpy.data.objects["HG_Body"]
    path = r"/Users/ole/Documents/Human Generator/expressions"

    def combine_multiple_sks_to_one_array(sks, values, to_obj) -> np.ndarray:

        combined_sk_data = np.zeros(len(to_obj.data.vertices) * 3, dtype=np.float64)

        for sk, value in zip(sks, values):
            sk_data = np.empty(len(to_obj.data.vertices) * 3, dtype=np.float64)
            sk.data.foreach_get("co", sk_data)
            combined_sk_data += sk_data * value - combined_sk_data

        return combined_sk_data

    base_coordinates = np.empty(len(body.data.vertices) * 3, dtype=np.float64)
    body.data.vertices.foreach_get("co", base_coordinates)

    for root, _, files in os.walk(path):
        for file in files:
            if not file.endswith("txt"):
                continue
            sett_dict = {}

            sk_name = os.path.splitext(file)[0]

            with open(os.path.join(root, file)) as f:
                for line in f.readlines():
                    key, value = line.split()
                    sett_dict[key] = value

            sks = body.data.shape_keys.key_blocks
            keys = [sks[k] for k in sett_dict.keys()]
            values = [float(v) for v in sett_dict.values()]

            sk_coordinates = combine_multiple_sks_to_one_array(keys, values, body)
            relative_coordinates: np.ndarray = sk_coordinates - base_coordinates

            save_path = os.path.join(root, sk_name)
            np.save(save_path, relative_coordinates, allow_pickle=False)
