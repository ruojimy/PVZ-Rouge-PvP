import random
for s in (0, 1, 7, 12345678901, -5):
    r = random.Random(s)
    out = ["seed %d:" % s]
    out += ["%.17g" % r.random() for _ in range(3)]
    out += [str(r.randint(1, 100)) for _ in range(5)]
    out += [str(r.randint(-50, 50)) for _ in range(3)]
    out.append(str(r.getrandbits(40)))
    out.append("%.17g" % r.uniform(-3.5, 9.25))
    out.append(str(r.randint(0, 1000000007)))
    print(" ".join(out))
for a, b in ((7, 2), (-7, 2), (7, -2), (7.5, 2), (-7.5, 0.5), (1e10, 3), (-0.0, 5), (5.3, 0.1), (-100.25, 48)):
    print("fd %.17g mod %.17g" % (float(a) // b, float(a) % b))
print("round %g %g %g %g" % (round(2.5), round(3.5), round(-2.5), round(2.4999)))
