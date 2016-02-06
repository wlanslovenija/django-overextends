import types

import django
from django.template import base, loader as template_loader

if django.VERSION < (1, 9):
    from django.template.debug import DebugLexer
    base.add_to_builtins("overextends.templatetags.overextends_tags")
else:
    DebugLexer = base.DebugLexer


# We have to monkey-patch Django to pass origins to tokens even when
# TEMPLATE_DEBUG is set to False. This is required to know which
# template is rendering overextends tag and remove it from the template
# search path.
# See https://code.djangoproject.com/ticket/17199#comment:9

base.Lexer = DebugLexer

def make_origin(display_name, loader, name, dirs):
    if display_name:
        return template_loader.LoaderOrigin(display_name, loader, name, dirs)
    else:
        return None

template_loader.make_origin = make_origin

# Django 1.8+.
try:
    from django.template import engine

    # Wrap the function to include a self argument.
    def engine_make_origin(self, *args):
        return make_origin(*args)

    engine.Engine.make_origin = types.MethodType(engine_make_origin, None, engine.Engine)
    engine.Lexer = DebugLexer
except ImportError:
    pass
