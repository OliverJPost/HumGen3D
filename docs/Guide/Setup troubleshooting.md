---
description: "What the Human Generator setup's messages mean and what to do: files that are not content packs, connection and proxy errors, disk space, paused downloads, online access."
---

# Setup troubleshooting

This page lists the messages the setup can show while it downloads the trial or installs content packs from your files, with what to do. Each heading is the message as the add-on shows it. In every case below, content you already installed keeps working.

For the normal steps, see [[Installation]]. If nothing here helps, press **Contact support** in the setup window or the sidebar: it opens an email to our support address with the add-on and Blender version, the error and the pack already filled in, and copies the same details to the clipboard for webmail.

## Installing from files

These are about the full version and other packs you install from `.hgpack` files, see [[Installation#Install the full version]].

### Not a content pack

The file list shows **Not a content pack** next to a file that is not a Human Generator pack, and leaves it out. Human Generator packs are `.hgpack` files. If the file is one and still shows this, your browser probably unzipped the download and it was zipped again by hand; see [[Invalid File Structure Error]].

### Older than installed

The file is an older version of a pack than the one in your content folder, so it is left out. Nothing needs doing. If you picked it by mistake, download the current file from your purchase.

### This add-on needs 4.1 or newer

> Base Humans is an older file than this add-on needs. Download the current one from your purchase.

The file is a version of the pack from before this version of the add-on. It still installs, but the add-on then asks for an update. Download the current pack from your purchase and select that one.

### Base Humans isn't among these files

> Base Humans isn't among these files. Humans can't be made without it.

Every human needs the Base Humans pack. Download it from your purchase too and add it with **Select more files…**. When you come from the trial the message is *The trial content stays until it is installed.*: the other packs install, and the trial is replaced once Base Humans is in.

### Install failed

> Install failed
> Packs that finished stay installed. Your files are not changed.

The reason is shown above it, with the name of the pack. Most often it is [[#Can't write to the content folder]] or [[#Not enough space]]. A file that got damaged on the way shows *This file is not a Human Generator content pack.*: download it again. Then press **Retry**; packs that finished are not installed again.

### An install is running

> An install is running. Wait until it is done.

You selected or dropped files while packs are being installed. Add them when it is done.

## Connection

### Can't reach humgen3d.com

> Can't reach humgen3d.com. Check your internet connection and try again. Your installed content works as usual.

During a download the message is *Can't reach the download server.* Check that this computer is online, then press **Try again** or **Retry**. On a company network, a firewall may block the add-on: ask your IT department to allow the [[#Hosts to allow|hosts below]]. The full version doesn't need a connection: it installs from files, see [[Installation#Install the full version]].

### humgen3d.com took too long to answer

> humgen3d.com took too long to answer. Try again in a minute.

During a download: *The download server stopped answering.* Try again in a minute. A slow or busy connection can cause this.

### A secure connection to humgen3d.com couldn't be made

> A secure connection to humgen3d.com couldn't be made. A proxy or security software may be intercepting it.

Some company networks and some antivirus programs open secure connections to inspect them. Blender doesn't trust the certificate they put in between, so the connection fails. Ask your IT department to allow the [[#Hosts to allow|hosts below]] without inspection, or turn off the web protection of your antivirus while you download. A different network, such as a phone hotspot, also works.

### Your network's proxy asks for a login

> Your network's proxy asks for a login. Sign in to it, or ask your IT department to allow humgen3d.com.

Your network sends traffic through a proxy that needs a login, which Blender can't give. Ask your IT department to allow the [[#Hosts to allow|hosts below]].

### humgen3d.com is having a problem right now

> humgen3d.com is having a problem right now. Try again in a few minutes.

The problem is on our side. Try again in a few minutes.

### The download server sent a web page instead of the file

> The download server sent a web page instead of the file. If your network needs a sign-in page, sign in and try again.

Hotel, train and guest networks often show a sign-in page first. Open any website in your browser, sign in to the network, then press **Retry**. The part that was already downloaded is kept.

### humgen3d.com gave an unexpected answer

The setup shows *humgen3d.com gave an unexpected answer. Try again later, or contact* followed by our support address.

Try again later. If it keeps happening, write to support.

### Too many downloads from this network

> Too many downloads from this network. Try again in an hour.

The trial download stops for an hour after many requests from one network. This counts every computer on the network, so in a studio or school a colleague's downloads count too.

### Downloads are paused right now

> Downloads are paused right now. Try again later.

We switched the trial download off for a while, for example during maintenance. The setup may show a message from us with more details instead. Try again later. Installing packs from files works regardless.

### Hosts to allow

For firewalls, proxies and security software, the setup connects to these hosts over HTTPS (port 443):

- `humgen3d.com`
- `*.r2.cloudflarestorage.com`
- `downloads.humangenerator3d.com`

## Download and disk

### Not enough space

> Not enough space: 3.2 GB needed, 1.8 GB free

The numbers show what the selected packs need once unpacked, and what is free on the disk of the content folder. Free some space, untick packs you don't need (such as **8K Textures**), or press **Change…** next to *Content folder* and pick a folder on another disk.

When the setup shows *Couldn't check the free space on this disk*, which happens on some network drives, it still installs. Make sure there is enough room.

### Can't write to the content folder

> Can't write to the content folder. Check the free space and the folder's permissions.

The disk is full, or you don't have permission to write to the folder. On a shared studio folder, ask whoever manages it, or pick a folder of your own with **Change…**.

### That drive isn't connected

> That drive isn't connected. Connect it, or choose another folder.

The content folder is on a drive that isn't there. Connect it, or press **Change…** and pick another folder. See also [[Installation#Moving or reconnecting your content folder]].

### Another Blender window is downloading the content

> Another Blender window is downloading the content.

For an install from files the message is *Another Blender window is installing content.* Only one Blender can install into a content folder at a time. Wait until the other window is done, or close it. If that Blender crashed, the setup goes on by itself after 10 minutes.

### Connection lost. Trying again in 10 s

When the connection drops, the setup tries again by itself three times, each time from where it stopped. You don't need to do anything.

### Download failed

> Download failed
> Packs that finished stay installed, and the download resumes where it stopped.

The reason is shown above. Fix it with the sections on this page, then press **Retry**. Packs that finished are not downloaded again.

### The downloaded file is damaged

> The downloaded file is damaged. Try again.

The file didn't arrive complete. Press **Retry**.

### Download paused

**Pause** in the setup stops the download and keeps what it fetched. *Download paused* then shows how much is done, with **Resume** to go on and **Discard download** to throw the partial files away.

If you close Blender during a download, start it again from the HumGen tab (**Set up Human Generator**, or the update button) and press **Install**. The download continues from the part that was already fetched.

### A newer Human Generator is needed for the latest content

> A newer Human Generator is needed for the latest content.

The newest content packs need a newer version of the add-on. Update the add-on in Blender's extension list (Edit > Preferences > Get Extensions), then update the packs.

### A pack can't be downloaded

When the server won't hand out the trial pack, *Download failed* gives the reason, for example *Trial Content: This pack can't be downloaded right now.* Try again later.

*This pack comes with the full version. Install it from the files of your purchase.* means the pack is not part of the trial. See [[Installation#Install the full version]].

## The setup window

### The setup window doesn't show

The setup is a window inside the 3D viewport. If it doesn't show, press `N` in the 3D viewport and open the **HumGen** tab. The *Setup* panel has **Continue setup**, and **Pop-up not showing? Set up in this panel**, which shows the same steps as plain buttons in the sidebar.

### This viewport is too small for the setup

> This viewport is too small for the setup. Make it larger, or go on in the sidebar.

Make the 3D viewport larger, for example with `Ctrl Space`, or press **Continue in the sidebar**.

### Downloading needs Blender's online access, which is turned off

> Downloading needs Blender's online access, which is turned off.

Blender 4.2 and later has an *Allow Online Access* setting, and the setup needs it to download the trial. Press **Allow online access** in the setup, the HumGen tab or the add-on preferences. The setting is also under Edit > Preferences > System > Network.

Apart from the trial download, Human Generator only uses the network for a daily check for updates. Turning online access off stops that check too. The full version installs from files and needs no connection. See [[Installation#What the add-on sends]].

### Blender was started in offline mode

> Blender was started in offline mode. Start it normally to download content.

Blender was started with `--offline-mode`, which can't be changed while it runs. Start Blender without that option.

### Could not load the pack list

The setup couldn't get the list of packs from humgen3d.com. The reason follows the message; see the [[#Connection]] sections above. Press **Try again** when it is fixed.

### No Human Generator content in this folder

You picked a folder with **Use this folder** or **Select folder** that has no Human Generator content packs in it. Pick the folder that has the `content_packs` folder inside, or install the content with the setup.
