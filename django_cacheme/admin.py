from django import forms
from django.contrib import admin
from .models import Invalidation
from .cache_model import CacheMe as cacheme


def get_cache_tags():
    return [(i, i) for i in cacheme.tags.keys()]


class InvalidationForm(forms.ModelForm):

    invalid_tags = forms.MultipleChoiceField(
        choices=get_cache_tags,
        label="Tags",
        required=False,
        widget=forms.CheckboxSelectMultiple()
    )

    class Meta:
        model = Invalidation
        fields = ('user', 'created', 'pattern', 'invalid_tags')


@admin.register(Invalidation)
class InvalidationAdmin(admin.ModelAdmin):
    list_display = ('user', 'pattern', 'created')
    form = InvalidationForm
    fields = ('user', 'created', 'pattern', 'invalid_tags')

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj:
            tags = obj.tags.split(',')
            form.declared_fields['invalid_tags'].initial = tags
            form.declared_fields['invalid_tags'].disabled = True
        return form

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('user', 'pattern', 'created')
        return ('user', 'created')

    def save_model(self, request, obj, form, change):
        obj.user = request.user
        tags = form.cleaned_data['invalid_tags']
        obj.tags = ','.join(tags)
        super().save_model(request, obj, form, change)
