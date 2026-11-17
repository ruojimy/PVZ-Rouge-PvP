"""Positional interpolation of guest and local slow-motion authority frames.

Never advances combat or mutates a received snapshot. Latest poses, health,
spawns and removals take effect immediately; positions catch up in <=50 ms.
"""
import time


def same_pose(before, after):
    """Compare only spatial discontinuities; health/resources/animation stay live.

    A repeated room observation is not a new interpolation endpoint. Native tick
    alone is insufficient: a command can teleport a player within the same tick.
    """
    if ((before.get('native_frame') or {}).get('positions',{}) !=
            (after.get('native_frame') or {}).get('positions',{})):
        return False
    old_players=before.get('players',{})
    players=after.get('players',{})
    if len(old_players)!=len(players):return False
    for side,player in players.items():
        old=old_players.get(side)
        if old is None:return False
        for key in ('x','y','teleport_ready_at','absent'):
            if old.get(key)!=player.get(key):return False
        if (old.get('hp',1)>0)!=(player.get('hp',1)>0):return False
    # Keep the published roster order: a different roster is a new visual state.
    return [(u.get('id'),u.get('x'),u.get('y'),u.get('hp',1)>0) for u in before.get('units',[])] == [(u.get('id'),u.get('x'),u.get('y'),u.get('hp',1)>0) for u in after.get('units',[])]


class GuestPresentation:
    def __init__(self, clock=time.monotonic):
        self.clock=clock
        self.clear()

    def clear(self):
        self.previous=None
        self.current=None
        self.received=0.
        self.duration=0.

    def accept(self, view):
        now=self.clock()
        old=self.current
        battle=view.get('battle') or {}
        prior=(old or {}).get('battle') or {}
        delta=battle.get('time',0)-prior.get('time',0)
        # The longer bridge is reserved for confirmed authority slow motion.
        # Normal network interpolation keeps its existing low-latency bounds.
        pressure=(view.get('pacing') or {}).get('slow',False)
        max_delta=.5 if pressure else .15
        max_gap=.65 if pressure else .2
        continuous=(old and view.get('phase')=='battle' and old.get('phase')=='battle'
                and not view.get('paused') and not old.get('paused')
                and not view.get('audit_error') and not view.get('disconnected')
                and not old.get('audit_error') and not old.get('disconnected')
                and view.get('terrain_hash')==old.get('terrain_hash')
                and view.get('match_id')==old.get('match_id')
                and view.get('match_number')==old.get('match_number')
                and view.get('loading_id')==old.get('loading_id')
                and view.get('mode')==old.get('mode')
                and battle.get('terrain_revision')==prior.get('terrain_revision')
                and battle.get('local_seat')==prior.get('local_seat'))
        if continuous and delta==0 and same_pose(prior,battle):
            # Replace the observation (including same-tick health and ACKs), but
            # retain the original interpolation endpoints and wall-clock origin.
            self.current=view
            return
        shown=self.sample(old) if old is not None else None
        self.previous=None
        self.duration=0.
        if continuous and 0 < delta <= max_delta and now-self.received <= max_gap:
            # An early snapshot interrupts an in-progress interpolation.
            # Continue from what was actually shown, not the last target.
            self.previous=shown
            self.duration=min(.12 if pressure else .05,delta)
        self.current=view
        self.received=now

    def sample(self, view):
        if view is not self.current or self.previous is None or self.duration<=0:
            return view
        alpha=min(1.,max(0.,(self.clock()-self.received)/self.duration))
        if alpha>=1.:return view
        latest=view['battle'];prior=self.previous['battle']
        terrain=view.get('map') or latest.get('map') or {}
        width=terrain.get('width',0);tile=terrain.get('tile_size',48)
        offsets={}

        def offset(before,after):
            dx=before[0]-after[0];dy=before[1]-after[1]
            if width:dx=(dx+width/2)%width-width/2
            # Teleports, respawns and large corrections must snap, never slide
            # through terrain. Ring seam crossings remain continuous.
            if abs(dx)>tile*2 or abs(dy)>tile*2:return (0.,0.)
            return (dx*(1-alpha),dy*(1-alpha))

        old_positions=(prior.get('native_frame') or {}).get('positions',{})
        prior_offsets=prior.get('_visual_offsets',{})
        for uid,position in (latest.get('native_frame') or {}).get('positions',{}).items():
            if uid in old_positions:
                old_position=old_positions[uid];dx,dy=prior_offsets.get(uid,(0.,0.))
                offsets[uid]=offset((old_position[0]+dx,old_position[1]+dy),position)
        battle=dict(latest)
        players={}
        for side,player in latest.get('players',{}).items():
            before=prior.get('players',{}).get(side)
            delta=(0.,0.)
            if (before and before.get('teleport_ready_at')==player.get('teleport_ready_at')
                    and before.get('hp',1)>0 and player.get('hp',1)>0):
                delta=offset((before['x'],before['y']),(player['x'],player['y']))
            # players[] uses the client's faction perspective, but recorded
            # draw entities retain the real seat ID. A second-seat guest must
            # not overwrite its mate's body offset with its own movement.
            real_side=side
            local_seat=latest.get('local_seat')
            if local_seat in ('plant2','zombie2'):
                faction=local_seat[:-1]
                if side==faction:real_side=local_seat
                elif side==local_seat:real_side=faction
            offsets['hero:'+real_side]=delta
            players[side]=dict(player,x=(player['x']+delta[0])%width if width else player['x']+delta[0],y=player['y']+delta[1])
        battle['players']=players
        # Health bars and target outlines track the same body as the native
        # composite (body, armor, head, shadow and owned primitives together).
        units=[]
        for unit in latest.get('units',[]):
            dx,dy=offsets.get(unit.get('id'),(0.,0.))
            units.append(dict(unit,x=(unit['x']+dx)%width if width else unit['x']+dx,y=unit['y']+dy))
        battle['units']=units
        battle['_visual_offsets']=offsets
        return dict(view,battle=battle)
