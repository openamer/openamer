import sys, io
sys.path.insert(0, r"C:\Users\damir\openamer-repo")
from rich.console import Console
from openamer_cli.banner import build_welcome_banner
buf = io.StringIO()
c = Console(file=buf, width=180, force_terminal=True, color_system="truecolor", legacy_windows=False)
build_welcome_banner(c, model="deepseek-v4.1-flash", cwd=r"C:\Users\damir", provider="openrouter")
out = buf.getvalue()
open(r"C:\Users\damir\openamer-repo\_banner_render.txt", "w", encoding="utf-8").write(out)
print("OK lines:", out.count("\n"))
