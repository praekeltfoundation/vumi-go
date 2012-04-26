from django import forms


def padded_queryset(queryset, size=6, padding=None):
    nr_of_results = queryset.count()
    if nr_of_results >= size:
        return queryset[:size]

    filler = [padding] * (size - nr_of_results)
    results = list(queryset)
    results.extend(filler)
    return results


def make_read_only_form(form):
    """turn all fields in a form readonly"""
    for field_name, field in form.fields.items():
        widget = field.widget
        if isinstance(widget,
                (forms.RadioSelect, forms.CheckboxSelectMultiple)):
            widget.attrs.update({
                'disabled': 'disabled'
            })
        else:
            widget.attrs.update({
                'readonly': 'readonly'
            })
    return form
