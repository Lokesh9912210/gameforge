"""Checks that the automatic play-tester accepts good games and rejects broken ones.
Run:  python tests/check_playtest.py"""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from forge import checker
S = Path(__file__).resolve().parent.parent / "forge" / "samples"
cases = {
 "fixed sample (should PASS)": (S/"neon_duel_fixed.py").read_text(),
 "stuck-menu sample (should FAIL: stuck)": (S/"neon_duel_stuck.py").read_text(),
 "crash at start (should FAIL: crash)": "import asyncio, pygame\nasync def main():\n    pygame.init()\n    screen = pygame.display.set_mode((800,600))\n    while True:\n        x = 1/0\n        await asyncio.sleep(0)\nasyncio.run(main())\n",
 "no asyncio.sleep (should FAIL: static)": "import pygame\nprint('hi')\nasyncio.run(main())\n",
 "syntax error (should FAIL: syntax)": "def main(:\n  pass\n",
 "SysFont (should FAIL: browser-unsafe)": "import asyncio, pygame\nf = pygame.font.SysFont('arial', 20)\nasync def main():\n    await asyncio.sleep(0)\nasyncio.run(main())\n",
 "frozen static screen (should FAIL: frozen)": "import asyncio, pygame\nasync def main():\n    pygame.init()\n    s = pygame.display.set_mode((800,600))\n    s.fill((10,10,10))\n    while True:\n        pygame.display.flip()\n        await asyncio.sleep(0)\nasyncio.run(main())\n",
 "starts immediately, keys move square (should PASS)": "import asyncio, pygame\nasync def main():\n    pygame.init()\n    s = pygame.display.set_mode((800,600))\n    c = pygame.time.Clock(); x = 100\n    while True:\n        for e in pygame.event.get():\n            if e.type == pygame.QUIT: return\n        k = pygame.key.get_pressed()\n        if k[pygame.K_RIGHT]: x += 5\n        s.fill((0,0,0)); pygame.draw.rect(s,(255,0,0),(x,300,30,30))\n        pygame.display.flip(); c.tick(60)\n        await asyncio.sleep(0)\nasyncio.run(main())\n",
}
for name, code in cases.items():
    d = Path(tempfile.mkdtemp())
    r = checker.check_game(d, code)
    print(("PASS" if r is None else "FAIL"), "|", name, "|", (r or "").splitlines()[0][:110] if r else "")
