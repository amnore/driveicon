from functools import partial
from typing import Mapping

from indexed import IndexedOrderedDict
from gi.repository import Gio, GLib, Gtk, Gdk


def _create_item(
        label: str | None,
        detailed_action: str | None = None,
        icon: Gio.Icon | list[str] | None = None,
        submenu: Gio.Menu | None = None,
        section: Gio.Menu | None = None,
) -> Gio.MenuItem:
    item = Gio.MenuItem()
    item.set_label(label)
    item.set_submenu(submenu)
    item.set_section(section)
    if detailed_action is not None:
        item.set_detailed_action(detailed_action)

    match icon:
        case None:
            pass
        case [*_]:
            item.set_icon(Gio.ThemedIcon(names=icon))
        case _:
            item.set_icon(icon)

    return item


class MountMenu:
    def __init__(self, application: Gtk.Application):
        self.__volume_monitor: Gio.VolumeMonitor = Gio.VolumeMonitor.get()
        self.__action_group = Gio.SimpleActionGroup()
        self.__menu = Gio.Menu()
        self.__mount_operation = Gtk.MountOperation(parent=Gtk.ApplicationWindow(
            application=application
        ))
        self.__action_items: dict[int, Gio.Drive | Gio.Volume | Gio.Mount] = {}

        for signal_name in [
            'drive-changed',
            'drive-connected',
            'drive-disconnected',
            'mount-added',
            'mount-changed',
            'mount-removed',
            'volume-added',
            'volume-changed',
            'volume-removed'
        ]:
            self.__volume_monitor.connect(signal_name, self.__rebuild_menu)

        actions = [
            ('mount', self.__mount),
            ('unmount', self.__unmount),
            ('open', self.__open),
            ('eject', self.__eject),
        ]
        for name, callback in actions:
            action = Gio.SimpleAction(
                name=name,
                parameter_type=GLib.VariantType.new('s')
            )
            action.connect('activate', callback)

            self.__action_group.add_action(action)

        self.__rebuild_menu()

    @property
    def menu(self) -> Gio.Menu:
        return self.__menu

    @property
    def action_group(self):
        return self.__action_group

    def __rebuild_menu(self, *_):
        def eject_item(obj):
            return _create_item('Eject', f'eject::{id(obj)}', ['media-eject'])

        def open_item(obj):
            return _create_item('Open', f'open::{id(obj)}', ['document-open-folder', 'document-open'])

        def mount_item(obj):
            return _create_item('Mount', f'mount::{id(obj)}', ['media-mount'])

        def unmount_item(obj):
            return _create_item('Unmount', f'unmount::{id(obj)}', ['media-eject'])

        def menu_item(obj, menu, is_submenu=True):
            item = _create_item(
                obj.get_name(),
                icon=obj.get_icon(),
                submenu=menu if is_submenu else None,
                section=menu if not is_submenu else None,
            )
            return item

        def add_mount_items(menu, mount, is_toplevel = False):
            self.__action_items[id(mount)] = mount

            if is_toplevel and mount.can_eject():
                menu.append_item(eject_item(mount))

            menu.append_item(open_item(mount))
            if mount.can_unmount():
                menu.append_item(unmount_item(mount))

        def add_volume_items(menu, volume, is_toplevel = False):
            self.__action_items[id(volume)] = volume

            if is_toplevel and volume.can_eject():
                menu.append_item(eject_item(volume))

            section = Gio.Menu()
            menu.append_item(menu_item(volume, section, False))

            if (mount := volume.get_mount()) is not None:
                add_mount_items(section, mount)
            elif volume.can_mount():
                section.append_item(mount_item(volume))

        self.__menu.remove_all()
        self.__action_items.clear()

        for drive in self.__volume_monitor.get_connected_drives():
            self.__action_items[id(drive)] = drive
            submenu = Gio.Menu()
            self.__menu.append_item(menu_item(drive, submenu))

            if drive.can_eject():
                submenu.append_item(eject_item(drive))

            for volume in drive.get_volumes():
                add_volume_items(submenu, volume)

        for volume in self.__volume_monitor.get_volumes():
            if id(volume) in self.__action_items:
                continue

            submenu = Gio.Menu()
            self.__menu.append_item(menu_item(volume, submenu))
            add_volume_items(submenu, volume, True)

        for mount in self.__volume_monitor.get_mounts():
            if id(mount) in self.__action_items:
                continue

            submenu = Gio.Menu()
            self.__menu.append_item(menu_item(mount, submenu))
            add_mount_items(submenu, mount, True)

    def __mount(self, _, id: GLib.Variant):
        self.__action_items[int(id.get_string())].mount_asyncio(Gio.MountMountFlags.NONE, self.__mount_operation)

    def __unmount(self, _, id: GLib.Variant):
        self.__action_items[int(id.get_string())].unmount_with_operation_asyncio(
            Gio.MountUnmountFlags.NONE,
            self.__mount_operation,
        )

    def __open(self, _, id: GLib.Variant):
        Gtk.show_uri(None, self.__action_items[int(id.get_string())].get_default_location().get_uri(), Gdk.CURRENT_TIME)

    def __eject(self, _, id: GLib.Variant):
        self.__action_items[int(id.get_string())].eject_with_operation_asyncio(
            Gio.MountUnmountFlags.NONE,
            self.__mount_operation,
        )