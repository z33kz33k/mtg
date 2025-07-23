"""

    mtg.utils.check_type
    ~~~~~~~~~~~~~~~~~~~~
    Type checking decorators.
    Validate types of input arguments of decorated functions (or methods).
    This module provides only basic type validation based on `isinstance()` check.

    @author: z33k

"""
from functools import wraps
from typing import Any, Callable, Iterable, Type


# type aliases
# method with signature def methodname(self, # *args)
type Method = Callable[[Any, tuple[Any, ...]], Any]
# function with signature def funcname(*args)
type Function = Callable[[tuple[Any, ...]], Any]


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
    """Validate ```value`` to be of ``type_`` or ``None``.

    Raises:
        TypeError: on value not being of type_ or None
    """
    if not isinstance(value, type_):
        raise TypeError(
            f"Input value ({value}) can only be of a '{fullqualname(type_)}' type, "
            f"got: '{type(value)}'.")


def _validate_type_or_none(value: Any, type_: Type) -> None:
    """Validate ```value`` to be of ``type_`` or ``None``.

    Raises:
        TypeError: on value not being of type_ or None
    """
    if not (isinstance(value, type_) or value is None):
        raise TypeError(
            f"Input value ({value}) can only be of a '{fullqualname(type_)}' type or "
            f"None, got: '{type(value)}'.")


def _validate_types(value: Any, *types: Type) -> None:
    """Validate ```value`` to be of one of ``types``.

    Raises:
        TypeError: on value not being of one of types
    """
    if not isinstance(value, types):
        namestr = types_to_namestr(types)
        raise TypeError(
            f"Input value ({value}) can only be of either of a [{namestr}] types, got: "
            f"'{type(value)}'.")


def _validate_types_or_none(value: Any, *types: Type) -> None:
    """Validate ```value`` to be of one of ``types`` or ``None``.

    Raises:
        TypeError: on value not being of one of types
    """
    if not (isinstance(value, types) or value is None):
        namestr = types_to_namestr(types)
        raise TypeError(
            f"Input value ({value}) can only be of either of [{namestr}] types or "
            f"None, got: '{type(value)}'.")


def assert_output_not_none(func: Function | Method) -> Function | Method:
    """Assert decorated ``func``'s output is not ``None``.

    Args:
        func: function (or method) to check output of

    Returns:
        checked function (or method)
    """
    @wraps(func)
    def wrap(*args: Any, **kwargs: Any) -> Any:
        output = func(*args, **kwargs)
        assert output is not None, f"{func}'s output mustn't be None."
        return output
    return wrap


def type_checker(
        *positional_types: Type, is_method=False, none_allowed=False,
        **keyword_types: Type) -> Function | Method:
    """Validate decorated function's positional arguments to be of ``positional_types``
    (respectively) and its keyword arguments to be of ``keyword_types``.

    Note:
        Defaults, if specified, have to be passed as keywords arguments. Otherwise, they will be
        treated as types to validate.

        If length of ``positional_types`` doesn't match the length of the arguments, the shorter
        range gets validated. ``keyword_types`` that don't match anything in decorated function's
        keyword arguments are ignored.

    Args:
        positional_types: variable number of expected types of decorated function's arguments
        is_method: True, if the decorated function is a bound method (so its first argument has to be treated differently)
        none_allowed: True, if ``None`` is allowed as a substitute for the given types
        keyword_types: a mapping of decorated function's keyword argument names to their expected types

    Returns:
        validated function (or method)
    """
    def decorate(func: Function | Method) -> Function | Method:
        @wraps(func)
        def wrap(*args: Any, **kwargs: Any) -> Any:
            self = None
            if is_method:
                self, *args = args
            for arg, et in zip(args, positional_types):
                if none_allowed:
                    _validate_type_or_none(arg, et)
                else:
                    _validate_type(arg, et)
            for k, v in kwargs.items():
                if et := keyword_types.get(k):
                    if none_allowed:
                        _validate_type_or_none(v, et)
                    else:
                        _validate_type(v, et)
            if self is not None:
                args = [self, *args]
            return func(*args, **kwargs)
        return wrap
    return decorate


def uniform_type_checker(
        *expected_types: Type, is_method=False, none_allowed=False) -> Function | Method:
    """Validate all of decorated function's positional and keyword arguments to be of one of
    ``expected_types``.

    Note:
        Defaults, if specified, have to be passed as keywords arguments. Otherwise, they will be
        treated as types to validate.

    Args:
        expected_types: variable number of expected types of decorated function's arguments
        is_method: True, if the decorated function is a bound method (so its first argument has to be treated differently)
        none_allowed: True, if ``None`` is allowed as a substitute for the given types

    Returns:
        validated function (or method)
    """
    def decorate(func: Function | Method) -> Function | Method:
        @wraps(func)
        def wrap(*args: Any, **kwargs: Any) -> Any:
            self = None
            if is_method:
                self, *args = args
            for arg in [*args, *kwargs.values()]:
                if none_allowed:
                    _validate_types_or_none(arg, *expected_types)
                else:
                    _validate_types(arg, *expected_types)
            if self is not None:
                args = [self, *args]
            return func(*args, **kwargs)
        return wrap
    return decorate


# TODO: choose arg to validate with optional meta arg 'arg_idx'
def generic_iterable_type_checker(
        *expected_types: Type, is_method=False, none_allowed=False) -> Function | Method:
    """Validate all items of decorated function's first argument to be one of ``expected_types``.

    Note:
        Defaults, if specified, have to be passed as keywords arguments. Otherwise, they will be
        treated as types to validate.

        The first argument of decorated function has to be an iterable or `TypeError` is raised. Any
        other arguments are ignored.

    Args:
        expected_types: variable number of expected types of decorated function's input iterable's items
        is_method: True, if the decorated function is a bound method (so its first argument has to be treated differently)
        none_allowed: True, if ``None`` is allowed as a substitute for the given types

    Returns:
        validated function (or method)
    """
    def decorate(func: Function | Method) -> Function | Method:
        @wraps(func)
        def wrap(*args: Any, **kwargs: Any) -> Any:
            self = None
            if is_method:
                self, *args = args
            if args:
                input_iterable, *args = args
                for item in input_iterable:
                    if none_allowed:
                        _validate_type_or_none(item, *expected_types)
                    else:
                        _validate_types(item, *expected_types)
                args = [input_iterable, *args]
            if self is not None:
                args = [self, *args]
            return func(*args, **kwargs)
        return wrap
    return decorate


# TODO: choose arg to validate with optional meta arg 'arg_idx'
def generic_dict_type_checker(
        key_expected_types: Iterable[Type], value_expected_types: Iterable[Type],
        is_method=False, none_allowed=False) -> Function | Method:
    """Validate all keys and values of decorated function's first argument to be, respectively,
    one of ``key_expected_types`` and one of ``value_expected_types.

    Note:
        Defaults, if specified, have to be passed as keywords arguments. Otherwise, they will be
        treated as types to validate.

        The first argument of decorated function has to be a dictionary or `TypeError` is raised.
        Any other arguments are ignored.

    Args:
        key_expected_types: iterable of expected types of decorated function's input dict's keys
        value_expected_types: iterable of expected types of decorated function's input dict's values
        is_method: True, if the decorated function is a bound method (so its first argument has to be treated differently)
        none_allowed: True, if ``None`` is allowed as a substitue for the given types

    Returns:
        validated function (or method)
    """
    def decorate(func: Function | Method) -> Function | Method:
        @wraps(func)
        def wrap(*args: Any, **kwargs: Any) -> Any:
            self = None
            if is_method:
                self, *args = args
            if args:
                input_dict, *args = args
                _validate_type(input_dict, dict)
                for k, v in input_dict.items():
                    if none_allowed:
                        _validate_type_or_none(k, *key_expected_types)
                        _validate_type_or_none(v, *value_expected_types)
                    else:
                        _validate_types(k, *key_expected_types)
                        _validate_types(v, *value_expected_types)
                args = [input_dict, *args]
            if self is not None:
                args = [self, *args]
            return func(*args, **kwargs)
        return wrap
    return decorate
