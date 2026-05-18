"""Tool: VMD molecular structure rendering."""
import subprocess
from pathlib import Path
from motus.registry import registry


def render_system(args: dict) -> str:
    """Render system snapshot with VMD + Tachyon."""
    gro_file = args["gro_file"]
    output_dir = args.get("output_dir", str(Path(gro_file).parent / "analysis" / "figures"))
    style = args.get("style", "cpk")

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    rep = {"cpk": "CPK 0.6 0.3 10.0 8.0",
           "vdw": "VDW 1.0 20.0",
           "licorice": "Licorice 0.15 10.0 10.0"}.get(style, "CPK 0.6 0.3 10.0 8.0")

    tcl = f"""
mol new {gro_file} type gro
mol delrep 0 top
mol representation {rep}
mol color Name
mol selection {{all}}
mol addrep top
display projection Orthographic
display depthcue off
display shadows on
display ambientocclusion on
display aoambient 0.35
display aodirect 0.65
color Display Background white
axes location off
rotate x by 20; rotate y by 30; scale by 1.4
render TachyonInternal {output_dir}/system_snapshot.tga
quit
"""
    tcl_path = Path(output_dir) / "_render.tcl"
    tcl_path.write_text(tcl)

    try:
        r = subprocess.run(
            ["xvfb-run", "-a", "-s", "-screen 0 3840x2880x24",
             "vmd", "-dispdev", "opengl", "-e", str(tcl_path), "-size", "3840", "2880"],
            capture_output=True, text=True, timeout=180
        )
    except subprocess.TimeoutExpired:
        return "VMD render TIMED OUT"
    except FileNotFoundError:
        return "VMD or xvfb-run not found. Install: sudo apt-get install vmd xvfb"

    tga = Path(output_dir) / "system_snapshot.tga"
    if tga.exists():
        try:
            from PIL import Image
            img = Image.open(str(tga))
            png = str(tga).replace(".tga", ".png")
            img.save(png)
            tga.unlink()
            size_kb = Path(png).stat().st_size / 1024
            return f"✓ Rendered: {png} ({img.size[0]}x{img.size[1]}, {size_kb:.0f} KB)"
        except Exception:
            return f"TGA saved at {tga}, PNG conversion failed"
    return f"Render failed. VMD STDERR: {r.stderr[-500:]}"


registry.register(
    name="render_system",
    description="Generate a publication-quality molecular structure image using VMD ray-tracing (CPK ball-and-stick style).",
    parameters={
        "gro_file": {"type": "string", "description": "Path to .gro structure file"},
        "output_dir": {"type": "string", "description": "Directory to save the image"},
        "style": {"type": "string", "enum": ["cpk", "vdw", "licorice"],
                  "description": "Rendering style (cpk recommended for papers)"},
    },
    handler=render_system,
    emoji="🔬",
)
