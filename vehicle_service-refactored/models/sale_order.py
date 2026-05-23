from odoo import models, fields, api, _

# Sequences per category for section lines
SECTION_SEQUENCES = {
    'labor': 1,
    'parts': 101,
    'third_party': 201,
    'supplies': 301,
    'others': 401,
}

SECTION_LABELS = {
    'labor': 'Labor',
    'parts': 'Parts',
    'third_party': 'Third Party',
    'supplies': 'Supplies',
    'others': 'Others',
}


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # -------------------------------------------------------------------------
    # Fields
    # -------------------------------------------------------------------------

    service_type = fields.Selection([
        ('sale', 'Normal Sale'),
        ('repair', 'Repair Order'),
    ], string='Service Type', default='repair', required=True)

    repair_status = fields.Selection([
        ('diagnosis', 'Diagnosis'),
        ('waiting_parts', 'Waiting for Parts'),
        ('in_progress', 'In Progress'),
        ('ready', 'Ready for Delivery'),
        ('delivered', 'Delivered'),
    ], string='Repair Status', tracking=True, default='diagnosis')

    vehicle_id = fields.Many2one(
        'workshop.vehicle',
        string='Vehicle',
        domain="[('partner_id', '=', partner_id)]",
    )

    vehicle_brand = fields.Char(related='vehicle_id.brand', string='Brand')
    vehicle_model = fields.Char(related='vehicle_id.model_name', string='Model')
    vehicle_year = fields.Integer(related='vehicle_id.year', string='Year')
    vehicle_color = fields.Char(related='vehicle_id.color', string='Color')

    current_mileage = fields.Integer(string='Mileage')
    fuel_level = fields.Selection([
        ('0', '0%'), ('25', '25%'), ('50', '50%'),
        ('75', '75%'), ('100', '100%'),
    ], string='Fuel Level', default='50')
    reception_date = fields.Datetime(string='Reception Date', default=fields.Datetime.now)
    reception_accepted = fields.Boolean(string='Reception Accepted')
    reception_accepted_date = fields.Datetime(string='Acceptance Date')

    bodywork_status = fields.Text(string='Bodywork Status')
    accessories_included = fields.Char(string='Accessories')
    dash_warning_lights = fields.Char(string='Dashboard Warning Lights')
    symptom_description = fields.Text(string='Symptom / Fault Description')
    max_authorized_budget = fields.Float(string='Maximum Authorized Budget')

    # One2many per category — filtered views for each repair tab
    labor_line_ids = fields.One2many(
        'sale.order.line', 'order_id', string='Labor Lines',
        domain=[('line_category', '=', 'labor'), ('display_type', '=', False)],
    )
    parts_line_ids = fields.One2many(
        'sale.order.line', 'order_id', string='Parts Lines',
        domain=[('line_category', '=', 'parts'), ('display_type', '=', False)],
    )
    third_party_line_ids = fields.One2many(
        'sale.order.line', 'order_id', string='Third-party Lines',
        domain=[('line_category', '=', 'third_party'), ('display_type', '=', False)],
    )
    supplies_line_ids = fields.One2many(
        'sale.order.line', 'order_id', string='Supplies Lines',
        domain=[('line_category', '=', 'supplies'), ('display_type', '=', False)],
    )
    other_line_ids = fields.One2many(
        'sale.order.line', 'order_id', string='Other Lines',
        domain=[('line_category', '=', 'others'), ('display_type', '=', False)],
    )

    # -------------------------------------------------------------------------
    # Onchange
    # -------------------------------------------------------------------------

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Clear vehicle when partner changes to avoid orphan references."""
        self.ensure_one()
        if self.vehicle_id and self.vehicle_id.partner_id != self.partner_id:
            self.vehicle_id = False

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _prepare_repair_section_line(self, category):
        """Return vals dict for a section line of the given category."""
        return {
            'display_type': 'line_section',
            'sequence': SECTION_SEQUENCES.get(category, 1000),
            'name': SECTION_LABELS.get(category, category),
            'product_id': False,
            'product_uom_id': False,
            'product_uom_qty': 0,
            'discount': 0,
            'price_unit': 0,
            'line_category': category,
        }

    def _repair_section_commands(self):
        """Return ORM commands to create all repair section lines."""
        return [
            (0, 0, self._prepare_repair_section_line(cat))
            for cat in SECTION_SEQUENCES
        ]

    def _ensure_repair_sections(self):
        """Create any missing section lines for repair orders (batch-safe)."""
        SaleOrderLine = self.env['sale.order.line']
        for order in self.filtered(lambda o: o.service_type == 'repair'):
            existing_cats = order.order_line.filtered(
                lambda l: l.display_type == 'line_section'
            ).mapped('line_category')
            missing = [
                cat for cat in SECTION_SEQUENCES if cat not in existing_cats
            ]
            if missing:
                SaleOrderLine.create([
                    dict(self._prepare_repair_section_line(cat), order_id=order.id)
                    for cat in missing
                ])

    def _remove_repair_sections(self):
        """Remove all repair section lines (called when switching to normal sale)."""
        section_lines = self.order_line.filtered(
            lambda l: l.display_type == 'line_section'
            and l.line_category in SECTION_SEQUENCES
        )
        section_lines.unlink()

    # -------------------------------------------------------------------------
    # ORM overrides
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('service_type') == 'repair':
                # Assign RO sequence only if name is still the default placeholder
                if vals.get('name', _('New')) == _('New'):
                    vals['name'] = (
                        self.env['ir.sequence'].next_by_code('workshop.repair.order')
                        or _('New')
                    )
                # Prepend section lines only when none exist yet
                order_lines = vals.get('order_line', [])
                has_sections = any(
                    (isinstance(line, dict) and line.get('display_type') == 'line_section')
                    or (
                        isinstance(line, (list, tuple))
                        and len(line) >= 3
                        and line[0] == 0
                        and isinstance(line[2], dict)
                        and line[2].get('display_type') == 'line_section'
                    )
                    for line in order_lines
                )
                if not has_sections:
                    vals['order_line'] = self._repair_section_commands() + order_lines
        return super().create(vals_list)

    def write(self, vals):
        result = super().write(vals)
        if 'service_type' not in vals:
            return result
        repair_orders = self.filtered(lambda o: o.service_type == 'repair')
        sale_orders = self - repair_orders
        repair_orders._ensure_repair_sections()
        sale_orders._remove_repair_sections()
        return result

    # -------------------------------------------------------------------------
    # Report helper
    # -------------------------------------------------------------------------

    def _get_order_lines_to_report(self):
        res = super()._get_order_lines_to_report()
        if self.service_type != 'repair':
            return res
        # Remove section lines whose category has no detail lines
        detail_cats = res.filtered(lambda l: not l.display_type).mapped('line_category')
        empty_sections = res.filtered(
            lambda l: l.display_type == 'line_section'
            and l.line_category not in detail_cats
        )
        return res - empty_sections

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def action_open_reception_form(self):
        self.ensure_one()
        return {
            'name': _('Reception'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'view_id': self.env.ref('vehicle_service.view_sale_order_reception_form').id,
            'res_id': self.id,
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit'},
        }

    def action_print_reception_form(self):
        self.ensure_one()
        return self.env.ref('vehicle_service.action_report_reception_document').report_action(self)

    def action_send_reception_email(self):
        self.ensure_one()
        template = self.env.ref('vehicle_service.email_template_reception')
        compose_form = self.env.ref('mail.email_compose_message_wizard_form')
        return {
            'name': _('Send Reception'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'target': 'new',
            'context': {
                'default_model': 'sale.order',
                'default_res_id': self.id,
                'default_use_template': bool(template.id),
                'default_template_id': template.id,
                'default_composition_mode': 'comment',
            },
            'view_id': compose_form.id,
        }

    def action_accept_reception(self):
        self.write({
            'reception_accepted': True,
            'reception_accepted_date': fields.Datetime.now(),
        })
        return True
