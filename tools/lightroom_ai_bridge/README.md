Copied unchanged from https://github.com/aslanoov/lightroom-ai-bridge (bridge/), MIT licence, (c) 2026 Mustafa Aslanov; see LICENSE.

- attention_check.py: per-region brightness/contrast/saturation of a render; does the subject win attention?
- measure_tilt.py: roll and keystone of a render, in degrees.
- find_plumb.py: roll from one isolated vertical structure.

Run with the repo venv: venv\Scripts\python tools\lightroom_ai_bridge\attention_check.py render.jpg --region subject:L,R,T,B
