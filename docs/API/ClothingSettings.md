> Interface class for accessing OutfitSettings and FootwearSettings.

Accessible from: `human.clothing`


### Properties
---
##### Footwear:
```py
human.clothing.footwear
>>> FootwearSettings
```
*Read-only*
Use this property to access FootwearSettings.  FootwearSettings allows you to change the footwear of the human.   
`Returns `[[FootwearSettings]]` `

---
##### Outfit:
```py
human.clothing.outfit
>>> OutfitSettings
```
*Read-only*
Use this property to access OutfitSettings.  OutfitSettings allows you to change the outfits (excluding footwear) of the human.   
`Returns `[[OutfitSettings]]` `

---
### Methods
---
##### As Dict
```py
human.clothing.as_dict()
>>> dict
```
*Inherited from [[Could not find source]]*
Returns dict of clothing settings.   


**Returns:**
- `returns (dict)`: dict[str, dict[str, Any]]

---
##### Set From Dict
```py
human.clothing.set_from_dict(data: dict)
>>> list
```
*Inherited from [[Could not find source]]*
Set clothing settings from dict.   

**Arguments:**
- `data (dict)`: Dict of clothing settings.  

**Returns:**
- `returns (list)`: list[str]

---
