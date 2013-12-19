# -*- coding: utf-8 -*-

"""Utilities for go.vumitools tests."""

from vumi.persist.fields import (
    ForeignKeyProxy, ManyToManyProxy, DynamicProxy, ListProxy)


def field_eq(f1, f2):
    if f1 == f2:
        return True
    if isinstance(f1, ManyToManyProxy) and isinstance(f2, ManyToManyProxy):
        return f1.keys() == f2.keys()
    if isinstance(f1, ForeignKeyProxy) and isinstance(f2, ForeignKeyProxy):
        return f1.key == f2.key
    if isinstance(f1, DynamicProxy) and isinstance(f2, DynamicProxy):
        return f1.items() == f2.items()
    if isinstance(f1, ListProxy) and isinstance(f2, ListProxy):
        return list(f1) == list(f2)
    return False


def model_eq(m1, m2):
    fields = m1.field_descriptors.keys()
    if fields != m2.field_descriptors.keys():
        return False
    if m1.key != m2.key:
        return False
    for field in fields:
        if not field_eq(getattr(m1, field), getattr(m2, field)):
            return False
    return True
