"""Reviewed, production-only fixture observer elision; never edit the probe stage.

Apply BEFORE the historical statement stripper. Every edited method is scoped to
one of the exact allowlisted paths, one exact signature and a pinned SHA-256 of its original
body (including braces/whitespace, with CRLF normalized to LF). A changed body,
missing/duplicate signature or unexpected remaining observer call is an error,
not an invitation to infer whether new C++ is safe to delete.

Only the pure fixture bodies listed below become {}. Mixed methods lose explicit
call statements only, replaced by null statements so an if/else cannot rebind.
In particular, actual damage/controller calls, registration, surface_index's
save/restore and catch/rethrow ordering, and match_probe's business log_event
callbacks are NOT observer bodies. PlantProbe before/after are fixture injection
hooks; these production rules do not apply to the independent reference probes.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re


class ObserverContractError(ValueError):
    """The source no longer matches the reviewed production contract."""


def sha256(text):
    return hashlib.sha256(text.encode("utf8")).hexdigest()


def code_mask(text):
    """Mask C++ comments/quoted literals, preserving offsets and newlines.

    This is only a delimiter/call guard, not a C++ optimizer/parser. Body hashes
    are the authority. Raw string literals are deliberately unsupported here.
    """
    chars = list(text)
    i = 0
    while i < len(text):
        start = i
        if text.startswith('//', i):
            end = text.find('\n', i)
            i = len(text) if end < 0 else end
        elif text.startswith('/*', i):
            end = text.find('*/', i + 2)
            if end < 0:
                raise ObserverContractError('unterminated C++ comment')
            i = end + 2
        elif text.startswith('R"', i):
            raise ObserverContractError('unreviewed raw string literal')
        elif text[i] in ('"', "'"):
            quote = text[i]
            i += 1
            while i < len(text):
                if text[i] == '\\':
                    i += 2
                elif text[i] == quote:
                    i += 1
                    break
                else:
                    i += 1
            else:
                raise ObserverContractError('unterminated C++ literal')
        else:
            i += 1
            continue
        for at in range(start, min(i, len(chars))):
            if chars[at] not in '\r\n':
                chars[at] = ' '
    return ''.join(chars)


def body_span(text, signature):
    """Return the unique exact signature's braced body, excluding no tokens."""
    if text.count(signature) != 1:
        raise ObserverContractError(f'expected one signature: {signature}')
    mask = code_mask(text)
    start = text.index(signature)
    if mask[start:start + len(signature)] != signature:
        raise ObserverContractError(f'signature is not C++ code: {signature}')
    at = start + len(signature)
    while at < len(text) and text[at].isspace():
        at += 1
    if at == len(text) or text[at] != '{':
        raise ObserverContractError(f'expected body after: {signature}')
    depth = 0
    for end in range(at, len(text)):
        if mask[end] == '{':
            depth += 1
        elif mask[end] == '}':
            depth -= 1
            if depth == 0:
                return at, end + 1
    raise ObserverContractError(f'unbalanced body: {signature}')


def remove_statements(body, statements):
    """Remove only reviewed, exact statements; keep their C++ statement slot."""
    for statement in statements:
        if not statement.endswith(';') or body.count(statement) != 1:
            raise ObserverContractError(f'expected one fixture statement: {statement}')
        body = body.replace(statement, ';', 1)
    return body


@dataclass(frozen=True)
class BodyRule:
    signature: str
    source_body_sha256: str
    # None means the complete reviewed body is fixture-only. An explicit tuple
    # means all other bytes of the original body, including throws, survive.
    statements: tuple | None = None


PHASE = 'probes/content_phase_probe.cpp'
ZOMBIES = 'probes/content_zombies_probe.cpp'
CONTROLLERS = 'probes/content_controllers_probe.cpp'
ZOMBIES64 = 'probes/content_zombies64_probe.cpp'

# The SHA constants intentionally require human review when source changes.
# Never update them automatically as part of composition generation.
RULES = {
    ZOMBIES64: (
        # This inherited observer is reached by MatchProbe::alias_art before
        # NativeCanvas applies the real alias. Custom-zombie art gates call it
        # repeatedly; retain the independent probe, elide only its JSON history.
        BodyRule('void alias_art(const std::string& source,const std::string& target)override', '25c610a7927c4f6f13ef520193137a2b8ae922da2001933cbe3cd2e41e849f38', (
            'aliases64.push_back({source,target});',)),
    ),
    PHASE: (
        BodyRule('HitResult hit(size_t i,double f,double a)override', '51714c5c264860ab5a40a4243b1bc09504fc2cd0653548a35136a323f7948921', (
            'p.calls.push_back({"pea_damage",i,f,a});',
            'p.before("pea_damage");', 'p.after("pea_damage");')),
        BodyRule('HitResult surface_hit(size_t i,double f,double a)override', '37e942523a5f89f78bbc74f1d09531d3dbc68d83521be2637f7e026ed54c2b25', (
            'p.calls.push_back({"pea_surface",i,f,a});',
            'p.before("pea_surface");', 'p.after("pea_surface");')),
        BodyRule('void knock(size_t i,double a)override', 'cd2a35b4532f4eca4007c258a205f2dfd87aaef6ad760e6e534d84657282f993', (
            'p.calls.push_back({"pea_knockback",i,a});',
            'p.before("pea_knockback");', 'p.after("pea_knockback");')),
        BodyRule('void plant70_event(const Plant70Event& value)override', '60ba6804cbba07224cebfce21473be232a993f6c633b857f157936518d1ba69b'),
        BodyRule('void lantern_wake(const Field<std::string>& id,const std::vector<Field<std::string>>& targets)override', '6c54d2a18429423c75da2b9eecdfa4120eebffbc80fd5becbcf784d8caad9f70'),
        BodyRule('void draw_lettuce_flash(const LettuceFlash& flash)override', 'ce2f67d47a2ebc43a805c4c8a3e5b78accf85051f66448b71927cb0bfd457dbb'),
    ),
    ZOMBIES: (
        # Nonvirtual helper shared by the gate callers below and in CONTROLLERS.
        # Removing only its body would still allocate each caller's J::array().
        BodyRule('void event(const std::string& name,const ZombieRef& unit,J extra=J::array())', 'fc54d979c21bd99af7f17788a1bdfce89a62e8c9acab064be350a4255eadab38'),
        BodyRule('void cart_before(const ZombieRef& unit)override', '0e6d0457871e3b0b21d5db3b21a77713fe7498b7e5192333aed861e83ea1a2af', ('event("cart_before",unit);',)),
        BodyRule('void cart_animate(const ZombieRef& unit,bool active,bool fired)override', '969c30c8197fdbe49642ce102d7b9862bf5e035c6cef4c728f5408ed46dc31b8', ('event("cart_animate",unit,J::array({active,fired}));',)),
        BodyRule('void september_gate(const ZombieRef& unit)override', 'c0933678435a12727d067c37cc94ba3c275d4c0b40cbed66afcbd9b728a9c828', ('event("september_gate",unit);',)),
        BodyRule('void september_wave_chase(const ZombieRef& unit)override', 'a10dda05eb44c172cea5732109e1748505048acef2083bcf7722ca06dd8c3cd5', ('event("wave_chase",unit);',)),
        BodyRule('void september_finish(const ZombieRef& unit)override', '6dcd5a16e197e7942732ca8665dcdb9e2a2bfc7f1bf778f71205e0af7c333464', ('event("september_finish",unit);',)),
        BodyRule('void zombies56_gate(const ZombieRef& unit)override', '542084636565b9d218810f554b931bf4dec182f2b875495db255275004bae920', ('event("zombies56_gate",unit);',)),
        BodyRule('void zombies56_finish(const ZombieRef& unit)override', '281992f7bda8c41f37ad601625539ec84f80d4bec1b0cc22adba75b43f8dd6ae', ('event("zombies56_finish",unit);',)),
        BodyRule('void zombies70_gate(const ZombieRef& unit)override', '4ac7d41a913bd632606b63527add598c8134e34d71d6f565e07becbbfb30a225', ('event("zombies70_gate",unit);',)),
        BodyRule('void barrel_correct_pair(const ZombieRef& unit)override', '4846deacaaa8e63b8c32b70837886621167db6f91083c3afa8dfec2e959b0644', ('event("barrel_correct",unit);',)),
        BodyRule('void barrel_detach(const ZombieRef& unit,double remaining)override', 'ef12b0005aa501ed9e97cfaf6e4a25b22ae907da9e64af46e62bccbe0b957f25', ('event("barrel_detach",unit,J::array({remaining}));',)),
        BodyRule('void barrel_break(const ZombieRef& unit)override', 'f1d5db92a37a2e97b503b06def124364541bf6688f1b4fd7eef46638d7a4d760', ('event("barrel_break",unit);',)),
        BodyRule('void barrel_move(const ZombieRef& unit,double factor)override', '8ab7b4d862837d4f954f93c898a6e3b5b9a6ddf321f075deac503b4ac8fad326', ('event("barrel_move",unit,J::array({factor}));',)),
        BodyRule('void barrel_contact(const ZombieRef& unit,double factor)override', 'fd2d20b22597afee0ecea3bcea6bc3397ad586352dfa132652256a04921f1628', ('event("barrel_contact",unit,J::array({factor}));',)),
        BodyRule('double bite_damage(const ZombieRef& unit,const ContentTarget& target)override', 'efd18043b192a7eb576abe85235e259a7c3e58fdeb0bcb114ba57950c9e73a66', ('event("bite",unit,J::array({content_label(target)}));',)),
        BodyRule('void tint_poison(const ZombieRef& unit)override', 'f2f559e7c6ac2b41119fc84d17c7b73f17756dd455c4664aa7540bf68c493fdf', ('event("tint",unit);',)),
        BodyRule('void draw_content_zombie(const ZombieRef& unit)override', '9ffd4a86bef8725810dd42415f0a226e23c9e8a050733a5580fe2e487d649417', ('event("draw",unit);',)),
        BodyRule('void stun_star(Point point,Point dimensions)override', 'b6cb26b52f55e8d10cb73450df2f462ac128cb6997f8dc704f5fac3f90c5f98b'),
    ),
    CONTROLLERS: (
        BodyRule('double bite_damage(const ZombieRef& unit,const ContentTarget& target)override', 'bde09aa31ff513ddf54f62ee0bfd3aef0d350094f757d80509cfd7a226537a56', ('event("bite",unit,J::array({content_label(target)}));',)),
        BodyRule('void hide_headhunt_plants(const ZombieRef& unit)override', '765e70f4f29e8f5abf078fc13f93b3862f9f97c70072c738a715efc5a98d9dd9', ('event("hide_headhunt",unit);',)),
        BodyRule('void september_gate(const ZombieRef& unit)override', '45a1af9a25d7e86848cdc4817a84e6eef44fa3f91c04514bbbc8d17f785d2a8f', ('event("september_gate",unit);',)),
        BodyRule('void september_wave_chase(const ZombieRef& unit)override', '9bfe7c4e9d6c82732e387c14a232706b31fb5d771285ad86c0db2c652fd2e70a', ('event("wave_chase",unit);',)),
        BodyRule('void september_finish(const ZombieRef& unit)override', 'e81cf96b3b0c5d5192f23b13edc41e1768a9352a1382078b4d3eebedf7e697ae', ('event("september_finish",unit);',)),
        BodyRule('void zombies56_gate(const ZombieRef& unit)override', '8fd0663d108b3ea34d32b35a37dd8c30ab321e25388d9007eac16ff3167101f9', ('event("zombies56_gate",unit);',)),
        BodyRule('void zombies56_finish(const ZombieRef& unit)override', 'f050747e63c50be6d9b85facfdc07dd8487e6e0cb45662183a3290d37d6b6a03', ('event("zombies56_finish",unit);',)),
        BodyRule('void zombies70_gate(const ZombieRef& unit)override', '751d0b1f2ab8b5b0e553094ed41318f24ce7e71fe71deb853e562381464f0de1', ('event("zombies70_gate",unit);',)),
        BodyRule('void barrel_correct_pair(const ZombieRef& unit)override', 'fbf6397198cce07f1a19e46dc4507d36e519c48a84bb0b3a09ee67790569447d', ('event("barrel_correct",unit);',)),
        BodyRule('void barrel_detach(const ZombieRef& unit,double hp)override', '33ef984651c8dade2b28433ba10dbc7fea02202edf5203164a4557095a69a9ce', ('event("barrel_detach",unit,J::array({hp}));',)),
        BodyRule('void barrel_break(const ZombieRef& unit)override', 'b5bb73a67ffa225ba2596e38f414f24dc4142b2e54e3a6004af9b6f89d9a9b08', ('event("barrel_break",unit);',)),
        BodyRule('void barrel_move(const ZombieRef& unit,double factor)override', '61b261c072a8a31107258091bbda19eef1364d1462cf21de93081feaaef24ad2', ('event("barrel_move",unit,J::array({factor}));',)),
        BodyRule('void barrel_contact(const ZombieRef& unit,double factor)override', '29d0d96f4f0a4795221e1b5e40c8356d1c89029b0ff192fa05a6b0047155fc7a', ('event("barrel_contact",unit,J::array({factor}));',)),
        BodyRule('void zombie56_event(const Zombie56Event& value)override', '98f56ced4113f4d7ce58a0b236e993cabdeb5fed445f4f94a8eabe7e769cc045'),
        BodyRule('void zombie70_event(const Zombie70Event& value)override', '8fdf7606febd6b3bfcd02c07070939a9e23e1ae2363f90365c04fd6fa9d3cc16'),
        BodyRule('void barrel_event(const BarrelEvent& value)override', '3c6170893e0fed937df4e7d4779e2ee165af4b6cb134906026bc0c97795ac030'),
        # Factory methods are NOT pure observers: retain return values and all
        # native registration mutations, removing just the fixture push_back.
        BodyRule('ZombieRef spawn_bone_grave(Cell cell,const BoneSource& source)override', 'b32e999a674441796a1d2e01bb4b55d1f8313c5cf3fa11266ebc256542dcbe8b', ('factory_events.push_back({"bone_grave",cell.y,cell.x,nullable(source.metadata->id),source.direction});',)),
        BodyRule('PlantRef spawn_bone_gravebuster(Cell cell,double facing,const Field<std::string>& parent)override', '23dfc16794e70454fea2022d6e7804b725aa5d3ebe15402e4cf4efac735f33bd', ('factory_events.push_back({"bone_gravebuster",cell.y,cell.x,facing,nullable(parent)});',)),
        BodyRule('void draw_zombie70_effects()override', '51b4a821a0faf214b5d17d908be4953aafdda10b647ec7fd15e9ef61651660a0'),
        BodyRule('void register_barrel(const ZombieRef& unit,const Field<std::string>& parent)override', '53084870663e398e5bae5803965a2c88eaaeb1362f15ba1dcbc459d040964d5c', ('factory_events.push_back({"register_barrel",index(unit),nullable(parent)});',)),
        BodyRule('void crush_barrel_plant(const ZombieRef& unit,const PlantRef& plant)override', 'ddfa3daa472e2d87cec68a5ac1a1f50eb6bbe7adaeb3db2b232751b3df7687ca', ('factory_events.push_back({"crush",index(unit),content_label(plant)});',)),
        BodyRule('void draw_barrel_sprite(Point point,double angle)override', 'f20d0264616b7dd249e7c1360be938b58865382ec7778b4864c4f918f301e335'),
    ),
}


def validate_observers(path, text, *, after_legacy=False):
    """Guard the known residuals; never use these patterns to delete code."""
    mask = code_mask(text)
    # These seven fixture arrays are never gameplay journals. Guard every source,
    # including files outside the body-rule allowlist, after the reviewed strip.
    if after_legacy and re.search(
            r'\b(?:aliases64|draws64|events64|spawns64|cost_calls|grenade_events|poison_events)'
            r'\s*\.\s*(?:push_back|emplace_back)\s*\(', mask):
        raise ObserverContractError(f'{path}: unexpected retained probe log append')
    if path not in RULES:
        return
    # The sole retained bare event token is the empty helper definition. Any
    # new inherited/qualified caller in these reviewed files requires review.
    expected = 1 if path == ZOMBIES else 0
    if len(re.findall(r'\bevent\s*\(', mask)) != expected:
        raise ObserverContractError(f'{path}: unexpected fixture event caller')
    if path == PHASE:
        if re.search(r'\bp\s*\.\s*(?:calls\s*\.\s*(?:push_back|emplace_back)|before|after)\s*\(', mask):
            raise ObserverContractError(f'{path}: unexpected ObservedLower fixture call')
        if after_legacy and re.search(r'\b(?:phase_events|phase_draws)\s*\.\s*(?:push_back|emplace_back)\s*\(', mask):
            raise ObserverContractError(f'{path}: unexpected phase fixture log append')
    elif path == ZOMBIES64:
        if re.search(r'\baliases64\s*\.\s*(?:push_back|emplace_back)\s*\(', mask):
            raise ObserverContractError(f'{path}: unexpected alias fixture log append')
    else:
        if re.search(r'\b(?:content_events|controller_events|factory_events)\s*\.\s*(?:push_back|emplace_back)\s*\(', mask):
            raise ObserverContractError(f'{path}: unexpected fixture log append')


def transform(path, text):
    """Return new source + manifest entries; non-allowlisted paths are untouched."""
    if path not in RULES:
        return text, []
    text = text.replace('\r\n', '\n')
    edits = []
    records = []
    # Validate every source body first; never partially return a transformed file.
    for rule in RULES[path]:
        start, end = body_span(text, rule.signature)
        body = text[start:end]
        digest = sha256(body)
        if digest != rule.source_body_sha256:
            raise ObserverContractError(
                f'{path}: unreviewed body for {rule.signature}: '
                f'expected {rule.source_body_sha256}, got {digest}')
        new = '{}' if rule.statements is None else remove_statements(body, rule.statements)
        edits.append((start, end, new))
        records.append({
            'signature': rule.signature,
            'source_body_sha256': digest,
            'observer_result_body_sha256': sha256(new),
            'transform': 'empty_fixture_body' if rule.statements is None else 'null_fixture_statements',
            'expected_count': 1,
            'removed_statements': list(rule.statements or ()),
        })
    previous = len(text)
    for start, end, new in sorted(edits, reverse=True):
        if end > previous:
            raise ObserverContractError(f'{path}: overlapping body rules')
        text = text[:start] + new + text[end:]
        previous = start
    validate_observers(path, text)
    return text, records
