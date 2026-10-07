# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Connects the clothing geometry code to Blender humans and clothing objects.

All geometry is handled in the space of the rig object, in which the human
stands upright in its rest pose no matter where the rig is in the scene.

Clothing objects can steer the fit with:
- a vertex group `hg_loose`: 0 hugs the body, 1 drapes freely. Without it the
  looseness is derived from how far the garment is from the base body.
- custom property `hg_fit_slope`: how fast cloth returns to the body below a
  belly or bust, around 0.1 for a boxy fit, 0.6 (default) for a regular one.
- custom property `hg_skirt`: treat both legs as one volume. Detected if unset.
- custom property `hg_bust_drape`: 0-1, how strongly cloth spans the bust
  instead of wrapping each breast. Defaults to 1 for anything that also covers
  the midriff and 0 for items like bikini tops.
"""

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Iterable, Optional

import bpy
import numpy as np
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.common.geometry import world_coords_from_obj
from HumGen3D.common.progress import Steps, phase, run
from HumGen3D.common.surface import (
    edges_from_tris,
    make_bvh,
    smooth_field,
    vert_normals,
)
from HumGen3D.human.clothing.fitting import (
    BodyBinding,
    drape_envelope,
    fit_shape,
    loose_displacement,
    resolve_collisions,
    vertex_covariance,
)
from HumGen3D.human.clothing.skinning import skin_matrices, unskin
from HumGen3D.human.clothing.weights import transfer_weights_steps
from mathutils.bvhtree import BVHTree

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

LOOSE_GROUP = "hg_loose"
DEFAULT_SLOPE = 0.6
TIGHT_GAP = 0.004
LOOSE_GAP = 0.016
# Converting a garment happens once, so the weight solve may take its time
FINAL_SOLVE_ITERATIONS = 6000

_ARM = ("upper_arm", "forearm", "hand", "palm", "f_", "thumb")
_LEG = ("thigh", "shin", "foot", "toe")
_HEAD = ("head", "neck")
_TORSO = ("spine", "shoulder", "breast")


@dataclass
class _Body:
    """What all humans with the same body mesh have in common."""

    bones: list[str]
    tris: np.ndarray
    edges: np.ndarray
    weights: np.ndarray
    torso: np.ndarray
    torso_legs: np.ndarray
    hips: np.ndarray
    shoulders: np.ndarray
    midriff: np.ndarray
    bust: np.ndarray


class _Shape:
    """One body shape in the rest pose, with lazily computed extras."""

    def __init__(self, key: int, co: np.ndarray, body: _Body) -> None:
        self.key = key
        self.co = co
        self.body = body
        self.pairs: dict[int, dict[Any, np.ndarray]] = {}
        self.correctives: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self._envelopes: dict[tuple[bool, float], np.ndarray] = {}
        self._bvh: Optional[BVHTree] = None
        self._normals: Optional[np.ndarray] = None

    @property
    def bvh(self) -> BVHTree:
        if self._bvh is None:
            self._bvh = make_bvh(self.co, self.body.tris)
        return self._bvh

    @property
    def normals(self) -> np.ndarray:
        if self._normals is None:
            self._normals = vert_normals(self.co, self.body.tris)
        return self._normals

    def envelope(self, skirt: bool, slope: float) -> np.ndarray:
        key = (skirt, round(slope, 3))
        if key not in self._envelopes:
            mask = self.body.torso_legs if skirt else self.body.torso
            pushed = drape_envelope(self.co, mask, slope=slope)
            self._envelopes[key] = self.co + smooth_field(
                pushed - self.co, self.body.edges, 10
            )
        return self._envelopes[key]


@dataclass
class _Garment:
    """A clothing mesh bound to the base body it was made for."""

    binding: BodyBinding
    is_skirt: bool
    covers_midriff: bool
    looseness: np.ndarray
    correctives: Optional[dict[str, np.ndarray]] = None


@dataclass
class Conversion:
    """Result of turning a worn mesh into a clothing asset.

    Attributes:
        base: Coordinates fitting the unmodified body of the human's gender.
        rest: Coordinates fitting this human in its rest pose. Skinning these
            with `weights` gives back the mesh exactly as it was worn.
        weights: Weight matrix (vertices, bones).
        bones: Bone name for every column of `weights`.
        solver: How the weights were computed, see `transfer_weights`. "kept"
            if existing weights were used.
    """

    base: np.ndarray
    rest: np.ndarray
    weights: np.ndarray
    bones: list[str] = field(default_factory=list)
    solver: str = "kept"


@dataclass
class BodyReference:
    """The unmodified body of one gender, usable after the human is gone.

    Attributes:
        co: Body coordinates in the space of the rig.
        tris: Body triangles.
        weights: Weight matrix (vertices, bones), rows summing to 1.
        bones: Deform bone name for every column of `weights`.
    """

    co: np.ndarray
    tris: np.ndarray
    weights: np.ndarray
    bones: list[str]


_BODIES: dict[tuple[int, int], _Body] = {}
_SHAPES: "OrderedDict[int, _Shape]" = OrderedDict()
_GARMENTS: "OrderedDict[tuple[int, int], _Garment]" = OrderedDict()


def clear_caches() -> None:
    """Forget all cached body and garment data, for example after a file load."""
    _BODIES.clear()
    _SHAPES.clear()
    _GARMENTS.clear()


def body_reference(human: "Human") -> BodyReference:
    """Get what is needed to weight clothing for the gender of a human.

    Clothing in the content library fits the unmodified body of its gender, so
    this is all a batch script needs to transfer weights to library files.

    Args:
        human: Any human of the gender in question.

    Returns:
        Copy of the base body data that stays valid when the human is deleted.
    """
    body = _body(human)
    co = _gender_co(human, human.gender)
    return BodyReference(co, body.tris.copy(), body.weights.copy(), list(body.bones))


def fit_to_human(human: "Human", cloth_obj: bpy.types.Object) -> np.ndarray:
    """Compute the shape of a clothing object on the current body of a human.

    Args:
        human: Human the clothing is worn by.
        cloth_obj: Clothing object whose base shape fits the unmodified body.

    Returns:
        Coordinates in the local space of `cloth_obj`.
    """
    rig = human.objects.rig
    body = _body(human)
    base = _shape(_gender_co(human, human.gender), body)
    target = _shape(_shaped_co(human), body)
    matrix = _rig_matrix(cloth_obj, rig)
    g_base = _transformed(_base_data_co(cloth_obj), matrix)
    garment = _garment(g_base, _triangles(cloth_obj), base)

    pair = target.pairs.setdefault(base.key, {})
    if "covariance" not in pair:
        pair["covariance"] = vertex_covariance(base.co, target.co, body.edges)

    is_shoe = "shoe" in cloth_obj
    painted = _group_values(cloth_obj, LOOSE_GROUP)
    looseness = garment.looseness if painted is None else painted
    skirt = bool(cloth_obj.get("hg_skirt", garment.is_skirt))
    slope = float(cloth_obj.get("hg_fit_slope", DEFAULT_SLOPE))
    bust = float(cloth_obj.get("hg_bust_drape", float(garment.covers_midriff)))

    loose_field = None
    if not is_shoe:
        loose_key = (skirt, round(slope, 3))
        if loose_key not in pair:
            pair[loose_key] = loose_displacement(
                base.envelope(skirt, slope), target.envelope(skirt, slope), body.edges
            )
        loose_field = pair[loose_key]

    iron = bust > 0 and not is_shoe
    fitted = fit_shape(
        g_base,
        garment.binding,
        base.co,
        target.co,
        pair["covariance"],
        loose_field=loose_field,
        looseness=looseness,
        envelope_b=target.envelope(skirt, slope) if iron else None,
        iron_mask=body.bust * bust if iron else None,
        iron_weight=painted,
    )
    fitted = resolve_collisions(
        fitted, target.co, body.tris, bvh=target.bvh, b_normals=target.normals
    )
    return _transformed(fitted, np.linalg.inv(matrix))


def convert_worn(
    human: "Human",
    cloth_obj: bpy.types.Object,
    context: bpy.types.Context,
    recalculate_weights: bool = True,
    progress: Optional[Callable[[float], None]] = None,
) -> Conversion:
    """Turn a mesh that sits on a posed, shaped human into a clothing asset.

    See `convert_worn_steps`. `progress` is called with a fraction from 0 to 1
    as the conversion advances.
    """
    return run(
        convert_worn_steps(human, cloth_obj, context, recalculate_weights), progress
    )


def convert_worn_steps(
    human: "Human",
    cloth_obj: bpy.types.Object,
    context: bpy.types.Context,
    recalculate_weights: bool = True,
) -> Steps[Conversion]:
    """Turn a mesh that sits on a posed, shaped human into a clothing asset.

    Takes the object the way it currently looks, with its shape keys and
    armature modifier if it has any, and removes first the pose and then the
    body shape of the human from it. Done in resumable steps that yield the
    fraction of the work that is done, nothing is modified.

    Args:
        human: Human the object sits on.
        cloth_obj: Mesh object to convert. It is not modified.
        context: Blender context.
        recalculate_weights: Transfer weights from the body. If False the
            existing vertex groups of the object are used.

    Returns:
        The converted geometry and weights, in the space of the rig.

    Raises:
        HumGenException: If a modifier changes the vertex count of the object.
    """
    rig, body_obj = human.objects.rig, human.objects.body
    body = _body(human)
    body_matrix = _rig_matrix(body_obj, rig)
    body_rest = _transformed(_evaluated_co(body_obj, context, ()), body_matrix)
    body_posed = _transformed(
        _evaluated_co(body_obj, context, ("ARMATURE",)), body_matrix
    )
    worn = _evaluated_co(cloth_obj, context, ("ARMATURE",))
    if len(worn) != len(cloth_obj.data.vertices):
        raise HumGenException("A modifier changes the vertex count of the clothing.")
    worn = _transformed(worn, _rig_matrix(cloth_obj, rig))
    tris = _triangles(cloth_obj)

    matrices = skin_matrices(rig, body.bones)
    dual_quaternion = _preserves_volume(body_obj)
    rest_bvh = make_bvh(body_rest, body.tris)
    solver = "kept"
    if recalculate_weights:
        # In the posed space limbs may touch, so the first weights are only
        # used to take the pose out. The final ones come from the rest pose.
        weights, _ = yield from phase(
            transfer_weights_steps(
                worn, tris, body_posed, body.tris, body.weights, draft=True
            ),
            0.0,
            0.1,
        )
        # The final solve with its many iterations takes most of the time
        for final, (start, end) in ((False, (0.1, 0.2)), (True, (0.2, 0.9))):
            rest = unskin(worn, weights, matrices, dual_quaternion)
            weights, info = yield from phase(
                transfer_weights_steps(
                    rest,
                    tris,
                    body_rest,
                    body.tris,
                    body.weights,
                    bvh=rest_bvh,
                    draft=not final,
                    maxiter=FINAL_SOLVE_ITERATIONS,
                ),
                start,
                end,
            )
        solver = info["solver"]
    else:
        weights = weight_matrix(cloth_obj, body.bones)
    rest = unskin(worn, weights, matrices, dual_quaternion)
    yield 0.9

    base = _shape(_gender_co(human, human.gender), body)
    binding = BodyBinding(rest, tris, body_rest, body.tris, bvh=rest_bvh)
    covariance = vertex_covariance(body_rest, base.co, body.edges)
    base_co = fit_shape(
        rest, binding, body_rest, base.co, covariance, keep_outside=False
    )
    return Conversion(base_co, rest, weights, body.bones, solver)


def corrective_deltas(
    human: "Human", g_base: np.ndarray, g_tris: np.ndarray, names: list[str]
) -> dict[str, np.ndarray]:
    """Transfer corrective shape keys of the body to a garment.

    Args:
        human: Human whose body holds the corrective shape keys.
        g_base: Base shape of the garment in the space of the rig.
        g_tris: Garment triangles.
        names: Names of the body shape keys to transfer.

    Returns:
        Per shape key that exists on the body the garment displacement.
    """
    body_obj = human.objects.body
    body = _body(human)
    matrix = _rig_matrix(body_obj, human.objects.rig)
    base = _shape(_gender_co(human, human.gender), body)
    garment = _garment(g_base, g_tris, base)
    basis = _transformed(_co(body_obj.data.vertices), matrix)
    key_blocks = body_obj.data.shape_keys.key_blocks

    deltas = {}
    for name in names:
        if name not in key_blocks:
            continue
        if name not in base.correctives:
            delta = _transformed(_co(key_blocks[name].data), matrix) - basis
            target = base.co + delta
            base.correctives[name] = (
                target,
                vertex_covariance(base.co, target, body.edges),
            )
        target, covariance = base.correctives[name]
        moved = fit_shape(
            g_base,
            garment.binding,
            base.co,
            target,
            covariance,
            smooth=1,
            keep_outside=False,
        )
        deltas[name] = moved - g_base
    return deltas


def missing_correctives(
    human: "Human", cloth_obj: bpy.types.Object, min_move: float = 0.0005
) -> dict[str, np.ndarray]:
    """Compute corrective shape keys for clothing that was saved without any.

    Without them the body is pushed through the clothing wherever one of its
    own corrective shape keys is active, like at a raised shoulder.

    Args:
        human: Human the clothing is worn by.
        cloth_obj: Clothing object whose base shape fits the unmodified body.
        min_move: Shape keys that move no vertex further than this are left out.

    Returns:
        Per corrective shape key of the body that affects the clothing, the
        shape key coordinates in the local space of `cloth_obj`.
    """
    rig, body_obj = human.objects.rig, human.objects.body
    matrix = _rig_matrix(cloth_obj, rig)
    g_base = _transformed(_base_data_co(cloth_obj), matrix)
    g_tris = _triangles(cloth_obj)
    base = _shape(_gender_co(human, human.gender), _body(human))
    garment = _garment(g_base, g_tris, base)
    if garment.correctives is None:
        names = [
            key.name
            for key in body_obj.data.shape_keys.key_blocks
            if key.name.startswith("cor_")
        ]
        garment.correctives = {
            name: delta
            for name, delta in corrective_deltas(human, g_base, g_tris, names).items()
            if np.abs(delta).max() > min_move
        }
    inverse = np.linalg.inv(matrix)
    return {
        name: _transformed(g_base + delta, inverse)
        for name, delta in garment.correctives.items()
    }


def other_gender_base(
    human: "Human", g_base: np.ndarray, g_tris: np.ndarray, gender: str
) -> np.ndarray:
    """Refit the base shape of a garment to the unmodified body of a gender.

    Args:
        human: Human of the gender the garment was made for.
        g_base: Base shape of the garment in the space of the rig.
        g_tris: Garment triangles.
        gender: "male" or "female".

    Returns:
        Base shape for that gender. Unchanged if it is the human's own gender.
    """
    if gender == human.gender:
        return g_base
    body = _body(human)
    base = _shape(_gender_co(human, human.gender), body)
    other = _gender_co(human, gender)
    garment = _garment(g_base, g_tris, base)
    covariance = vertex_covariance(base.co, other, body.edges)
    return fit_shape(g_base, garment.binding, base.co, other, covariance)


def write_weights(
    cloth_obj: bpy.types.Object,
    bones: list[str],
    weights: np.ndarray,
    remove: Iterable[str] = (),
) -> None:
    """Replace the deform vertex groups of a clothing object.

    Args:
        cloth_obj: Clothing object to write to.
        bones: Bone name for every column of `weights`.
        weights: Weight matrix (vertices, bones).
        remove: Names of other vertex groups to remove, for example the mask
            and hair groups older versions copied over from the body. A group
            that one of the object's modifiers uses is never removed.
    """
    in_use = {getattr(modifier, "vertex_group", "") for modifier in cloth_obj.modifiers}
    stale = (set(remove) - in_use) | set(bones)
    for group in [g for g in cloth_obj.vertex_groups if g.name in stale]:
        cloth_obj.vertex_groups.remove(group)
    for column, name in enumerate(bones):
        values = weights[:, column]
        used = np.where(values > 1e-4)[0]
        if not len(used):
            continue
        group = cloth_obj.vertex_groups.new(name=name)
        for index in used:
            group.add([int(index)], float(values[index]), "REPLACE")


def to_rig_space(obj: bpy.types.Object, rig: bpy.types.Object) -> np.ndarray:
    """Get the matrix from the local space of an object to that of the rig.

    Args:
        obj: Object to get the matrix for.
        rig: Rig of the human.

    Returns:
        4x4 matrix as numpy array.
    """
    return _rig_matrix(obj, rig)


def base_shape_co(cloth_obj: bpy.types.Object, rig: bpy.types.Object) -> np.ndarray:
    """Get the base shape of a clothing object in the space of the rig.

    Args:
        cloth_obj: Clothing object.
        rig: Rig of the human.

    Returns:
        Coordinates of the reference shape key, or of the mesh without keys.
    """
    return _transformed(_base_data_co(cloth_obj), _rig_matrix(cloth_obj, rig))


def triangles(obj: bpy.types.Object) -> np.ndarray:
    """Get the triangulated faces of a mesh object.

    Args:
        obj: Mesh object.

    Returns:
        Array (triangles, 3) of vertex indices.
    """
    return _triangles(obj)


def _body(human: "Human") -> _Body:
    body_obj, rig = human.objects.body, human.objects.rig
    mesh = body_obj.data
    key = (len(mesh.vertices), len(body_obj.vertex_groups))
    if key in _BODIES:
        return _BODIES[key]

    bones = [bone.name for bone in rig.data.bones if bone.use_deform]
    weights = weight_matrix(body_obj, bones)
    weights /= np.maximum(weights.sum(axis=1, keepdims=True), 1e-12)
    tris = _triangles(body_obj)
    edges = edges_from_tris(tris)

    def total(prefixes: tuple[str, ...]) -> np.ndarray:
        columns = [i for i, name in enumerate(bones) if name.startswith(prefixes)]
        return weights[:, columns].sum(axis=1)

    arm, leg, head = total(_ARM), total(_LEG), total(_HEAD)
    other = 1.0 - total(_TORSO + _ARM + _LEG + _HEAD)  # face rig and the like
    torso_legs = (arm < 0.3) & (head < 0.3) & (other < 0.3)
    torso = torso_legs & (leg < 0.5)

    shoulder = total(("shoulder",)) + _bone(weights, bones, "spine.003")
    breast = np.clip(total(("breast",)) * 3.0, 0, 1)
    spread = smooth_field(breast[:, None], edges, 25)[:, 0]
    spread /= max(float(spread.max()), 1e-9)

    body = _Body(
        bones=bones,
        tris=tris,
        edges=edges,
        weights=weights,
        torso=torso,
        torso_legs=torso_legs,
        hips=_bone(weights, bones, "spine") > 0.5,
        shoulders=torso & (shoulder > 0.5),
        midriff=_bone(weights, bones, "spine.001") > 0.4,
        bust=np.clip(np.maximum(breast, spread * 1.5), 0, 1),
    )
    _BODIES[key] = body
    return body


def _bone(weights: np.ndarray, bones: list[str], name: str) -> np.ndarray:
    if name not in bones:
        return np.zeros(len(weights))
    return weights[:, bones.index(name)]


def _shape(co: np.ndarray, body: _Body) -> _Shape:
    key = hash(co.tobytes())
    if key in _SHAPES:
        _SHAPES.move_to_end(key)
    else:
        _SHAPES[key] = _Shape(key, co, body)
        while len(_SHAPES) > 8:
            _SHAPES.popitem(last=False)
    return _SHAPES[key]


def _garment(g_base: np.ndarray, g_tris: np.ndarray, base: _Shape) -> _Garment:
    key = (hash(g_base.tobytes()), base.key)
    if key in _GARMENTS:
        _GARMENTS.move_to_end(key)
        return _GARMENTS[key]

    body = base.body
    binding = BodyBinding(g_base, g_tris, base.co, body.tris, bvh=base.bvh)

    def bound_to(mask: np.ndarray) -> np.ndarray:
        on_mask = binding.interp(mask.astype(np.float64)[:, None])[:, 0] > 0.5
        return on_mask & binding.reliable

    gap = np.clip((binding.dist - TIGHT_GAP) / (LOOSE_GAP - TIGHT_GAP), 0, 1)
    looseness = gap * gap * (3 - 2 * gap)
    if bound_to(body.shoulders).sum() >= 20:
        # Hangs from the shoulders: the torso part drapes below the collar
        depth = g_base[:, 2].max() - g_base[:, 2]
        below_collar = np.clip((depth - 0.04) / 0.08, 0, 1)
        looseness = np.where(bound_to(body.torso), below_collar, looseness)

    garment = _Garment(
        binding=binding,
        is_skirt=_is_skirt(g_base, g_tris, base),
        covers_midriff=bool(bound_to(body.midriff).sum() >= 20),
        looseness=looseness,
    )
    _GARMENTS[key] = garment
    while len(_GARMENTS) > 48:
        _GARMENTS.popitem(last=False)
    return garment


def _is_skirt(g_base: np.ndarray, g_tris: np.ndarray, base: _Shape) -> bool:
    """Whether cloth spans the space between the legs, facing front or back."""
    if not base.body.hips.any():
        return False
    crotch = base.co[base.body.hips][:, 2].min()
    normals = vert_normals(g_base, g_tris)
    between = (
        (g_base[:, 2] < crotch - 0.08)
        & (g_base[:, 2] > crotch - 0.25)
        & (np.abs(g_base[:, 0]) < 0.025)
        & (np.abs(normals[:, 1]) > 0.7)
    )
    return bool(between.sum() >= 2)


def _gender_co(human: "Human", gender: str) -> np.ndarray:
    body_obj = human.objects.body
    if gender == "male":
        data = body_obj.data.shape_keys.key_blocks["Male"].data
    else:
        data = body_obj.data.vertices
    return _transformed(_co(data), _rig_matrix(body_obj, human.objects.rig))


def _shaped_co(human: "Human") -> np.ndarray:
    body_obj = human.objects.body
    local = world_coords_from_obj(
        body_obj, data=human.keys.all_deformation_shapekeys, local=True
    )
    return _transformed(local, _rig_matrix(body_obj, human.objects.rig))


def _rig_matrix(obj: bpy.types.Object, rig: bpy.types.Object) -> np.ndarray:
    if obj.parent == rig and obj.parent_type in ("OBJECT", "ARMATURE"):
        # Does not depend on the depsgraph being up to date
        return np.array(obj.matrix_parent_inverse @ obj.matrix_basis)
    return np.array(rig.matrix_world.inverted() @ obj.matrix_world)


def _co(data: Any) -> np.ndarray:
    co = np.empty(len(data) * 3, dtype=np.float64)
    data.foreach_get("co", co)
    return co.reshape(-1, 3)


def _transformed(co: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    return co @ matrix[:3, :3].T + matrix[:3, 3]


def _base_data_co(cloth_obj: bpy.types.Object) -> np.ndarray:
    keys = cloth_obj.data.shape_keys
    return _co(keys.reference_key.data if keys else cloth_obj.data.vertices)


def _triangles(obj: bpy.types.Object) -> np.ndarray:
    mesh = obj.data
    mesh.calc_loop_triangles()
    tris = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
    mesh.loop_triangles.foreach_get("vertices", tris)
    return tris.reshape(-1, 3).astype(np.int64)


def weight_matrix(obj: bpy.types.Object, bones: list[str]) -> np.ndarray:
    """Read vertex groups of an object into a weight matrix.

    Args:
        obj: Mesh object.
        bones: Names of the vertex groups to read, one per column.

    Returns:
        Array (vertices, bones). Not normalised, missing groups stay zero.
    """
    column = {
        group.index: bones.index(group.name)
        for group in obj.vertex_groups
        if group.name in bones
    }
    weights = np.zeros((len(obj.data.vertices), len(bones)))
    for vertex in obj.data.vertices:
        for element in vertex.groups:
            if element.group in column:
                # Added up, a group can be listed more than once per vertex
                weights[vertex.index, column[element.group]] += element.weight
    return weights


def _group_values(obj: bpy.types.Object, name: str) -> Optional[np.ndarray]:
    group = obj.vertex_groups.get(name)
    if group is None:
        return None
    values = np.zeros(len(obj.data.vertices))
    for vertex in obj.data.vertices:
        for element in vertex.groups:
            if element.group == group.index:
                values[vertex.index] = element.weight
    return values


def _evaluated_co(
    obj: bpy.types.Object, context: bpy.types.Context, keep: tuple[str, ...]
) -> np.ndarray:
    """Local coordinates with shape keys and only the `keep` modifier types."""
    shown = {modifier.name: modifier.show_viewport for modifier in obj.modifiers}
    for modifier in obj.modifiers:
        modifier.show_viewport = modifier.show_viewport and modifier.type in keep
    try:
        evaluated = obj.evaluated_get(context.evaluated_depsgraph_get())
        co = _co(evaluated.to_mesh().vertices)
        evaluated.to_mesh_clear()
    finally:
        for modifier in obj.modifiers:
            modifier.show_viewport = shown[modifier.name]
    return co


def _preserves_volume(body_obj: bpy.types.Object) -> bool:
    for modifier in body_obj.modifiers:
        if modifier.type == "ARMATURE":
            return bool(modifier.use_deform_preserve_volume)
    return False
