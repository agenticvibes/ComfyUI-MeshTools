# Copyright (c) 2025 agenticvibes
# Licensed under the MIT License — see LICENSE for full text

import os
import numpy as np
import trimesh as Trimesh
from pathlib import Path

import folder_paths


# ──────────────────────────────────────────────
# Utility: meshlib decimation
# ──────────────────────────────────────────────

def _meshlib_decimate(vertices, faces, settings):
    """Decimate a mesh using meshlib."""
    import meshlib.mrmeshnumpy as mrmeshnumpy
    import meshlib.mrmeshpy as mrmeshpy

    mesh = mrmeshnumpy.meshFromFacesVerts(faces, vertices)
    mesh.packOptimally()
    mrmeshpy.decimateMesh(mesh, settings)

    out_verts = mrmeshnumpy.getNumpyVerts(mesh)
    out_faces = mrmeshnumpy.getNumpyFaces(mesh.topology)

    result = Trimesh.Trimesh(vertices=out_verts, faces=out_faces)
    print(f"Decimated to {result.vertices.shape[0]} vertices and {result.faces.shape[0]} faces")
    return result


# ──────────────────────────────────────────────
# Utility: UV unwrap via xatlas
# ──────────────────────────────────────────────

def _uv_unwrap(mesh):
    """UV unwrap a mesh using xatlas."""
    import xatlas

    if isinstance(mesh, Trimesh.Scene):
        mesh = mesh.dump(concatenate=True)

    if len(mesh.faces) > 500_000_000:
        raise ValueError("Mesh has more than 500M faces, which is not supported.")

    vmapping, indices, uvs = xatlas.parametrize(mesh.vertices, mesh.faces)
    mesh.vertices = mesh.vertices[vmapping]
    mesh.faces = indices
    mesh.visual.uv = uvs
    return mesh


# ──────────────────────────────────────────────
# Utility: postprocessing (floaters, degenerate faces, face reduction)
# ──────────────────────────────────────────────

def _remove_floaters(mesh):
    """Remove small disconnected components using pymeshlab."""
    import pymeshlab
    import tempfile

    ms = pymeshlab.MeshSet()
    with tempfile.NamedTemporaryFile(suffix=".ply", delete=False) as f:
        mesh.export(f.name)
        ms.load_new_mesh(f.name)

    ms.apply_filter("compute_selection_by_small_disconnected_components_per_face", nbfaceratio=0.005)
    ms.apply_filter("compute_selection_transfer_face_to_vertex", inclusive=False)
    ms.apply_filter("meshing_remove_selected_vertices_and_faces")

    with tempfile.NamedTemporaryFile(suffix=".ply", delete=False) as f:
        ms.save_current_mesh(f.name)
        result = Trimesh.load(f.name, force="mesh")
    return result


def _remove_degenerate_faces(mesh):
    """Remove degenerate (zero-area) faces."""
    areas = mesh.area_faces
    valid = areas > 0
    mesh.update_faces(valid)
    mesh.remove_unreferenced_vertices()
    return mesh


def _reduce_faces(mesh, max_facenum):
    """Reduce face count using pymeshlab quadric edge collapse."""
    if mesh.faces.shape[0] <= max_facenum:
        return mesh

    import pymeshlab
    import tempfile

    ms = pymeshlab.MeshSet()
    with tempfile.NamedTemporaryFile(suffix=".ply", delete=False) as f:
        mesh.export(f.name)
        ms.load_new_mesh(f.name)

    ms.apply_filter(
        "meshing_decimation_quadric_edge_collapse",
        targetfacenum=max_facenum,
        qualitythr=1.0,
        preserveboundary=True,
        boundaryweight=3,
        preservenormal=True,
        preservetopology=True,
        autoclean=True,
    )

    with tempfile.NamedTemporaryFile(suffix=".ply", delete=False) as f:
        ms.save_current_mesh(f.name)
        result = Trimesh.load(f.name, force="mesh")
    return result


# ══════════════════════════════════════════════
# Node: Postprocess Mesh
# ══════════════════════════════════════════════

class MeshToolsPostprocess:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "trimesh": ("TRIMESH", {"tooltip": "Input 3D mesh to process"}),
                "remove_floaters": ("BOOLEAN", {"default": True, "tooltip": "Remove small disconnected mesh fragments that float in space"}),
                "remove_degenerate_faces": ("BOOLEAN", {"default": True, "tooltip": "Remove zero-area faces that can cause rendering artifacts"}),
                "reduce_faces": ("BOOLEAN", {"default": True, "tooltip": "Reduce polygon count using quadric edge collapse decimation"}),
                "max_facenum": ("INT", {"default": 40000, "min": 1, "max": 10000000, "step": 1, "tooltip": "Maximum number of faces after reduction. Only used when reduce_faces is enabled"}),
                "smooth_normals": ("BOOLEAN", {"default": False, "tooltip": "Recalculate vertex normals for smoother shading"}),
            },
        }

    RETURN_TYPES = ("TRIMESH",)
    RETURN_NAMES = ("trimesh",)
    FUNCTION = "process"
    CATEGORY = "MeshTools"
    DESCRIPTION = "Remove floaters, degenerate faces, and reduce polygon count."

    def process(self, trimesh, remove_floaters, remove_degenerate_faces, reduce_faces, max_facenum, smooth_normals):
        new_mesh = trimesh.copy()
        if remove_floaters:
            new_mesh = _remove_floaters(new_mesh)
            print(f"Removed floaters: {new_mesh.vertices.shape[0]} verts, {new_mesh.faces.shape[0]} faces")
        if remove_degenerate_faces:
            new_mesh = _remove_degenerate_faces(new_mesh)
            print(f"Removed degenerate faces: {new_mesh.vertices.shape[0]} verts, {new_mesh.faces.shape[0]} faces")
        if reduce_faces:
            new_mesh = _reduce_faces(new_mesh, max_facenum)
            print(f"Reduced faces: {new_mesh.vertices.shape[0]} verts, {new_mesh.faces.shape[0]} faces")
        if smooth_normals:
            new_mesh.vertex_normals = Trimesh.smoothing.get_vertices_normals(new_mesh)
        return (new_mesh,)


# ══════════════════════════════════════════════
# Node: Export Mesh
# ══════════════════════════════════════════════

class MeshToolsExport:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "trimesh": ("TRIMESH", {"tooltip": "3D mesh to export"}),
                "filename_prefix": ("STRING", {"default": "3D/Mesh", "tooltip": "Output path prefix relative to ComfyUI output directory"}),
                "file_format": (["glb", "obj", "ply", "stl", "3mf", "dae"], {"tooltip": "3D file format. GLB recommended for web/game use, OBJ for editing"}),
            },
            "optional": {
                "save_file": ("BOOLEAN", {"default": True, "tooltip": "When disabled, exports to a temporary file instead of a numbered output"}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("mesh_path",)
    FUNCTION = "process"
    CATEGORY = "MeshTools"
    DESCRIPTION = "Export a mesh to file in GLB, OBJ, PLY, STL, 3MF, or DAE format."
    OUTPUT_NODE = True

    def process(self, trimesh, filename_prefix, file_format, save_file=True):
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(
            filename_prefix, folder_paths.get_output_directory()
        )
        output_path = Path(full_output_folder, f"{filename}_{counter:05}_.{file_format}")
        output_path.parent.mkdir(exist_ok=True)
        if save_file:
            trimesh.export(output_path, file_type=file_format)
            relative_path = Path(subfolder) / f"{filename}_{counter:05}_.{file_format}"
        else:
            temp_file = Path(full_output_folder, f"meshtools_temp_.{file_format}")
            trimesh.export(temp_file, file_type=file_format)
            relative_path = Path(subfolder) / f"meshtools_temp_.{file_format}"
        return (str(relative_path),)


# ══════════════════════════════════════════════
# Node: UV Unwrap
# ══════════════════════════════════════════════

class MeshToolsUVWrap:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "trimesh": ("TRIMESH", {"tooltip": "3D mesh to UV unwrap. Required before texture painting"}),
            },
        }

    RETURN_TYPES = ("TRIMESH",)
    RETURN_NAMES = ("trimesh",)
    FUNCTION = "process"
    CATEGORY = "MeshTools"
    DESCRIPTION = "UV unwrap a mesh for texture application using xatlas."

    def process(self, trimesh):
        trimesh = _uv_unwrap(trimesh)
        return (trimesh,)


# ══════════════════════════════════════════════
# Node: Load Mesh
# ══════════════════════════════════════════════

class MeshToolsLoad:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "mesh_path": ("STRING", {"default": "", "tooltip": "Path to GLB/OBJ mesh file to load."}),
            },
        }

    RETURN_TYPES = ("TRIMESH",)
    RETURN_NAMES = ("trimesh",)
    FUNCTION = "load"
    CATEGORY = "MeshTools"
    DESCRIPTION = "Load a mesh from a GLB or OBJ file path."

    def load(self, mesh_path):
        if not os.path.exists(mesh_path):
            mesh_path = os.path.join(folder_paths.get_input_directory(), mesh_path)

        trimesh = Trimesh.load(mesh_path, force="mesh")
        return (trimesh,)


# ══════════════════════════════════════════════
# Node: Instant-Meshes Remesh
# ══════════════════════════════════════════════

class MeshToolsRemesh:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "trimesh": ("TRIMESH", {"tooltip": "Input mesh to remesh. Note: vertex colors and textures will be removed"}),
                "merge_vertices": ("BOOLEAN", {"default": True, "tooltip": "Merge duplicate vertices before remeshing for cleaner topology"}),
                "vertex_count": ("INT", {"default": 10000, "min": 100, "max": 10000000, "step": 1, "tooltip": "Target number of vertices in the remeshed output"}),
                "smooth_iter": ("INT", {"default": 8, "min": 0, "max": 100, "step": 1, "tooltip": "Number of Laplacian smoothing iterations. Higher = smoother but may lose detail"}),
                "align_to_boundaries": ("BOOLEAN", {"default": True, "tooltip": "Align remeshed edges to the original mesh boundaries"}),
                "triangulate_result": ("BOOLEAN", {"default": True, "tooltip": "Convert quad faces to triangles in the output"}),
                "max_facenum": ("INT", {"default": 40000, "min": 1, "max": 10000000, "step": 1, "tooltip": "Maximum face count after remeshing. Applies decimation if exceeded"}),
            },
        }

    RETURN_TYPES = ("TRIMESH",)
    RETURN_NAMES = ("trimesh",)
    FUNCTION = "remesh"
    CATEGORY = "MeshTools"
    DESCRIPTION = "Remesh using instant-meshes. Note: removes all vertex colors and textures."

    def remesh(self, trimesh, merge_vertices, vertex_count, smooth_iter, align_to_boundaries, triangulate_result, max_facenum):
        try:
            import pynanoinstantmeshes as PyNIM
        except ImportError:
            raise ImportError("pynanoinstantmeshes not found. Install with: pip install pynanoinstantmeshes")

        new_mesh = trimesh.copy()
        if merge_vertices:
            new_mesh.merge_vertices()

        new_verts, new_faces = PyNIM.remesh(
            np.array(new_mesh.vertices, dtype=np.float32),
            np.array(new_mesh.faces, dtype=np.uint32),
            vertex_count,
            align_to_boundaries=align_to_boundaries,
            smooth_iter=smooth_iter,
        )
        if new_verts.shape[0] - 1 != new_faces.max():
            raise ValueError("Instant-meshes failed to remesh the mesh")

        new_verts = new_verts.astype(np.float32)
        if triangulate_result:
            new_faces = Trimesh.geometry.triangulate_quads(new_faces)

        result = Trimesh.Trimesh(vertices=new_verts, faces=new_faces)
        if len(result.faces) > max_facenum:
            result = _reduce_faces(result, max_facenum)

        return (result,)


# ══════════════════════════════════════════════
# Node: Meshlib Decimate (Advanced)
# ══════════════════════════════════════════════

class MeshToolsDecimate:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "trimesh": ("TRIMESH", {"tooltip": "Input mesh to decimate"}),
                "subdivideParts": ("INT", {"default": 16, "min": 1, "max": 64, "step": 1, "tooltip": "Number of parallel threads for decimation. Match to your CPU core count"}),
            },
            "optional": {
                "target_face_num": ("INT", {"min": 0, "max": 10000000, "tooltip": "Absolute target face count. Set either this or target_face_ratio"}),
                "target_face_ratio": ("FLOAT", {"min": 0.000, "max": 0.999, "tooltip": "Target as fraction of original faces (0.5 = half). Set either this or target_face_num"}),
                "strategy": (["None", "MinimizeError", "ShortestEdgeFirst"], {"default": "None", "tooltip": "Decimation priority: MinimizeError preserves shape, ShortestEdgeFirst is faster"}),
                "maxError": ("FLOAT", {"min": 0.0, "max": 1.0, "tooltip": "Maximum geometric error allowed per decimation step. Lower = more accurate"}),
                "maxEdgeLen": ("FLOAT", {"tooltip": "Maximum allowed edge length after decimation"}),
                "maxBdShift": ("FLOAT", {"tooltip": "Maximum boundary vertex displacement during decimation"}),
                "maxTriangleAspectRatio": ("FLOAT", {"tooltip": "Reject decimations that create thin triangles above this ratio"}),
                "criticalTriAspectRatio": ("FLOAT", {"tooltip": "Hard limit on triangle aspect ratio — decimation steps that exceed this are rejected"}),
                "tinyEdgeLength": ("FLOAT", {"tooltip": "Edges shorter than this are prioritized for collapse"}),
                "stabilizer": ("FLOAT", {"tooltip": "Stabilization factor to prevent oscillation during optimization"}),
                "angleWeightedDistToPlane": ("BOOLEAN", {"tooltip": "Weight error metric by face angles for more perceptually uniform results"}),
                "optimizeVertexPos": ("BOOLEAN", {"tooltip": "Optimize vertex positions after each collapse for better shape preservation"}),
                "collapseNearNotFlippable": ("BOOLEAN", {"tooltip": "Allow collapsing edges near non-flippable boundaries"}),
                "touchNearBdEdges": ("BOOLEAN", {"tooltip": "Allow decimation of edges near mesh boundaries"}),
                "maxAngleChange": ("FLOAT", {"tooltip": "Maximum allowed change in face normal angle per step (radians)"}),
                "decimateBetweenParts": ("BOOLEAN", {"tooltip": "Allow decimation across part boundaries in multi-part meshes"}),
                "minFacesInPart": ("INT", {"tooltip": "Minimum faces to keep in each mesh part during parallel decimation"}),
            },
        }

    RETURN_TYPES = ("TRIMESH",)
    RETURN_NAMES = ("trimesh",)
    FUNCTION = "decimate"
    CATEGORY = "MeshTools"
    DESCRIPTION = "Advanced mesh decimation using meshlib with full control over decimation parameters."

    def decimate(self, trimesh, subdivideParts, target_face_num=0, target_face_ratio=0.0, strategy="None",
                 maxError=0.0, maxEdgeLen=0.0, maxBdShift=0.0, maxTriangleAspectRatio=0.0,
                 criticalTriAspectRatio=0.0, tinyEdgeLength=0.0, stabilizer=0.0,
                 angleWeightedDistToPlane=False, optimizeVertexPos=False,
                 collapseNearNotFlippable=False, touchNearBdEdges=False,
                 maxAngleChange=0.0, decimateBetweenParts=False, minFacesInPart=0):
        try:
            import meshlib.mrmeshpy as mrmeshpy
        except ImportError:
            raise ImportError("meshlib not found. Install with: pip install meshlib")

        if target_face_num == 0 and target_face_ratio == 0.0:
            raise ValueError("target_face_num or target_face_ratio must be set")

        current_faces_num = trimesh.faces.shape[0]
        print(f"Current faces: {current_faces_num}")

        settings = mrmeshpy.DecimateSettings()
        if target_face_num > 0:
            settings.maxDeletedFaces = current_faces_num - target_face_num
        elif target_face_ratio > 0.0:
            settings.maxDeletedFaces = current_faces_num - int(current_faces_num * target_face_ratio)

        if strategy == "MinimizeError":
            settings.strategy = mrmeshpy.DecimateStrategy.MinimizeError
        elif strategy == "ShortestEdgeFirst":
            settings.strategy = mrmeshpy.DecimateStrategy.ShortestEdgeFirst

        for attr, val, check in [
            ("maxError", maxError, lambda v: v > 0.0),
            ("maxEdgeLen", maxEdgeLen, lambda v: v > 0.0),
            ("maxBdShift", maxBdShift, lambda v: v > 0.0),
            ("maxTriangleAspectRatio", maxTriangleAspectRatio, lambda v: v > 0.0),
            ("criticalTriAspectRatio", criticalTriAspectRatio, lambda v: v > 0.0),
            ("tinyEdgeLength", tinyEdgeLength, lambda v: v > 0.0),
            ("stabilizer", stabilizer, lambda v: v > 0.0),
            ("maxAngleChange", maxAngleChange, lambda v: v > 0.0),
            ("minFacesInPart", minFacesInPart, lambda v: v > 0),
        ]:
            if check(val):
                setattr(settings, attr, val)

        for attr, val in [
            ("angleWeightedDistToPlane", angleWeightedDistToPlane),
            ("optimizeVertexPos", optimizeVertexPos),
            ("collapseNearNotFlippable", collapseNearNotFlippable),
            ("touchNearBdEdges", touchNearBdEdges),
            ("decimateBetweenParts", decimateBetweenParts),
        ]:
            if val:
                setattr(settings, attr, val)

        settings.packMesh = True
        settings.subdivideParts = subdivideParts

        return (_meshlib_decimate(trimesh.vertices, trimesh.faces, settings),)


# ══════════════════════════════════════════════
# Node: Simple Meshlib Decimate
# ══════════════════════════════════════════════

class MeshToolsSimpleDecimate:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "trimesh": ("TRIMESH", {"tooltip": "Input mesh to decimate"}),
                "subdivideParts": ("INT", {"default": 16, "min": 1, "max": 64, "step": 1, "tooltip": "Number of CPU cores to use"}),
            },
            "optional": {
                "target_face_num": ("INT", {"min": 0, "max": 10000000, "tooltip": "Target face count. Set either this or target_face_ratio"}),
                "target_face_ratio": ("FLOAT", {"min": 0.000, "max": 0.999, "tooltip": "Target as fraction of original (0.5 = half). Set either this or target_face_num"}),
            },
        }

    RETURN_TYPES = ("TRIMESH",)
    RETURN_NAMES = ("trimesh",)
    FUNCTION = "decimate"
    CATEGORY = "MeshTools"
    DESCRIPTION = "Simple mesh decimation using meshlib — just set target face count or ratio."

    def decimate(self, trimesh, subdivideParts, target_face_num=0, target_face_ratio=0.0):
        try:
            import meshlib.mrmeshpy as mrmeshpy
        except ImportError:
            raise ImportError("meshlib not found. Install with: pip install meshlib")

        if target_face_num == 0 and target_face_ratio == 0.0:
            raise ValueError("target_face_num or target_face_ratio must be set")

        current_faces_num = trimesh.faces.shape[0]
        print(f"Current faces: {current_faces_num}")

        settings = mrmeshpy.DecimateSettings()
        if target_face_num > 0:
            settings.maxDeletedFaces = current_faces_num - target_face_num
        elif target_face_ratio > 0.0:
            settings.maxDeletedFaces = current_faces_num - int(current_faces_num * target_face_ratio)

        settings.packMesh = True
        settings.subdivideParts = subdivideParts

        return (_meshlib_decimate(trimesh.vertices, trimesh.faces, settings),)


# ══════════════════════════════════════════════
# Registration
# ══════════════════════════════════════════════

NODE_CLASS_MAPPINGS = {
    "MeshToolsPostprocess": MeshToolsPostprocess,
    "MeshToolsExport": MeshToolsExport,
    "MeshToolsUVWrap": MeshToolsUVWrap,
    "MeshToolsLoad": MeshToolsLoad,
    "MeshToolsRemesh": MeshToolsRemesh,
    "MeshToolsDecimate": MeshToolsDecimate,
    "MeshToolsSimpleDecimate": MeshToolsSimpleDecimate,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MeshToolsPostprocess": "MeshTools Postprocess",
    "MeshToolsExport": "MeshTools Export Mesh",
    "MeshToolsUVWrap": "MeshTools UV Unwrap",
    "MeshToolsLoad": "MeshTools Load Mesh",
    "MeshToolsRemesh": "MeshTools Remesh (Instant-Meshes)",
    "MeshToolsDecimate": "MeshTools Decimate (Advanced)",
    "MeshToolsSimpleDecimate": "MeshTools Simple Decimate",
}
