from django import template
from django.template.defaultfilters import stringfilter
from django.utils.html import escape
import re

register = template.Library()

@register.filter
@stringfilter
def split(value, arg):
    """
    Splits the string by the given argument.
    
    Example usage: {{ "a/b/c"|split:"/" }}
    """
    return value.split(arg)

@register.filter
@stringfilter
def header_value(value, header):
    """
    Extracts the value after a header in a line.
    
    Example usage: {{ "From: John Doe"|header_value:"From:" }}
    Returns: " John Doe"
    """
    if header in value:
        return value.split(header, 1)[1].strip()
    return value

@register.filter
@stringfilter
def text_to_html(text):
    """
    Converts plain text to HTML, preserving line breaks and whitespace.
    
    Example usage: {{ "Line 1\nLine 2"|text_to_html }}
    Returns: "<p>Line 1<br>Line 2</p>"
    """
    text = escape(text)  # Escape HTML entities
    paragraphs = text.split('\n\n')
    result = []
    for p in paragraphs:
        if p.strip():
            result.append('<p>{}</p>'.format(p.replace('\n', '<br>')))
    return '\n'.join(result)

@register.filter
@stringfilter
def preserve_html(content):
    """
    Ensures HTML content is preserved with all formatting.
    Prevents Django template engine from escaping HTML characters.
    
    Example usage: {{ html_content|preserve_html|safe }}
    """
    # Make sure content doesn't get double-escaped
    return content 