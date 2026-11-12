# live PvP71 region shovel
if event.button == 3:
    z = 哪个无南瓜植物(sby, sbx)
else:
    z = 哪个植物(sby, sbx)
if z != -1:
    植物[z]['死'] = 0
    植物[z]['铲死'] = 0
