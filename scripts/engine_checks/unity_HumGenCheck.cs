// Editor script: imports the exported FBX as a Humanoid and reports what the docs claim about Unity.
// Run: Unity -batchmode -nographics -projectPath <project> -executeMethod HumGenCheck.Run -quit
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static class HumGenCheck
{
    static readonly List<string> log = new List<string>();

    public static void Run()
    {
        Application.logMessageReceived += (msg, stack, type) => { if (type != LogType.Log) log.Add(type + ": " + msg); };
        var report = new Dictionary<string, object>();
        try
        {
            var fbxPath = Directory.GetFiles("Assets/HumGen", "*.fbx", SearchOption.AllDirectories).Where(p => !p.Contains("@")).First().Replace("\\", "/");
            report["fbx"] = fbxPath;
            AssetDatabase.ImportAsset(fbxPath, ImportAssetOptions.ForceSynchronousImport);
            var importer = AssetImporter.GetAtPath(fbxPath) as ModelImporter;
            importer.animationType = ModelImporterAnimationType.Human;
            importer.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
            importer.importBlendShapes = true;
            importer.SaveAndReimport();

            var go = AssetDatabase.LoadAssetAtPath<GameObject>(fbxPath);
            var animator = go.GetComponent<Animator>();
            var avatar = animator != null ? animator.avatar : null;
            report["avatar_valid"] = avatar != null && avatar.isValid;
            report["avatar_human"] = avatar != null && avatar.isHuman;
            var mapped = avatar != null ? avatar.humanDescription.human.Select(h => h.humanName).ToList() : new List<string>();
            var all = HumanTrait.BoneName.ToList();
            report["human_bones_mapped"] = mapped.Count;
            report["human_bones_total"] = all.Count;
            report["human_bones_unmapped"] = all.Where(b => !mapped.Contains(b)).ToList();
            report["lod_group"] = go.GetComponentInChildren<LODGroup>() != null;
            report["scale"] = go.transform.localScale.x;
            var bounds = new List<float>();
            foreach (var r in go.GetComponentsInChildren<SkinnedMeshRenderer>()) bounds.Add(r.bounds.size.y);
            report["height_m"] = bounds.Count > 0 ? bounds.Max() : 0f;

            var materials = new List<Dictionary<string, object>>();
            foreach (var r in go.GetComponentsInChildren<Renderer>())
            {
                foreach (var m in r.sharedMaterials)
                {
                    if (m == null) { materials.Add(new Dictionary<string, object> { { "renderer", r.name }, { "material", "null" } }); continue; }
                    var entry = new Dictionary<string, object> { { "renderer", r.name }, { "material", m.name }, { "shader", m.shader.name } };
                    entry["mainTexture"] = m.mainTexture != null ? m.mainTexture.name : null;
                    entry["normalMap"] = m.HasProperty("_BumpMap") && m.GetTexture("_BumpMap") != null ? m.GetTexture("_BumpMap").name : null;
                    entry["metallicGloss"] = m.HasProperty("_MetallicGlossMap") && m.GetTexture("_MetallicGlossMap") != null ? m.GetTexture("_MetallicGlossMap").name : null;
                    entry["renderMode"] = m.HasProperty("_Mode") ? m.GetFloat("_Mode") : -1f;
                    materials.Add(entry);
                }
                var smr = r as SkinnedMeshRenderer;
                if (smr != null && smr.sharedMesh != null && smr.sharedMesh.blendShapeCount > 0)
                    report["blend_shapes_" + r.name] = smr.sharedMesh.blendShapeCount;
            }
            report["materials"] = materials;

            var textures = new List<string>();
            foreach (var t in AssetDatabase.FindAssets("t:Texture", new[] { "Assets/HumGen" }))
            {
                var p = AssetDatabase.GUIDToAssetPath(t);
                var ti = AssetImporter.GetAtPath(p) as TextureImporter;
                textures.Add(Path.GetFileName(p) + " " + (ti != null ? ti.textureType.ToString() : "?"));
            }
            report["textures"] = textures;
            var clips = AssetDatabase.FindAssets("t:AnimationClip", new[] { "Assets/HumGen" }).Select(AssetDatabase.GUIDToAssetPath).ToList();
            report["clips"] = clips;
        }
        catch (Exception e)
        {
            report["exception"] = e.ToString();
        }
        report["log"] = log;
        File.WriteAllText("report.json", MiniJson(report));
        Debug.Log("REPORT WRITTEN");
        EditorApplication.Exit(0);
    }

    // Minimal JSON writer, enough for the report (JsonUtility can't do dictionaries)
    static string MiniJson(object o)
    {
        switch (o)
        {
            case null: return "null";
            case string s: return "\"" + s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n") + "\"";
            case bool b: return b ? "true" : "false";
            case float f: return f.ToString(System.Globalization.CultureInfo.InvariantCulture);
            case int i: return i.ToString();
            case Dictionary<string, object> d: return "{" + string.Join(",", d.Select(kv => MiniJson(kv.Key) + ":" + MiniJson(kv.Value))) + "}";
            case System.Collections.IEnumerable e: return "[" + string.Join(",", e.Cast<object>().Select(MiniJson)) + "]";
            default: return MiniJson(o.ToString());
        }
    }
}
