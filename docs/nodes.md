# ComfyUI-MeshTools Node Reference

## MeshTools Load

Load a 3D mesh from a file on disk. Supports GLB, OBJ, PLY, and other formats supported by trimesh.

**Inputs:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `mesh_path` | STRING | `""` | Path to the mesh file. Can be an absolute path or a filename in ComfyUI's input directory. |

**Outputs:**

| Output | Type | Description |
|---|---|---|
| `trimesh` | TRIMESH | The loaded 3D mesh object. |

---

## MeshTools Export

Export a mesh to a file in the ComfyUI output directory. Supports multiple 3D formats.

**Inputs:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `trimesh` | TRIMESH | - | The mesh to export. |
| `filename_prefix` | STRING | `"3D/Mesh"` | Output path prefix relative to ComfyUI's output directory. Subdirectories are created automatically. Files are numbered sequentially (e.g. `Mesh_00001_.glb`). |
| `file_format` | ENUM | - | Output format. **GLB** is recommended for web and game engines (binary, compact, includes materials). **OBJ** is widely supported for editing in Blender/Maya. **PLY** is good for point clouds and scans. **STL** is standard for 3D printing (no color/texture). **3MF** is a modern 3D printing format. **DAE** (Collada) is an interchange format. |
| `save_file` | BOOLEAN | `True` | When enabled, saves with a sequential number. When disabled, writes to a temporary file — useful for preview workflows where you don't want to accumulate output files. |

**Outputs:**

| Output | Type | Description |
|---|---|---|
| `mesh_path` | STRING | Relative path to the exported file within ComfyUI's output directory. |

---

## MeshTools UV Unwrap

Generate UV coordinates for a mesh using the xatlas library. This is required before applying textures — most generated meshes don't come with UV maps.

The algorithm automatically cuts the mesh into charts and lays them out in UV space. For meshes with over 500M faces, an error is raised.

**Inputs:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `trimesh` | TRIMESH | - | Mesh to unwrap. If the mesh already has UVs they will be replaced. |

**Outputs:**

| Output | Type | Description |
|---|---|---|
| `trimesh` | TRIMESH | The mesh with UV coordinates assigned. Vertex count may increase because xatlas splits vertices at UV seams. |

---

## MeshTools Postprocess

Clean up a generated mesh by removing artifacts and optionally reducing polygon count. Useful as a post-processing step after mesh generation.

**Inputs:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `trimesh` | TRIMESH | - | Input mesh to clean up. |
| `remove_floaters` | BOOLEAN | `True` | Remove small disconnected mesh fragments ("floaters") that float in space. Uses pymeshlab's connected component analysis — removes components smaller than 0.5% of total face count. |
| `remove_degenerate_faces` | BOOLEAN | `True` | Remove faces with zero area. These are common in generated meshes and can cause rendering artifacts, UV mapping issues, and problems in game engines. |
| `reduce_faces` | BOOLEAN | `True` | Reduce polygon count using quadric edge collapse decimation. This preserves overall shape while significantly reducing face count. Only active when the mesh has more faces than `max_facenum`. |
| `max_facenum` | INT | `40000` | Target maximum face count when `reduce_faces` is enabled. 40,000 faces is a good balance between detail and performance. For 3D printing, you may want more (100k+). For real-time/game use, fewer (10k-20k). |
| `smooth_normals` | BOOLEAN | `False` | Recalculate vertex normals using area-weighted averaging. This produces smoother shading but can soften intentionally hard edges. |

**Outputs:**

| Output | Type | Description |
|---|---|---|
| `trimesh` | TRIMESH | The cleaned-up mesh. |

---

## MeshTools Remesh (Instant-Meshes)

Completely retopologize a mesh using the Instant Meshes algorithm. This creates a clean, uniform quad/tri mesh from any input geometry.

**Warning:** This operation removes all vertex colors, textures, and UV coordinates. Use before texturing, not after.

**Inputs:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `trimesh` | TRIMESH | - | Input mesh. All vertex attributes except geometry will be stripped. |
| `merge_vertices` | BOOLEAN | `True` | Merge duplicate vertices before remeshing. Recommended — produces cleaner input for the algorithm. |
| `vertex_count` | INT | `10000` | Target number of vertices in the output mesh. The actual count may differ slightly. Higher values preserve more detail. |
| `smooth_iter` | INT | `8` | Number of Laplacian smoothing iterations applied during remeshing. Higher values produce smoother results but may lose fine detail and sharp edges. Set to 0 to disable. |
| `align_to_boundaries` | BOOLEAN | `True` | Align the new mesh edges to the original mesh boundaries. Produces cleaner results at mesh borders. |
| `triangulate_result` | BOOLEAN | `True` | Convert the output from quads to triangles. Most pipelines expect triangulated meshes. Disable if you want quad topology (e.g., for subdivision surface modeling). |
| `max_facenum` | INT | `40000` | If the remeshed result exceeds this face count, apply additional decimation. Acts as a safety cap. |

**Outputs:**

| Output | Type | Description |
|---|---|---|
| `trimesh` | TRIMESH | The retopologized mesh with clean, uniform faces. |

---

## MeshTools Decimate (Advanced)

Reduce mesh polygon count using the meshlib library with full control over decimation parameters. For most users, the **Simple Decimate** node is easier to use.

**Inputs:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `trimesh` | TRIMESH | - | Input mesh to decimate. |
| `subdivideParts` | INT | `16` | Number of parallel threads for decimation. Set to your CPU core count for best performance. |
| `target_face_num` | INT | - | Absolute target face count. Set either this **or** `target_face_ratio`, not both. |
| `target_face_ratio` | FLOAT | - | Target as a fraction of original faces. 0.5 = keep half the faces. Set either this **or** `target_face_num`. |
| `strategy` | ENUM | `"None"` | **None**: default meshlib strategy. **MinimizeError**: prioritize shape preservation (slower but better quality). **ShortestEdgeFirst**: collapse shortest edges first (faster, good for uniform meshes). |
| `maxError` | FLOAT | `0.0` | Maximum geometric error per decimation step. Lower values = more accurate shape preservation. 0.0 = unlimited. |
| `maxEdgeLen` | FLOAT | - | Maximum allowed edge length. Prevents creation of overly long, thin triangles. |
| `maxBdShift` | FLOAT | - | Maximum displacement of boundary vertices during decimation. Preserves mesh boundaries. |
| `maxTriangleAspectRatio` | FLOAT | - | Soft limit on triangle aspect ratio. Decimation steps that create thinner triangles are penalized. |
| `criticalTriAspectRatio` | FLOAT | - | Hard limit. Decimation steps that would exceed this ratio are rejected entirely. |
| `tinyEdgeLength` | FLOAT | - | Edges shorter than this are prioritized for collapse, regardless of other criteria. |
| `stabilizer` | FLOAT | - | Stabilization factor to prevent oscillation during vertex position optimization. |
| `angleWeightedDistToPlane` | BOOLEAN | - | Weight the error metric by face angles for more perceptually uniform results. |
| `optimizeVertexPos` | BOOLEAN | - | After each edge collapse, optimize the new vertex position for minimal error. Better quality but slower. |
| `collapseNearNotFlippable` | BOOLEAN | - | Allow collapsing edges near non-flippable boundaries. Can help with complex topology. |
| `touchNearBdEdges` | BOOLEAN | - | Allow decimation of edges near mesh boundaries. Disable to preserve boundary shape. |
| `maxAngleChange` | FLOAT | - | Maximum change in face normal angle per step (radians). Prevents drastic shape changes. |
| `decimateBetweenParts` | BOOLEAN | - | Allow decimation across part boundaries when using parallel processing. |
| `minFacesInPart` | INT | - | Minimum face count to maintain in each mesh part during parallel decimation. |

**Outputs:**

| Output | Type | Description |
|---|---|---|
| `trimesh` | TRIMESH | The decimated mesh. |

---

## MeshTools Simple Decimate

Reduce mesh polygon count with minimal configuration. Just set a target face count or ratio.

Uses the same meshlib engine as the Advanced Decimate node but with sensible defaults for all parameters.

**Inputs:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `trimesh` | TRIMESH | - | Input mesh to decimate. |
| `subdivideParts` | INT | `16` | Number of parallel threads. Set to your CPU core count. |
| `target_face_num` | INT | - | Target face count. Set either this **or** `target_face_ratio`. |
| `target_face_ratio` | FLOAT | - | Target as fraction of original (0.5 = half the faces). Set either this **or** `target_face_num`. |

**Outputs:**

| Output | Type | Description |
|---|---|---|
| `trimesh` | TRIMESH | The decimated mesh. |
