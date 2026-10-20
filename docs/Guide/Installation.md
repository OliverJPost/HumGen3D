---
description: "Install Human Generator in Blender 4.2 or newer, download the content packs with the setup, activate your order, and find your content folder again after a move."
---

# Installation

Human Generator has two parts: the add-on, and the content packs with the humans, clothing, hair and poses. You install the add-on yourself. The add-on then downloads the content packs for you.

If something goes wrong on the way, see [[Setup troubleshooting]].

## Requirements

### Blender version

Human Generator needs **Blender 4.2 or newer**, on Windows, macOS or Linux.

On Blender 4.0 and 4.1 the add-on still loads, but it does nothing except show this notice, with its version number, in the HumGen tab and in its preferences:

> Human Generator needs Blender 4.2 or newer.
> Your content and saved files are not affected.

The **Learn more** button opens this page. You have two choices:

- **Move to Blender 4.2 or newer.** You can install it next to your current Blender. Install the add-on there as described below. It finds the content folder you already have, so you don't download anything again.
- **Stay on Blender 4.0 or 4.1.** The last version of Human Generator for these Blender versions is **4.0.38**. Keep it installed and don't install a newer version from the updater in its preferences. If you already updated and now see the notice, remove Human Generator under Edit > Preferences > Add-ons and install the 4.0.38 zip again. Write to support@humgen3d.com if you no longer have that zip.

### Disk space and internet

The standard content packs are a 2 to 4 GB download, and installing them needs room to unpack. The setup shows the free space on the disk before it starts. Downloading needs an internet connection and Blender's online access setting (see [[Setup troubleshooting#Downloading needs Blender's online access, which is turned off|online access]]). Once the content is installed, Human Generator works offline.

## Install the add-on

**From the website (recommended).** Open [humgen3d.com/install](https://humgen3d.com/install), or [humgen3d.com/trial](https://humgen3d.com/trial) for the free trial. Drag the **Drag into Blender to install** button into any Blender window and confirm the dialog. Blender adds the Human Generator repository and installs the add-on from it. Updates then show up in Blender's extension list like any other extension.

**From a zip file.** Download the add-on zip from the same page. In Blender, go to Edit > Preferences > Get Extensions, open the menu at the top right and choose **Install from Disk**. Pick the zip; don't unzip it first. Blender doesn't update an add-on installed this way. To get updates later, press **Enable add-on updates** in the add-on preferences, which adds the Human Generator repository.

> [!info] Already have Human Generator in your add-ons folder?
> A legacy install of Human Generator in Blender 4.2 or newer keeps working. If you install the new version next to it, see [[#Installed twice]].

## Set up the content

The setup opens by itself the first time Blender starts with Human Generator and no content. If it doesn't, or you closed it, press `N` in the 3D viewport, open the **HumGen** tab and press **Set up Human Generator**.

1. **Welcome.** Press **Get started**. If you installed from the trial page, the buttons are **Install the free trial** and **I have a licence** instead. If the setup found Human Generator content on this computer, it offers that folder first, see [[#Already a customer? Nothing changes]].
2. **How do you want to start?** Choose **Free trial** or **Activate licence**. The trial needs no account and installs one human, an outfit, a hairstyle and four poses. Activate licence asks for your order and installs the full library, see [[#Activate your order]].
3. **Packs.** The standard packs are ticked. **8K Textures** is unticked: it is a 2 GB download for close-ups and large prints, and Base Humans already has the same skins in 4K. Tick it now or add it later from the preferences. Press **Change…** next to *Content folder* to pick where the content goes.
4. **Install.** The download runs in the background. Press **Continue in background** to keep working; the progress stays in the HumGen tab. **Pause** stops the download and keeps what it fetched.
5. **Done.** *Human Generator is ready* shows the folder. Press **Create your first human**, or **Show me around** for a short tour.

> [!info]- Setup window not showing?
> The setup is a window inside the 3D viewport. If it doesn't show, open the HumGen tab in the sidebar. The *Setup* panel there has **Continue setup**, and **Pop-up not showing? Set up in this panel**, which has the same steps as plain buttons.

## Activate your order

The licence step asks for two things: your **Order ID or licence key** and **The email you used for the order**. You also tick that you accept the Human Generator Asset License and the privacy policy. Then press **Activate**.

Your order is checked once. The add-on remembers it on this computer, in a small settings file outside Blender, and uses it only to download content packs and their updates. Only downloads are linked to your order: content you installed keeps working without it, also offline, and also if you forget the order later.

<span id="order-guid"></span>
### Order ID or licence key

The order ID is the long code of your Superhive order (Superhive was called BlenderMarket before). You find it in two places:

- the order confirmation email from Superhive;
- your Superhive account: log in, go to [Orders](https://superhivemarket.com/account/orders) and open your Human Generator order.

Copy the whole code as it is. If you have a licence key instead, it starts with `HG3D-`; enter that in the same field.

### Email

Enter the email you placed the order with, the address the order email from Superhive went to. It ties the order to you: once an order is activated with an address, only that address can activate it again. That stops someone who guesses an order ID from downloading your content. Our server stores the address as a hash, not as text.

Tick **Let me know about updates and offers** if you want our news at this address. It is off by default.

## Already a customer? Nothing changes

If you used Human Generator 4 before, you don't need to download or activate anything to keep working.

- **Your content is found automatically.** The setup looks in the folder of your preferences, the folder an earlier version remembered, the preferences of the older add-on and the default folder. When it finds content, the welcome screen shows *Found Human Generator content in* with the folder. Press **Use this folder**. Nothing is downloaded and no order is asked.
- **If it isn't found,** press **Select folder** next to *I already have the content packs* on the welcome screen, and pick the folder with your packs.
- **Your order is asked once,** only when you download something: an update, or a pack you add. The setup then shows *One more step to download updates*. Enter your order, or press **Not now** to keep working with the content you have.

## Updates

**The add-on** updates through Blender's extension list (Edit > Preferences > Get Extensions) when you installed it from the website.

**The content packs** are checked once a day while Blender's online access is on. When there is something new, the *Setup* panel in the HumGen tab shows *Content update available*, or *Content update needed* when this version of the add-on needs the newer pack, with a button such as **Update 2 packs**. The add-on preferences list every pack with its version, and have **Check for updates** and an update button.

A pack update replaces only the files of that pack. Your own content, saved with the content saving tools, stays where it is.

If you see *A newer Human Generator is needed for the latest content.*, update the add-on first, then the packs.

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
- **Download again…** opens the setup to download the content into a new folder.

Nothing is created or downloaded while the folder is missing.

To move the content on purpose, move the folder in your file manager, then press **Locate folder…**. You can also change the folder in the add-on preferences: Content Packs tab, **Change folder…** next to *Content folder*. Blend files you saved before the move may still look for textures in the old place. Blender's File > External Data > Find Missing Files fixes those.

## Your licence

The Content Packs tab of the add-on preferences shows the order this computer downloads with, masked, with its tier: *Personal licence* or *Commercial licence*.

- **Upgrade to Commercial** shows for a Personal licence. It opens [humgen3d.com/upgrade](https://humgen3d.com/upgrade), which takes you to the Commercial upgrade on Superhive. The row shows *Commercial licence* after the next download. To update it right away, press **Change…** and activate again.
- **Change…** opens the licence step of the setup, to enter another order ID or licence key.
- **Forget** removes the order from this computer, after you confirm. Installed content stays. The setup asks for an order again the next time you download.

When the server didn't accept the stored order, the row says *Your order or licence key was not accepted.* with the reason, **Enter again…** and **Contact support**. See [[Setup troubleshooting#Order and licence]].

## Upgrading from the trial

The trial shows **I have a licence** next to every buy button, and next to **Get the full version** in the *Setup* panel of the HumGen tab. After you buy Human Generator:

1. Press **I have a licence**.
2. Enter your order ID and email in *Activate the full version*, see [[#Activate your order]].
3. Choose the packs and press **Install**.

The full library replaces the trial content automatically. Your own saved content stays.

## Packs from other creators

The Human Generator packs always come through the setup. Content packs that other creators made install from files: in the add-on preferences, open the Content Packs tab, then **Packs from other creators**. Press **Select pack files**, pick the `.hgpack` files, and press **Install selected packs**. To make a pack of your own, see [[Exporting your content as a pack]].
