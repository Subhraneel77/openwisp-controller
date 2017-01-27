from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import ugettext_lazy as _
from sortedm2m.fields import SortedManyToManyField

from django_netjsonconfig.base.config import TemplatesVpnMixin as BaseMixin
from django_netjsonconfig.base.config import AbstractConfig
from django_netjsonconfig.base.template import AbstractTemplate
from django_netjsonconfig.base.vpn import AbstractVpn, AbstractVpnClient

from ..models import OrgMixin, ShareableOrgMixin


class TemplatesVpnMixin(BaseMixin):
    class Meta:
        abstract = True

    @classmethod
    def clean_templates_org(cls, action, instance, pk_set, **kwargs):
        templates = cls.get_templates_from_pk_set(action, pk_set)
        if not templates:
            return templates
        # when using the admin, templates will be a list
        # we need to get the queryset from this list in order to proceed
        if not isinstance(templates, models.QuerySet):
            template_model = cls.templates.rel.model
            pk_list = [template.pk for template in templates]
            templates = template_model.objects.filter(pk__in=pk_list)
        # lookg for invalid templates
        invalids = templates.exclude(organization=instance.organization)\
                            .exclude(organization=None)\
                            .values('name')
        if templates and invalids:
            names = ''
            for invalid in invalids:
                names = '{0}, {1}'.format(names, invalid['name'])
            names = names[2:]
            message = _('The following templates are owned by different '
                        'which do not match the organization of this '
                        'configuration: {0}').format(names)
            raise ValidationError(message)
        # return valid templates in order to save computation
        # in the following operations
        return templates

    @classmethod
    def clean_templates(cls, action, instance, pk_set, **kwargs):
        """
        adds organization validation
        """
        templates = cls.clean_templates_org(action, instance, pk_set, **kwargs)
        # perform validation of configuration (local config + templates)
        super(TemplatesVpnMixin, cls).clean_templates(action, instance, templates, **kwargs)


class Config(OrgMixin, TemplatesVpnMixin, AbstractConfig):
    """
    Concrete Config model
    """
    templates = SortedManyToManyField('config.Template',
                                      related_name='config_relations',
                                      verbose_name=_('templates'),
                                      blank=True,
                                      help_text=_('configuration templates, applied from'
                                                  'first to last'))
    vpn = models.ManyToManyField('config.Vpn',
                                 through='config.VpnClient',
                                 related_name='vpn_relations',
                                 blank=True)

    class Meta(AbstractConfig.Meta):
        abstract = False


class Template(ShareableOrgMixin, AbstractTemplate):
    """
    OpenWISP2 Template model
    """
    vpn = models.ForeignKey('config.Vpn',
                            verbose_name=_('VPN'),
                            blank=True,
                            null=True)

    def clean(self):
        self._validate_org_relation('vpn')

    class Meta(AbstractTemplate.Meta):
        abstract = False


class Vpn(ShareableOrgMixin, AbstractVpn):
    """
    OpenWISP2 VPN model
    """
    ca = models.ForeignKey('pki.Ca', verbose_name=_('Certification Authority'))
    cert = models.ForeignKey('pki.Cert',
                             verbose_name=_('x509 Certificate'),
                             help_text=_('leave blank to create automatically'),
                             blank=True,
                             null=True)

    def clean(self):
        self._validate_org_relation('ca')
        self._validate_org_relation('cert')

    class Meta(AbstractVpn.Meta):
        abstract = False


class VpnClient(AbstractVpnClient):
    """
    m2m through model
    """
    config = models.ForeignKey('config.Config',
                               on_delete=models.CASCADE)
    vpn = models.ForeignKey('config.Vpn',
                            on_delete=models.CASCADE)
    cert = models.OneToOneField('pki.Cert',
                                on_delete=models.CASCADE,
                                blank=True,
                                null=True)

    class Meta(AbstractVpnClient.Meta):
        abstract = False