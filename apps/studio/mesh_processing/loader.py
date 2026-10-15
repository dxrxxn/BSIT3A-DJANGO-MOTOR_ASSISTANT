from pathlib import Path
import trimesh

def load_mesh(path: str | Path) -> trimesh.Trimesh:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Mesh file not found: {path}")
    loaded = trimesh.load(str(path), force='mesh')
    if isinstance(loaded, trimesh.Scene):
        meshes = [g for g in loaded.geometry.values()
                  if isinstance(g, trimesh.Trimesh) and len(g.faces)]
        if not meshes:
            raise ValueError("Scene contains no triangle meshes.")
        loaded = trimesh.util.concatenate(meshes)
    if not isinstance(loaded, trimesh.Trimesh):
        raise ValueError(f"Could not interpret {path.name} as a triangle mesh.")
    if len(loaded.faces) == 0:
        raise ValueError(f"{path.name} loaded with zero faces.")
    return loaded
