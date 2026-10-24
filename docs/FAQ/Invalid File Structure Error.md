---
description: "Why a content pack from another creator shows Incorrect file structure when you install it in Human Generator, and how to fix it."
---

# Invalid File Structure Error

This is about content packs made by other creators, which you install from a file under **Packs from other creators** in the add-on preferences (see [[Installation#Packs from other creators]]). The Human Generator packs themselves come through the setup, which never shows this error.

When you select a pack file, the list can show *Incorrect file structure* (or *Incorrect zip method*) next to it. The pack is then not installed. A `.hgpack` file is a zip file with a `content_packs` folder at its top. Something changed that layout, usually a browser that unzipped the download.

## Download the pack again

Safari unzips some downloads by itself. Then you get a folder instead of the `.hgpack` file, and zipping it again by hand puts an extra folder at the top.

- Turn off *Open "safe" files after downloading* in Safari's settings, under General, and download the pack again.
- Or download it with another browser.

## If you can't download it again

Zip the contents of the folder, not the folder itself:

1. Open the folder that Safari made and select everything inside it:
![[Screenshot 2021-11-23 at 16.48.46.webp]]
2. Right-click (or Ctrl-click) and choose **Compress**:
 ![[Screenshot 2021-11-23 at 16.49.51.webp]]
3. Rename the new `Archive.zip` to the original pack name, ending in `.hgpack`:
 ![[Pasted image 20211123165051.webp]]
