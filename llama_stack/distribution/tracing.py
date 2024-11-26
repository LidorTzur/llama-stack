# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.

import asyncio
import inspect
import json
from functools import wraps
from typing import Any, AsyncGenerator, Callable, Type, TypeVar

from pydantic import BaseModel

from llama_stack.providers.utils.telemetry import tracing

T = TypeVar("T")


def serialize_value(value: Any) -> str:
    """Helper function to serialize values to string representation."""
    try:
        if isinstance(value, BaseModel):
            return value.model_dump_json()
        elif isinstance(value, list) and value and isinstance(value[0], BaseModel):
            return json.dumps([item.model_dump_json() for item in value])
        elif hasattr(value, "to_dict"):  # For objects with to_dict method
            return json.dumps(value.to_dict())
        elif isinstance(value, (dict, list, int, float, str, bool)):
            return json.dumps(value)
        else:
            return str(value)
    except Exception:
        return str(value)


def traced(input: str = None):
    """
    A method decorator that enables tracing with input and output capture.

    Args:
        input: Name of the input parameter to capture in traces
    """

    def decorator(method: Callable) -> Callable:
        method._trace_input = input
        return method

    return decorator


def trace_protocol(cls: Type[T]) -> Type[T]:
    """
    A class decorator that automatically traces all methods in a protocol/base class
    and its inheriting classes.
    """

    def trace_method(method: Callable) -> Callable:
        is_async = asyncio.iscoroutinefunction(method)
        is_async_gen = inspect.isasyncgenfunction(method)

        def get_traced_input(args: tuple, kwargs: dict) -> dict:
            trace_input = getattr(method, "_trace_input", None)
            if not trace_input:
                return {}

            # Get the mapping of parameter names to values
            sig = inspect.signature(method)
            bound_args = sig.bind(None, *args, **kwargs)  # None for self
            bound_args.apply_defaults()
            params = dict(list(bound_args.arguments.items())[1:])  # Skip 'self'

            # Return the input value if the key exists
            if trace_input in params:
                return {"input": serialize_value(params[trace_input])}
            return {}

        def create_span_context(self: Any, *args: Any, **kwargs: Any) -> tuple:
            class_name = self.__class__.__name__
            method_name = method.__name__

            span_type = (
                "async_generator" if is_async_gen else "async" if is_async else "sync"
            )
            span_attributes = {
                "class": class_name,
                "method": method_name,
                "type": span_type,
                "args": serialize_value(args),
                **get_traced_input(args, kwargs),
            }

            return class_name, method_name, span_attributes

        @wraps(method)
        async def async_gen_wrapper(
            self: Any, *args: Any, **kwargs: Any
        ) -> AsyncGenerator:
            class_name, method_name, span_attributes = create_span_context(
                self, *args, **kwargs
            )

            with tracing.span(f"{class_name}.{method_name}", span_attributes) as span:
                try:
                    async for item in method(self, *args, **kwargs):
                        yield item
                finally:
                    span.set_attribute("output", "streaming output")

        @wraps(method)
        async def async_wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            class_name, method_name, span_attributes = create_span_context(
                self, *args, **kwargs
            )

            with tracing.span(f"{class_name}.{method_name}", span_attributes) as span:
                try:
                    result = await method(self, *args, **kwargs)
                    span.set_attribute("output", serialize_value(result))
                    return result
                except Exception as e:
                    span.set_attribute("error", str(e))
                    raise

        @wraps(method)
        def sync_wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            class_name, method_name, span_attributes = create_span_context(
                self, *args, **kwargs
            )

            with tracing.span(f"{class_name}.{method_name}", span_attributes) as span:
                try:
                    result = method(self, *args, **kwargs)
                    span.set_attribute("output", serialize_value(result))
                    return result
                except Exception as e:
                    raise

        if is_async_gen:
            return async_gen_wrapper
        elif is_async:
            return async_wrapper
        else:
            return sync_wrapper

    # Store the original __init_subclass__ if it exists
    original_init_subclass = getattr(cls, "__init_subclass__", None)

    # Define a new __init_subclass__ to handle child classes
    def __init_subclass__(cls_child, **kwargs):  # noqa: N807
        # Call original __init_subclass__ if it exists
        if original_init_subclass:
            original_init_subclass(**kwargs)

        traced_methods = {}
        for parent in cls_child.__mro__[1:]:  # Skip the class itself
            for name, method in vars(parent).items():
                if inspect.isfunction(method) and method._trace_input:
                    traced_methods[name] = method._trace_input

        # Trace child class methods if their name matches a traced parent method
        for name, method in vars(cls_child).items():
            if inspect.isfunction(method) and not name.startswith("_"):
                if name in traced_methods:
                    # Copy the trace configuration from the parent
                    method._trace_input = traced_methods[name]

                cls_child.__dict__[name] = trace_method(method)

    # Set the new __init_subclass__
    cls.__init_subclass__ = classmethod(__init_subclass__)

    return cls
