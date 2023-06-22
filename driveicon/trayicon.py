from enum import Enum
from functools import partial
from itertools import filterfalse, chain
from typing import Iterable

from gi.repository import GLib, GObject, Gio, Dbusmenu, Gtk, Gdk
from dasbus.connection import SessionMessageBus
from dasbus.server.interface import dbus_interface, dbus_signal
from dasbus.server.template import InterfaceTemplate
from dasbus.identifier import DBusServiceIdentifier, DBusObjectIdentifier
from dasbus.typing import Str, UInt32, Bool, Int, Byte, ObjPath, List, Tuple


class SNICategory(Enum):
    APPLICATION_STATUS = 'ApplicationStatus'
    COMMUNICATIONS = 'Communications'
    SYSTEM_SERVICES = 'SystemServices'
    HARDWARE = 'Hardware'


class SNIStatus(Enum):
    PASSIVE = 'Passive'
    ACTIVE = 'Active'
    NEEDS_ATTENTION = 'NeedsAttention'


class _DBusMenuItemType:
    STANDARD = 'standard'
    SEPARATOR = 'separator'


class _DBusMenuItemToggleType:
    CHECKMARK = 'checkmark'
    RADIO = 'radio'
    NONE = ''


class _DBusMenuItemToggleState:
    OFF = 0
    ON = 1
    INDETERMINATE = -1


class _DBusMenuItemProperty:
    TYPE = 'type'
    LABEL = 'label'
    ENABLED = 'enabled'
    VISIBLE = 'visible'
    ICON_NAME = 'icon-name'
    ICON_DATA = 'icon-data'
    SHORTCUT = 'shortcut'
    TOGGLE_TYPE = 'toggle-type'
    TOGGLE_STATE = 'toggle-state'
    CHILDREN_DISPLAY = 'children-display'


_VARIANT_TYPE_STRING = GLib.VariantType.new('s')
_VARIANT_TYPE_BOOL = GLib.VariantType.new('b')

_VARIANT_BOOL_TRUE = GLib.Variant.new_boolean(True)


@dbus_interface('org.kde.StatusNotifierItem')
class _TrayIconProxy(InterfaceTemplate):
    def __init__(self, tray_icon: 'TrayIcon', object_path: str) -> None:
        super().__init__(tray_icon)
        self.__object_path = object_path

    @property
    def Category(self) -> Str:
        return self.implementation.category

    @property
    def Id(self) -> Str:
        return self.implementation.id

    @property
    def Title(self) -> Str:
        return self.implementation.title

    @property
    def Status(self) -> Str:
        return self.implementation.status

    @property
    def WindowId(self) -> UInt32:
        return self.implementation.window_id

    @property
    def IconName(self) -> Str:
        return self.__icon_name(self.implementation.icon)

    @property
    def IconPixmap(self) -> List[Tuple[Int, Int, List[Byte]]]:
        return self.__icon_pixmap(self.implementation.icon)

    @property
    def OverlayIconName(self) -> Str:
        return self.__icon_name(self.implementation.overlay_icon)

    @property
    def OverlayIconPixmap(self) -> List[Tuple[Int, Int, List[Byte]]]:
        return self.__icon_pixmap(self.implementation.overlay_icon)

    @property
    def AttentionIconName(self) -> Str:
        return self.__icon_name(self.implementation.attention_icon)

    @property
    def AttentionIconPixmap(self) -> List[Tuple[Int, Int, List[Byte]]]:
        return self.__icon_pixmap(self.implementation.attention_icon)

    @property
    def AttentionMovieName(self) -> Str:
        return ''

    @property
    def ToolTip(self) -> Tuple[Str, List[Tuple[Int, Int, List[Byte]]], Str, Str]:
        if self.implementation.tooltip is None:
            return '', [], '', ''
        icon, title, description = self.implementation.tooltip
        return self.__icon_name(icon), self.__icon_pixmap(icon), title, description

    @property
    def ItemIsMenu(self) -> Bool:
        return self.implementation.item_is_menu

    @property
    def Menu(self) -> ObjPath:
        return self.__object_path

    def ContextMenu(self, x: Int, y: Int) -> None:
        self.implementation.emit('context-menu', x, y)

    def Activate(self, x: Int, y: Int) -> None:
        self.implementation.emit('activate', x, y)

    def SecondaryActivate(self, x: Int, y: Int) -> None:
        self.implementation.emit('secondary-activate', x, y)

    def Scroll(self, delta: Int, orientation: Str) -> None:
        self.implementation.emit('scroll', delta, orientation)

    @dbus_signal
    def NewTitle(self) -> None:
        pass

    @dbus_signal
    def NewIcon(self) -> None:
        pass

    @dbus_signal
    def NewAttentionIcon(self) -> None:
        pass

    @dbus_signal
    def NewOverlayIcon(self) -> None:
        pass

    @dbus_signal
    def NewToolTip(self) -> None:
        pass

    @dbus_signal
    def NewStatus(self, status: Str) -> None:
        pass

    @staticmethod
    def __icon_name(icon: Gio.Icon) -> str:
        if isinstance(icon, Gio.ThemedIcon):
            return icon.get_names()[0]
        else:
            return ''

    @staticmethod
    def __icon_pixmap(icon: Gio.Icon) -> List[Tuple[Int, Int, List[Byte]]]:
        return []


class _DBusMenuProxy:
    def __init__(self, object_path: str, root_menu: Gio.MenuModel, action_group: Gio.ActionGroup) -> None:
        self.__root_menu = root_menu
        self.__action_group = action_group
        self.__root_node = Dbusmenu.Menuitem()
        self.__action_enabled_items: dict[str, list[Dbusmenu.Menuitem]] = {}
        self.__action_state_items: dict[str, list[tuple[Dbusmenu.Menuitem, GLib.Variant]]] = {}
        self.__items_changed_handlers: dict[Gio.MenuModel, int] = {}
        self.__server = Dbusmenu.Server(
            dbus_object=object_path,
            root_node=self.__root_node
        )
        self.__icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())

        self.__rebuild_menu()
        self.__action_group.connect('action-state-changed', self.__on_action_state_changed)
        self.__action_group.connect('action-enabled-changed', self.__on_action_enabled_changed)

    def __build_dbus_menu_items(self, menu: Gio.MenuModel) -> Iterable[Dbusmenu.Menuitem]:
        at_first_item = True
        at_section_end = False

        if menu not in self.__items_changed_handlers:
            handler_id = menu.connect(
                'items-changed',
                partial(lambda self, *_: self.__rebuild_menu(), self),
            )
            self.__items_changed_handlers[menu] = handler_id

        for i in range(menu.get_n_items()):
            if (section := menu.get_item_link(i, Gio.MENU_LINK_SECTION)) is not None:
                if not at_first_item:
                    yield self.__build_separator()
                if menu.get_item_attribute_value(i, Gio.MENU_ATTRIBUTE_LABEL) is not None:
                    yield self.__build_dbus_menu_item(menu.iterate_item_attributes(i), is_section_header=True)
                for item in self.__build_dbus_menu_items(section):
                    yield item
                at_section_end = True
            else:
                if at_section_end:
                    yield self.__build_separator()
                    at_section_end = False

                yield self.__build_dbus_menu_item(
                    menu.iterate_item_attributes(i),
                    menu.get_item_link(i, Gio.MENU_LINK_SUBMENU),
                )

            at_first_item = False

    def __build_dbus_menu_item(
            self,
            attrs: Gio.MenuAttributeIter,
            submenu: Gio.MenuModel | None = None,
            is_section_header = False,
    ) -> Dbusmenu.Menuitem:
        item = Dbusmenu.Menuitem()
        action = None
        target = None

        def activate_action(action_group, action, target, *_):
            action_group.activate_action(action, target)

        for name, value in attrs:
            match name:
                case Gio.MENU_ATTRIBUTE_TARGET:
                    target = value
                case Gio.MENU_ATTRIBUTE_ACTION:
                    action = value.get_string()
                case Gio.MENU_ATTRIBUTE_LABEL:
                    item.property_set(_DBusMenuItemProperty.LABEL, value.get_string())
                case Gio.MENU_ATTRIBUTE_ICON:
                    icon = Gio.Icon.deserialize(value)
                    if isinstance(icon, Gio.ThemedIcon):
                        if not self.__icon_theme.has_gicon(icon):
                            continue

                        icon_printable = self.__icon_theme.lookup_by_gicon(
                            icon,
                            24,
                            1,
                            Gtk.TextDirection.NONE,
                            Gtk.IconLookupFlags.FORCE_SYMBOLIC,
                        )
                        item.property_set(_DBusMenuItemProperty.ICON_NAME, icon_printable.get_icon_name())
                    else:
                        raise ValueError(f'icon of type {type(icon)} is not supported')

        if is_section_header:
            item.property_set_bool(_DBusMenuItemProperty.ENABLED, False)
            return item

        if action is not None:
            item.connect('item-activated', partial(activate_action, self.__action_group, action, target))

            item.property_set_bool(_DBusMenuItemProperty.ENABLED, self.__action_group.get_action_enabled(action))
            self.__action_enabled_items.setdefault(action, []).append(item)

            state_type = self.__action_group.get_action_state_type(action)
            if state_type == _VARIANT_TYPE_STRING or state_type == _VARIANT_TYPE_BOOL:
                is_string = state_type == _VARIANT_TYPE_STRING
                toggle_type = _DBusMenuItemToggleType.RADIO if is_string else _DBusMenuItemToggleType.CHECKMARK
                expected_value = target if is_string else _VARIANT_BOOL_TRUE
                current_value = self.__action_group.get_action_state(action)

                item.property_set(_DBusMenuItemProperty.TOGGLE_TYPE, toggle_type)
                item.property_set_int(
                    _DBusMenuItemProperty.TOGGLE_STATE,
                    _DBusMenuItemToggleState.ON if expected_value == current_value else _DBusMenuItemToggleState.OFF,
                )
                self.__action_state_items.setdefault(action, []).append((item, expected_value))

        if submenu is not None:
            submenu_is_empty = True
            for submenu_item in self.__build_dbus_menu_items(submenu):
                item.child_append(submenu_item)
                submenu_is_empty = False
            if not submenu_is_empty:
                item.property_set(_DBusMenuItemProperty.CHILDREN_DISPLAY, 'submenu')

        return item

    def __rebuild_menu(self) -> None:
        self.__action_state_items = {}
        self.__action_enabled_items = {}

        for model, handler_id in self.__items_changed_handlers.items():
            model.disconnect(handler_id)
        self.__items_changed_handlers.clear()

        self.__root_node.take_children()
        for item in self.__build_dbus_menu_items(self.__root_menu):
            self.__root_node.child_append(item)

    def __on_action_enabled_changed(self, _, name: str, enabled: bool) -> None:
        for item in self.__action_enabled_items.get(name, []):
            item.property_set_bool(_DBusMenuItemProperty.ENABLED, enabled)

    def __on_action_state_changed(self, _, name: str, value: GLib.Variant) -> None:
        for item, expected_value in self.__action_state_items.get(name, []):
            item.property_set_int(
                _DBusMenuItemProperty.TOGGLE_STATE,
                _DBusMenuItemToggleState.ON if value == expected_value else _DBusMenuItemToggleState.OFF,
            )

    @staticmethod
    def __build_separator() -> Dbusmenu.Menuitem:
        item = Dbusmenu.Menuitem()
        item.property_set(_DBusMenuItemProperty.TYPE, _DBusMenuItemType.SEPARATOR)
        return item


class TrayIcon(GObject.Object):
    __bus = SessionMessageBus()
    __watcher = DBusServiceIdentifier(__bus, ('org', 'kde', 'StatusNotifierWatcher'))
    __watcher_object = DBusObjectIdentifier(('StatusNotifierWatcher',))

    def __init__(
            self,
            *,
            category = SNICategory.APPLICATION_STATUS,
            id: str,
            title: str,
            status = SNIStatus.ACTIVE,
            window_id = 0,
            icon: Gio.Icon,
            overlay_icon: Gio.Icon | None = None,
            attention_icon: Gio.Icon | None = None,
            tooltip: tuple[Gio.Icon | None, str, str] | None = None,
            item_is_menu = False,
            action_group: Gio.SimpleActionGroup,
            menu_model: Gio.MenuModel,
            object_path='/SNIMenu',
    ) -> None:
        super().__init__()
        self.__category = category
        self.__id = id
        self.__title = title
        self.__status = status
        self.__window_id = window_id
        self.__icon = icon
        self.__overlay_icon = overlay_icon
        self.__attention_icon = attention_icon
        self.__tooltip = tooltip
        self.__item_is_menu = item_is_menu
        self.__action_group = action_group
        self.__interface = _TrayIconProxy(self, object_path)
        self.__menu_proxy = _DBusMenuProxy(
            object_path,
            menu_model,
            self.__action_group,
        )

        self.__bus.publish_object(object_path, self.__interface)
        proxy = self.__watcher.get_proxy(self.__watcher_object)
        proxy.RegisterStatusNotifierItem(object_path)

    @property
    def category(self) -> str:
        return self.__category.value

    @property
    def id(self) -> str:
        return self.__id

    @property
    def title(self) -> str:
        return self.__title

    @title.setter
    def title(self, title: str) -> None:
        self.__title = title
        self.__interface.NewTitle.emit()

    @property
    def status(self) -> str:
        return self.__status.value

    @status.setter
    def status(self, status: SNIStatus) -> None:
        self.__status = status
        self.__interface.NewStatus.emit(status.value)

    @property
    def window_id(self) -> int:
        return self.__window_id

    @property
    def icon(self) -> Gio.Icon:
        return self.__icon

    @icon.setter
    def icon(self, icon: Gio.Icon) -> None:
        self.__icon = icon
        self.__interface.NewIcon.emit()

    @property
    def overlay_icon(self) -> Gio.Icon:
        return self.__overlay_icon

    @overlay_icon.setter
    def overlay_icon(self, overlay_icon: Gio.Icon) -> None:
        self.__overlay_icon = overlay_icon
        self.__interface.NewOverlayIcon.emit()

    @property
    def attention_icon(self) -> Gio.Icon:
        return self.__attention_icon

    @attention_icon.setter
    def attention_icon(self, attention_icon: Gio.Icon) -> None:
        self.__attention_icon = attention_icon
        self.__interface.NewAttentionIcon.emit()

    @property
    def tooltip(self) -> tuple[Gio.Icon | None, str, str] | None:
        return self.__tooltip

    @tooltip.setter
    def tooltip(self, tooltip: tuple[Gio.Icon | None, str, str] | None):
        self.__tooltip = tooltip
        self.__interface.NewToolTip.emit()

    @property
    def item_is_menu(self) -> bool:
        return self.__item_is_menu

    @GObject.Signal('context-menu')
    def context_menu(self, x: int, y: int) -> None:
        pass

    @GObject.Signal('activate')
    def activate(self, x: int, y: int) -> None:
        pass

    @GObject.Signal('secondary-activate')
    def secondary_activate(self, x: int, y: int) -> None:
        pass

    @GObject.Signal('scroll')
    def scroll(self, delta: int, orientation: str) -> None:
        pass
