---
description: "Install Human Generator in Blender 4.2 or newer, install the free trial or the content packs of your purchase with the setup, and find your content folder again after a move."
---

# Installation

Human Generator has two parts: the add-on, and the content packs with the humans, clothing, hair and poses. You install the add-on yourself. Its setup then installs the content: it downloads the free trial, or it installs the full version from the `.hgpack` files of your purchase.

If something goes wrong on the way, see [[Setup troubleshooting]].

## Requirements

### Blender version

Human Generator needs **Blender 4.2 or newer**, on Windows, macOS or Linux.

On Blender 4.0 and 4.1 the add-on still loads, but it only shows this notice, with its version number, in the HumGen tab and in its preferences:

> Human Generator needs Blender 4.2 or newer.
> Your content and saved files are not affected.

The **Learn more** button opens this page. You have two choices:

- **Move to Blender 4.2 or newer.** You can install it next to your current Blender. Install the add-on there as described below. It finds the content folder you already have, so you don't install anything again.
- **Stay on Blender 4.0 or 4.1.** The last version of Human Generator for these Blender versions is **4.0.33**. If you updated and now see the notice, go back to it with the updater: press **Open the updater** in the notice, or open the add-on preferences. There, press **Check now for humgen3d update**, then **Install main / old version**, choose **v4.0.33** and press OK. Restart Blender afterwards. If its updater later offers a newer version, don't install it on this Blender.

### Disk space and internet

The trial is a download of about 270 MB. The full version is 2 to 4 GB of pack files, and installing them needs room to unpack. The setup shows the free space on the disk before it starts.

Only the trial needs an internet connection, and Blender's online access setting (see [[Setup troubleshooting#Downloading needs Blender's online access, which is turned off|online access]]). The full version installs from files on your computer and works offline, as does Human Generator itself once the content is installed.

## Install the add-on

The add-on is a zip file. For the free trial you get it on the install guide of your trial request: request the trial on [humgen3d.com](https://humgen3d.com) and press **Install right away**, or open the link in the email we send you. Do this on the computer you run Blender on. Opened without a trial request, [humgen3d.com/trial](https://humgen3d.com/trial) asks for your email first.

**Drag the zip file into Blender (recommended).** Press **Download Human Generator** on the install guide, then drag the downloaded zip file into any Blender window, straight from your browser's download list or from your Downloads folder, and confirm with **OK**. Don't unzip it first. Safari unzips downloads by itself: switch off *Open "safe" files after downloading* in Safari's General settings first, or use another browser.

**Install from Disk.** The same zip, without dragging: in Blender, go to Edit > Preferences > Get Extensions, open the menu at the top right and choose **Install from Disk**, and pick the zip.

Blender doesn't update an add-on installed from a zip by itself. See [[#Updates]] for how a new version gets in.

> [!info] Already have Human Generator in your add-ons folder?
> A legacy install of Human Generator in Blender 4.2 or newer keeps working. If you install the new version next to it, see [[#Installed twice]].

## Set up the content

The setup opens by itself the first time Blender starts with Human Generator and no content. If it doesn't, or you closed it, press `N` in the 3D viewport, open the **HumGen** tab and press **Set up Human Generator**.

With the add-on from your install guide, the welcome screen has two buttons, **Install the free trial** and **I bought it**: follow [[#Install the free trial]], or [[#Install the full version]] if you already bought it. The free trial is only offered to an add-on that came from an install guide. Any other copy of the add-on has one button there, **Install the content packs**, which leads to [[#Install the full version]].

If the setup found Human Generator content on this computer, the welcome screen offers that folder first, see [[#Already a customer? Nothing changes]].

> [!info]- Setup window not showing?
> The setup is a window inside the 3D viewport. If it doesn't show, open the HumGen tab in the sidebar. The *Setup* panel there has **Continue setup**, and **Pop-up not showing? Set up in this panel**, which has the same steps as plain buttons.

## Install the free trial

The trial needs no account. It installs one human, an outfit, a hairstyle and four poses, so you can try the workflow. The rest of the library shows as locked.

1. **Install the free trial** shows the trial pack and its size. Press **Change…** next to *Content folder* to pick where the content goes.
2. Press **Install**. The download runs in the background. Press **Continue in background** to keep working; the progress stays in the HumGen tab. **Pause** stops the download and keeps what it fetched.
3. **Done.** *Human Generator is ready* shows the folder. Press **Get started**, or **Show me around** for the pages of the Get started tutorial, which also show while the content installs.

## Install the full version

The full version is not downloaded by the add-on. It comes as content packs, files that end in `.hgpack`, with your purchase. You download them yourself and the setup installs them. This needs no account, no key and no connection. If you installed the add-on from your install guide, it tells us one time that the full version was installed, when a connection is allowed: see [[Installation#What the add-on sends|What the add-on sends]].

1. **Download the packs.** Bought on Superhive (called BlenderMarket before)? Log in, go to [Orders](https://superhivemarket.com/account/orders), open your Human Generator order and download the `.hgpack` files. Don't unzip them. If your browser unzipped one, see [[Invalid File Structure Error]].
2. **Open the file list.** In the setup, press **Install the content packs**. From the trial, press **I bought it**, which is next to every buy button, also in the *Trial version* box at the top of the HumGen tab.
3. **Select the files.** Press **Select .hgpack files…** and pick the packs. You can select several at once, and add more with **Select more files…**. You can also drag `.hgpack` files from your file manager onto a 3D viewport while the setup window is closed.
4. **Check the list.** Every file shows its pack, version and size, with a tick box. Press **Change…** next to *Content folder* to pick where the content goes.
5. Press **Install**. The packs are unpacked one after the other. Your files stay where they are; you can delete them afterwards, or keep them as a backup.

The list says what it does with each file:

- A pack you don't have yet is ticked and shows its size.
- *Installed 4.0, update to 4.1*: the file is newer than the pack you have. Installing it replaces only that pack's files.
- **Installed**: you already have this version.
- **Older than installed**: you have a newer version, so the file is left out.
- **Not needed**: the trial pack, when the full library is installed or among the files.
- **Not a content pack**: any other file.

**Base Humans** is the pack every human needs. When it isn't among the files and isn't installed, the setup says so. Coming from the trial, the trial content stays until Base Humans is installed; the full library then replaces it automatically. Your own saved content stays.

**8K Textures** is optional: it is large, for close-ups and large prints, and Base Humans already has the same skins in 4K.

**HG Export** holds the recipes and engine data of the Process tab. Without it that tab is greyed out, see [[Process/Overview#HG Export pack missing?|HG Export pack missing?]].

## Already a customer? Nothing changes

If you used Human Generator 4 before, you don't need to install anything again to keep working.

- **Your content is found automatically.** The setup looks in the folder of your preferences, the folder an earlier version remembered, the preferences of the older add-on and the default folder. When it finds content, the welcome screen shows *Found Human Generator content in* with the folder. Press **Use this folder**.
- **If it isn't found,** press **Select folder** next to *I already have the content installed* on the welcome screen, and pick the folder with your packs.

## Updates

**The add-on.** When a new version is out, the add-on preferences say *A new version of Human Generator is available.* with **Download the new version**. It opens your install guide: download the zip there and drag it into Blender, as you did the first time. Blender replaces the installed version; your content, content folder and settings stay as they are. Restart Blender afterwards, so everything runs on the new version.

The older add-on in your add-ons folder (version 4.0.38 and before) keeps its own updater, at the bottom of its preferences.

**The content packs** are checked once a day while Blender's online access is on. The check only compares version numbers. When there is something new, the *Setup* panel in the HumGen tab shows *Content update available*, or *Content update needed* when this version of the add-on needs the newer pack, with a button such as **Update 2 packs**. The add-on preferences list every pack with its version, and have **Check for updates** and an update button.

- **The trial** updates by download: the button opens the trial's list with the newer version ticked.
- **The full version** updates from files. The button opens the file list, which names the packs that have a newer version, for example *Base Humans 4.2*. Download those files from your purchase and select them, as in [[#Install the full version]].

Don't want an update now? Press **Hide** next to it. The notice then stays away until a newer version of that pack comes out. The preferences still list it.

A pack update replaces only the files of that pack. Your own content, saved with the content saving tools, stays where it is.

If you see *A newer Human Generator is needed for the latest content.*, update the add-on first, then the packs.

## What the add-on sends

Human Generator works offline. It connects to humgen3d.com for the things below, and only while Blender's *Allow Online Access* setting is on:

- **The update check**, once a day: one request for the list of current versions. It carries the versions of the add-on and of Blender, and your operating system.
- **The trial download**: the request for the download link, and the download itself.
- **Three events, only if you installed the add-on from your install guide.** The zip you download there holds your trial request id, in a file named `trial.json`. Such an install tells us three things, each one time, when it happens: that the setup opened, that the trial content was installed, and that the full version was installed. Each is one small request that reads `{"event": "trial_installed", "trial": "<your id>"}` plus the same versions as the update check. The trial download names the id too. This is how we know whether the trial gets installed and whether trials lead to the full version.

A copy of the add-on that did not come from an install guide has no trial request id and sends none of these events: there, installing packs from files sends nothing at all. The **Buy** buttons open humgen3d.com in your browser. Our [privacy policy](https://humgen3d.com/privacy) has the details.

## Installed twice

When you install the new version next to an older Human Generator in your add-ons folder, both are switched on. Two copies can't run at once, so the new one only shows a notice in the HumGen tab:

> Human Generator is installed twice.
> The older copy in your add-ons folder is still switched on.

Press **Use the new version**. It takes over the content folder and settings of the older copy and switches that copy off. Afterwards Blender says *Human Generator now runs as an extension. You can remove the older copy in Preferences > Add-ons.* If it asks you to restart Blender, do so.

The older copy shows *A newer Human Generator is installed as an extension.* with **Switch off this copy**, which does the same from its side.

## Moving or reconnecting your content folder

When the content folder is set but not there, for example on an unplugged drive or a folder you renamed, the HumGen tab shows:

> Can't find your content folder
> If it's on an external or network drive, connect it and press Try again.

- **Try again** looks again, after you connect the drive.
- **Locate folder…** lets you pick the folder in its new place.
- **Install again…** opens the setup to install the content into a new folder.

Nothing is created or installed while the folder is missing.

To move the content on purpose, move the folder in your file manager, then press **Locate folder…**. You can also change the folder in the add-on preferences: Content Packs tab, **Change folder…** next to *Content folder*. Blend files you saved before the move may still look for textures in the old place. Blender's File > External Data > Find Missing Files fixes those.

## Packs from other creators

Content packs that other creators made install the same way as the full version: in the add-on preferences, open the Content Packs tab and press **Install content packs from files…**. Select the `.hgpack` files and press **Install**. To make a pack of your own, see [[Exporting your content as a pack]].
