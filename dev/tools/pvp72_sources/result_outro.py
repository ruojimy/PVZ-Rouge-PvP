"""PvP64 end-of-match outro, presentation only.

When a match ends (a surrender or a hero's death) the authority has already
stopped advancing the world, so the last frame is the frozen battlefield.
Before the original black curtains (result_animation) this shows that frozen
field: the camera glides to the losing hero, the hero topples over (unless the
native knockdown already shows him lying), and the view holds for a moment.
Nothing here touches battle state; the curtains then start from this picture.
"""
import math
import time

PAN = 1.0
FALL = .9
HOLD = .7
DURATION = PAN+FALL+HOLD


def _ease(t):
    t = max(0., min(1., t))
    return t*t*(3-2*t)


def losing_side(result, local=None):
    winner = result.get('winner') if isinstance(result, dict) else result
    if winner == 'plant':
        return 'zombie'
    if winner == 'zombie':
        return 'plant'
    return local if local in ('plant', 'zombie') else 'plant'


def wrap_toward(start, end, width):
    if not width:
        return end
    return start+((end-start+width/2.) % width-width/2.)


class ResultOutro:
    def __init__(self):
        self.started = None
        self.loser = None
        self.start_point = None
        self.end_point = None
        self.already_down = False
        self.battle = None

    @property
    def active(self):
        return self.started is not None

    def start(self, view, local_side=None, now=None):
        battle = view.get('battle') or {}
        players = battle.get('players') or {}
        result = battle.get('result') or view.get('result')
        terrain = battle.get('map') or view.get('map') or {}
        self.loser = losing_side(result, local_side)
        coop_victory = view.get('mode') == 'coop' and isinstance(result, dict) and result.get('winner') == 'plant'
        # Co-op has no zombie Dave: hold/pan on a survivor, never topple the winner.
        if coop_victory:
            self.loser = local_side if local_side in players else 'plant'
        hero = players.get(self.loser)
        viewer = players.get(local_side) or players.get('plant') or hero
        if not hero or not viewer:
            self.started = None
            return False
        width = terrain.get('width', 0)
        tile = terrain.get('tile_size', 48)
        self.start_point = (viewer['x'], viewer['y'])
        self.end_point = (wrap_toward(viewer['x'], hero['x'], width), hero['y']-tile*.5)
        pose = hero.get('native_pose') or {}
        self.already_down = coop_victory or bool(pose.get('玩家倒地', 0))
        self.facing = 1 if hero.get('facing', 1) >= 0 else -1
        self.battle = battle
        self.started = time.monotonic() if now is None else float(now)
        return True

    def skip(self):
        self.started = None
        self.battle = None

    def progress(self, now=None):
        now = time.monotonic() if now is None else float(now)
        return max(0., now-self.started)

    def camera(self, elapsed):
        t = _ease(elapsed/PAN)
        (x0, y0), (x1, y1) = self.start_point, self.end_point
        return (x0+(x1-x0)*t, y0+(y1-y0)*t)

    def fall_angle(self, elapsed):
        if self.already_down:
            return 0.
        t = max(0., min(1., (elapsed-PAN)/FALL))
        # Accelerating topple, a small bounce at the end.
        angle = 90.*t*t
        if t >= 1.:
            angle = 90.
        return -self.facing*angle

    def draw(self, renderer, state, view, now=None):
        """Render one outro frame; False once it has finished."""
        if self.started is None:
            return False
        elapsed = self.progress(now)
        if elapsed >= DURATION:
            self.skip()
            return False
        from .world_view import WorldView
        screen = renderer.screen
        width, height = screen.get_size()
        if not hasattr(renderer, 'world'):
            renderer.world = WorldView(renderer.pg, renderer.bridge, renderer.asset_dir)
        world = renderer.world
        battle = self.battle or view.get('battle') or {}
        terrain = battle.get('map') or view.get('map')
        settings = dict(state, outro_camera=self.camera(elapsed),
                        outro_hide='hero:'+self.loser if not self.already_down else None)
        renderer.camera = world.render(screen, battle, (0, 0, width, height), self.loser, settings, terrain=terrain)
        if not self.already_down:
            world.draw_fallen_hero(screen, battle, 'hero:'+self.loser, self.fall_angle(elapsed))
        # Darken slightly as the hold ends, leading into the curtains.
        fade = max(0., min(1., (elapsed-PAN-FALL)/HOLD))
        if fade > 0:
            shade = renderer.pg.Surface((width, height), renderer.pg.SRCALPHA)
            shade.fill((0, 0, 0, int(90*fade)))
            screen.blit(shade, (0, 0))
        return True
