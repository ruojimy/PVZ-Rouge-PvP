# live PvP71 region zombie_body_index
if x not in 同竖尸:
    同竖尸[x] = [y, y - 1]
else:
    同竖尸[x].append(y - 1)
    同竖尸[x].append(y)
if y not in 同横尸:
    同横尸[y] = [x]
else:
    同横尸[y].append(x)
if y - 1 not in 同横尸:
    同横尸[y - 1] = [x]
else:
    同横尸[y - 1].append(x)
