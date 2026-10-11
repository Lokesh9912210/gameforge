"""Headless play-test. Run as:  python playtest_runner.py main.py

Runs the generated game with no window, presses keys on its behalf, and checks that
(1) it does not crash and (2) the screen actually reacts, i.e. the game is not stuck
on a menu or frozen. Prints one line:  PLAYTEST_RESULT {"ok": true|false, "reason": "..."}
"""
import asyncio
import hashlib
import json
import os
import runpy
import sys
import traceback

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame  # noqa: E402


class AllKeys:
    """Stand-in for pygame.key.get_pressed(): reports every key as pressed (or none)."""
    def __init__(self):
        self.on = False

    def __getitem__(self, _index):
        return self.on


KEYS = AllKeys()
pygame.key.get_pressed = lambda: KEYS

PRESS = [pygame.K_SPACE, pygame.K_RETURN, pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d,
         pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_f, pygame.K_j, pygame.K_k]


def report(ok, reason=""):
    print("PLAYTEST_RESULT " + json.dumps({"ok": ok, "reason": reason}), flush=True)
    os._exit(0)


def frame_hash():
    surf = pygame.display.get_surface()
    if surf is None:
        return None
    to_bytes = getattr(pygame.image, "tobytes", None) or pygame.image.tostring
    return hashlib.md5(to_bytes(surf, "RGB")).hexdigest()


def key_event(kind, key):
    return pygame.event.Event(kind, key=key, mod=0, unicode="", scancode=0)


real_run = asyncio.run


def fake_run(coro, *args, **kwargs):
    async def driver():
        loop = asyncio.get_running_loop()
        task = asyncio.ensure_future(coro)

        async def wait(seconds):
            end = loop.time() + seconds
            while loop.time() < end and not task.done():
                await asyncio.sleep(0.02)

        def check_finished():
            if task.done():
                exc = task.exception() if not task.cancelled() else None
                if exc:
                    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-1200:]
                    report(False, f"The game crashed while running:\n{tb}")
                report(False, "The game closed by itself right after starting.")

        await wait(1.0)
        check_finished()
        hashes = [frame_hash()]
        if hashes[0] is None:
            report(False, "The game never opened a display surface (pygame.display.set_mode was not called).")
        await wait(0.5)
        check_finished()
        hashes.append(frame_hash())

        KEYS.on = True
        for k in PRESS:
            pygame.event.post(key_event(pygame.KEYDOWN, k))
        await wait(0.8)
        check_finished()
        hashes.append(frame_hash())

        KEYS.on = False
        for k in PRESS:
            pygame.event.post(key_event(pygame.KEYUP, k))
        await wait(0.5)
        check_finished()
        hashes.append(frame_hash())

        if len(set(hashes)) == 1:
            report(False, "The screen never changes, even after pressing SPACE, ENTER, WASD, the arrow keys and F. "
                          "The game is probably stuck on a menu or title screen with no working start key, "
                          "or the main loop is frozen.")
        report(True)

    return real_run(driver())


asyncio.run = fake_run

if __name__ == "__main__":
    path = sys.argv[1]
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)))
    try:
        runpy.run_path(path, run_name="__main__")
    except SystemExit:
        report(False, "The game called exit() / sys.exit() while starting.")
    except BaseException:
        report(False, "Error while starting the game:\n" + traceback.format_exc()[-1200:])
    report(False, "The game never started its async main loop (asyncio.run(main()) was not reached).")
