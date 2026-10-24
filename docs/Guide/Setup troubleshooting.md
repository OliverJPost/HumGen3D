---
description: "What the Human Generator setup's messages mean and what to do: license key not found, wrong email, connection and proxy errors, disk space, paused downloads, online access."
---

# Setup troubleshooting

This page lists the messages the setup can show while it activates your license or downloads the content packs, with what to do. Each heading is the message as the add-on shows it. In every case below, content you already installed keeps working.

For the normal steps, see [[Installation]]. If nothing here helps, write to support@humgen3d.com with your license key (your Superhive order GUID) and the message you see.

## License key

### We couldn't find a Superhive order with this order GUID

> We couldn't find a Superhive order with this order GUID. Copy the long code from your order email again, not the short order number, or contact support@humgen3d.com.

- Use the order GUID, the long code of letters and numbers, not Superhive's short order number. Copy it again from the order email or from [Orders](https://superhivemarket.com/account/orders) in your Superhive account, see [humgen3d.com/license-key](https://humgen3d.com/license-key). Copy the whole code.
- Use the order of Human Generator. Orders of other products don't count, also when they are from the same shop.
- For an `HG3D-` license key the message is *We couldn't find this license key. Check the key in your purchase email, or contact support@humgen3d.com.*
- Still not found? Write to support with the order GUID.

### This license is linked to a different email

> This license is linked to a different email. Use the email you bought with.

Once a license is activated, only the email it was first activated with can activate it again. Use the address the Superhive order email went to, not for example your PayPal address. If your email address changed, write to support.

### This purchase was refunded

> This purchase was refunded, so it can't download content. Content you already installed is not affected.

A refunded purchase can't download content packs. If you moved to another order, for example for an upgrade, press **Change…** in the preferences or **Enter license key** in the setup and enter the new order GUID.

### This license is no longer active

> This license is no longer active. Contact support@humgen3d.com if you think this is a mistake.

Write to support.

### This purchase is still being processed

> This purchase is still being processed. Try again in a few minutes.

A new order can take a few minutes to reach us. Wait a little, then press **Activate** again.

### Too many attempts from this network

> Too many attempts from this network. Try again in an hour.

After many failed attempts from one network, the activation stops for an hour. This counts every computer on the network, so in a studio or school a colleague's attempts count too. Wait an hour, and check the license key and email before you try again.

### We couldn't confirm your license

The setup shows this when the server refuses the stored license key during a download, with the reason below it. The buttons:

- **Enter license key** opens the license step with the stored key filled in. Correct it or enter another one.
- **Retry** tries again with the same key, for example after support fixed it.
- **Contact support** opens an email to support@humgen3d.com.

The key stays stored. The add-on preferences show *Your license key was not accepted.* with **Enter again…** and **Contact support** until you change it.

### The license step says something is missing

The setup checks the form before it sends it:

- *Enter your license key. Bought on Superhive? Use the order GUID from your order email.*
- *This is the order number. Enter the order GUID instead: the long code of letters and numbers in your order email.* You entered Superhive's short order number. Copy the long order GUID instead.
- *Enter the email you bought with.*
- *Accept the license and the privacy policy to continue.* Tick the box below the email field.

## Connection

### Can't reach humgen3d.com

> Can't reach humgen3d.com. Check your internet connection and try again. Your installed content works as usual.

During a download the message is *Can't reach the download server.* Check that this computer is online, then press **Try again** or **Retry**. On a company network, a firewall may block the add-on: ask your IT department to allow the [[#Hosts to allow|hosts below]].

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

The problem is on our side, or at Superhive, which checks the order. The message can also say *The activation service is unavailable right now.* or *Superhive is slow to answer right now.* Try again in a few minutes.

### The download server sent a web page instead of the file

> The download server sent a web page instead of the file. If your network needs a sign-in page, sign in and try again.

Hotel, train and guest networks often show a sign-in page first. Open any website in your browser, sign in to the network, then press **Retry**. The part that was already downloaded is kept.

### humgen3d.com gave an unexpected answer

> humgen3d.com gave an unexpected answer. Try again later, or contact support@humgen3d.com.

Try again later. If it keeps happening, write to support.

### Downloads are paused right now

> Downloads are paused right now. Try again later.

We switched downloads off for a while, for example during maintenance. The setup may show a message from us with more details instead. Try again later.

### Hosts to allow

For firewalls, proxies and security software, the setup connects to these hosts over HTTPS (port 443):

- `humgen3d.com`
- `*.r2.cloudflarestorage.com`
- `downloads.humangenerator3d.com`

## Download and disk

### Not enough space

> Not enough space: 3.2 GB needed, 1.8 GB free

The numbers show what the selected packs need, with room to unpack them, and what is free on the disk of the content folder. Free some space, untick packs you don't need (such as **8K Textures**), or press **Change…** next to *Content folder* and pick a folder on another disk.

When the setup shows *Couldn't check the free space on this disk*, which happens on some network drives, it still installs. Make sure there is enough room.

### Can't write to the content folder

> Can't write to the content folder. Check the free space and the folder's permissions.

The disk is full, or you don't have permission to write to the folder. On a shared studio folder, ask whoever manages it, or pick a folder of your own with **Change…**.

### That drive isn't connected

> That drive isn't connected. Connect it, or choose another folder.

The content folder is on a drive that isn't there. Connect it, or press **Change…** and pick another folder. See also [[Installation#Moving or reconnecting your content folder]].

### Another Blender window is downloading the content

> Another Blender window is downloading the content.

Only one Blender can download into a content folder at a time. Wait until the other window is done, or close it. If that Blender crashed, the setup goes on by itself after 10 minutes.

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

If you close Blender during a download, start it again from the HumGen tab (**Set up Human Generator**, or the update button) and press **Install**. Finished packs stay installed and the download continues from the part that was already fetched.

### A newer Human Generator is needed for the latest content

> A newer Human Generator is needed for the latest content.

The newest content packs need a newer version of the add-on. Update the add-on in Blender's extension list (Edit > Preferences > Get Extensions), then update the packs.

### A pack can't be downloaded

When the server won't hand out one pack, *Download failed* names the pack and the reason, for example *8K Textures: This pack can't be downloaded right now.*

- *This pack needs a license. Enter your license key to download it.* The pack is not part of the trial. See [[Installation#Upgrading from the trial]].
- *This pack isn't offered for download any more.* Write to support if you need it.
- *This pack can't be downloaded right now.* Try again later.

## The setup window

### The setup window doesn't show

The setup is a window inside the 3D viewport. If it doesn't show, press `N` in the 3D viewport and open the **HumGen** tab. The *Setup* panel has **Continue setup**, and **Pop-up not showing? Set up in this panel**, which shows the same steps as plain buttons in the sidebar.

### This viewport is too small for the setup

> This viewport is too small for the setup. Make it larger, or go on in the sidebar.

Make the 3D viewport larger, for example with `Ctrl Space`, or press **Continue in the sidebar**.

### Downloading needs Blender's online access, which is turned off

> Downloading needs Blender's online access, which is turned off.

Blender 4.2 and later has an *Allow Online Access* setting, and the setup needs it to download. Press **Allow online access** in the setup, the HumGen tab or the add-on preferences. The setting is also under Edit > Preferences > System > Network.

Apart from the download, Human Generator only uses the network for a daily check for updates. Turning online access off stops that check too.

### Blender was started in offline mode

> Blender was started in offline mode. Start it normally to download content.

Blender was started with `--offline-mode`, which can't be changed while it runs. Start Blender without that option.

### Could not load the pack list

The setup couldn't get the list of packs from humgen3d.com. The reason follows the message; see the [[#Connection]] sections above. Press **Try again** when it is fixed.

### No Human Generator content in this folder

You picked a folder with **Use this folder** or **Select folder** that has no Human Generator content packs in it. Pick the folder that has the `content_packs` folder inside, or download the content with the setup.
