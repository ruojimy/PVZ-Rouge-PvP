"""PvP-only presentation persistence and local address discovery."""
import ipaddress
import json
import os
import socket
from pathlib import Path

from .catalog import CARDS, RULES, allowed, catalog_hash, rules_hash, validate_deck


NETWORK_ERRORS = {
    "relay_unreachable": "无法连接云端中继，请检查网络或中继地址，也可改用高级直连。",
    "relay_timeout": "云端连接超时，请稍后重试。",
    "relay_protocol_mismatch": "云端中继协议不兼容，请更新对战版本。",
    "room_not_found": "未找到云端房间，请核对房间码并确认主机已创建房间。",
    "room_expired": "云端房间已过期，请主机重新创建。",
    "host_offline": "主机暂时离线，请等待主机恢复连接。",
    "host_left": "主机已离开云端房间。",
    "host_in_use": "主机连接仍在清理，请稍候重试。",
    "resume_rejected": "云端重连凭证无效，请重新创建房间。",
    "rate_limited": "连接过于频繁，请稍后重试。",
    "connection_limit": "当前网络连接数已达限制，请稍后重试。",
    "server_full": "云端房间已满，请稍后重试或使用直连。",
    "server_busy": "云端服务繁忙，请稍后重试。",
    "invalid_preamble": "云端返回了无效数据，请核对中继地址。",
    "room_code_invalid": "房间口令错误，请核对后重新连接。",
    "identity_mismatch": "双方版本、规则、卡池或地图适配不同，请使用同一份对战版本。",
    "protocol_mismatch": "联机协议版本不同，请使用同一份对战版本。",
    "room_full": "房间玩家席位已满，请等待空位或创建新房间。",
    "handshake_rejected": "主机拒绝连接，请核对房间信息。",
    "address_resolution_failed": "无法解析主机地址，请检查地址格式。",
    "connect_timeout": "连接主机超时，请检查地址、端口和网络。",
    "connection_failed": "无法连接主机，请确认房间已开启及端口可达。",
    "listen_failed": "无法监听此端口，端口可能已占用；请更换端口重试。",
    "reconnect_expired": "重连等待已超时，可重新连接或取消。",
    "protocol_error": "收到无效联机数据，连接已停止。",
    "transport_error": "联机连接发生错误，可以重试。",
    "closed": "连接已关闭，可以重新连接。",
    "event_queue_full": "联机事件队列拥堵，连接已停止，请重试。",
}


def network_error(code):
    return NETWORK_ERRORS.get(code, "联机状态异常，可以核对房间信息后重试。")


def copy_text(pygame, value):
    """Windows Unicode clipboard; pygame fallback on other systems."""
    import os
    if os.name != "nt":
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        pygame.scrap.put(pygame.SCRAP_TEXT, (value + "\0").encode("utf-8"))
        return
    import ctypes
    user, kernel = ctypes.windll.user32, ctypes.windll.kernel32
    kernel.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel.GlobalAlloc.restype = ctypes.c_void_p
    kernel.GlobalLock.argtypes = [ctypes.c_void_p];kernel.GlobalLock.restype = ctypes.c_void_p
    kernel.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel.GlobalFree.argtypes = [ctypes.c_void_p]
    user.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user.SetClipboardData.restype = ctypes.c_void_p
    data = (value + "\0").encode("utf-16-le")
    handle = kernel.GlobalAlloc(0x0002, len(data))
    if not handle:
        raise OSError("Clipboard allocation failed")
    owned = True
    try:
        pointer = kernel.GlobalLock(handle)
        if not pointer:
            raise OSError("Clipboard lock failed")
        ctypes.memmove(pointer, data, len(data));kernel.GlobalUnlock(handle)
        if not user.OpenClipboard(None):
            raise OSError("Clipboard is in use")
        try:
            if not user.EmptyClipboard() or not user.SetClipboardData(13, handle):
                raise OSError("Clipboard write failed")
            owned = False
        finally:
            user.CloseClipboard()
    finally:
        if owned:
            kernel.GlobalFree(handle)


def read_clipboard(pygame):
    """Read clipboard only in response to the user's explicit paste gesture."""
    import os
    if os.name != "nt":
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        return (pygame.scrap.get(pygame.SCRAP_TEXT) or b"").decode("utf-8", "ignore").rstrip("\0")
    import ctypes
    user, kernel = ctypes.windll.user32, ctypes.windll.kernel32
    user.GetClipboardData.argtypes = [ctypes.c_uint];user.GetClipboardData.restype = ctypes.c_void_p
    kernel.GlobalLock.argtypes = [ctypes.c_void_p];kernel.GlobalLock.restype = ctypes.c_void_p
    kernel.GlobalUnlock.argtypes = [ctypes.c_void_p]
    if not user.OpenClipboard(None):
        raise OSError("Clipboard is in use")
    try:
        handle = user.GetClipboardData(13)
        if not handle:
            return ""
        pointer = kernel.GlobalLock(handle)
        if not pointer:
            raise OSError("Clipboard lock failed")
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel.GlobalUnlock(handle)
    finally:
        user.CloseClipboard()


def _primary_ipv4():
    """Best-effort primary IPv4 via a UDP 'connect'; no packet is ever sent.

    Android's gethostname() is usually a random name that resolves nowhere, so
    on a phone the getaddrinfo pass below tends to return nothing usable. A UDP
    socket connect to TEST-NET-3 just asks the kernel which local source
    address it would use - the typical Wi-Fi/hotspot IPv4.
    """
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("203.0.113.1", 80))
        host = sock.getsockname()[0]
        ip = ipaddress.ip_address(host)
        if not ip.is_loopback and not ip.is_unspecified:
            return host
    except (OSError, ValueError):
        return None
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
    return None


def local_endpoints(port):
    candidates = []
    primary = _primary_ipv4()
    if primary:
        candidates.append("%s:%d" % (primary, port))
    try:
        addresses = socket.getaddrinfo(socket.gethostname(), None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except OSError:
        addresses = []
    for family, unused_type, unused_proto, unused_canon, sockaddr in addresses:
        host = sockaddr[0]
        try:
            ip = ipaddress.ip_address(host.split("%", 1)[0])
        except ValueError:
            continue
        if ip.is_loopback or ip.is_unspecified:
            continue
        if family == socket.AF_INET6:
            if ip.is_link_local and len(sockaddr) > 3 and sockaddr[3] and "%" not in host:
                host += "%" + str(sockaddr[3])
            value = "[%s]:%d" % (host, port)
        elif family == socket.AF_INET:
            value = "%s:%d" % (host, port)
        else:
            continue
        if value not in candidates:
            candidates.append(value)
    def rank(value):
        if not value.startswith("["):
            return (1, value)
        ip = ipaddress.ip_address(value[1:value.index("]")].split("%", 1)[0])
        return (2 if ip.is_link_local else 0, value)
    return sorted(candidates, key=rank)


def endpoint_note(value):
    if value.startswith("["):
        try:
            address = ipaddress.ip_address(value[1:value.index("]")].split("%", 1)[0])
            if address.is_link_local:
                return "链路本地地址：% 后的接口编号须按客机网络接口调整"
        except (ValueError, IndexError):
            pass
    return "本机候选地址不等于公网可达；优先列出 IPv6"


def save_decks(path, decks, rules=None):
    rules=rules or RULES
    for side, deck in decks.items():
        if side not in ('plant','plant2','zombie','zombie2'):raise ValueError('卡组席位无效')
        team='plant' if side.startswith('plant') else 'zombie'
        error = validate_deck(team,deck,slots=rules.get(team+'_slots',7))
        if error:
            raise ValueError(error)
    value = {"format": "pvp-decks-2", "rules_hash": rules_hash(), "catalog_hash": catalog_hash(), "decks": decks}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():path.with_name(path.name+'.previous').write_bytes(path.read_bytes())
    pending=path.with_name(path.name+'.pending')
    pending.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(str(pending),str(path))


def load_decks(path, bans=()):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get('format') not in ('pvp-decks-1','pvp-decks-2'):
        raise ValueError('不支持的阵容文件格式')
    decks = value.get("decks")
    if not isinstance(decks, dict):
        raise ValueError("卡组文件格式无效")
    for side, deck in decks.items():
        if side not in ('plant','plant2','zombie','zombie2'):
            raise ValueError("卡组阵营无效")
        if not isinstance(deck,list) or any(not isinstance(k,str) for k in deck):raise ValueError('卡组条目无效')
        team='plant' if side.startswith('plant') else 'zombie'
        decks[side]=list(dict.fromkeys(k for k in deck if k in CARDS and CARDS[k]['side']==team and allowed(k,bans)))
    return decks
