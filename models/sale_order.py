from odoo import models, fields, api, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    service_type = fields.Selection([
        ('sale', 'Normal Sale'),
        ('repair', 'Repair Order')
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
        domain="[('partner_id', '=', partner_id)]"
    )
    
    vehicle_brand = fields.Char(related='vehicle_id.brand', string='Brand', readonly=True)
    vehicle_model = fields.Char(related='vehicle_id.model_name', string='Model', readonly=True)
    vehicle_year = fields.Integer(related='vehicle_id.year', string='Year', readonly=True)
    vehicle_color = fields.Char(related='vehicle_id.color', string='Color', readonly=True)
    
    current_mileage = fields.Integer(string='Mileage')
    fuel_level = fields.Selection([
        ('0','0%'),('25','25%'),('50','50%'),('75','75%'),('100','100%')
    ], string='Fuel Level', default='50')
    reception_date = fields.Datetime(string='Reception Date', default=fields.Datetime.now)
    reception_accepted = fields.Boolean(string='Reception Accepted')
    reception_accepted_date = fields.Datetime(string='Acceptance Date')
    
    bodywork_status = fields.Text(string='Bodywork Status')
    accessories_included = fields.Char(string='Accessories')
    dash_warning_lights = fields.Char(string='Dashboard Warning Lights')
    symptom_description = fields.Text(string='Symptom / Fault Description')
    max_authorized_budget = fields.Float(string='Maximum Authorized Budget')

    # THESE FIELDS PHYSICALLY SEPARATE THE TABS
    labor_line_ids = fields.One2many('sale.order.line', 'order_id', 
                                    string='Labor Lines', 
                                    domain=[('line_category', '=', 'labor'), ('display_type', '=', False)])
    
    parts_line_ids = fields.One2many('sale.order.line', 'order_id', 
                                    string='Parts Lines', 
                                    domain=[('line_category', '=', 'parts'), ('display_type', '=', False)])

    third_party_line_ids = fields.One2many('sale.order.line', 'order_id',
                                    string='Third-party Lines',
                                    domain=[('line_category', '=', 'third_party'), ('display_type', '=', False)])

    supplies_line_ids = fields.One2many('sale.order.line', 'order_id',
                                    string='Supplies Lines',
                                    domain=[('line_category', '=', 'supplies'), ('display_type', '=', False)])

    other_line_ids = fields.One2many('sale.order.line', 'order_id',
                                    string='Other Lines',
                                    domain=[('line_category', '=', 'others'), ('display_type', '=', False)])

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for order in self:
            if order.vehicle_id and order.partner_id and order.vehicle_id.partner_id != order.partner_id:
                order.vehicle_id = False

    def _prepare_repair_section_line(self, name, category):
        section_sequences = {
            'labor': 1,
            'parts': 101,
            'third_party': 201,
            'supplies': 301,
            'others': 401,
        }
        return {
            'display_type': 'line_section',
            'sequence': section_sequences.get(category, 1000),
            'name': name,
            'product_id': False,
            'product_uom_id': False,
            'product_uom_qty': 0,
            'discount': 0,
            'price_unit': 0,
            'line_category': category,
        }

    def _repair_section_commands(self):
        return [
            (0, 0, self._prepare_repair_section_line('Labor', 'labor')),
            (0, 0, self._prepare_repair_section_line('Parts', 'parts')),
            (0, 0, self._prepare_repair_section_line('Third Party', 'third_party')),
            (0, 0, self._prepare_repair_section_line('Supplies', 'supplies')),
            (0, 0, self._prepare_repair_section_line('Others', 'others')),
        ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('service_type') == 'repair':
                order_lines = vals.get('order_line', [])
                if not any(
                    (isinstance(line, dict) and line.get('display_type') == 'line_section') or
                    (isinstance(line, (list, tuple)) and len(line) >= 3 and line[0] == 0 and line[2].get('display_type') == 'line_section')
                    for line in order_lines
                ):
                    order_lines = [
                        (0, 0, self._prepare_repair_section_line('Labor', 'labor')),
                        (0, 0, self._prepare_repair_section_line('Parts', 'parts')),
                    ] + order_lines
                    vals['order_line'] = order_lines
            if vals.get('service_type') == 'repair' and vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('workshop.repair.order') or _("New")
        return super().create(vals_list)

    def write(self, vals):
        if 'service_type' in vals:
            for order in self:
                if vals.get('service_type') == 'repair':
                    existing_sections = order.order_line.filtered(
                        lambda l: l.display_type == 'line_section'
                    )
                    section_map = {
                        'labor': 'Labor',
                        'parts': 'Parts',
                        'third_party': 'Third Party',
                        'supplies': 'Supplies',
                        'others': 'Others',
                    }
                    for cat, name in section_map.items():
                        if not existing_sections.filtered(lambda l, c=cat: l.line_category == c):
                            self.env['sale.order.line'].create({
                                'order_id': order.id,
                                **self._prepare_repair_section_line(name, cat),
                            })
                else:
                    section_lines = order.order_line.filtered(
                        lambda l: l.display_type == 'line_section' and l.line_category in ('labor', 'parts', 'third_party', 'supplies', 'others')
                    )
                    if section_lines:
                        section_lines.unlink()
        return super().write(vals)

    def _get_order_lines_to_report(self):
        res = super()._get_order_lines_to_report()
        if self.service_type != 'repair':
            return res
        to_remove = self.env['sale.order.line']
        for line in res:
            if line.display_type == 'line_section':
                has_details = any(
                    l.line_category == line.line_category and not l.display_type
                    for l in res
                )
                if not has_details:
                    to_remove += line
        return res - to_remove

    def action_open_reception_form(self):
        self.ensure_one()
        return {
            'name': 'Reception',
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
        ctx = {
            'default_model': 'sale.order',
            'default_res_id': self.id,
            'default_use_template': bool(template.id),
            'default_template_id': template.id,
            'default_composition_mode': 'comment',
        }
        return {
            'name': 'Send Reception',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'target': 'new',
            'context': ctx,
            'view_id': compose_form.id,
        }

    def action_accept_reception(self):
        self.write({
            'reception_accepted': True,
            'reception_accepted_date': fields.Datetime.now(),
        })
        return True

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    line_category = fields.Selection([
        ('labor','Labor'),
        ('parts','Parts'),
        ('third_party','Third Party'),
        ('supplies','Supplies'),
        ('others','Others')
    ], string="Category", default='others')

    def _repair_section_sequence(self):
        if self.display_type == 'line_section':
            return {
                'labor': 1,
                'parts': 101,
                'third_party': 201,
                'supplies': 301,
                'others': 401,
            }.get(self.line_category, 1000)
        return {
            'labor': 10,
            'parts': 110,
            'third_party': 210,
            'supplies': 310,
            'others': 410,
        }.get(self.line_category, 1000)

    def _repair_fix_sequence(self):
        repair_lines = self.filtered(lambda line: line.order_id.service_type == 'repair')
        for line in repair_lines:
            expected = line._repair_section_sequence()
            if line.sequence != expected:
                line.sequence = expected
        return True

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        repair_lines = lines.filtered(lambda l: l.order_id.service_type == 'repair')
        if repair_lines:
            repair_lines._repair_fix_sequence()
        return lines

    def write(self, vals):
        res = super().write(vals)
        repair_lines = self.filtered(lambda l: l.order_id.service_type == 'repair')
        if repair_lines:
            repair_lines._repair_fix_sequence()
        return res