'''Template tags for boxes used in dashboards'''
from django import template

register = template.Library()


@register.inclusion_tag('tools/icon_box.html')
def icon_box(box_class, icon_class, description_class, text, description):
    return {'box_class': box_class, 'icon_class': icon_class, 'description_class': description_class,
            'strong_text': text, 'description': description}


@register.inclusion_tag('tools/big_text_box.html')
def big_text_box(box_class, icon_class, big_text_class, description_class, big_text, description):
    return {'box_class': box_class, 'icon_class': icon_class, 'big_text_class': big_text_class,
            'description_class': description_class, 'big_text': big_text, 'description': description}