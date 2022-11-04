import inspect
import os
import re
from typing import get_type_hints

import bpy
from HumGen3D import Human
from HumGen3D.human.common_baseclasses.prop_collection import PropCollection

FOLDER = "/Users/ole/Library/Mobile Documents/iCloud~md~obsidian/Documents/Human Generator 2/API"  # noqa

generated_files = []
superclass_write_dict = {}


def find_source(instance, attr_name, max_levels=5):
    cls = getattr(instance, "__class__", instance)
    super_classes = inspect.getmro(cls)[1:-1]
    source = next(
        (cls for cls in super_classes if attr_name in cls.__dict__),
        None,
    )
    if not source and max_levels > 0:
        for cls in super_classes:
            source, source_name = find_source(cls, attr_name, max_levels - 1)
            if source:
                break
    else:
        source_name = source.__name__

    if source:
        return source, source_name
    else:
        return None, "Could not find source"


class Docstring:
    def __init__(self, text):
        self.params = {}
        if not text:
            self.description = ""
            self.returns = ""
            return

        pattern = re.compile(
            "^(?P<descr>[\S\s]+?)(?P<args>Args:[\S\s]+?)?(?P<returns>Returns:[\S\s]+?)?(?P<raises>Raises:[\S\s]+?)?\Z"  # noqa
        )
        match = pattern.match(text)
        groupdict = match.groupdict()
        descr = groupdict.get("descr")
        self.description = ""
        for line in descr.splitlines():
            self.description += line.strip() + " "

        arg_string = groupdict.get("args")
        prev_name = ""
        if arg_string:
            for line in arg_string.splitlines():
                if "Args:" in line:
                    continue
                elif ":" in line:
                    name, description = line.strip().split(":")
                    name = name.split(" ")[0]
                    prev_name = name
                    self.params[name] = description.strip()
                elif prev_name:
                    self.params[prev_name] += " " + line.strip()

        return_value = groupdict.get("returns")
        if return_value:
            self.returns = return_value.split(":")[1].strip()
        else:
            self.returns = ""


class DataItem:
    type: str  # noqa A002
    module: str

    def __init__(self, name, item_type, module, docstring_text):
        self.name = str(name)
        self.type = str(item_type).replace("typing.", "")  # noqa A002
        self.module = str(module)
        self.description = (
            self.get_description(docstring_text) if docstring_text else ""
        )

    @property
    def type_as_markdown(self):
        if self.module == "bpy_types":
            return f"`[bpy.types.{self.type}](https://docs.blender.org/api/current/bpy.types.{self.type}.html)`"  # noqa
        elif self.module.startswith("HumGen3D"):
            return f"`[[{self.type}]]`"
        else:
            return self.type

    @classmethod
    def from_type(cls, name, item_type, docstring_text) -> "DataItem":
        if item_type is None:
            return cls(name, "None", "builtins", docstring_text)
        elif not hasattr(item_type, "__module__"):
            return cls(name, item_type, "builtins", docstring_text)
        elif item_type.__module__ in ("typing", "types"):
            return cls(name, item_type, item_type.__module__, docstring_text)

        return cls(name, item_type.__name__, item_type.__module__, docstring_text)

    def get_description(self, docstring_text: str) -> str:
        docstring = Docstring(docstring_text)
        if isinstance(self, ReturnValue):
            return docstring.returns if docstring.returns else "No description"
        else:
            return next(
                (
                    description
                    for name, description in docstring.params.items()
                    if name == self.name
                ),
                "No description",
            )

    def as_md_text(self):
        return f"- `{self.name} ({self.type_as_markdown})`: {self.description}\n"

    def __repr__(self) -> str:
        return (
            f"Param '{self.name}' of type '{self.type}' with descr '{self.description}'"
        )


class Parameter(DataItem):
    name: str

    @classmethod
    def from_error(cls, error):
        return cls(error, "Exception", "builtins", error)

    def as_inline(self):
        return f"{self.name}: {self.type}"


class ReturnValue(DataItem):
    @classmethod
    def from_type(cls, val_type, docstring_text):
        return super().from_type("returns", val_type, docstring_text)


class Method:
    def __init__(self, name, instance, example_output):
        self.name = name
        self.instance = instance
        try:
            self.attr = getattr(instance.__class__, name)
            self.docstring_txt = self.attr.__doc__
        except AttributeError:
            self.attr = None
            self.docstring_txt = ""
        self.params, self.kparams, self.return_param = self.parse_annotations()

    def parse_annotations(self):
        try:
            annotations = get_type_hints(self.attr)
        except NameError as e:
            return [Parameter.from_error(str(e))], [], Parameter.from_error(str(e))
        docstring = self.docstring_txt

        return_type = ReturnValue.from_type(annotations.pop("return", None), docstring)

        arguments = [
            Parameter.from_type(name, val_type, docstring)
            for name, val_type in annotations.items()
        ]

        return arguments, arguments, return_type

    def as_md_text(self, namespace) -> str:
        display_name = self.name.replace("_", " ").title().replace("Hg", "HG")
        text = f"##### {display_name}\n"
        params = ", ".join([param.as_inline() for param in self.params])
        return_type = self.return_param.type
        text += f"```py\n{namespace}.{self.name}({params})\n>>> {return_type}\n```\n"

        write_super_mode = None
        write_to_superclass = False
        if (
            self.name not in self.instance.__dict__
            or self.name not in self.instance.__class__.__dict__
        ):
            source, source_name = find_source(self.instance, self.name)
            text += f"*Inherited from [[{source_name}]]*\n"
            global superclass_write_dict
            if source:
                if source_name not in superclass_write_dict:
                    write_super_mode = "w"
                    write_to_superclass = True
                elif self.name not in superclass_write_dict[source_name]:
                    write_super_mode = "a"
                    write_to_superclass = True

        dc = Docstring(self.docstring_txt)
        descr = dc.description
        if not descr:
            descr = "No description available."
        text += descr + "\n\n"

        if self.params:
            text += "**Arguments:**\n"
            for param in self.params:
                text += param.as_md_text()

        text += "\n"

        if self.return_param and self.return_param.type != "NoneType":
            text += "**Returns:**\n"
            text += self.return_param.as_md_text()

        text += "\n---\n"

        if write_to_superclass:
            with open(os.path.join(FOLDER, source_name + ".md"), write_super_mode) as f:
                f.write(text.replace(f"*Inherited from [[{source_name}]]*\n", ""))
            superclass_write_dict.setdefault(source_name, []).append(self.name)

        return text

    def __repr__(self) -> str:
        return f"Method '{self.name}' with attr {self.attr}"


class Property:
    def __init__(self, name, instance, example_output, parent_namespace):
        self.name = name
        self.attr = getattr(instance.__class__, name, None)
        if not self.attr:
            self.docstring = ""
            self.type = "None"

        docstring_txt = self.attr.__doc__
        self.docstring = Docstring(docstring_txt) if docstring_txt else ""
        try:
            annotations = get_type_hints(self.attr.fget)
        except (NameError, AttributeError, TypeError) as e:
            self.type = ReturnValue.from_type(str(e), docstring_txt)
            return

        self.type = ReturnValue.from_type(
            annotations.pop("return", None), docstring_txt
        )

        if isinstance(example_output, PropCollection):
            return

        if getattr(example_output.__class__, "__module__", "").startswith("HumGen3D"):
            global generated_files
            if example_output.__class__.__name__ not in generated_files:
                if parent_namespace:
                    namespace = f"{parent_namespace}.{name}"
                else:
                    namespace = name
                document_from_instance(example_output, namespace)

    def as_md_text(self, namespace) -> str:
        display_name = self.name.replace("_", " ").title()
        text = f"##### {display_name}:\n"

        text += f"```py\n{namespace}.{self.name}\n>>> {self.type.type}\n```\n"
        if getattr(self.attr, "fset", "") is None:
            text += "*Read-only*\n"

        text += (
            self.docstring.description + "\n"
            if self.docstring
            else "No docstring available.\n"
        )
        text += f"`Returns {self.type.type_as_markdown} `" + "\n"

        text += "\n---\n"

        return text

    def __repr__(self) -> str:
        return f"Property '{self.name}' with attr {self.attr}"


class DocumentationInstance:
    def __init__(self, instance, parent_namespace):
        self.instance = instance
        self.cls_name = instance.__class__.__name__
        self.docstring = instance.__doc__
        self.members = inspect.getmembers(instance)
        self.staticmethods: dict[str, Method] = {}
        self.classmethods: dict[str, Method] = {}
        self.methods: dict[str, Method] = {}
        self.properties: dict[str, Property] = {}
        self.filename = instance.__class__.__name__ + ".md"

        for name, member in self.members:
            if name.startswith("_"):
                continue
            elif inspect.ismethod(member):
                if not hasattr(member, "__self__"):
                    self.staticmethods[name] = Method(name, instance, member)
                elif member.__self__ is instance.__class__:
                    self.classmethods[name] = Method(name, instance, member)
                else:
                    self.methods[name] = Method(name, instance, member)
            else:
                self.properties[name] = Property(
                    name, instance, member, parent_namespace
                )

    def get_file_header(self, parent_namespace):
        text = "> {}\n\n".format(
            self.docstring if self.docstring else "No docstring available."
        )
        if parent_namespace:
            text += f"Accessible from: `{parent_namespace}`\n"
        super_classes = inspect.getmro(self.instance.__class__)[1:-1]
        if super_classes:
            inheritance_sources = ", ".join(
                [f"[[{cls.__name__}]]" for cls in super_classes]
            )
            text += f"Inherits from {inheritance_sources}\n"
        text += "\n\n"

        return text


def document_from_instance(instance, parent_namespace):
    docinstance = DocumentationInstance(instance, parent_namespace)

    md_file = os.path.join(FOLDER, docinstance.filename)
    with open(md_file, "w") as f:
        f.write(docinstance.get_file_header(parent_namespace))

        if docinstance.properties:
            f.write("### Properties\n---\n")
            for prop in docinstance.properties.values():
                f.write(prop.as_md_text(parent_namespace))

        if docinstance.classmethods:
            f.write("### Classmethods\n---\n")
            for method in docinstance.classmethods.values():
                f.write(method.as_md_text(parent_namespace))

        if docinstance.methods:
            f.write("### Methods\n---\n")
            for method in docinstance.methods.values():
                f.write(method.as_md_text(parent_namespace))

        if docinstance.staticmethods:
            f.write("### Staticmethods\n---\n")
            for method in docinstance.staticmethods.values():
                f.write(method.as_md_text(parent_namespace))

    print(f"Created {md_file}")  # noqa
    global generated_files
    generated_files.append(instance.__class__.__name__)


def main():
    chosen = Human.get_preset_options("male", context=bpy.context)[1]
    human = Human.from_preset(chosen)

    try:
        document_from_instance(human, "human")
    finally:
        human.delete()
