extends SceneTree
# Loads the exported character and reports what the docs claim about Godot.

func _init():
	var report := {}
	var path := "res://Jake.glb"
	var scene = load(path)
	if scene == null:
		report["error"] = "could not load " + path
		_finish(report)
		return
	var root = scene.instantiate()
	# Skeleton
	var skel: Skeleton3D = _find(root, "Skeleton3D")
	var bones := []
	if skel:
		for i in skel.get_bone_count():
			bones.append(skel.get_bone_name(i))
	report["bone_count"] = bones.size()
	report["bones"] = bones
	# Humanoid profile: which profile bones have an exactly matching skeleton bone
	var profile := SkeletonProfileHumanoid.new()
	var matched := []
	var missing := []
	for i in profile.get_bone_size():
		var name := profile.get_bone_name(i)
		if name in bones:
			matched.append(name)
		else:
			missing.append(name)
	report["profile_bones_matched"] = matched.size()
	report["profile_bones_total"] = profile.get_bone_size()
	report["profile_bones_missing"] = missing
	report["skeleton_bones_outside_profile"] = bones.filter(func(b): return not (b in matched))
	# Meshes and materials
	var meshes := []
	for node in _find_all(root, "MeshInstance3D"):
		var mi: MeshInstance3D = node
		var entry := {"name": mi.name, "surfaces": [], "blend_shapes": mi.get_blend_shape_count()}
		for s in mi.mesh.get_surface_count():
			var mat = mi.mesh.surface_get_material(s)
			if mat == null:
				mat = mi.get_surface_override_material(s)
			var m := {"material": mat.resource_name if mat else "none"}
			if mat is BaseMaterial3D:
				m["transparency"] = ["DISABLED", "ALPHA", "ALPHA_SCISSOR", "ALPHA_HASH", "ALPHA_DEPTH_PRE_PASS"][mat.transparency]
				m["cull_mode"] = ["BACK", "FRONT", "DISABLED"][mat.cull_mode]
				m["albedo_texture"] = mat.albedo_texture != null
				m["normal_texture"] = mat.normal_texture != null
				m["metallic_texture"] = mat.metallic_texture != null
				m["roughness_texture"] = mat.roughness_texture != null
			entry["surfaces"].append(m)
		meshes.append(entry)
	report["meshes"] = meshes
	report["animation_players"] = _find_all(root, "AnimationPlayer").size()
	_finish(report)

func _find(node: Node, cls: String) -> Node:
	if node.get_class() == cls:
		return node
	for c in node.get_children():
		var r = _find(c, cls)
		if r:
			return r
	return null

func _find_all(node: Node, cls: String, out: Array = []) -> Array:
	if node.get_class() == cls:
		out.append(node)
	for c in node.get_children():
		_find_all(c, cls, out)
	return out

func _finish(report: Dictionary):
	var f := FileAccess.open("res://report.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(report, "  "))
	f.close()
	print("REPORT WRITTEN")
	quit()
