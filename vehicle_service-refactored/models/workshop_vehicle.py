from odoo import models, fields, api


class WorkshopVehicle(models.Model):
    _name = 'workshop.vehicle'
    _description = 'Workshop Vehicle'
    _rec_name = 'display_name'
    _rec_names_search = ['license_plate', 'brand', 'model_name', 'partner_id.name']
    _order = 'license_plate'

    # -------------------------------------------------------------------------
    # Fields
    # -------------------------------------------------------------------------

    license_plate = fields.Char(string='License Plate', required=True, index=True)
    brand = fields.Char(string='Brand')
    model_name = fields.Char(string='Model and Version')
    year = fields.Integer(string='Manufacturing Year')
    color = fields.Char(string='Color')
    vin_number = fields.Char(string='VIN / Chassis')
    engine_type = fields.Char(string='Engine / Fuel Type')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, index=True)
    repair_order_ids = fields.One2many('sale.order', 'vehicle_id', string='RO History')
    repair_order_count = fields.Integer(
        string='Repair Orders', compute='_compute_repair_order_count'
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    _license_plate_unique = models.Constraint(
        'unique(license_plate)',
        'A vehicle with this license plate already exists.',
    )

    # -------------------------------------------------------------------------
    # Computed fields
    # -------------------------------------------------------------------------

    @api.depends('brand', 'model_name', 'year', 'color', 'license_plate')
    def _compute_display_name(self):
        for record in self:
            parts = filter(None, [
                record.brand,
                record.model_name,
                str(record.year) if record.year else None,
                record.color,
                record.license_plate,
            ])
            record.display_name = ', '.join(parts)

    @api.depends('repair_order_ids')
    def _compute_repair_order_count(self):
        for record in self:
            record.repair_order_count = len(record.repair_order_ids)

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def action_view_repair_orders(self):
        self.ensure_one()
        return {
            'name': 'Repair Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id, 'default_service_type': 'repair'},
        }
