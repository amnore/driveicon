import gi

gi.require_versions({
    'Gtk': '4.0',
    'Gio': '2.0',
    'GObject': '2.0',
    'Pango': '1.0',
    'Dbusmenu': '0.4',
})

import asyncio
from gi.repository import Gtk, Gio
from gi.events import GLibEventLoopPolicy

from .trayicon import TrayIcon, SNIStatus
from . import wrappers
from .mountmenu import MountMenu


def on_activate(application: Gtk.Application):
    application.mount_manager = MountMenu(application)

    application.tray_icon = TrayIcon(
        id=application.get_application_id(),
        title='Drives',
        icon=Gio.ThemedIcon(name='drive-removable-media'),
        action_group=application.mount_manager.action_group,
        menu_model=application.mount_manager.menu,
        item_is_menu=True,
    )

    def set_visibility(_, menu):
        if menu.get_n_items() == 0:
            application.tray_icon.status = SNIStatus.PASSIVE
        else:
            application.tray_icon.status = SNIStatus.ACTIVE

    set_visibility(None, application.mount_manager.menu)
    application.mount_manager.connect('menu-changed', set_visibility)


def main():
    asyncio.set_event_loop_policy(GLibEventLoopPolicy())
    wrappers.wrap_all()

    app = Gtk.Application(application_id='one.markle.DriveIcon')
    app.connect('activate', on_activate)

    try:
        app.run()
    except KeyboardInterrupt:
        pass
