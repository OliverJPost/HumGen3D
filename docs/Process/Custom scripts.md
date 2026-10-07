---
permalink: scripts
---


> [!info] Part of the [[Process/Overview|Processing System]]


Custom scripts are Python scripts that can do simple or advanced extra processing on your humans.

> [!warning] Breaking functionality
> Some scripts might break other functionality of Human Generator. If it is an official script we will put in the description what it breaks, but 3rd party scripts might unexpectedly break HG functionality. 

> [!warning] Malicious scripts
> Only use scripts from sources you trust. Python scripts can contain malware. Human Generator is not responsible for 3rd party scripts you download on the internet.

![[Screenshot_Blender_000188.webp]]
1. **Script selector**: From this dropdown you can select which scripts to add. By adding a script it will be run as part of the processing system.
2. **Add new script button**: Want to write your own script? Click here and a new template script will be created for you. For more information on how to use the HG Python API see [[API/Overview|API Overview]].
3. **Script description and options**: Here you can find the description of the script. Creators of scripts might also put warnings here about what functionality might be broken by using the script. If the script has custom options they will also appear here.
4. **Script order buttons**: Here you can move the script up and down in the stack of scripts. Scripts will be executed as the last step of processing in top to bottom order of the script stack.
5. **Remove script button**: This removes it from the stack, so it will no longer be executed. It does NOT delete the script from your computer.