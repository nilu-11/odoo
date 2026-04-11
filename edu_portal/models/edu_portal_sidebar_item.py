"""Portal sidebar navigation registry.

Seeded by built-in XML data (portal_sidebar_data.xml) and extended by
bridge modules adding more sidebar items. Read once per request by
controllers/helpers.py::_resolve_portal_registry.
"""
from odoo import fields, models


class EduPortalSidebarItem(models.Model):
    _name = 'edu.portal.sidebar.item'
    _description = 'Portal Sidebar Item'
    _order = 'sequence, id'

    # ═══ Identity / Core ═══
    key = fields.Char(
        string='Key',
        required=True,
        help="Stable identifier used for active-state highlighting.",
    )
    label = fields.Char(
        string='Label',
        required=True,
        translate=True,
    )
    icon = fields.Char(
        string='Icon',
        help="Unicode glyph or class name rendered as the sidebar icon.",
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    url = fields.Char(
        string='URL',
        required=True,
        help="Target route, e.g. /portal/teacher/home",
    )

    # ═══ Scope ═══
    role = fields.Selection(
        selection=[
            ('teacher', 'Teacher'),
            ('student', 'Student'),
            ('parent',  'Parent'),
            ('all',     'All'),
        ],
        string='Role',
        required=True,
        default='all',
    )
    active = fields.Boolean(default=True)

    # ═══ Dynamic resolution ═══
    visibility_method = fields.Char(
        string='Visibility Method',
        help=(
            "Optional dotted path 'model.method'. Called as "
            "self.env[model].method(); must return bool. "
            "Silently skipped if model/method missing."
        ),
    )
    badge_method = fields.Char(
        string='Badge Method',
        help=(
            "Optional dotted path 'model.method'. Called as "
            "self.env[model].method(); must return int or str. "
            "Silently skipped if model/method missing."
        ),
    )

    _sql_constraints = [
        ('uniq_key_role',
         'UNIQUE(key, role)',
         'Sidebar item key must be unique per role.'),
    ]
