from cacheme import nodes
from cacheme.nodes import Node, Field
from django.db.models import Model
from django.db.models.signals import m2m_changed, post_delete, post_save


model_signals = {}


def invalid_cache(sender, instance, created=False, **kwargs):
    if 'pre_' in kwargs.get('action', ''):
        return

    InvalidNode = model_signals[sender]
    if InvalidNode.meta.get('m2m') and 'pk_set' in kwargs:  # m2m signal
        field_from = InvalidNode.m2m_models.get(instance.__class__)
        field_to = InvalidNode.m2m_models.get(kwargs['model'])
        if field_from and field_to:
            InvalidNode.objects.invalid(**{field_from: instance})
            pks = kwargs['pk_set']
            for pk in pks:
                InvalidNode.objects.invalid(**{field_to: pk})
    # elif InvalidNode.meta.get('m2m'):  # post save/delete signal for m2m
    #     fields = InvalidNode.fields
    #     for field in fields:
    #         InvalidNode.objects.invalid(**{field: getattr(instance, field)})
    else:  # normal post save/delete signal
        InvalidNode.objects.invalid(instance=instance)


class ModelInvalidNode(nodes.InvalidNode):
    _meta_fields = ('model', 'm2m')

    def __init__(self, **kwargs):
        if self.meta.get('m2m'):
            self._init_m2m(kwargs)
        else:
            self._init_simple_model(kwargs)

        super().__init__(**kwargs)

    def _init_simple_model(self, kwargs):
        if 'instance' in kwargs and isinstance(kwargs['instance'], Model):
            for field in self.required_fields.keys():
                kwargs[field] = getattr(kwargs['instance'], field)

    def _init_m2m(self, kwargs):
        for field in self.required_fields.keys():
            value = kwargs.get(field, None)
            if value and type(value) in (int, str):
                continue
            elif value and isinstance(value, Model):
                kwargs[field] = value.pk
            elif value:
                raise Exception(
                    'value for field {field} should be instance or int/string'.format(field)
                )
            else:
                kwargs[field] = 'all'

    @classmethod
    def _update_class(cls):
        if 'model' in cls.meta:
            model = cls.meta['model']
            if model in model_signals:
                raise Exception(
                    'invalid node {node} using {model} already exists'.format(
                        node=model_signals['model'],
                        model=model
                    )
                )
            model_signals[model] = cls
            if cls.meta.get('m2m', False):
                cls.m2m_models = dict()
                for field in cls.required_fields.keys():
                    model_field = model._meta.get_field(field)
                    field_model = model_field.related_model
                    cls.m2m_models[field_model] = field

                # post_save/delete not support now
                # post_save.connect(invalid_cache, model)
                # post_delete.connect(invalid_cache, model)
                m2m_changed.connect(invalid_cache, model)
            else:
                post_save.connect(invalid_cache, model)
                post_delete.connect(invalid_cache, model)
