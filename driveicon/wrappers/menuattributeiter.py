from gi.repository import Gio, GLib


def _menu_attribute_iter_next(self: Gio.MenuAttributeIter) -> tuple[str, GLib.Variant]:
    if not self.next():
        raise StopIteration()
    return self.get_name(), self.get_value()


def _wrap_menu_attribute_iter() -> None:
    setattr(Gio.MenuAttributeIter, '__iter__', lambda self: self)
    setattr(Gio.MenuAttributeIter, '__next__', _menu_attribute_iter_next)