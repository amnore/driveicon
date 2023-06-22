import asyncio
from typing import Iterable
from functools import partialmethod, partial

from gi.repository import GLib, Gio, GObject


def _find_async_methods_with_async_suffix(cls) -> Iterable[tuple[str, str, str]]:
    for begin_method in filter(lambda n: n.endswith('_async'), dir(cls)):
        prefix = begin_method[:-6]
        finish_method = prefix + '_finish'
        if hasattr(cls, finish_method):
            yield begin_method, finish_method, prefix + '_asyncio'


def _find_async_methods_with_finish_suffix(cls) -> Iterable[tuple[str, str, str]]:
    for finish_method in filter(lambda n: n.endswith('_finish'), dir(cls)):
        begin_method = finish_method[:-7]
        if hasattr(cls, begin_method):
            yield begin_method, finish_method, begin_method + '_asyncio'


def _wrap_gio(target, begin_method: str, finish_method: str, wrapped_method: str, default_params = None):
    if default_params is None:
        default_params = {}

    async_begin = getattr(target, begin_method)
    async_finish = getattr(target, finish_method)

    class Wrapper:
        def __init__(self, async_begin, async_finish, default_params):
            self.__async_begin = async_begin
            self.__async_finish = async_finish
            self.__default_params = default_params

        def __call__(self, *args, **kwargs) -> asyncio.Future:
            future = asyncio.get_event_loop().create_future()
            async_begin(
                *args,
                **(default_params | kwargs),
                cancellable=None,
                callback=partial(self.__finish_callback, future),
            )

            return future

        def __finish_callback(self, future: asyncio.Future, obj: GObject.Object, result: Gio.AsyncResult):
            try:
                ret = self.__async_finish(obj, result)
                future.set_result(ret)
            except Exception as e:
                future.set_exception(e)

    wrapper = Wrapper(async_begin, async_finish, default_params)
    setattr(target, wrapped_method, partialmethod(wrapper))


def _wrap_async():
    classes_with_async_suffix = [Gio.File, Gio.FileEnumerator]
    classes_with_finish_suffix = [Gio.Drive, Gio.Volume, Gio.Mount]

    io_priority_param = ('io_priority', GLib.PRIORITY_DEFAULT)
    class_extra_params = {
        Gio.File: dict([io_priority_param]),
        Gio.FileEnumerator: dict([io_priority_param]),
    }

    class_lists = [classes_with_async_suffix, classes_with_finish_suffix]
    find_method_lists = [_find_async_methods_with_async_suffix, _find_async_methods_with_finish_suffix]

    for class_list, find_method in zip(class_lists, find_method_lists):
        for cls in class_list:
            extra_params = class_extra_params.get(cls, {})
            for method_spec in find_method(cls):
                _wrap_gio(cls, *method_spec, extra_params)
