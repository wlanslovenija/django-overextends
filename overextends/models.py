
# This app doesn't contain any models, but as its template tags need to
# be added to built-ins at start-up time, this is a good place to do it.

from django.template.base import add_to_builtins


add_to_builtins("overextends.templatetags.overextends_tags")

from django.template import base, debug, loader as template_loader

# We have to monkey-patch Django to pass origins to tokens even when
# TEMPLATE_DEBUG is set to False. This is required to know which
# template is rendering overextends tag and remove it from the template
# search path.
# See https://code.djangoproject.com/ticket/17199#comment:9

base.Lexer = debug.DebugLexer

def make_origin(display_name, loader, name, dirs):
    if display_name:
        return template_loader.LoaderOrigin(display_name, loader, name, dirs)
    else:
        return None

template_loader.make_origin = make_origin
