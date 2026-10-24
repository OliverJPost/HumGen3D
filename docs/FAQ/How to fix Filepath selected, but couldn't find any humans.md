---
description: "What to do when Human Generator says it can't find any humans in the content folder: point it at the right folder, reconnect the drive, or download the content."
---

# How to fix "Filepath selected, but couldn't find any humans"

Human Generator has a content folder set, but there are no humans in it. The HumGen tab then shows *No content installed yet* with **Set up Human Generator**, and Python scripts get the error *Filepath selected, but no humans found in path*.

- **First time on this computer?** Press **Set up Human Generator** and let the setup download the content, see [[Installation#Set up the content]].
- **You have the content in another folder,** for example after a Blender or Human Generator update: press **Set up Human Generator**. The setup looks for your content and offers **Use this folder** when it finds it. Otherwise press **Select folder** next to *I already have the content packs*. See [[Installation#Already a customer? Nothing changes]].
- **The folder is on a drive that isn't connected:** the HumGen tab shows *Can't find your content folder* instead. Connect the drive and press **Try again**, see [[Installation#Moving or reconnecting your content folder]].

Pick the folder that has the `content_packs` folder inside it, not the `content_packs` folder itself.
