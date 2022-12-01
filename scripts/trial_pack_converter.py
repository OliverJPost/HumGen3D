import os
from zipfile import ZIP_DEFLATED, ZipFile

PATH = "/Users/ole/Desktop/cpack export"
TRIAL_CONTENT_PATH = "/Users/ole/Documents/HG_TRIAL"


def replace_with_trial_content(source_zip, target_zip):
    """Look through all files of source_zip to find files that exist in TRIAL_CONTENT_PATH.
    If they exist there, place them in the target_zip in the same location as they were in the source_zip.
    """
    replaced = 0
    for filename in source_zip.namelist():
        if "__MACOSX" in filename:
            continue
        if filename.endswith("/"):
            continue
        trial_path = os.path.join(TRIAL_CONTENT_PATH, filename)
        if os.path.exists(trial_path):
            replaced += 1
            target_zip.write(trial_path, filename)
        else:
            if filename.endswith(".png"):
                print(f"Missing trial content for {filename}")
            target_zip.writestr(filename, source_zip.read(filename))
    return replaced


def main():
    for file in os.listdir(PATH):
        if not file.endswith(".hgpack"):
            print(f"Skipping {file}")
            continue
        path = os.path.join(PATH, file)
        print(f"Processing {path}")

        with ZipFile(path) as source_zip:
            new_path = os.path.join(PATH, "TRIAL_" + file)
            with ZipFile(new_path, "w", ZIP_DEFLATED) as target_zip:
                replaced = replace_with_trial_content(source_zip, target_zip)

        print(f"Replaced {replaced} files with trial content.")


if __name__ == "__main__":
    main()
