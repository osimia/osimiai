from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
import markdown2

register = template.Library()

@register.filter(name='markdown')
@stringfilter
def markdown(value):
    html = markdown2.markdown(
        value,
        extras=["fenced-code-blocks", "code-friendly", "tables", "spoiler"],
    )
    return mark_safe(html)
