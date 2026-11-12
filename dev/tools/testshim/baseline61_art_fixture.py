"""PvP61 pixel art: two lightning reeds (24 px plant canvas), scarecrow and crow.

Drawn from integer primitives only, so authority, clients and card icons hold
identical pixels without shipping image files. Zombie-side units use a 32 px
canvas that the atlas scales to the two-tile zombie cell, feet on the bottom.
"""

PLANT_NAMES = ('闪电芦苇', '超载芦苇')
ZOMBIE_NAMES = ('稻草人', '乌鸦')
NAMES = PLANT_NAMES + ZOMBIE_NAMES
ASSETS = NAMES + tuple(n + '-帧' + str(i) for n in NAMES for i in range(4))

_REED = {
    '闪电芦苇': dict(stem=((28, 66, 34), (70, 140, 58), (138, 196, 92)),
                 head=((40, 52, 96), (88, 128, 214), (196, 228, 255)), spark=(255, 240, 120)),
    '超载芦苇': dict(stem=((48, 36, 66), (104, 74, 128), (170, 136, 196)),
                 head=((86, 20, 40), (196, 58, 92), (255, 196, 214)), spark=(255, 140, 220)),
}


def _reed(pg, name, frame):
    canvas = pg.Surface((24, 24), pg.SRCALPHA)
    draw = pg.draw
    p = _REED[name]
    dark, mid, light = p['stem']
    # Three reed blades from a shared clump; the tallest carries the head.
    draw.polygon(canvas, dark, [(9, 23), (7, 14), (5, 9), (8, 13), (11, 23)])
    draw.polygon(canvas, dark, [(14, 23), (17, 15), (21, 11), (18, 16), (16, 23)])
    draw.line(canvas, mid, (8, 22), (6, 11), 1)
    draw.line(canvas, mid, (15, 22), (19, 13), 1)
    draw.rect(canvas, dark, (10, 8, 4, 16))
    draw.rect(canvas, mid, (11, 8, 2, 16))
    draw.line(canvas, light, (11, 10), (11, 21), 1)
    draw.ellipse(canvas, dark, (6, 20, 12, 4))
    # Cattail-like head, pointing right (the facing direction).
    hd, hm, hl = p['head']
    draw.ellipse(canvas, hd, (8, 1, 13, 9))
    draw.ellipse(canvas, hm, (9, 2, 11, 7))
    draw.line(canvas, hl, (11, 3), (17, 3), 1)
    draw.rect(canvas, hd, (20, 4, 3, 3))
    pulse = (0, 1, 2, 1)[frame]
    draw.rect(canvas, p['spark'], (21, 4, 2, 2))
    if pulse:
        # A small zigzag discharge at the tip; it flickers with the frame.
        draw.lines(canvas, p['spark'], False, [(22, 5), (23, 3 - pulse // 2), (21, 1 + pulse // 2)], 1)
        canvas.set_at((23, 6), hl)
    eye = (255, 255, 255)
    draw.rect(canvas, eye, (15, 4, 2, 2))
    canvas.set_at((16, 5), (20, 20, 40))
    if name == '超载芦苇':
        # Coil bands mark the overloaded variant.
        for x in (11, 14):
            draw.line(canvas, (255, 214, 90), (x, 2), (x, 8), 1)
    return canvas


def _scarecrow(pg, frame):
    canvas = pg.Surface((32, 32), pg.SRCALPHA)
    draw = pg.draw
    wood, wood_dark = (140, 98, 56), (88, 58, 30)
    straw, straw_dark = (236, 200, 96), (184, 140, 52)
    cloth, cloth_dark = (78, 110, 160), (48, 70, 110)
    sack, sack_dark = (214, 186, 136), (150, 122, 80)
    if frame == 3:
        # Fallen over: the whole figure lies along the ground line.
        draw.rect(canvas, wood_dark, (2, 27, 26, 3))
        draw.rect(canvas, wood, (3, 28, 24, 1))
        draw.ellipse(canvas, sack_dark, (22, 22, 9, 8))
        draw.ellipse(canvas, sack, (23, 23, 7, 6))
        draw.rect(canvas, cloth_dark, (8, 23, 12, 6))
        draw.rect(canvas, cloth, (9, 24, 10, 4))
        for x in (5, 7, 20):
            draw.line(canvas, straw, (x, 26), (x - 2, 23), 1)
        return canvas
    arm = (0, -2, 0, 2)[frame]
    # Pole, from the ground up through the body.
    draw.rect(canvas, wood_dark, (15, 12, 3, 20))
    draw.rect(canvas, wood, (16, 12, 1, 20))
    # Cross bar with straw cuffs (arms bob between frames).
    draw.line(canvas, wood_dark, (4, 15 + arm), (28, 15 - arm), 3)
    draw.line(canvas, wood, (4, 14 + arm), (28, 14 - arm), 1)
    for x, y in ((3, 15 + arm), (29, 15 - arm)):
        draw.line(canvas, straw, (x, y), (x - 1 if x < 16 else x + 1, y + 3), 1)
        draw.line(canvas, straw_dark, (x, y), (x, y + 3), 1)
    # Patched shirt.
    draw.polygon(canvas, cloth_dark, [(10, 13), (23, 13), (24, 24), (9, 24)])
    draw.polygon(canvas, cloth, [(11, 14), (22, 14), (23, 23), (10, 23)])
    draw.rect(canvas, (176, 64, 52), (12, 17, 3, 3))
    draw.rect(canvas, (226, 200, 120), (19, 19, 2, 2))
    for x in (10, 13, 20, 23):
        draw.line(canvas, straw, (x, 24), (x + (1 if x > 16 else -1), 27), 1)
    # Burlap sack head with a stitched smile.
    draw.ellipse(canvas, sack_dark, (10, 3, 13, 11))
    draw.ellipse(canvas, sack, (11, 4, 11, 9))
    draw.rect(canvas, (40, 30, 24), (13, 7, 2, 2))
    draw.rect(canvas, (40, 30, 24), (18, 7, 2, 2))
    draw.lines(canvas, (90, 60, 40), False, [(13, 10), (15, 11), (18, 11), (20, 10)], 1)
    # Straw hat.
    draw.rect(canvas, straw_dark, (7, 4, 19, 2))
    draw.rect(canvas, straw, (11, 0, 11, 4))
    draw.rect(canvas, (176, 64, 52), (11, 3, 11, 1))
    return canvas


def _crow(pg, frame):
    canvas = pg.Surface((32, 32), pg.SRCALPHA)
    draw = pg.draw
    black, feather, sheen = (22, 20, 30), (48, 46, 64), (98, 104, 140)
    beak, beak_dark = (238, 180, 52), (170, 116, 26)
    if frame == 3:
        draw.ellipse(canvas, black, (6, 22, 20, 8))
        draw.ellipse(canvas, feather, (8, 23, 15, 5))
        draw.polygon(canvas, black, [(4, 26), (10, 20), (12, 26)])
        draw.polygon(canvas, beak, [(25, 25), (30, 26), (25, 27)])
        draw.line(canvas, (230, 230, 230), (20, 24), (22, 26), 1)
        draw.line(canvas, (230, 230, 230), (22, 24), (20, 26), 1)
        return canvas
    # Wings: up, level, down and level again across the flap cycle.
    wing = (-8, 0, 7, 0)[frame]
    draw.polygon(canvas, black, [(9, 16), (16, 15), (12, 8 + wing), (3, 10 + wing)])
    draw.polygon(canvas, feather, [(10, 15), (15, 15), (11, 9 + wing), (5, 11 + wing)])
    for n in range(3):
        draw.line(canvas, sheen, (5 + n * 3, 11 + wing), (10 + n * 2, 15), 1)
    # Body and tail.
    draw.ellipse(canvas, black, (8, 13, 17, 11))
    draw.ellipse(canvas, feather, (10, 14, 13, 8))
    draw.polygon(canvas, black, [(9, 18), (1, 22), (3, 17), (9, 15)])
    draw.line(canvas, sheen, (12, 16), (20, 16), 1)
    # Head, beak and a red eye, facing right.
    draw.ellipse(canvas, black, (20, 9, 9, 9))
    draw.polygon(canvas, beak_dark, [(27, 12), (32, 14), (27, 16)])
    draw.polygon(canvas, beak, [(27, 12), (31, 13), (27, 14)])
    draw.rect(canvas, (210, 40, 40), (24, 11, 2, 2))
    canvas.set_at((25, 11), (255, 220, 220))
    # Legs hang below the body.
    draw.line(canvas, beak_dark, (15, 24), (14, 28), 1)
    draw.line(canvas, beak_dark, (18, 24), (19, 28), 1)
    # The near wing is drawn over the body.
    draw.polygon(canvas, black, [(13, 17), (22, 16), (17, 11 - wing // 2), (9, 12 - wing // 2)])
    draw.polygon(canvas, feather, [(14, 16), (20, 16), (16, 12 - wing // 2), (11, 13 - wing // 2)])
    return canvas


def artwork(pg, name):
    if name not in ASSETS:
        return None
    root = name.split('-')[0]
    frame = int(name[-1]) if '-帧' in name else 0
    if root in PLANT_NAMES:
        return _reed(pg, root, frame)
    if root == '稻草人':
        return _scarecrow(pg, frame)
    return _crow(pg, frame)
