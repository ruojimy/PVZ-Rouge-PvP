"""PvP75: carry the owned Python catalog changes into the typed cold catalog.

cold_catalog_data.cpp has reviewed hand repairs since 74.x (stone cost, defense
lines, secret text). A whole regeneration would drop them, so this tool only:
  * replaces the listed fields of existing cards with the Python values;
  * appends complete blocks for the new PvP75 cards (plus typed-only extras);
  * updates the cost / cooldown tables and the reserve count.
`--check` fails when the file differs from what the tool would write.
"""
import argparse
import importlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/typed72'))
KERNEL = ROOT / 'build/typed72-integrated-v44/source/src/sim/typed'
DATA = KERNEL / 'cold_catalog_data.cpp'
FIELDS = KERNEL / 'cold_card_fields.h'
NEW = ['plant:巴豆', 'plant:激光豆', 'zombie:盾卫僵尸', 'zombie:克苏鲁之仆', 'secret:聚能', 'zsecret:守卫']  # PvP76: two secrets
# Typed-only numbers that the V catalog never carried (see 74.4 defense lines).
EXTRA = {'zombie:盾卫僵尸': ['c.defense.set(6.);']}
PATCH_FIELDS = ('cost', 'cooldown', 'hp', 'description', 'native_description', 'allow_air')
PATCH_CARDS = ['plant:杨桃', 'plant:三叶草', 'plant:玉米加农炮', 'zombie:小鬼僵尸', 'zombie:黑普通僵尸',
               'zombie:海豚僵尸', 'zombie:撑杆跳僵尸', 'zombie:雪橇车小队', 'secret:大帝',
               'zombie:投篮车僵尸', 'zombie:小鬼炮', 'zsecret:补贴', 'zsecret:海陆空',
               'zombie:路灯花僵尸', 'zombie:三叶草僵尸', 'zombie:潜水僵尸', 'zombie:雪橇车小队僵尸']  # PvP76 balance
# PvP76: per-card native health fields (雪橇车小队 30 per member); other cards keep their reviewed cold values.
PATCH_EXTRA = {'zombie:雪橇车小队': ('native_hp', 'native_izombie_hp', 'native_hard_hp'),
               'zombie:雪橇车小队僵尸': ('native_hp', 'native_izombie_hp', 'native_hard_hp')}


def load():
    import proxy_reference
    proxy_reference.load()
    return importlib.import_module(proxy_reference.PACKAGE + '.catalog'), importlib.import_module(proxy_reference.PACKAGE + '.balance')


def cpp(value):
    if isinstance(value, str): return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool): return 'true' if value else 'false'
    if isinstance(value, (int, float)): return repr(float(value))
    if isinstance(value, (list, tuple)): return '{' + ','.join(cpp(v) for v in value) + '}'
    raise TypeError(type(value).__name__)


def groups():
    text = FIELDS.read_text(encoding='utf8')
    out = {}
    for name, body in re.findall(r'#define PVZ72_COLD_(\w+)\(X\) (.*)', text):
        out[name] = re.findall(r'X\((\w+)\)', body)
    required = set(out['REQUIRED_STRINGS'] + out['REQUIRED_NUMBERS'] + out['REQUIRED_FLAGS'])
    known = required | set(f for k, v in out.items() if k.startswith('OPTIONAL') for f in v) | {'slow', 'targets', 'native_secret_names'}
    return required, known


def line(name, value, required):
    if value is None: return 'c.' + name + '.set_null();'
    if name in required: return 'c.' + name + '=' + cpp(value) + ';'
    if name == 'slow': return 'c.slow.set(ColdNumber{' + cpp(value) + '});'
    return 'c.' + name + '.set(' + cpp(value) + ');'


def block(card, required, known):
    rows = ['{ ColdCard c;']
    for name in sorted(card):
        if name not in known: raise SystemExit('Field without typed slot: %s.%s' % (card['id'], name))
        rows.append(line(name, card[name], required))
    rows += EXTRA.get(card['id'], [])
    rows.append('d.cards.push_back(std::move(c)); }')
    return '\n'.join(rows)


def render(text, catalog, balance):
    required, known = groups()
    blocks = re.split(r'(?m)^(?=\{ ColdCard c;$)', text)
    head, cards, tail = blocks[0], blocks[1:-1], blocks[-1]
    last, rest = blocks[-1].split('d.cards.push_back(std::move(c)); }\n', 1)
    cards.append(last + 'd.cards.push_back(std::move(c)); }\n')
    ids = [re.search(r'^c\.id="([^"]*)";$', b, re.M).group(1) for b in cards]
    for key in PATCH_CARDS:
        i = ids.index(key)
        b = cards[i]
        for name in PATCH_FIELDS + PATCH_EXTRA.get(key, ()):
            if name not in catalog.CARDS[key]: continue
            new = line(name, catalog.CARDS[key][name], required)
            pattern = re.compile(r'^c\.' + name + r'(=.*|\.set\(.*\)|\.set_null\(\));$', re.M)
            if pattern.search(b): b = pattern.sub(lambda m: new, b, count=1)
            else: b = b.replace('d.cards.push_back(std::move(c)); }', new + '\nd.cards.push_back(std::move(c)); }')
        cards[i] = b
    for key in NEW:
        new = block(catalog.CARDS[key], required, known) + '\n'
        if key in ids: cards[ids.index(key)] = new
        else: cards.append(new); ids.append(key)
    head = re.sub(r'd\.cards\.reserve\(\d+\);', 'd.cards.reserve(%d);' % len(cards), head)
    tables = {'costs': balance_table(catalog, 'COSTS'), 'zombie_cooldowns': balance_table(catalog, 'ZOMBIE_COOLDOWNS'),
              'plant_cooldowns': balance_table(catalog, 'PLANT_COOLDOWNS'), 'health': balance_table(catalog, 'HEALTH')}
    for table, values in tables.items():
        for key, value in values.items():
            row = 'd.%s.emplace(%s,%s);' % (table, cpp(key), cpp(value))
            pattern = re.compile(r'^d\.' + table + r'\.emplace\(' + re.escape(cpp(key)) + r',[^)]*\);$', re.M)
            if pattern.search(rest): rest = pattern.sub(lambda m: row, rest, count=1)
            else:
                anchor = list(re.finditer(r'^d\.' + table + r'\.emplace\(.*\);$', rest, re.M))[-1]
                rest = rest[:anchor.end()] + '\n' + row + rest[anchor.end():]
    return head + ''.join(cards) + rest


def balance_table(catalog, name):
    keys = {'COSTS': ['zombie:小鬼僵尸', 'zombie:黑普通僵尸', 'zombie:海豚僵尸', 'zombie:撑杆跳僵尸', 'plant:杨桃',
                      'plant:巴豆', 'plant:激光豆', 'zombie:盾卫僵尸', 'zombie:克苏鲁之仆',
                      'zombie:路灯花僵尸', 'zombie:三叶草僵尸'],
            'ZOMBIE_COOLDOWNS': ['zombie:小鬼僵尸', 'zombie:盾卫僵尸', 'zombie:克苏鲁之仆', 'zombie:潜水僵尸'],
            'PLANT_COOLDOWNS': ['plant:巴豆', 'plant:激光豆'],
            'HEALTH': ['zombie:投篮车僵尸', 'zombie:小鬼炮']}[name]
    table = getattr(catalog, name)
    return {k: table[k] for k in keys}


V_CATALOG = ROOT / 'src/sim/pvp/gen/pm_catalog.cpp'
CRLF, LF = chr(13) + chr(10), chr(10)
V_BEGIN, V_END = '    // PvP75 BEGIN (tools/pvp75_catalog_sync.py)\n', '    // PvP75 END\n'
V_ANCHOR = '    pm_catalog::ROOM_TICK_RATES = V::tuple({V(30.0), V(60.0)});\n'


def v_block(catalog):
    """Runtime V catalog: the same Python values, loaded from one JSON literal."""
    keys = sorted(set(NEW) | set(PATCH_CARDS))
    payload = dict(cards={k: catalog.CARDS[k] for k in keys},
                   costs=balance_table(catalog, 'COSTS'), zombie_cooldowns=balance_table(catalog, 'ZOMBIE_COOLDOWNS'),
                   plant_cooldowns=balance_table(catalog, 'PLANT_COOLDOWNS'), health=balance_table(catalog, 'HEALTH'),
                   ruleset=catalog.RULES['ruleset'], mechanics75=catalog.RULES['mechanics75'],
                   mechanics76=catalog.RULES['mechanics76'])
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    assert ')PVP75"' not in text
    rows = [V_BEGIN,
            '    {\n',
            # MSVC caps one literal piece near 16 KiB; adjacent raw pieces concatenate.
            '        static const char* const pvp75=' + ' '.join('R"PVP75(' + text[i:i + 3000] + ')PVP75"' for i in range(0, len(text), 3000)) + ';\n',
            '        const V data = callm(py::stdlib(SV("json")), SY("loads"), Args{V(std::string(pvp75))});\n',
            '        for (const auto& [key, card] : py::items_vec(rd(data, SV("cards")))) pvz::setitem(pm_catalog::CARDS, key, card);\n',
            '        for (const auto& [key, value] : py::items_vec(rd(data, SV("costs")))) pvz::setitem(pm_balance::COSTS, key, value);\n',
            '        for (const auto& [key, value] : py::items_vec(rd(data, SV("zombie_cooldowns")))) pvz::setitem(pm_balance::ZOMBIE_COOLDOWNS, key, value);\n',
            '        for (const auto& [key, value] : py::items_vec(rd(data, SV("plant_cooldowns")))) pvz::setitem(pm_balance::PLANT_COOLDOWNS, key, value);\n',
            '        for (const auto& [key, value] : py::items_vec(rd(data, SV("health")))) pvz::setitem(pm_balance::HEALTH, key, value);\n',
            '        pvz::setitem(pm_catalog::RULES, SV("ruleset"), rd(data, SV("ruleset")));\n',
            '        pvz::setitem(pm_catalog::RULES, SV("mechanics75"), rd(data, SV("mechanics75")));\n',
            '        pvz::setitem(pm_catalog::RULES, SV("mechanics76"), rd(data, SV("mechanics76")));\n',
            '    }\n',
            V_END]
    return ''.join(rows)


def v_render(text, catalog):
    nl = CRLF if CRLF in text else LF
    block = v_block(catalog).replace(LF, nl)
    begin, end_mark, anchor = (x.replace(LF, nl) for x in (V_BEGIN, V_END, V_ANCHOR))
    if begin in text:
        start = text.index(begin); end = text.index(end_mark, start) + len(end_mark)
        return text[:start] + block + text[end:]
    assert text.count(anchor) == 1
    return text.replace(anchor, block + anchor, 1)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true'); a = ap.parse_args()
    catalog, balance = load()
    text = DATA.read_text(encoding='utf8')
    out = render(text, catalog, balance)
    v_text = V_CATALOG.read_bytes().decode('utf8')
    v_out = v_render(v_text, catalog)
    if a.check:
        if out != text: raise SystemExit('cold_catalog_data.cpp is not in sync with the PvP75 Python catalog')
        if v_out != v_text: raise SystemExit('pm_catalog.cpp PvP75 block is not in sync with the Python catalog')
        print('PvP75 cold/V catalog: checked'); return
    if out != text: DATA.write_bytes(out.encode('utf8'))
    if v_out != v_text: V_CATALOG.write_bytes(v_out.encode('utf8'))
    print('PvP75 cold catalog:', 'updated' if out != text else 'unchanged', len(re.findall(r'^\{ ColdCard c;$', out, re.M)), 'cards;',
          'V catalog:', 'updated' if v_out != v_text else 'unchanged')


if __name__ == '__main__':
    main()
