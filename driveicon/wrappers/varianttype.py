from gi.repository.GLib import VariantType

def _variant_type_equal(left: VariantType | None, right: VariantType | None) -> bool:
    if left is None:
        return right is None
    return right is not None and left.equal(right)


def _wrap_variant_type():
    setattr(VariantType, '__eq__', _variant_type_equal)