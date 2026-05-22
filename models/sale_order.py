from odoo import models, fields, api, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    service_type = fields.Selection([
        ('sale', 'Venta Normal'),
        ('repair', 'Repair Order')
    ], string='Tipo de Servicio', default='repair', required=True)

    repair_status = fields.Selection([
        ('diagnosis', 'Diagnóstico'),
        ('waiting_parts', 'Esperando Repuestos'),
        ('in_progress', 'En Reparación'),
        ('ready', 'Listo para Entrega'),
        ('delivered', 'Entregado'),
    ], string='Estado de Reparación', tracking=True, default='diagnosis')

    vehicle_id = fields.Many2one(
        'workshop.vehicle', 
        string='Vehículo',
        domain="[('partner_id', '=', partner_id)]"
    )
    
    vehicle_brand = fields.Char(related='vehicle_id.brand', string='Marca', readonly=True)
    vehicle_model = fields.Char(related='vehicle_id.model_name', string='Modelo', readonly=True)
    vehicle_year = fields.Integer(related='vehicle_id.year', string='Año', readonly=True)
    vehicle_color = fields.Char(related='vehicle_id.color', string='Color', readonly=True)
    
    current_mileage = fields.Integer(string='Kilometraje')
    fuel_level = fields.Selection([
        ('0','0%'),('25','25%'),('50','50%'),('75','75%'),('100','100%')
    ], string='Combustible', default='50')
    reception_date = fields.Datetime(string='Fecha de Recepción', default=fields.Datetime.now)
    reception_accepted = fields.Boolean(string='Recepción Aceptada')
    reception_accepted_date = fields.Datetime(string='Fecha Aceptación')
    
    bodywork_status = fields.Text(string='Estado Carrocería')
    accessories_included = fields.Char(string='Accesorios')
    dash_warning_lights = fields.Char(string='Testigos Tablero')
    symptom_description = fields.Text(string='Descripción del Síntoma / Falla')
    max_authorized_budget = fields.Float(string='Presupuesto Máximo')

    # ESTOS CAMPOS SEPARAN LAS PESTAÑAS FÍSICAMENTE
    labor_line_ids = fields.One2many('sale.order.line', 'order_id', 
                                    string='Líneas de Mano de Obra', 
                                    domain=[('line_category', '=', 'labor'), ('display_type', '=', False)])
    
    parts_line_ids = fields.One2many('sale.order.line', 'order_id', 
                                    string='Líneas de Repuestos', 
                                    domain=[('line_category', '=', 'parts'), ('display_type', '=', False)])

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for order in self:
            if order.vehicle_id and order.partner_id and order.vehicle_id.partner_id != order.partner_id:
                order.vehicle_id = False

    def _prepare_repair_section_line(self, name, category):
        section_sequences = {
            'labor': 1,
            'parts': 101,
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
            (0, 0, self._prepare_repair_section_line('Mano de Obra', 'labor')),
            (0, 0, self._prepare_repair_section_line('Repuestos', 'parts')),
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
                        (0, 0, self._prepare_repair_section_line('Mano de Obra', 'labor')),
                        (0, 0, self._prepare_repair_section_line('Repuestos', 'parts')),
                    ] + order_lines
                    vals['order_line'] = order_lines
            if vals.get('service_type') == 'repair' and vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('workshop.repair.order') or _("New")
        return super().create(vals_list)

    def write(self, vals):
        if 'service_type' in vals:
            for order in self:
                if vals.get('service_type') == 'repair':
                    if not order.order_line.filtered(lambda l: l.display_type == 'line_section'):
                        self.env['sale.order.line'].create({
                            'order_id': order.id,
                            **self._prepare_repair_section_line('Mano de Obra', 'labor'),
                        })
                        self.env['sale.order.line'].create({
                            'order_id': order.id,
                            **self._prepare_repair_section_line('Repuestos', 'parts'),
                        })
                else:
                    section_lines = order.order_line.filtered(lambda l: l.display_type == 'line_section' and l.line_category in ('labor', 'parts'))
                    if section_lines:
                        section_lines.unlink()
        return super().write(vals)

    def action_open_reception_form(self):
        self.ensure_one()
        return {
            'name': 'Recepción',
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
            'name': 'Enviar Recepción',
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
        ('labor','Mano de Obra'),
        ('parts','Repuestos'),
        ('third_party','Terceros'),
        ('supplies','Insumos'),
        ('others','Otros')
    ], string="Categoría", default='others')

    def _repair_section_sequence(self):
        if self.display_type == 'line_section':
            return {
                'labor': 1,
                'parts': 101,
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
        lines._repair_fix_sequence()
        return lines

    def write(self, vals):
        res = super().write(vals)
        self._repair_fix_sequence()
        return res