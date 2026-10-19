---
description: How to install Human Generator and its content packs, activate your Superhive order, and update the add-on and the content later.
---

# Installation

Human Generator is two things: the add-on, and the content packs with the humans, clothing, hair and poses. The add-on downloads the packs for you the first time you use it.

## Install the add-on

**Blender 4.2 and later.** Open your order on Superhive, or the trial page, and drag the **Install in Blender** button into any Blender window. Blender adds the Human Generator repository and installs the add-on from it. Updates then show up in Blender's extension list like any other extension.

**Blender 4.0 and 4.1.** Download the zip, go to Edit > Preferences > Add-ons > Install, and pick the zip. Do not unzip it first. Updates come through the updater at the bottom of the add-on's preferences.

## Set up the content

Open the sidebar of the 3D viewport (press `N`) and go to the HumGen tab. Press **Set up Human Generator**.

1. **Free trial** needs no account. It installs the trial content: one human, a skin, an outfit, a hairstyle and four poses. The rest of the library is visible but locked.
2. **Activate licence** asks for your Superhive order and installs the full library.

Then choose the content folder and the packs to install. The download runs in the background; you can close the window and keep working, and it opens again when the download is done.

The standard packs are ticked. **8K Textures** is listed unticked: it is a 2 GB download that only matters for close-ups and large prints, because Base Humans already includes the same skins in 4K. Tick it when you need it, now or later from the preferences.

> [!info]- Pop-up not showing?
> The setup opens as a window inside the 3D viewport. If nothing shows, the HumGen tab offers **Set up in this panel**, which has the same steps as plain buttons.

> [!info]- Blender asks to allow online access
> Blender 4.2 and later has an "Allow Online Access" setting. The setup needs it to download the content and asks for it with one button. Nothing else in Human Generator uses the network, apart from a daily check for updates that you can turn off by turning that setting off.

## Order GUID

Activating asks for the **order GUID** of your Superhive purchase and the email address of your Superhive account. The GUID is in the order confirmation email from Superhive and on the order page of your Superhive account. Copy it as it is; spaces and braces around it are fine.

The order is checked once. After that, the add-on remembers it on this computer and uses it only to download content packs and their updates.

## Email

The email address is the one of your Superhive account. It ties the order to you: once an order has been activated with an address, only that address can activate it again. That stops someone who guesses an order number from downloading your content. The address is stored on our server as a hash, not as text. Tick **Let me know about updates and offers** if you want our news; it is off by default.

## Already have the content?

If the packs are already on your computer, press **Change** next to the content folder in the setup and pick that folder. Packs found there count as installed. The add-on also remembers the folder in a small settings file outside Blender, so a new Blender version or a switch from the legacy add-on to the extension finds it again.

## Updates

The add-on checks once a day for new versions of itself and of the content packs, when Blender's online access is on. The HumGen tab shows a notice with an **Update** button when there is something new; the preferences list every pack with its version and a **Check for updates** button.

A pack update replaces only the files of that pack. Your own content, saved with the content saving tools, stays where it is.

> [!info]- Installing a pack from a file
> Packs downloaded from your Superhive account, or packs someone else made, install from the add-on preferences: Content Packs > Install from file.
