
import os

from django import template
from django.template import Template, TemplateSyntaxError, TemplateDoesNotExist
from django.template.loader_tags import ExtendsNode
from django.template.loader import find_template, get_template_from_string, LoaderOrigin


register = template.Library()


class OverExtendsNode(ExtendsNode):
    """
    Allows the template ``foo/bar.html`` to extend ``foo/bar.html``,
    given that there is another version of it that can be loaded. This
    allows templates to be created in a project that extend their app
    template counterparts, or even app templates that extend other app
    templates with the same relative name/path.

    We use our own version of ``find_template``, that uses an explict
    list of template directories to search for the template, based on
    the directories that the known template loaders
    (``app_directories`` and ``filesystem``) use. This list gets stored
    in the template context, and each time a template is extended, its
    absolute path gets removed from the list, so that subsequent
    searches for the same relative name/path can find parent templates
    in other directories, which allows circular inheritance to occur.

    Django's ``app_directories``, ``filesystem``, and ``cached``
    loaders are supported. The ``eggs`` loader, and any other loaders
    which use and set ``LoaderOrigin`` should also theoretically work.
    """

    context_name = "OVEREXTENDS_DIRS"

    def __init__(self, nodelist, parent_name, template_name, template_path, template_dirs=None):
        super(OverExtendsNode, self).__init__(nodelist, parent_name, template_dirs)

        self.template_name = template_name
        self.template_path = template_path

    def populate_context(self, context):
        """
        Store a dictionary in the template context mapping template
        names to the lists of template directories available to
        search for that template. Each time a template is extended, its
        origin directory is removed from its directories list.
        """

        # These imports want settings, which aren't available when this
        # module is imported to ``add_to_builtins``, so do them here.
        from django.template.loaders.app_directories import app_template_dirs
        from django.conf import settings

        if self.context_name not in context:
            context[self.context_name] = {}
        if self.template_name not in context[self.context_name]:
            all_dirs = list(settings.TEMPLATE_DIRS) + list(app_template_dirs)
            # os.path.abspath is needed under uWSGI, and also ensures we
            # have consistent path separators across different OSes.
            context[self.context_name][self.template_name] = list(map(os.path.abspath, all_dirs))

    def remove_template_path(self, context):
        """
        Remove template's absolute path from the context dict so
        that it won't be used again when the same relative name/path
        is requested.
        """

        remove_path = os.path.abspath(self.template_path[:-len(self.template_name) - 1])
        # The following should always succeed otherwise we have some unsupported
        # configuration - template was loaded from a source which was not added in
        # populate_context.
        context[self.context_name][self.template_name].remove(remove_path)

    def find_template(self, template_name, context):
        """
        Wrapper for Django's ``find_template`` that uses the current
        template context to keep track of which template directories have
        already been used when finding a template and skips them.
        This allows multiple templates with the same relative name/path to
        be discovered, so that circular template inheritance cannot occur.
        """

        dirs = context[self.context_name].get(template_name, None)
        return find_template(template_name, dirs)

    def get_parent(self, context):
        """
        Same as Django's ``get_parent``, only calling our ``get_template``.
        """

        parent = self.parent_name.resolve(context)
        if not parent:
            error_msg = "Invalid template name in 'extends' tag: %r." % parent
            if self.parent_name.filters or\
                    isinstance(self.parent_name.var, Variable):
                error_msg += " Got this from the '%s' variable." %\
                    self.parent_name.token
            raise TemplateSyntaxError(error_msg)
        if hasattr(parent, 'render'):
            return parent # parent is a Template object
        return self.get_template(parent, context)

    def get_template(self, template_name, context):
        """
        Similar to Django's ``get_template``, but tracking used template
        directories.
        """

        self.populate_context(context)
        self.remove_template_path(context)
        template, origin = self.find_template(template_name, context)
        if not hasattr(template, 'render'):
            # template needs to be compiled
            template = get_template_from_string(template, origin, template_name)
        return template

@register.tag
def overextends(parser, token):
    """
    Extended version of Django's ``extends`` tag that allows circular
    inheritance to occur, eg a template can both be overridden and
    extended at once.
    """

    bits = token.split_contents()

    template_name = None
    template_path = None
    if hasattr(token, 'source'):
        origin, source = token.source
        if isinstance(origin, LoaderOrigin):
            template_name = origin.loadname
            template_path = origin.name

    if template_name is None or template_path is None:
        raise TemplateSyntaxError("'%s' can only be used with templates loaded by template loaders using and setting 'LoaderOrigin'" % bits[0])

    if len(bits) != 2:
        raise TemplateSyntaxError("'%s' takes one argument" % bits[0])
    parent_name = parser.compile_filter(bits[1])
    nodelist = parser.parse()
    if nodelist.get_nodes_by_type(ExtendsNode):
        raise TemplateSyntaxError("'%s' cannot appear more than once "
                                  "in the same template" % bits[0])
    return OverExtendsNode(nodelist, parent_name, template_name, template_path)
