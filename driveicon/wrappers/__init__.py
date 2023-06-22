from ._async import _wrap_async
from .bitset import _wrap_bitset
from .menuattributeiter import _wrap_menu_attribute_iter
from .varianttype import _wrap_variant_type


def wrap_all():
    _wrap_async()
    _wrap_bitset()
    _wrap_menu_attribute_iter()
    _wrap_variant_type()

