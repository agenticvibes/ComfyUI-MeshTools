# ComfyUI-MeshTools

Generic mesh manipulation nodes for ComfyUI. Works with any 3D mesh — not tied to any specific generation pipeline.

## Nodes

| Node | Description |
|---|---|
| **MeshTools Load** | Load a mesh from GLB/OBJ file |
| **MeshTools Export** | Export mesh to GLB, OBJ, PLY, STL, 3MF, or DAE |
| **MeshTools UV Unwrap** | UV unwrap using xatlas |
| **MeshTools Postprocess** | Remove floaters, degenerate faces, reduce polygon count |
| **MeshTools Remesh** | Remesh using instant-meshes |
| **MeshTools Decimate** | Advanced meshlib decimation with full parameter control |
| **MeshTools Simple Decimate** | Simple face count reduction via meshlib |

## Installation

Clone or copy into `ComfyUI/custom_nodes/`:

```
ComfyUI/custom_nodes/ComfyUI-MeshTools/
```

Install dependencies:

```bash
pip install -r requirements.txt
```

**No model downloads required.**

## Dependencies

- `trimesh` — mesh loading/export
- `xatlas` — UV unwrapping
- `meshlib` — mesh decimation
- `pymeshlab` — floater removal, face reduction
- `pynanoinstantmeshes` — remeshing (optional, only for Remesh node)

## License

MIT — see [LICENSE](LICENSE).
