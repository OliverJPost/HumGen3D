"""Generate the Python API reference (docs/API/api.json) from the source code.

Reads the code statically with griffe, so Blender is not needed:

    python scripts/api_docs.py          # write docs/API/api.json
    python scripts/api_docs.py --check  # exit 1 if api.json is out of date

Which classes are documented: the public entry points below, every class
reached from them through a property or attribute, every class a public
method returns, and their base classes inside HumGen3D. `accessors` records
how a class is reached from `human` (e.g. `human.hair.eyelashes`); the website
builds the API sidebar from it.
"""

import argparse
import json
import shutil
import sys
import tempfile
from collections import deque
from pathlib import Path
from typing import Any, Optional

import griffe

REPO = Path(__file__).resolve().parent.parent
OUTPUT = REPO / "docs" / "API" / "api.json"
PACKAGE = "HumGen3D"

# (class path, how it is reached in user code)
ENTRY_POINTS = [
    ("human.human.Human", "human"),
    ("batch_generator.generator.BatchHumanGenerator", None),
]
# A class reachable through more paths than this is a shared value type
# (NodeInput, PropCollection), not a place in the human.* tree.
SHARED_TYPE_PATHS = 2
SKIP_DIRS = {"venv", "docs", "tests", "scripts", "extern", "wheels", ".git"}


def load_package() -> griffe.Module:
    """Load a copy of the package; griffe skips folders without __init__.py."""
    tmp = Path(tempfile.mkdtemp())
    root = tmp / PACKAGE
    for src in REPO.rglob("*.py"):
        rel = src.relative_to(REPO)
        if rel.parts[0] in SKIP_DIRS:
            continue
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    for folder in [root, *(p for p in root.rglob("*") if p.is_dir())]:
        (folder / "__init__.py").touch()
    return griffe.load(
        PACKAGE,
        search_paths=[str(tmp)],
        docstring_parser="google",
        allow_inspection=False,
    )


def class_refs(expr: Any) -> list[str]:
    """Canonical paths of HumGen3D classes named in an annotation or call."""
    if expr is None or isinstance(expr, str):
        return []
    names = [expr] if isinstance(expr, griffe.ExprName) else []
    if hasattr(expr, "iterate"):
        names += [e for e in expr.iterate(flat=True) if isinstance(e, griffe.ExprName)]
    return [
        n.canonical_path
        for n in names
        if n.canonical_path and n.canonical_path.startswith(PACKAGE + ".")
    ]


def is_plain(expr: Any) -> bool:
    """A class, `Optional[...]` or a union of classes; not a container."""
    if isinstance(expr, griffe.ExprName):
        return True
    if isinstance(expr, griffe.ExprBinOp):
        return True
    if isinstance(expr, griffe.ExprSubscript):
        left = getattr(expr.left, "canonical_path", "")
        return left in ("typing.Union", "typing.Optional")
    return False


def type_text(expr: Any) -> Optional[str]:
    if expr is None:
        return None
    return str(expr).strip("'\"")


def attribute_type(member: griffe.Attribute) -> tuple[Optional[str], Any]:
    """Annotation, or the class instantiated in `self.x = SomeClass(...)`."""
    if member.annotation is not None:
        return type_text(member.annotation), member.annotation
    value = member.value
    if isinstance(value, griffe.ExprCall) and isinstance(value.function, griffe.ExprName):
        return value.function.name, value.function
    return None, None


def parse_docstring(obj: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"summary": "", "description": "", "params": {}, "returns": None, "raises": [], "examples": []}
    if not obj.docstring:
        return out
    text_parts = []
    for section in obj.docstring.parse("google"):
        kind = section.kind.value
        if kind == "text":
            text_parts.append(section.value)
        elif kind in ("parameters", "other parameters"):
            for p in section.value:
                out["params"][p.name] = clean(p.description)
        elif kind == "returns":
            out["returns"] = " ".join(clean(r.description) for r in section.value if r.description) or None
        elif kind == "raises":
            out["raises"] = [{"type": type_text(r.annotation), "description": clean(r.description)} for r in section.value]
        elif kind == "examples":
            for item in section.value:
                kind_value, text = item
                out["examples"].append({"kind": kind_value.value, "text": text})
        elif kind == "admonition":
            text_parts.append(f"**{section.title}**: {section.value.description}")
    text = "\n\n".join(t.strip() for t in text_parts if t.strip())
    summary, _, rest = text.partition("\n\n")
    out["summary"] = " ".join(summary.split())
    out["description"] = rest.strip()
    return out


def clean(text: Optional[str]) -> str:
    """Join wrapped lines and drop a repeated `(type):` prefix."""
    text = " ".join((text or "").split())
    if text.startswith("(") and "):" in text[:20]:
        text = text.split("):", 1)[1].strip()
    return text


def location(obj: Any) -> dict[str, Any]:
    rel = Path(obj.filepath).as_posix().split(f"/{PACKAGE}/", 1)[-1]
    return {"file": rel, "line": obj.lineno}


def signature(fn: griffe.Function, doc: dict[str, Any]) -> list[dict[str, Any]]:
    params = []
    for p in fn.parameters:
        if p.name in ("self", "cls"):
            continue
        params.append({
            "name": p.name,
            "type": type_text(p.annotation),
            "default": str(p.default) if p.default is not None else None,
            "kind": p.kind.value,
            "description": doc["params"].get(p.name, ""),
        })
    return params


def document_member(name: str, member: Any, owner: griffe.Class) -> Optional[dict[str, Any]]:
    target = member.final_target if member.is_alias else member
    defined_in = target.parent
    if not defined_in.path.startswith(PACKAGE + "."):
        return None
    doc = parse_docstring(target)
    entry: dict[str, Any] = {
        "name": name,
        "summary": doc["summary"],
        "description": doc["description"],
        "examples": doc["examples"],
        "inheritedFrom": defined_in.name if defined_in.path != owner.path else None,
        **location(target),
    }
    labels = set(target.labels)
    if target.is_attribute:
        type_str, type_expr = attribute_type(target)
        entry.update({
            "kind": "property" if "property" in labels else "attribute",
            "type": type_str,
            "readonly": "property" in labels and "writable" not in labels,
        })
        # `human.age` is an AgeSettings; `human.age.keys` is a list of items,
        # which documents the item class but is not a path to it.
        plain = is_plain(type_expr)
        return {**entry, "_refs": class_refs(type_expr), "_plain": plain}
    if target.is_function:
        kind = "classmethod" if "classmethod" in labels else "staticmethod" if "staticmethod" in labels else "method"
        entry.update({
            "kind": kind,
            "params": signature(target, doc),
            "returns": {"type": type_text(target.returns), "description": doc["returns"]},
            "raises": doc["raises"],
        })
        return {**entry, "_refs": class_refs(target.returns)}
    return None


def is_public(name: str) -> bool:
    return not name.startswith("_")


def build() -> dict[str, Any]:
    pkg = load_package()
    classes: dict[str, dict[str, Any]] = {}
    accessors: dict[str, list[str]] = {}
    queue: deque[tuple[str, Optional[str]]] = deque()

    def reach(path: str, accessor: Optional[str]) -> None:
        if accessor:
            paths = accessors.setdefault(path, [])
            if accessor in paths or len(accessor.split(".")) > 6:
                return
            paths.append(accessor)
        elif path in classes:
            return
        queue.append((path, accessor))

    for path, accessor in ENTRY_POINTS:
        reach(f"{PACKAGE}.{path}", accessor)

    while queue:
        path, accessor = queue.popleft()
        try:
            cls = pkg.modules_collection.get_member(path)
        except (KeyError, griffe.AliasResolutionError):
            continue
        if cls.is_alias:
            cls = cls.final_target
        if not cls.is_class:
            continue
        first_visit = cls.path not in classes
        if first_visit:
            doc = parse_docstring(cls)
            classes[cls.path] = {
                "name": cls.name,
                "path": cls.path.removeprefix(PACKAGE + "."),
                "summary": doc["summary"],
                "description": doc["description"],
                "examples": doc["examples"],
                "bases": [type_text(b) for b in cls.bases],
                **location(cls),
                "members": [],
            }
            for base in cls.bases:
                for ref in class_refs(base):
                    reach(ref, None)

        def order(item: tuple[str, Any]) -> tuple[int, str, int]:
            member = item[1]
            inherited = bool(getattr(member, "inherited", False))
            owner = member.final_target.parent.name if inherited else ""
            return (int(inherited), owner, (member.final_target if inherited else member).lineno or 0)

        for name, member in sorted(cls.all_members.items(), key=order):
            if not is_public(name):
                continue
            try:
                entry = document_member(name, member, cls)
            except griffe.AliasResolutionError:
                continue
            if not entry:
                continue
            refs = entry.pop("_refs")
            plain = entry.pop("_plain", False)
            if first_visit:
                classes[cls.path]["members"].append(entry)
            for ref in refs:
                child = f"{accessor}.{name}" if accessor and plain else None
                reach(ref, child)

    known = {c["name"] for c in classes.values()}
    result = []
    for path, data in classes.items():
        data["accessors"] = sorted(accessors.get(path, []), key=lambda a: (a.count("."), a))
        is_base = any(
            data["name"] in other["bases"] for other in classes.values()
        )
        data["role"] = (
            "entry" if any(path == f"{PACKAGE}.{p}" for p, _ in ENTRY_POINTS)
            # Small value types (NodeInput, PropCollection) used all over
            else "type" if len(data["accessors"]) > SHARED_TYPE_PATHS
            else "attribute" if data["accessors"]
            else "base" if is_base
            else "referenced"
        )
        result.append(data)
    result.sort(key=lambda c: c["name"])
    return {"package": PACKAGE, "classes": result, "documentedNames": sorted(known)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if api.json is out of date")
    args = parser.parse_args()

    text = json.dumps(build(), indent=1, ensure_ascii=False) + "\n"
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != text:
            print(f"{OUTPUT.relative_to(REPO)} is out of date: run python scripts/api_docs.py")
            sys.exit(1)
        print("API docs up to date")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8")
    data = json.loads(text)
    print(f"Wrote {OUTPUT.relative_to(REPO)}: {len(data['classes'])} classes")


if __name__ == "__main__":
    main()
