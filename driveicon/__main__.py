import gi

gi.require_versions({
    'Gtk': '4.0',
    'Gio': '2.0',
    'GObject': '2.0',
    'Pango': '1.0',
    'Dbusmenu': '0.4',
})

import asyncio
import gbulb
from gi.repository import Gtk, Gio

from .trayicon import TrayIcon
from . import wrappers
from .mountmenu import MountMenu


def on_activate(application: Gtk.Application):
    application.mount_manager = MountMenu(application)

    application.tray_icon = TrayIcon(
        id='one.markle.DriveIcon',
        title='Drives',
        icon=Gio.ThemedIcon(name='drive-removable-media'),
        action_group=application.mount_manager.action_group,
        menu_model=application.mount_manager.menu,
        item_is_menu=True,
    )


gbulb.install(True)
wrappers.wrap_all()

app = Gtk.Application(application_id='one.markle.DriveIcon')
app.connect('activate', on_activate)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_forever(application=app)