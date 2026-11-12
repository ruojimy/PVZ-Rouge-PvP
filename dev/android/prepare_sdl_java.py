#!/usr/bin/env python3
"""Copy SDL 2.28.5 Java and backport two Android 13/14 USB HID fixes.

The dependency cache is read-only. Only the assembly-local HIDDeviceManager
changes; native SDL libraries and the other eight Java files remain identical.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import sys

HID = 'org/libsdl/app/HIDDeviceManager.java'
HID_SHA256 = '814c3b0bd916aeb57beabe3996e8e947d228c1068716019afabde254cacd98f2'
JAVA_FILES = tuple('org/libsdl/app/' + name + '.java' for name in (
    'HIDDevice', 'HIDDeviceBLESteamController', 'HIDDeviceManager', 'HIDDeviceUSB',
    'SDL', 'SDLActivity', 'SDLAudioManager', 'SDLControllerManager', 'SDLSurface'))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def prepare(source, output, report_path, patch_path):
    source = source.resolve()
    output = output.resolve()
    report_path = report_path.resolve()
    patch_path = patch_path.resolve()
    if output.exists() or report_path.exists() or patch_path.exists():
        raise ValueError('Output, report and patch paths must be new')
    found = {p.relative_to(source).as_posix() for p in source.rglob('*.java')}
    if found != set(JAVA_FILES):
        raise ValueError('Expected exactly the original nine SDL 2.28.5 Java files')
    originals = {name: (source / name).read_bytes() for name in JAVA_FILES}
    if sha256(originals[HID]) != HID_SHA256:
        raise ValueError('HIDDeviceManager.java SHA256 does not match the reviewed SDL 2.28.5 source')

    # Byte edits preserve original newlines and all unrelated Java source.
    register_before = b'        mContext.registerReceiver(mUsbBroadcast, filter);'
    register_after = b'''        if (Build.VERSION.SDK_INT >= 33) {
            mContext.registerReceiver(mUsbBroadcast, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            mContext.registerReceiver(mUsbBroadcast, filter);
        }'''
    permission_before = b'                mUsbManager.requestPermission(usbDevice, PendingIntent.getBroadcast(mContext, 0, new Intent(HIDDeviceManager.ACTION_USB_PERMISSION), flags));'
    permission_after = b'''                Intent permissionIntent = new Intent(HIDDeviceManager.ACTION_USB_PERMISSION);
                permissionIntent.setPackage(mContext.getPackageName());
                mUsbManager.requestPermission(usbDevice, PendingIntent.getBroadcast(mContext, 0, permissionIntent, flags));'''
    patched = originals[HID]
    for label, before, after in [('usb_receiver_export_flag', register_before, register_after),
                                 ('usb_permission_explicit_package', permission_before, permission_after)]:
        if patched.count(before) != 1:
            raise ValueError('Expected one reviewed source pattern: ' + label)
        patched = patched.replace(before, after, 1)

    # All validation precedes creating the assembly output. No source writes.
    output.mkdir(parents=True)
    files = {}
    for name in JAVA_FILES:
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if name == HID:
            destination.write_bytes(patched)
        else:
            shutil.copyfile(str(source / name), str(destination))
        actual = destination.read_bytes()
        expected = patched if name == HID else originals[name]
        if actual != expected:
            raise ValueError('Assembly Java copy verification failed: ' + name)
        if (source / name).read_bytes() != originals[name]:
            raise ValueError('Dependency source changed during preparation: ' + name)
        files[name] = {'before_sha256': sha256(originals[name]),
                       'after_sha256': sha256(actual), 'changed': actual != originals[name]}
    diff = ''.join(difflib.unified_diff(originals[HID].decode('utf-8').splitlines(True),
        patched.decode('utf-8').splitlines(True), fromfile='a/' + HID, tofile='b/' + HID))
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_text(diff, encoding='utf-8')
    report = {'format': 'pvp72-sdl-java-backport-1', 'sdl_version': '2.28.5',
              'source': str(source), 'output': str(output), 'dependency_cache_modified': False,
              'copied_files': len(files), 'changed_files': [name for name in JAVA_FILES if files[name]['changed']],
              'guard_sha256': HID_SHA256, 'files': files,
              'patch': {'path': str(patch_path), 'sha256': sha256(patch_path.read_bytes())},
              'fixes': ['SDK>=33 USB mixed broadcast filter uses RECEIVER_NOT_EXPORTED; older SDK retains legacy registration',
                        'USB permission Intent is package-scoped; original mutable PendingIntent flags are retained'],
              'upstream': 'https://github.com/libsdl-org/SDL/blob/SDL2/android-project/app/src/main/java/org/libsdl/app/HIDDeviceManager.java'}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--patch', required=True, type=Path)
    args = parser.parse_args()
    try:
        report = prepare(args.source, args.output, args.report, args.patch)
    except (OSError, ValueError) as error:
        print('SDL Java preparation failed: ' + str(error), file=sys.stderr)
        return 2
    print(json.dumps({'copied_files': report['copied_files'], 'changed_files': report['changed_files'],
                      'hid_sha256': report['files'][HID]['after_sha256']}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
