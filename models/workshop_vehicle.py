from odoo import models, fields, api


class WorkshopVehicle(models.Model):
    _name = 'workshop.vehicle'
    _description = 'Vehicle Record'
    _rec_names_search = ['license_plate', 'brand', 'model_name', 'partner_id.name']

    license_plate = fields.Char(string='License Plate', required=True)
    brand = fields.Char(string='Brand')
    model_name = fields.Char(string='Model and Version')
    year = fields.Integer(string='Manufacturing Year')
    color = fields.Char(string='Color')
    vin_number = fields.Char(string='VIN / Chassis')
    engine_type = fields.Char(string='Engine / Fuel Type')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    repair_order_ids = fields.One2many('sale.order', 'vehicle_id', string='RO History')

    _license_plate_unique = models.Constraint(
        'unique(license_plate)',
        'The license plate already exists!',
    )

    @api.depends('brand', 'model_name', 'year', 'color', 'license_plate')
    def _compute_display_name(self):
        for record in self:
            parts = [
                record.brand,
                record.model_name,
                str(record.year) if record.year else False,
                record.color,
                record.license_plate
            ]
            record.display_name = ", ".join(filter(None, parts))