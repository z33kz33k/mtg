"""

    mtgcards.utils.validate.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Type validating decorators.

    Validate input positional arguments' type of function and methods.

    This module provides only basic type validation based on `isintance()` check.

    TODO: improve this (e.g. handle passing kwargs to decorators - that would also probably cut
        down the number of needed functions drastically)

"""
from functools import wraps
from typing import Any, Dict, Iterable, Type

from mtgcards.const import Method, Function, T, MethodGeneric, FunctionGeneric


def fullqualname(class_: Type) -> str:
    """Return fully qualified name of ``class_``.

    Example: 'builtins.int'
    """
    return f"{class_.__module__}.{class_.__name__}"


def types_to_namestr(types: Iterable[Type]) -> str:
    """Convert ``types`` to a string representation using their fully qualified names.

    Example: '[builtins.str, builtins.int, builtins.float]'
    """
    return ", ".join([fullqualname(t) for t in types])


def _validate_type(value: Any, type_: Type) -> None:
    """Validate ```value`` to be of ``type_``.

    :raises TypeError: on value not being of type_
    """
    if not isinstance(value, type_):
        raise TypeError(f"Input value can only be of a '{fullqualname(type_)}' type, "
                        f"got: '{type(value)}'.")


def _validate_type_or_none(value: Any, type_: Type) -> None:
    """Validate ```value`` to be of ``type_`` or ``None``.

    :raises TypeError: on value not being of type_ or None
    """
    if not (isinstance(value, type_) or value is None):
        raise TypeError(f"Input value can only be of a '{fullqualname(type_)}' type or None, "
                        f"got: '{type(value)}'.")


def _validate_types(value: Any, *types: Type) -> None:
    """Validate ```value`` to be of one of ``types``.

    :raises TypeError: on value not being of one of types
    """
    if not isinstance(value, types):
        namestr = types_to_namestr(types)
        raise TypeError(f"Input value can only be of either of a [{namestr}] types, "
                        f"got: '{type(value)}'.")


def _validate_types_or_none(value: Any, *types: Type) -> None:
    """Validate ```value`` to be of one of ``types`` or ``None``.

    :raises TypeError: on value not being of one of types
    """
    if not (isinstance(value, types) or value is None):
        namestr = types_to_namestr(types)
        raise TypeError(f"Input value can only be of either of [{namestr}] types or None, "
                        f"got: '{type(value)}'.")


def validate_method_input_types(*expected_types: Type) -> Method:
    """Validate decorated method's positional arguments to be of ``expected_types`` (respectively).

    .. note:: Any keyword arguments are ignored.

    If length of `expected_types` doesn't match the length of the arguments,
    the shorter range is validated.

    :param expected_types: variable number of expected types of method's arguments
    :return: validated method
    """
    def decorate(method: Method) -> Method:
        @wraps(method)
        def wrap(self: Any, *args: Any, **kwargs) -> Any:
            for arg, et in zip(args, expected_types):
                _validate_type(arg, et)
            return method(self, *args, **kwargs)
        return wrap
    return decorate


def validate_method_input_types_or_none(*expected_types: Type) -> Method:
    """Validate decorated method's positional arguments to be of ``expected_types``
    (respectively) or None.

    .. note:: Any keyword arguments are ignored.

    If length of `expected_types` doesn't match the length of the arguments,
    the shorter range is validated.

    :param expected_types: variable number of expected types of method's arguments
    :return: validated method
    """
    def decorate(method: Method) -> Method:
        @wraps(method)
        def wrap(self: Any, *args: Any, **kwargs) -> Any:
            for arg, et in zip(args, expected_types):
                _validate_type_or_none(arg, et)
            return method(self, *args, **kwargs)
        return wrap
    return decorate


def validate_method_uniform_input_type(expected_type: Type) -> Method:
    """Validate all of decorated method's positional arguments to be of ``expected_type``.

    .. note:: Any keyword arguments are ignored.

    :param expected_type: expected type of method's arguments
    :return: validated method
    """
    def decorate(method: Method) -> Method:
        @wraps(method)
        def wrap(self: Any, *args: Any, **kwargs) -> Any:
            for arg in args:
                _validate_type(arg, expected_type)
            return method(self, *args, **kwargs)
        return wrap
    return decorate


def validate_method_uniform_input_types(*expected_types: Type) -> Method:
    """Validates all of decorated method's positional arguments to be of either of
    ``expected_types``.

    .. note:: Any keyword arguments are ignored.

    :param expected_types: variable number of expected types of method's arguments
    :return: validated method
    """
    def decorate(method: Method) -> Method:
        @wraps(method)
        def wrap(self: Any, *args: Any, **kwargs) -> Any:
            for arg in args:
                _validate_types(arg, *expected_types)
            return method(self, *args, **kwargs)
        return wrap
    return decorate


def validate_method_uniform_input_types_or_none(*expected_types: Type) -> Method:
    """Validate all of decorated method's positional arguments to be either of ``expected_types``
    or ``None``.

    .. note:: Any keyword arguments are ignored.

    :param expected_types: variable number of expected types of method's arguments
    :return: validated method
    """
    def decorate(method: Method) -> Method:
        @wraps(method)
        def wrap(self: Any, *args: Any, **kwargs) -> Any:
            for arg in args:
                _validate_types_or_none(arg, *expected_types)
            return method(self, *args, **kwargs)
        return wrap
    return decorate


def validate_method_input_iterable_generic_types(*expected_types: Type) -> Method:
    """Validate all of decorated method's input iterable's items to be of one of ``expected_types``.

    .. note:: The first argument has to be an iterable or `TypeError` is raised. Any other
    arguments are ignored.

    :param expected_types: variable number of expected types of input iterable's items
    :return: validated method
    """
    def decorate(method: Method) -> Method:
        @wraps(method)
        def wrap(self: Any, input_iterable: Iterable[Any], *args, **kwargs) -> Any:
            for item in input_iterable:
                _validate_types(item, *expected_types)
            return method(self, input_iterable, *args, **kwargs)
        return wrap
    return decorate


def validate_method_input_iterable_generic_types_or_none(*expected_types: Type) -> Method:
    """Validate all of decorated method's input iterable's items to be of one of
    ``expected_types`` or None.

    .. note:: The first argument has to be an iterable or `TypeError` is raised. Any other
    arguments are ignored.

    :param expected_types: variable number of expected types of input iterable's items
    :return: validated method
    """
    def decorate(method: Method) -> Method:
        @wraps(method)
        def wrap(self: Any, input_iterable: Iterable[Any], *args, **kwargs) -> Any:
            for item in input_iterable:
                _validate_types_or_none(item, *expected_types)
            return method(self, input_iterable, *args, **kwargs)
        return wrap
    return decorate


def validate_method_input_dict_generic_type(keytype: Type, valuetype: Type) -> Method:
    """Validate all of decorated method's input dict's keys to be of ``keytype`` and values to be
    of ``valuetype`.

    .. note:: The first argument has to be a dictionary or `TypeError` is raised. Any other
    arguments are ignored.

    :param keytype: expected type of input dict's keys
    :param valuetype: expected type of input dict's values
    :return: validated method
    """
    def decorate(method: Method) -> Method:
        @wraps(method)
        def wrap(self: Any, input_dict: Dict[keytype, valuetype], *args, **kwargs) -> Any:
            _validate_type(input_dict, dict)
            for k, v in input_dict.items():
                _validate_type(k, keytype)
                _validate_type(v, valuetype)
            return method(self, input_dict, *args, **kwargs)
        return wrap
    return decorate


def validate_func_input_types(*expected_types: Type) -> Function:
    """Validate decorated function's positional arguments to be of ``expected_types``
    (respectively).

    .. note:: Any keyword arguments are ignored.

    If length of `expected_types` doesn't match the length of the arguments,
    the shorter range is validated.

    :param expected_types: variable number of expected types of function's arguments
    :return: validated function
    """
    def decorate(func: Function) -> Function:
        @wraps(func)
        def wrap(*args: Any, **kwargs) -> Any:
            for arg, et in zip(args, expected_types):
                _validate_type(arg, et)
            return func(*args, **kwargs)
        return wrap
    return decorate


def validate_func_input_types_or_none(*expected_types: Type) -> Function:
    """Validate decorated function's positional arguments to be of ``expected_types``
    (respectively) or None.

    .. note:: Any keyword arguments are ignored.

    If length of `expected_types` doesn't match the length of the arguments,
    the shorter range is validated.

    :param expected_types: variable number of expected types of function's arguments
    :return: validated function
    """
    def decorate(func: Function) -> Function:
        @wraps(func)
        def wrap(*args: Any, **kwargs) -> Any:
            for arg, et in zip(args, expected_types):
                _validate_type_or_none(arg, et)
            return func(*args, **kwargs)
        return wrap
    return decorate


def validate_func_uniform_input_type(expected_type: Type) -> Function:
    """Validate all of decorated function's positional arguments to be of ``expected_type``.

    .. note:: Any keyword arguments are ignored.

    :param expected_type: expected type of other function's arguments
    :return: validated function
    """
    def decorate(func: Function) -> Function:
        @wraps(func)
        def wrap(*args: Any, **kwargs) -> Any:
            for arg in args:
                _validate_type(arg, expected_type)
            return func(*args, **kwargs)
        return wrap
    return decorate


def validate_func_uniform_input_types(*expected_types: Type) -> Function:
    """Validates all of decorated function's positional arguments to be either of
    ``expected_types``.

    .. note:: Any keyword arguments are ignored.

    :param expected_types: variable number of expected types of other function's arguments
    :return: validated function
    """
    def decorate(func: Function) -> Function:
        @wraps(func)
        def wrap(*args: Any, **kwargs) -> Any:
            for arg in args:
                _validate_types(arg, *expected_types)
            return func(*args, **kwargs)
        return wrap
    return decorate


def validate_func_input_iterable_generic_types(*expected_types: Type) -> Function:
    """Validate all of decorated function's input iterable's items to be one of ``expected_types``.

    .. note:: The first argument has to be an iterable or `TypeError` is raised. Any other
    arguments are ignored.

    :param expected_types: variable number of expected types of input iterable's items
    :return: validated function
    """
    def decorate(func: Function) -> Function:
        @wraps(func)
        def wrap(input_iterable: Iterable[Any], *args, **kwargs) -> Any:
            for item in input_iterable:
                _validate_types(item, *expected_types)
            return func(input_iterable, *args, **kwargs)
        return wrap
    return decorate


def validate_func_input_iterable_generic_types_or_none(*expected_types: Type) -> Function:
    """Validate all of decorated function's input iterable's items to be of one of``expected_types``
    or None.

    .. note:: The first argument has to be an iterable or `TypeError` is raised. Any other
    arguments are ignored.

    :param expected_types: variable number of expected types of input iterable's items
    :return: validated function
    """
    def decorate(func: Function) -> Function:
        @wraps(func)
        def wrap(input_iterable: Iterable[Type], *args, **kwargs) -> Any:
            for item in input_iterable:
                _validate_types_or_none(item, *expected_types)
            return func(input_iterable, *args, **kwargs)
        return wrap
    return decorate


def validate_func_input_dict_generic_type(keytype: Type, valuetype: Type) -> Function:
    """Validate all of decorated function's input dict's keys to be of ``keytype`` and values to be
    of ``valuetype`.

    .. note:: The first argument has to be a dictionary or `TypeError` is raised. Any other
    arguments are ignored.

    :param keytype: expected type of input dict's keys
    :param valuetype: expected type of input dict's values
    :return: validated function
    """
    def decorate(func: Function) -> Function:
        @wraps(func)
        def wrap(input_dict: Dict[keytype, valuetype], *args, **kwargs) -> Any:
            _validate_type(input_dict, dict)
            for k, v in input_dict.items():
                _validate_type(k, keytype)
                _validate_type(v, valuetype)
            return func(input_dict, *args, **kwargs)
        return wrap
    return decorate


def assert_method_output_not_none(method: MethodGeneric) -> MethodGeneric:
    """Assert decorated ``method``'s output is not ``None``.

    :param method: method to check output of
    :return: checked method
    """
    @wraps(method)
    def wrap(self: Any, *args: T, **kwargs: T) -> T:
        output = method(self, *args, **kwargs)
        assert output is not None, "output mustn't be None"
        return output
    return wrap


def assert_func_output_not_none(func: FunctionGeneric) -> FunctionGeneric:
    """Assert decorated ``func``'s output is not ``None``.

    :param func: function to check output of
    :return: checked function
    """
    @wraps(func)
    def wrap(*args: T, **kwargs: T) -> T:
        output = func(*args, **kwargs)
        assert output is not None, "output mustn't be None"
        return output
    return wrap
