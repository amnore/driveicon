from gi.repository import Gtk


def _bitset_iter(self: Gtk.Bitset) -> Gtk.BitsetIter:
    return Gtk.BitsetIter.init_first(self)[1]


def _bitset_iter_next(self: Gtk.BitsetIter) -> int:
    if not self.is_valid():
        raise StopIteration()

    value = self.get_value()
    self.next()
    return value


def _wrap_bitset():
    setattr(Gtk.Bitset, '__iter__', _bitset_iter)
    setattr(Gtk.Bitset, '__len__', Gtk.Bitset.get_size)
    setattr(Gtk.BitsetIter, '__iter__', lambda self: self)
    setattr(Gtk.BitsetIter, '__next__', _bitset_iter_next)
